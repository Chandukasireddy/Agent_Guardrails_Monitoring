"""Blocks messages that contain a word from a deny list."""

from __future__ import annotations

import re

from ..base import RAILS, Rail, RailContext, Verdict


@RAILS.register("keyword_block")
class KeywordBlock(Rail):
    description = "Blocks messages that contain any word from a deny list."
    defaults = {"words": ["secret", "password", "key", "flag"]}

    def check(self, ctx: RailContext) -> Verdict:
        low = ctx.text.lower()
        for word in self.params["words"]:
            if re.search(rf"\b{re.escape(word.lower())}", low):
                return Verdict.block(f"Contains the forbidden word '{word}'.", 0.6)
        return Verdict.ok()
