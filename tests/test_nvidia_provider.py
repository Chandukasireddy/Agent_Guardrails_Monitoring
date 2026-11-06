import httpx
import pytest

from token_vault.config import LLMSettings
from token_vault.llm import LLMError, ToolCall, ToolSpec
from token_vault.llm import nvidia_provider as nv
from token_vault.llm.rate_limit import SlidingWindowLimiter

FAKE_KEY = "nvapi-TEST-KEY-NOT-REAL"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_limiter_allows_the_quota_then_waits_for_the_window():
    clock = FakeClock()
    lim = SlidingWindowLimiter(3, window_seconds=60, max_wait_seconds=60, clock=clock, sleep=clock.sleep)
    for _ in range(3):
        lim.acquire()
    start = clock.now
    lim.acquire()  # 4th call must wait for the oldest one to age out
    assert clock.now - start >= 59.9
    assert lim.in_window() == 1  # the three earlier calls aged out; only the 4th is in the window


def test_limiter_gives_up_with_a_plain_message_when_the_wait_is_too_long():
    clock = FakeClock()
    lim = SlidingWindowLimiter(2, window_seconds=60, max_wait_seconds=5, clock=clock, sleep=clock.sleep)
    lim.acquire()
    lim.acquire()
    with pytest.raises(LLMError, match="busy"):
        lim.acquire()


def test_forty_per_minute_is_the_default_for_nvidia():
    assert LLMSettings().nvidia_rpm == 40


def _settings() -> LLMSettings:
    return LLMSettings(nvidia_rpm=40)


@pytest.fixture()
def provider(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", FAKE_KEY)
    # A fresh limiter per test so quota from one test does not leak into another.
    monkeypatch.setattr(nv, "limiter_for", lambda key, n: SlidingWindowLimiter(n))
    return nv.NvidiaProvider(_settings())


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(LLMError, match="NVIDIA_API_KEY"):
        nv.NvidiaProvider(_settings())


def test_chat_sends_tools_and_parses_tool_calls(provider, monkeypatch):
    seen = {}

    def fake_post(url, headers, json, timeout):  # noqa: A002
        seen.update(url=url, headers=headers, json=json)
        return httpx.Response(
            200,
            json={
                "model": "nvidia/nemotron-3.5-bolt-e4b",
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {"id": "call_9", "function": {"name": "shell", "arguments": '{"cmd": "ls"}'}}
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(nv.httpx, "post", fake_post)
    tool = ToolSpec(name="shell", description="run", input_schema={"type": "object"})
    reply = provider.chat("SYS", [{"role": "user", "content": "hi"}], [tool])

    assert seen["url"].endswith("/chat/completions")
    assert seen["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert seen["json"]["messages"][0] == {"role": "system", "content": "SYS"}
    assert seen["json"]["tools"][0]["function"]["name"] == "shell"
    assert reply.tool_calls == [ToolCall(id="call_9", name="shell", args={"cmd": "ls"})]
    assert reply.usage == {"input": 12, "output": 5}


def test_assistant_tool_calls_are_sent_back_with_matching_ids(provider):
    history = [
        {"role": "user", "content": "x"},
        {"role": "assistant", "content": "", "tool_calls": [ToolCall(id="c1", name="shell", args={"cmd": "ls"})]},
        {"role": "tool", "tool_call_id": "c1", "name": "shell", "content": "out"},
    ]
    msgs = provider._to_messages("SYS", history)
    assert msgs[2]["tool_calls"][0]["id"] == "c1"
    assert msgs[3]["tool_call_id"] == "c1"


def test_rate_limit_response_becomes_a_friendly_error(provider, monkeypatch):
    monkeypatch.setattr(
        nv.httpx, "post", lambda url, **kw: httpx.Response(429, text="too many", request=httpx.Request("POST", url))
    )
    with pytest.raises(LLMError, match="rate limit"):
        provider.chat("SYS", [{"role": "user", "content": "hi"}], [])


def test_errors_never_echo_the_key(provider, monkeypatch):
    monkeypatch.setattr(
        nv.httpx, "post", lambda url, **kw: httpx.Response(500, text="boom", request=httpx.Request("POST", url))
    )
    with pytest.raises(LLMError) as info:
        provider.chat("SYS", [{"role": "user", "content": "hi"}], [])
    assert FAKE_KEY not in str(info.value)


def test_every_call_takes_a_slot_from_the_limiter(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", FAKE_KEY)
    clock = FakeClock()
    lim = SlidingWindowLimiter(2, window_seconds=60, max_wait_seconds=0.0, clock=clock, sleep=clock.sleep)
    monkeypatch.setattr(nv, "limiter_for", lambda key, n: lim)
    monkeypatch.setattr(
        nv.httpx,
        "post",
        lambda url, **kw: httpx.Response(
            200, json={"choices": [{"message": {"content": "NO"}}]}, request=httpx.Request("POST", url)
        ),
    )
    p = nv.NvidiaProvider(_settings())
    assert p.judge("is it bad?", "hello") is False
    p.judge("is it bad?", "hello")
    with pytest.raises(LLMError, match="busy"):
        p.judge("is it bad?", "hello")
