"""Prometheus /metrics 노출 + 카운터 증가 검증."""
def test_metrics_endpoint_exposes_prom_format(client):
    # 관측 대상 요청을 몇 개 발생시킨다
    client.get("/health")
    client.post("/versions/strategies", json={"name": "MetricsProbe"})
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    # 4개 메트릭 노출 확인
    assert "qp_http_requests_total" in body
    assert "qp_http_request_duration_seconds" in body
    assert "qp_http_in_flight" in body
    # /versions/strategies 라우트 카운터 존재
    assert 'path_template="/versions/strategies"' in body


def test_metrics_ai_counter(client):
    r = client.post("/ai/screener/nl-to-filter", json={"text": "코스닥 소형주 PER 30 미만"})
    assert r.status_code == 200
    m = client.get("/metrics").text
    assert 'qp_ai_calls_total{kind="screener",outcome="ok"}' in m
