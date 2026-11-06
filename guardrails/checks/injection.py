"""Spots classic prompt-injection phrases such as 'ignore previous instructions'."""

from __future__ import annotations

import re

from ..base import CHECKS, Check, CheckContext, Verdict


@CHECKS.register("injection_heuristic")
class InjectionHeuristic(Check):
    description = "Spots classic prompt-injection phrases like 'ignore previous instructions'."
    defaults = {
        "patterns": [
            r"ignore (all |any |the )?(previous|prior|above|earlier)",
            r"disregard (all |your |the )?(rules|instructions)",
            r"forget (all |your )?(rules|instructions)",
            r"(system|developer) prompt",
            r"you are now",
            r"new instructions",
            r"developer mode",
            r"\bjailbreak\b",
            r"\bDAN\b",
        ]
    }

    def check(self, ctx: CheckContext) -> Verdict:
        for pattern in self.params["patterns"]:
            if re.search(pattern, ctx.text, re.IGNORECASE):
                return Verdict.block("Looks like a prompt-injection attempt.", 0.8)
        return Verdict.ok()
