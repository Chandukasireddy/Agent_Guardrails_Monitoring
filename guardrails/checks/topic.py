"""Input check: refuses messages that do not mention any allowed topic."""

from __future__ import annotations

from typing import ClassVar

from ..base import RAILS, Rail, RailContext, Verdict


@RAILS.register("topic_scope")
class TopicScope(Rail):
    name: ClassVar[str] = "topic_scope"
    description = "Refuses messages that do not mention any of the allowed topics."
    defaults = {"topics": []}

    def check(self, ctx: RailContext) -> Verdict:
        topics = [t.lower() for t in self.params["topics"]]
        if not topics:
            return Verdict.ok()
        low = ctx.text.lower()
        if any(t in low for t in topics):
            return Verdict.ok()
        return Verdict.block(f"Off topic. This desk only answers about: {', '.join(topics)}.", 0.2)
