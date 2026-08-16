# Live Gemini Benchmark

Runs the same PoC cases against the **real Gemini API** and reports
pass rate + p50/p95 latency against the thresholds in
`docs/03_ai_poc_prompts.md §3`:

| 지표 | 목표 |
|---|---|
| JSON schema pass rate | ≥ 95% |
| p50 latency | ≤ 2000 ms |
| p95 latency | ≤ 4500 ms |
| 무료 티어 초과율 | 0% |

## 실행

```bash
export QP_GEMINI_API_KEY=sk-your-key
export QP_GEMINI_MODEL=gemini-1.5-flash   # 또는 gemini-1.5-flash-latest / gemini-2.0-flash-exp
python3 bench/gemini_bench.py --all --json bench/latest.json
```

- exit code `0` = 모든 임계값 통과, `1` = 임계값 미달, `2` = 키 미설정.
- 결과 JSON에 `model`, `when`, 각 케이스별 지연·실패 사유 포함.
- 실패 케이스가 있으면 `poc/system_screener.txt` / `system_strategy.txt` 프롬프트를 재튜닝하거나
  `gemini_client._generate`의 `responseMimeType` 설정을 확인.

## 무료 티어 대응
- Gemini Flash 계열은 무료 티어 존재 (한도는 [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) 참고).
- 벤치 실행 전 `QP_GEMINI_DAILY_QUOTA_PER_USER`로 서버 측 상한을 미리 설정.
- 429 발생 시 서버가 지수 백오프(1s→2s→4s→8s, 최대 4회) 후 실패 응답.
