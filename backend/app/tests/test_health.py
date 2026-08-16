def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True and j["service"] == "quantpilot-backend"
