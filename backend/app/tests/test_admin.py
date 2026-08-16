"""/admin/audit 라우터 검증."""
def test_audit_list_and_filter(client):
    # 감사 대상 요청을 몇 개 유발
    client.post("/versions/strategies", json={"name": "AdminProbe"})
    client.get("/versions/strategies/no-such/commits")   # 404
    client.post("/ai/screener/nl-to-filter", json={"text": "코스닥 소형주 PER 30 미만"})

    r = client.get("/admin/audit?limit=10")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 3
    assert "rows" in body and len(body["rows"]) >= 3
    # payload_hash 64자
    for row in body["rows"]:
        assert isinstance(row["payload_hash"], str)
        assert len(row["payload_hash"]) in (0, 64)

    # endpoint 필터
    r2 = client.get("/admin/audit?endpoint=/versions")
    assert r2.status_code == 200
    assert all("/versions" in row["endpoint"] for row in r2.json()["rows"])

    # 404 필터
    r3 = client.get("/admin/audit?status_code=404")
    assert r3.status_code == 200
    assert all(row["status"] == 404 for row in r3.json()["rows"])


def test_audit_summary(client):
    client.post("/versions/strategies", json={"name": "SummaryProbe"})
    r = client.get("/admin/audit/summary?hours=24")
    assert r.status_code == 200
    body = r.json()
    assert body["window_hours"] == 24
    assert body["total"] >= 1
    assert 0.0 <= body["error_rate"] <= 1.0
    assert isinstance(body["top_endpoints"], list)
