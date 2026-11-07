"""Input check: refuses messages that do not mention any allowed topic."""

from __future__ import annotations

import re
from difflib import get_close_matches
from typing import ClassVar

from ..base import CHECKS, Check, CheckContext, Verdict


@CHECKS.register("topic_scope")
class TopicScope(Check):
    name: ClassVar[str] = "topic_scope"
    description = "Refuses messages that do not mention any of the allowed topics, allowing for typos."
    # fuzzy_cutoff: how close a word must be to a topic (0-1) to count as a typo of it. 1 turns typos off.
    # not_typos: real words that score as high as typos, so similarity alone cannot rule them out.
    defaults = {"topics": [], "fuzzy_cutoff": 0.83, "not_typos": []}

    def check(self, ctx: CheckContext) -> Verdict:
        topics = [t.lower() for t in self.params["topics"]]
        if not topics:
            return Verdict.ok()
        low = ctx.text.lower()
        if any(t in low for t in topics):
            return Verdict.ok()
        not_typos = {w.lower() for w in self.params["not_typos"]}
        for word in re.findall(r"[a-z]+", low):
            if word not in not_typos and get_close_matches(word, topics, n=1, cutoff=self.params["fuzzy_cutoff"]):
                return Verdict.ok()
        return Verdict.block(f"Off topic. This desk only answers about: {', '.join(topics)}.", 0.2)
