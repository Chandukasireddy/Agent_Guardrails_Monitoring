"""Blocks very long messages, which often hide injected instructions."""

from __future__ import annotations

from ..base import CHECKS, Check, CheckContext, Verdict


@CHECKS.register("length_limit")
class LengthLimit(Check):
    description = "Blocks very long messages, which often hide injected instructions."
    defaults = {"max_chars": 600}

    def check(self, ctx: CheckContext) -> Verdict:
        if len(ctx.text) > self.params["max_chars"]:
            return Verdict.block(f"Message longer than {self.params['max_chars']} characters.", 0.4)
        return Verdict.ok()
