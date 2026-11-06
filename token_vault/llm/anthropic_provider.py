"""Claude via the official Anthropic Python SDK."""

from __future__ import annotations

import logging
from typing import Any

from ..config import LLMSettings
from .base import PROVIDERS, LLMError, LLMProvider, LLMReply, ToolCall, ToolSpec

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@PROVIDERS.register("anthropic")
class AnthropicProvider(LLMProvider):
    def __init__(self, settings: LLMSettings) -> None:
        import anthropic

        self._anthropic = anthropic
        self.settings = settings
        self.model = settings.anthropic_model
        self.client = anthropic.Anthropic(timeout=settings.timeout_seconds)

    # -- conversion -------------------------------------------------------
    @staticmethod
    def _to_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            role = msg["role"]
            if role == "user":
                # A user message right after tool results joins that same user turn.
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                    out[-1]["content"].append({"type": "text", "text": msg["content"]})
                else:
                    out.append({"role": "user", "content": msg["content"]})
            elif role == "assistant":
                # Send the original blocks back unchanged (keeps thinking blocks valid).
                content = msg.get("raw") if msg.get("raw") is not None else msg.get("content") or "..."
                out.append({"role": "assistant", "content": content})
            elif role == "tool":
                block = {
                    "type": "tool_result",
                    "tool_use_id": msg["tool_call_id"],
                    "content": msg["content"],
                }
                # All results for one assistant turn go back in a single user message.
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
        return out

    @staticmethod
    def _to_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]

    # -- calls ------------------------------------------------------------
    def _create(self, **kwargs: Any) -> Any:
        a = self._anthropic
        try:
            if self.settings.anthropic_fallbacks:
                return self.client.beta.messages.create(
                    betas=[FALLBACK_BETA], fallbacks="default", **kwargs
                )
            return self.client.messages.create(**kwargs)
        except a.AuthenticationError as exc:
            raise LLMError("The Anthropic API key was rejected. Check ANTHROPIC_API_KEY in .env.") from exc
        except a.NotFoundError as exc:
            raise LLMError(f"Model '{kwargs.get('model')}' was not found. Check ANTHROPIC_MODEL.") from exc
        except a.RateLimitError as exc:
            raise LLMError("The guard is getting too many requests. Wait a moment and try again.") from exc
        except a.APIStatusError as exc:
            raise LLMError(f"The Anthropic API returned an error ({exc.status_code}).") from exc
        except a.APIConnectionError as exc:
            raise LLMError("Could not reach the Anthropic API. Check the internet connection.") from exc

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> LLMReply:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.settings.max_tokens,
            "system": system,
            "messages": self._to_messages(messages),
            "output_config": {"effort": self.settings.anthropic_effort},
        }
        if tools:
            kwargs["tools"] = self._to_tools(tools)
        response = self._create(**kwargs)

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, args=dict(block.input or {})))
        usage = getattr(response, "usage", None)
        return LLMReply(
            text="\n".join(text_parts).strip(),
            tool_calls=calls,
            raw=response.content,
            refused=response.stop_reason == "refusal",
            model=getattr(response, "model", self.model),
            usage={
                "input": getattr(usage, "input_tokens", 0) or 0,
                "output": getattr(usage, "output_tokens", 0) or 0,
            },
        )

    def judge(self, instruction: str, text: str) -> bool:
        response = self._create(
            model=self.settings.anthropic_judge_model,
            max_tokens=256,
            system=instruction + "\nAnswer with exactly one word: YES or NO.",
            messages=[{"role": "user", "content": text}],
            output_config={"effort": "low"},
        )
        if response.stop_reason == "refusal":
            return True
        answer = "".join(b.text for b in response.content if b.type == "text").strip().upper()
        return answer.startswith("YES")
