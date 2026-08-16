def test_seed_then_diff_and_revert(client):
    # create strategy (seeds v1.0..v1.3)
    r = client.post("/versions/strategies", json={"name": "RSI-Bounce"})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    # commits list — must contain 4 seeded commits with tags v1.0..v1.3
    r = client.get(f"/versions/strategies/{sid}/commits")
    assert r.status_code == 200
    commits = r.json()
    assert len(commits) == 4
    tags = sorted(c["tag"] for c in commits if c["tag"])
    assert tags == ["v1.0", "v1.1", "v1.2", "v1.3"]

    # diff v1.1 -> v1.3 should show at least one add + one replace
    r = client.get(f"/versions/strategies/{sid}/diff", params={"from_": "v1.1", "to": "v1.3"})
    assert r.status_code == 200
    diff = r.json()
    ops = [c for f in diff["files"] for c in f["changes"]]
    assert any(o["op"] == "replace" for o in ops)
    assert any(o["op"] == "add" for o in ops)

    # revert live to v1.1
    r = client.post(f"/versions/strategies/{sid}/revert",
                    json={"to_sha": "v1.1", "reason": "손절 완화로 인한 낙폭 확대 — 안전 복귀 필요", "environment": "live"})
    assert r.status_code == 200
    rev_sha = r.json()["revert_sha"]

    # after revert, commits count = 5 (seed 4 + revert 1)
    r = client.get(f"/versions/strategies/{sid}/commits")
    shas = [c["sha"] for c in r.json()]
    assert rev_sha in shas
    assert len(shas) == 5

    # reason too short → 400
    r = client.post(f"/versions/strategies/{sid}/revert",
                    json={"to_sha": "v1.0", "reason": "짧음", "environment": "live"})
    assert r.status_code in (400, 422)


def test_new_commit(client):
    r = client.post("/versions/strategies", json={"name": "Test-2"})
    sid = r.json()["id"]
    r = client.get(f"/versions/strategies/{sid}/commits")
    head = r.json()[0]["sha"]
    r = client.post(f"/versions/strategies/{sid}/commits", json={
        "message": "add trailing 2%",
        "files": {"rules.json": {"entry": [{"field": "RSI", "op": "<", "value": 25}],
                                    "exit": {"take_profit_pct": 3, "stop_loss_pct": -2, "trailing_pct": 2}}},
        "parent_sha": head,
    })
    assert r.status_code == 200
    assert len(r.json()["sha"]) == 40
