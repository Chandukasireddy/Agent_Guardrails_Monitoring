"""Blocks messages that contain a word from a deny list."""

from __future__ import annotations

import re

from ..base import CHECKS, Check, CheckContext, Verdict


@CHECKS.register("keyword_block")
class KeywordBlock(Check):
    description = "Blocks messages that contain any word from a deny list."
    defaults = {"words": ["secret", "password", "key", "flag"]}

    def check(self, ctx: CheckContext) -> Verdict:
        low = ctx.text.lower()
        for word in self.params["words"]:
            if re.search(rf"\b{re.escape(word.lower())}", low):
                return Verdict.block(f"Contains the forbidden word '{word}'.", 0.6)
        return Verdict.ok()
