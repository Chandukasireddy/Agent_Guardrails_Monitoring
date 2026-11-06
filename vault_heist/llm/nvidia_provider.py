"""NVIDIA's hosted models (build.nvidia.com) through the OpenAI-compatible chat API.

The free endpoint allows 40 requests a minute per key. Every call (guard reply, tool
round, judge) takes a slot from one shared limiter, so the whole room stays under the limit.
The API key is read from NVIDIA_API_KEY and is never logged or put in an error message.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

import httpx

from ..config import LLMSettings
from .base import PROVIDERS, LLMError, LLMProvider, LLMReply, ToolCall, ToolSpec
from .rate_limit import limiter_for

log = logging.getLogger(__name__)

MAX_REPLY_TOKENS = 1024  # guard replies are short; keeps each call quick


def _load_key() -> str:
    """The key comes from NVIDIA_API_KEY in .env (git-ignored). It never goes in a prompt."""
    return os.environ.get("NVIDIA_API_KEY", "").strip()


@PROVIDERS.register("nvidia")
class NvidiaProvider(LLMProvider):
    name = "nvidia"

    def __init__(self, settings: LLMSettings) -> None:
        key = _load_key()
        if not key:
            raise LLMError("No NVIDIA key found. Set NVIDIA_API_KEY in your .env file.")
        self._key = key
        self.settings = settings
        self.model = settings.nvidia_model
        self.url = settings.nvidia_url.rstrip("/") + "/chat/completions"
        self.limiter = limiter_for(key, settings.nvidia_rpm)

    @staticmethod
    def available(settings: LLMSettings) -> bool:  # noqa: ARG004 - same signature as other providers
        return bool(_load_key())

    def _to_messages(self, system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for msg in messages:
            if msg["role"] == "assistant":
                entry: dict[str, Any] = {"role": "assistant", "content": msg.get("content") or ""}
                calls = msg.get("tool_calls") or []
                if calls:
                    entry["tool_calls"] = [
                        {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.args)}}
                        for c in calls
                    ]
                out.append(entry)
            elif msg["role"] == "tool":
                out.append(
                    {"role": "tool", "tool_call_id": msg.get("tool_call_id", ""), "name": msg.get("name", ""), "content": msg["content"]}
                )
            else:
                out.append({"role": "user", "content": msg["content"]})
        return out

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.limiter.acquire()  # raises LLMError if the room has used its minute's quota
        try:
            r = httpx.post(
                self.url,
                headers={"Authorization": f"Bearer {self._key}", "Accept": "application/json"},
                json=payload,
                timeout=self.settings.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise LLMError("Could not reach the NVIDIA API. Check the internet connection.") from exc
        if r.status_code == 429:
            raise LLMError("The NVIDIA API rate limit was hit. Wait a minute and try again.")
        if r.status_code >= 400:
            raise LLMError(f"NVIDIA API error {r.status_code}: {r.text[:200]}")
        return r.json()

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> LLMReply:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_messages(system, messages),
            "temperature": 1,
            "top_p": 0.95,
            "max_tokens": min(self.settings.max_tokens, MAX_REPLY_TOKENS),
            "stream": False,
        }
        if tools:
            payload["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}}
                for t in tools
            ]
            payload["parallel_tool_calls"] = True
        if self.settings.nvidia_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": True}
        data = self._post(payload)

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {})
        calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            fn = call.get("function", {})
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(ToolCall(id=call.get("id") or uuid.uuid4().hex[:12], name=fn.get("name", ""), args=args))
        usage = data.get("usage") or {}
        return LLMReply(
            text=(message.get("content") or "").strip(),
            tool_calls=calls,
            model=data.get("model", self.model),
            usage={"input": usage.get("prompt_tokens", 0) or 0, "output": usage.get("completion_tokens", 0) or 0},
        )

    def judge(self, instruction: str, text: str) -> bool:
        data = self._post(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": instruction + "\nAnswer with exactly one word: YES or NO."},
                    {"role": "user", "content": text},
                ],
                "temperature": 0,
                "max_tokens": 8,
                "stream": False,
            }
        )
        content = ((data.get("choices") or [{}])[0].get("message", {}).get("content") or "")
        return content.strip().upper().startswith("YES")
