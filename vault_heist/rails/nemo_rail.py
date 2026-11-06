"""Optional adapter for NVIDIA NeMo Guardrails.

Install with ``uv sync --extra nemo`` and add to a level:

    input_rails:
      - name: nemo
        params: {config_path: guardrails/nemo}

The NeMo config decides whether the text is allowed. If NeMo is not
installed, the rail reports that and lets the message through, so the game
keeps running.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from ..config import ROOT
from .base import RAILS, Rail, RailContext, Verdict

log = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def _load_rails(config_path: str):  # type: ignore[no-untyped-def]
    from nemoguardrails import LLMRails, RailsConfig

    return LLMRails(RailsConfig.from_path(str(Path(ROOT, config_path))))


@RAILS.register("nemo")
class NemoRail(Rail):
    description = "Runs NVIDIA NeMo Guardrails (Colang flows) on the text."
    defaults = {"config_path": "guardrails/nemo", "refusal_marker": "I'm sorry, I can't"}

    def check(self, ctx: RailContext) -> Verdict:
        try:
            rails = _load_rails(self.params["config_path"])
        except ImportError:
            log.warning("NeMo Guardrails is not installed. Run: uv sync --extra nemo")
            return Verdict.ok()
        role = "user" if ctx.stage != "output" else "assistant"
        result = rails.generate(messages=[{"role": role, "content": ctx.text}])
        content = result.get("content", "") if isinstance(result, dict) else str(result)
        if self.params["refusal_marker"].lower() in content.lower():
            return Verdict.block("NeMo Guardrails refused this message.", 0.8)
        return Verdict.ok()
