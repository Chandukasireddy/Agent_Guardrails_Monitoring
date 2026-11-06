"""Two well-known guardrail patterns used by the workshop challenges.

- ``topic_scope``: a topical rail. Off-topic messages are refused before the model sees them
  (the NeMo Guardrails "topical rails" idea, written as plain code).
- ``pii_redactor``: an output rail that blocks replies containing contact details
  (the idea behind Presidio-style PII detection, with simple patterns).
"""

from __future__ import annotations

import re
from typing import ClassVar

from .base import RAILS, Rail, RailContext, Verdict

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


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


@RAILS.register("pii_redactor")
class PiiRedactor(Rail):
    name: ClassVar[str] = "pii_redactor"
    description = "Blocks replies that contain an email address or phone number."

    def check(self, ctx: RailContext) -> Verdict:
        if EMAIL.search(ctx.text) or PHONE.search(ctx.text):
            return Verdict.block("The reply contains personal contact details.", 0.4)
        return Verdict.ok()
