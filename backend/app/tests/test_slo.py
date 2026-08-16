def test_slo_summary_shape(client):
    # 트래픽 유발 (감사 로그 채우기)
    client.post("/versions/strategies", json={"name": "SloProbe"})
    client.get("/versions/strategies/no-such/commits")     # 404
    client.post("/ai/screener/nl-to-filter", json={"text": "코스닥 소형주 PER 30 미만"})

    r = client.get("/dashboard/slo")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window_days"] == 30
    for key in ["targets", "availability", "latency", "ai_quality", "burn_rate"]:
        assert key in body, key

    a = body["availability"]
    assert 0.0 <= a["value_pct"] <= 100.0
    assert a["grade"] in ("ok", "warn", "crit")
    assert a["requests"] >= 2

    lat = body["latency"]
    assert lat["p95_ms"] >= 0
    assert lat["grade"] in ("ok", "warn", "crit")

    aiq = body["ai_quality"]
    assert 0.0 <= aiq["schema_fail_pct"] <= 100.0
    assert aiq["grade"] in ("ok", "warn", "crit")

    br = body["burn_rate"]
    for k in ("1h", "6h", "24h"):
        assert k in br
        assert br[k] >= 0
