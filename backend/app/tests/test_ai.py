def test_screener_ok(client):
    r = client.post("/ai/screener/nl-to-filter", json={"text": "코스닥 소형주 상승률 20% 초과 PER 30 미만"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["market"] == "KOSDAQ"
    assert any(f["field"] == "PER" for f in j["filters"])


def test_strategy_ok(client):
    r = client.post("/ai/strategy/from-desc",
                    json={"text": "삼성전자 대형주에서 RSI 30 아래 매수, 3% 익절, -2% 손절, 최대 10일"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["exit"]["take_profit_pct"] == 3.0
    assert j["exit"]["stop_loss_pct"] == -2.0
    assert "warnings" in j and len(j["warnings"]) >= 1
