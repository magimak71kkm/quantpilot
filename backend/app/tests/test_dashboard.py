def test_dashboard_live(client):
    # 트래픽 유발
    client.get("/health")
    client.post("/versions/strategies", json={"name": "LiveProbe"})
    client.post("/ai/screener/nl-to-filter", json={"text": "코스닥 소형주 PER 30 미만"})
    client.get("/versions/strategies/no-such/commits")   # 404 유발

    r = client.get("/dashboard/live")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ["in_flight", "total_requests", "err_4xx", "err_5xx",
                "error_rate", "avg_latency_ms", "ai_ok", "ai_schema_fail", "top_paths"]:
        assert key in body, key
    assert body["total_requests"] >= 3
    assert body["err_4xx"] >= 1
    assert body["ai_ok"] >= 1
    assert isinstance(body["top_paths"], list)
