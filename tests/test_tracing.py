from token_vault.llm.base import ToolCall
from token_vault.pipeline.graph import langfuse_messages
from token_vault.tracing import session_id_for, usage_details


def test_session_id_never_contains_the_token():
    token = "a1b2c3d4e5f6-secret-player-token"
    sid = session_id_for({"token": token}, "level-1")
    assert token not in sid
    assert "a1b2c3d4" not in sid
    assert sid.endswith(":level-1")


def test_session_id_is_stable_per_player_and_level():
    player = {"token": "same-token"}
    assert session_id_for(player, "lvl") == session_id_for(player, "lvl")
    assert session_id_for(player, "lvl") != session_id_for(player, "other")


def test_usage_details_maps_provider_usage():
    assert usage_details({"input": 120, "output": 45}) == {"input": 120, "output": 45}


def test_usage_details_ignores_missing_or_bad_usage():
    assert usage_details(None) is None
    assert usage_details({}) is None
    assert usage_details({"input": "many"}) is None


def test_langfuse_messages_keeps_tool_call_ids_paired_with_results():
    history = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [ToolCall(id="call_1", name="vault_read", args={"item": "gold"})],
        },
        {"role": "tool", "tool_call_id": "call_1", "name": "vault_read", "content": "DENIED"},
    ]
    msgs = langfuse_messages("SYSTEM", history)

    assert msgs[0] == {"role": "system", "content": "SYSTEM"}
    assistant = msgs[2]
    assert assistant["tool_calls"][0]["id"] == "call_1"
    assert assistant["tool_calls"][0]["function"]["name"] == "vault_read"
    assert assistant["tool_calls"][0]["function"]["arguments"] == '{"item": "gold"}'
    assert msgs[3]["tool_call_id"] == "call_1"
