"""Flags emotional pressure, urgency, and authority claims (social engineering)."""

from __future__ import annotations

import re

from ..base import CHECKS, Check, CheckContext, Verdict


@CHECKS.register("pressure_detector")
class PressureDetector(Check):
    description = "Flags emotional pressure, urgency, and authority claims (social engineering)."
    defaults = {
        "patterns": [
            r"grand(ma|mother|pa|father)",
            r"dying|deathbed|hospital|funeral",
            r"urgent|emergency|right now|immediately",
            r"\bi am (the|your) (admin|administrator|boss|ceo|owner|developer|manager)",
            r"\b(ceo|cto|admin|administrator|supervisor) (here|speaking)",
            r"security audit|compliance check",
            r"\bi know (jensen|your boss|the ceo)",
            r"please,? i beg",
        ],
        "threshold": 1,
    }

    def check(self, ctx: CheckContext) -> Verdict:
        hits = [p for p in self.params["patterns"] if re.search(p, ctx.text, re.IGNORECASE)]
        if len(hits) >= self.params["threshold"]:
            return Verdict.block("Social-engineering pressure detected.", 0.7)
        return Verdict.ok(0.2 * len(hits))
