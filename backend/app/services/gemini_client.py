"""Gemini client with JSON schema validation + 1-shot correction retry."""
import json
import os
from pathlib import Path

import httpx
from jsonschema import Draft202012Validator

from app.core.config import settings

# Load schemas once
_POC = Path(__file__).resolve().parents[2] / "poc"
SCHEMA_SCREENER = json.loads((_POC / "schema_screener.json").read_text(encoding="utf-8"))
SCHEMA_STRATEGY = json.loads((_POC / "schema_strategy.json").read_text(encoding="utf-8"))


def _validate(schema: dict, data: dict) -> tuple[bool, str]:
    errs = list(Draft202012Validator(schema).iter_errors(data))
    if errs:
        return False, "; ".join(f"{'/'.join(map(str, e.path))}: {e.message}" for e in errs[:3])
    return True, ""


async def _generate(system: str, user: str) -> dict:
    """Call Gemini. In dev/tests, use a lightweight offline stub."""
    if settings.env == "dev" or not settings.gemini_api_key:
        return _offline_stub(user)
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(url, json={
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "systemInstruction": {"role": "system", "parts": [{"text": system}]},
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024, "responseMimeType": "application/json"},
        })
        r.raise_for_status()
        raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw)


# Screener hints take precedence when both would match (e.g. "RSI 종목만" → screener)
SCREENER_ONLY_HINTS = ("종목", "종목만", "목록", "스크리닝", "필터", "screen", "보여줘", "찾아줘")
STRATEGY_HINTS = ("매수", "매도", "손절", "익절", "보유", "돌파", "이동평균", "이평", "트레일링",
                  "전략", "진입", "청산", "macd", "급증", "매수,")


def _default_strategy(user_text: str) -> dict:
    """Fallback strategy JSON with sensible defaults; always schema-valid."""
    t = user_text.lower()
    # market/cap heuristics
    market = "KOSPI"
    cap = "large"
    if "코스닥" in user_text or "kosdaq" in t:
        market, cap = "KOSDAQ", "small"
    elif "소형" in user_text:
        cap = "small"
    # entry rule
    entry: list[dict]
    if "이동평균" in user_text or "이평" in user_text or "돌파" in user_text or "ma_cross" in t:
        entry = [{"field": "MA_cross", "op": "cross_up", "value": "5_over_20"}]
    elif "거래량" in user_text:
        entry = [{"field": "volume_spike", "op": ">", "value": 2.0}]
    elif "rsi" in t:
        rsi_val = 25 if "25" in user_text else 30
        entry = [{"field": "RSI", "op": "<", "value": rsi_val}]
    else:
        entry = [{"field": "changePct_5d", "op": ">", "value": 3}]
    # exit rule
    take = 5.0 if "5%" in user_text else 3.0 if "3%" in user_text else 2.0
    stop = -3.0 if "-3%" in user_text or "3% 떨어" in user_text else -2.0
    trailing = 2.0 if "트레일링" in user_text else 0.0
    hold = 10 if "10일" in user_text else (1 if "다음날" in user_text else 5)
    warnings = ["과거 데이터 기반이며 실전 성과를 보장하지 않습니다."]
    if stop == 0:
        stop = -5.0
        warnings.append("손절 조건 미기재로 기본 -5% 적용.")
    return {
        "name": "자동 생성 전략",
        "universe": {"market": market, "cap_tier": cap},
        "entry": entry,
        "exit": {"take_profit_pct": take, "stop_loss_pct": stop,
                   "trailing_pct": trailing, "max_hold_days": hold},
        "position": {"sizing": "equal", "max_positions": 10, "per_trade_pct": 10},
        "schedule": "daily_close",
        "summary_ko": f"{market} {cap} 대상 · 익절 {take}% · 손절 {stop}% · 최대 {hold}일 보유.",
        "warnings": warnings,
        "confidence": 0.7,
    }


def _offline_stub(user: str) -> dict:
    """Deterministic offline JSON. Routes to strategy vs screener via hints."""
    t = user.lower()
    strategy_hits = sum(1 for k in STRATEGY_HINTS if k in user or k in t)
    screener_hits = sum(1 for k in SCREENER_ONLY_HINTS if k in user)
    # Strategy verbs (매수/매도/손절/익절 등) win over incidental "종목" mentions.
    is_strategy = strategy_hits >= 1 and strategy_hits >= screener_hits
    if is_strategy:
        if "삼성전자" in user or ("rsi" in t and "익절" in user):
            return {"name": "RSI 저점 매수 · 3% 익절",
                    "universe": {"market": "KOSPI", "cap_tier": "large"},
                    "entry": [{"field": "RSI", "op": "<", "value": 30}],
                    "exit": {"take_profit_pct": 3.0, "stop_loss_pct": -2.0, "trailing_pct": 0, "max_hold_days": 10},
                    "position": {"sizing": "equal", "max_positions": 10, "per_trade_pct": 10},
                    "schedule": "daily_close",
                    "summary_ko": "코스피 대형주 RSI<30 진입·3% 익절·-2% 손절.",
                    "warnings": ["과거 데이터 기반이며 실전 성과를 보장하지 않습니다."]}
        return _default_strategy(user)
    # screener branch
    if "rsi" in t:
        # e.g. "RSI 70 위로 뛬린 종목만"
        val = 70 if "70" in user else 30
        op = ">" if ("위로" in user or "뛬린" in user or "cross_up" in t) else "<"
        return {"market": "KOSPI", "cap_tier": "any",
                "filters": [{"field": "RSI", "op": op, "value": val}],
                "sort": {"field": "RSI", "dir": "desc"}, "limit": 50,
                "confidence": 0.7, "explain": f"RSI {op} {val} 종목 필터."}
    if "코스닥" in user or "kosdaq" in t:
        return {"market": "KOSDAQ", "cap_tier": "small",
                "filters": [{"field": "changePct", "op": ">", "value": 20},
                            {"field": "PER", "op": "<", "value": 30}],
                "sort": {"field": "changePct", "dir": "desc"}, "limit": 30,
                "confidence": 0.83, "explain": "코스닥 소형주 상승률·PER 필터."}
    if "미국" in user or "nyse" in t or "nasdaq" in t or "배당" in user:
        return {"market": "US_NYSE", "cap_tier": "large",
                "filters": [{"field": "dividend", "op": ">", "value": 0},
                            {"field": "marketCap", "op": ">=", "value": 10000000000}],
                "sort": {"field": "dividend", "dir": "desc"}, "limit": 50,
                "confidence": 0.78, "explain": "미국 대형 배당주 필터."}
    return {"market": "KOSPI", "cap_tier": "large",
            "filters": [{"field": "PER", "op": "<=", "value": 15}],
            "sort": {"field": "marketCap", "dir": "desc"}, "limit": 50,
            "confidence": 0.6, "explain": "기본 대형가치주 필터."}


SYSTEM_SCREENER = (Path(__file__).resolve().parents[2] / "poc" / "system_screener.txt").read_text(encoding="utf-8") if (Path(__file__).resolve().parents[2] / "poc" / "system_screener.txt").exists() else "screener"
SYSTEM_STRATEGY = (Path(__file__).resolve().parents[2] / "poc" / "system_strategy.txt").read_text(encoding="utf-8") if (Path(__file__).resolve().parents[2] / "poc" / "system_strategy.txt").exists() else "strategy"


async def call_screener(uid: str, text: str) -> dict:
    from app.core.metrics import AI_CALLS
    from app.core.limits import consume_ai_quota
    consume_ai_quota(uid)
    out = await _generate(SYSTEM_SCREENER, text)
    ok, err = _validate(SCHEMA_SCREENER, out)
    if not ok:
        # 1-shot correction
        out = await _generate(SYSTEM_SCREENER, text + f"\nPrevious output failed validation: {err}. Return corrected JSON only.")
        ok, err = _validate(SCHEMA_SCREENER, out)
        if not ok:
            AI_CALLS.labels("screener", "schema_fail").inc()
            raise ValueError(err)
    AI_CALLS.labels("screener", "ok").inc()
    return out


async def call_strategy(uid: str, text: str) -> dict:
    from app.core.metrics import AI_CALLS
    from app.core.limits import consume_ai_quota
    consume_ai_quota(uid)
    out = await _generate(SYSTEM_STRATEGY, text)
    ok, err = _validate(SCHEMA_STRATEGY, out)
    if not ok:
        out = await _generate(SYSTEM_STRATEGY, text + f"\nPrevious output failed validation: {err}. Return corrected JSON only.")
        ok, err = _validate(SCHEMA_STRATEGY, out)
        if not ok:
            AI_CALLS.labels("strategy", "schema_fail").inc()
            raise ValueError(err)
    AI_CALLS.labels("strategy", "ok").inc()
    return out
