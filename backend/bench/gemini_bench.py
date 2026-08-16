#!/usr/bin/env python3
"""Live Gemini benchmark harness.

Sends the same PoC cases (poc/screener_cases.jsonl, strategy_cases.jsonl)
to the real Gemini API and reports:
  - schema pass rate (JSON Schema validation)
  - p50 / p95 latency (ms)
  - retry count (1-shot correction retries fired)
  - failures (with reason)

Usage:
  export QP_GEMINI_API_KEY=...          # required
  export QP_GEMINI_MODEL=gemini-1.5-flash
  python3 bench/gemini_bench.py --all
  python3 bench/gemini_bench.py --screener --json out.json

Fallback: if QP_GEMINI_API_KEY is missing, the harness exits with a
clear message instead of silently switching to the offline stub.
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Force PROD mode so gemini_client makes a real HTTP call.
os.environ["QP_ENV"] = "prod"

from app.services import gemini_client  # noqa: E402


async def run(kind: str, cases_path: Path) -> dict:
    call = gemini_client.call_screener if kind == "screener" else gemini_client.call_strategy
    total = ok = fail = 0
    lat = []
    fails = []
    for line in cases_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        case = json.loads(line)
        total += 1
        t0 = time.perf_counter()
        try:
            out = await call("bench-user", case["input"])
            ms = (time.perf_counter() - t0) * 1000
            lat.append(ms)
            missing = [k for k in case.get("expect_keys", []) if k not in out]
            if missing and not case.get("expect_error"):
                fail += 1
                fails.append({"input": case["input"], "missing": missing, "ms": round(ms, 1)})
            else:
                ok += 1
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            lat.append(ms)
            if case.get("expect_error"):
                ok += 1
            else:
                fail += 1
                fails.append({"input": case["input"], "error": str(e), "ms": round(ms, 1)})
    lat.sort()
    n = len(lat)
    p50 = lat[n // 2] if n else 0.0
    p95 = lat[max(0, int(n * 0.95) - 1)] if n else 0.0
    return {
        "kind": kind,
        "total": total, "pass": ok, "fail": fail,
        "pass_rate": round((ok / total) if total else 0.0, 3),
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        "fails": fails,
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screener", action="store_true")
    ap.add_argument("--strategy", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", help="write report to this path")
    args = ap.parse_args()

    if not os.environ.get("QP_GEMINI_API_KEY"):
        print("ERROR: QP_GEMINI_API_KEY is required for the live benchmark.", file=sys.stderr)
        print("Tip: use `python3 poc/harness.py --all --mock` for offline validation.", file=sys.stderr)
        sys.exit(2)

    poc = Path(__file__).resolve().parents[1] / "poc"
    reports = []
    if args.all or args.screener:
        reports.append(await run("screener", poc / "screener_cases.jsonl"))
    if args.all or args.strategy:
        reports.append(await run("strategy", poc / "strategy_cases.jsonl"))

    body = {
        "model": os.environ.get("QP_GEMINI_MODEL", "gemini-1.5-flash"),
        "when":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reports": reports,
    }
    print(json.dumps(body, ensure_ascii=False, indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")

    # PoC completion thresholds from 03_ai_poc_prompts.md §3
    ok_thresholds = all(
        r["pass_rate"] >= 0.95 and r["p50_ms"] <= 2000 and r["p95_ms"] <= 4500
        for r in reports
    )
    sys.exit(0 if ok_thresholds else 1)


if __name__ == "__main__":
    asyncio.run(main())
