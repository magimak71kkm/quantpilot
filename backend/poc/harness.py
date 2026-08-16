#!/usr/bin/env python3
"""AI PoC harness — validates screener/strategy outputs against JSON Schemas.

Runs offline via the mock LLM in gemini_client._offline_stub, or against real
Gemini when GEMINI_API_KEY is set and --mock is omitted.

Usage:
  python3 poc/harness.py --screener --mock
  python3 poc/harness.py --strategy --mock
  python3 poc/harness.py --all --mock
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

# Force dev mode for the client so it uses the offline stub
os.environ.setdefault("QP_ENV", "dev")

from app.services import gemini_client  # noqa: E402


async def run_cases(cases_path: Path, kind: str) -> dict:
    call = gemini_client.call_screener if kind == "screener" else gemini_client.call_strategy
    total = ok = errors = 0
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
            out = await call("test-user", case["input"])
            lat.append((time.perf_counter() - t0) * 1000)
            missing = [k for k in case.get("expect_keys", []) if k not in out]
            if missing and not case.get("expect_error"):
                errors += 1
                fails.append({"input": case["input"], "missing": missing, "out": out})
            else:
                ok += 1
        except Exception as e:
            lat.append((time.perf_counter() - t0) * 1000)
            if case.get("expect_error"):
                ok += 1
            else:
                errors += 1
                fails.append({"input": case["input"], "error": str(e)})
    lat.sort()
    p50 = lat[len(lat) // 2] if lat else 0.0
    p95 = lat[int(len(lat) * 0.95) - 1] if lat else 0.0
    return {"kind": kind, "total": total, "pass": ok, "fail": errors,
            "p50_ms": round(p50, 1), "p95_ms": round(p95, 1), "fails": fails}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screener", action="store_true")
    ap.add_argument("--strategy", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--mock", action="store_true", help="force offline stub")
    args = ap.parse_args()

    if args.mock:
        os.environ["QP_ENV"] = "dev"
        os.environ.pop("QP_GEMINI_API_KEY", None)

    reports = []
    if args.all or args.screener:
        reports.append(await run_cases(Path(__file__).parent / "screener_cases.jsonl", "screener"))
    if args.all or args.strategy:
        reports.append(await run_cases(Path(__file__).parent / "strategy_cases.jsonl", "strategy"))

    print(json.dumps(reports, ensure_ascii=False, indent=2))
    # Non-zero exit if any failure
    sys.exit(0 if all(r["fail"] == 0 for r in reports) else 1)


if __name__ == "__main__":
    asyncio.run(main())
