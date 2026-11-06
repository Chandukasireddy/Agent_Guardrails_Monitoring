"""LLM providers and the ``auto`` picker.

``auto`` uses Claude when ANTHROPIC_API_KEY is set, a local Ollama model when
one is running, and otherwise the offline mock guard, so the game always starts.
"""

from __future__ import annotations

import logging
import os

from ..config import LLMSettings
from . import anthropic_provider, mock_provider, ollama_provider  # noqa: F401 - registers providers
from .base import PROVIDERS, LLMError, LLMProvider, LLMReply, ToolCall, ToolSpec

log = logging.getLogger(__name__)

__all__ = ["LLMError", "LLMProvider", "LLMReply", "ToolCall", "ToolSpec", "PROVIDERS", "make_provider"]


def make_provider(settings: LLMSettings) -> LLMProvider:
    choice = settings.provider.lower().strip()
    if choice == "auto":
        if os.environ.get("ANTHROPIC_API_KEY"):
            choice = "anthropic"
        elif ollama_provider.OllamaProvider.available(settings):
            choice = "ollama"
        else:
            choice = "mock"
        log.info("LLM provider 'auto' picked: %s", choice)
    try:
        return PROVIDERS.get(choice)(settings)  # type: ignore[call-arg]
    except Exception as exc:  # noqa: BLE001 - fall back so the game still starts
        log.error("Could not start provider '%s' (%s). Falling back to the offline mock guard.", choice, exc)
        return PROVIDERS.get("mock")(settings)  # type: ignore[call-arg]
