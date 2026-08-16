def test_policy_get_and_update_and_history(client):
    r = client.get("/policy/slo")
    assert r.status_code == 200, r.text
    base = r.json()
    assert base["name"] == "default"
    prev_avail = base["availability_pct"]
    # 이전 테스트에서 수정되었을 수 있으므로 현재값 대비 다른 값으로 갱신
    new_avail = 99.5 if prev_avail != 99.5 else 99.4

    r = client.put("/policy/slo", json={
        "availability_pct": new_avail,
        "latency_p95_ms": 1500,
        "reason": "국내 브로커 지연 상향 조정 · 예산 재분배 검토",
    })
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["availability_pct"] == new_avail
    assert updated["latency_p95_ms"] == 1500

    # 이력 확인
    r = client.get("/policy/slo/history")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    top = body["rows"][0]
    assert top["prev"]["availability_pct"] == prev_avail
    assert top["next"]["availability_pct"] == new_avail

    # 유효성 검증 실패 케이스
    r = client.put("/policy/slo", json={"availability_pct": 150})
    assert r.status_code == 422

    # 변경 없는 요청 → 400
    r = client.put("/policy/slo", json={"reason": "재확인만 진행 · 값 유지"})
    assert r.status_code == 400


def test_slo_summary_uses_updated_targets(client):
    # 정책 목표를 낮춰서 grade 계산이 새 목표를 반영하는지 확인
    client.put("/policy/slo", json={"latency_p95_ms": 100, "reason": "엄격한 임계값으로 회귀 방지"})
    client.get("/versions/strategies/none/commits")   # 404 유발 (audit 기록)
    r = client.get("/dashboard/slo")
    assert r.status_code == 200
    body = r.json()
    assert body["targets"]["latency_p95_ms"] == 100
