"""Local models through Ollama's native chat API (works offline)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import httpx

from ..config import LLMSettings
from .base import PROVIDERS, LLMError, LLMProvider, LLMReply, ToolCall, ToolSpec

log = logging.getLogger(__name__)


@PROVIDERS.register("ollama")
class OllamaProvider(LLMProvider):
    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings
        self.model = settings.ollama_model
        self.base_url = settings.ollama_url.rstrip("/")
        self.tools_supported = True  # flipped off if the model rejects tools

    @staticmethod
    def available(settings: LLMSettings) -> bool:
        try:
            r = httpx.get(settings.ollama_url.rstrip("/") + "/api/tags", timeout=1.5)
            names = {m.get("name", "").split(":")[0] for m in r.json().get("models", [])}
            return r.status_code == 200 and settings.ollama_model.split(":")[0] in names
        except Exception:  # noqa: BLE001
            return False

    def _to_messages(self, system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for msg in messages:
            if msg["role"] == "assistant":
                entry: dict[str, Any] = {"role": "assistant", "content": msg.get("content", "")}
                if msg.get("tool_calls"):
                    entry["tool_calls"] = [
                        {"function": {"name": c.name, "arguments": c.args}} for c in msg["tool_calls"]
                    ]
                out.append(entry)
            elif msg["role"] == "tool":
                out.append({"role": "tool", "content": msg["content"], "tool_name": msg.get("name", "")})
            else:
                out.append({"role": "user", "content": msg["content"]})
        return out

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            r = httpx.post(self.base_url + "/api/chat", json=payload, timeout=self.settings.timeout_seconds)
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach Ollama at {self.base_url}. Is it running?") from exc
        if r.status_code >= 400:
            raise LLMError(f"Ollama error {r.status_code}: {r.text[:200]}")
        return r.json()

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> LLMReply:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_messages(system, messages),
            "stream": False,
        }
        if tools and self.tools_supported:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.input_schema},
                }
                for t in tools
            ]
        try:
            data = self._post(payload)
        except LLMError as exc:
            # Many small models do not support tool calling. Retry without tools.
            if "tools" in payload and "does not support tools" in str(exc):
                log.warning("Model %s does not support tools; continuing without them", self.model)
                self.tools_supported = False
                payload.pop("tools")
                data = self._post(payload)
            else:
                raise
        message = data.get("message", {})
        calls = []
        for call in message.get("tool_calls") or []:
            fn = call.get("function", {})
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(ToolCall(id=uuid.uuid4().hex[:12], name=fn.get("name", ""), args=args))
        return LLMReply(
            text=(message.get("content") or "").strip(),
            tool_calls=calls,
            model=self.model,
            usage={"input": data.get("prompt_eval_count", 0), "output": data.get("eval_count", 0)},
        )

    def judge(self, instruction: str, text: str) -> bool:
        data = self._post(
            {
                "model": self.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": instruction + "\nAnswer with exactly one word: YES or NO."},
                    {"role": "user", "content": text},
                ],
            }
        )
        return (data.get("message", {}).get("content") or "").strip().upper().startswith("YES")
