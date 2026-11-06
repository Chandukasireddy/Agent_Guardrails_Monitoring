"""The provider-neutral LLM interface.

Every provider turns the same neutral conversation into its own API format.
Neutral messages are plain dicts:

    {"role": "user", "content": "hi"}
    {"role": "assistant", "content": "hello", "tool_calls": [ToolCall...], "raw": <native>}
    {"role": "tool", "tool_call_id": "...", "name": "shell", "content": "output"}

``raw`` holds the provider's own assistant content so it can be sent back
unchanged on the next request (the Anthropic API needs this for thinking blocks).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..registry import Registry


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class LLMReply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None
    refused: bool = False
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)


class LLMError(RuntimeError):
    """A provider failed in a way the player should hear about in plain words."""


class LLMProvider:
    name: str = "base"
    model: str = ""

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> LLMReply:
        raise NotImplementedError

    def judge(self, instruction: str, text: str) -> bool:
        """Answer a yes/no safety question about ``text``. Used by the llm_judge rail."""
        raise NotImplementedError

    def describe(self) -> str:
        return f"{self.name} ({self.model})" if self.model else self.name


PROVIDERS: Registry[LLMProvider] = Registry("provider")
