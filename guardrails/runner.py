"""Runs one stage of checks and records every step.

A stage is one of three places a check can run:

- ``input``   on the visitor's message, before the model sees it
- ``tool``    on each tool call the model asks for, before the tool runs
- ``output``  on the model's reply, before the visitor sees it

Checks in a stage run in the order the challenge lists them. The first block
stops the stage. Each check becomes one trace span and one step in the route
panel of the game.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .base import RAILS, RailContext, Verdict

if TYPE_CHECKING:
    from vault_heist.config import Level, RailSpec
    from vault_heist.llm import LLMProvider
    from vault_heist.tracing import Trace

log = logging.getLogger(__name__)


@dataclass
class StageResult:
    verdict: Verdict | None  # None means every check in the stage let the text through
    rail: str = ""  # the check that blocked, or "" when nothing blocked
    events: list[dict[str, Any]] = field(default_factory=list)  # one entry per check that ran
    suspicion: float = 0.0  # the highest suspicion any check reported (drives the tripwire meter)


def run_stage(
    stage: str,
    specs: "list[RailSpec]",
    *,
    text: str,
    level: "Level",
    player: dict[str, Any],
    provider: "LLMProvider",
    trace: "Trace",
    tool_name: str = "",
    tool_args: dict[str, Any] | None = None,
) -> StageResult:
    """Run each check in ``specs`` on ``text``, stopping at the first block."""
    events: list[dict[str, Any]] = []
    top = 0.0
    for spec in specs:
        ctx = RailContext(
            stage=stage,
            text=text,
            level=level,
            player=player,
            provider=provider,
            tool_name=tool_name,
            tool_args=tool_args or {},
        )
        # Named after the challenge and the check, so Langfuse shows exactly which guardrail acted.
        with trace.span(f"{level.id}/{stage}/{spec.name}", kind="guardrail", input=text, rail=spec.name,
                        label=spec.label, explain=spec.explain) as span:
            try:
                verdict = RAILS.get(spec.name)(**spec.params).check(ctx)
            except Exception as exc:  # noqa: BLE001 - a broken check fails closed
                log.exception("Check %s crashed", spec.name)
                verdict = Verdict.block(f"Check error: {exc}", 0.0)
            status = "pass" if verdict.allowed else "block"
            span.end(output=verdict.reason or "allowed", status=status, reason=verdict.reason)
        top = max(top, verdict.suspicion)
        events.append({"stage": stage, "name": spec.name, "status": status, "reason": verdict.reason,
                       "label": spec.label, "explain": spec.explain, "ms": span.ms})
        if not verdict.allowed:
            return StageResult(verdict, spec.name, events, top)
    return StageResult(None, "", events, top)
