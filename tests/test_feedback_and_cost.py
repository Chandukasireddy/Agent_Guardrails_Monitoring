from vault_heist.tracing import cost_usd


def test_cost_is_tokens_times_price_per_million():
    cost = cost_usd({"input": 2_000_000, "output": 500_000}, price_in=0.05, price_out=0.20)
    assert cost["input"] == 0.1
    assert cost["output"] == 0.1
    assert cost["total"] == 0.2


def test_no_price_means_no_cost_recorded():
    assert cost_usd({"input": 10, "output": 10}, 0.0, 0.0) is None
    assert cost_usd({}, 0.05, 0.2)["total"] == 0


def test_demo_users_are_fixed_and_separate(client):
    a = client.post("/api/demo/a").json()
    again = client.post("/api/demo/A").json()
    b = client.post("/api/demo/B").json()
    assert a["token"] == again["token"]
    assert a["token"] != b["token"]
    assert a["name"] == "User A"
    assert client.post("/api/demo/Z").status_code == 404


def test_feedback_is_stored_for_own_reply(client, player):
    sent = client.post("/api/levels/key_vault/chat", json={"message": "hello"}).json()
    r = client.post("/api/feedback", json={"trace_id": sent["trace_id"], "vote": -1, "comment": "too chatty"})
    assert r.status_code == 200
    assert r.json()["vote"] == -1
    saved = client.get("/api/levels/key_vault").json()["feedback"]
    assert saved[sent["trace_id"]]["comment"] == "too chatty"


def test_feedback_on_someone_elses_reply_is_refused(client, player):
    sent = client.post("/api/levels/key_vault/chat", json={"message": "hello"}).json()
    other = client.post("/api/join", json={"name": "Someone else", "team": "X"}).json()
    r = client.post("/api/feedback", json={"trace_id": sent["trace_id"], "vote": 1},
                    headers={"X-Player-Token": other["token"]})
    assert r.status_code == 404


def test_guard_cannot_reach_the_real_project_env():
    from vault_heist.tools.workshop import ReadFile, WORKSHOP
    from vault_heist.tools.base import ToolContext
    from vault_heist.config import Level

    level = Level(id="k", order=1, title="k", secret="FAKE-X", system_prompt="x", authz="none")
    ctx = ToolContext(level=level, player={}, store=None)
    assert "DENIED" in ReadFile().run({"path": "../.env"}, ctx)
    assert "DENIED" in ReadFile().run({"path": "../../.env"}, ctx)
    assert "FAKE-NV-KEY-7F3A" in ReadFile().run({"path": ".env"}, ctx)
