"""Output check: blocks replies that contain an email address or a phone number."""

from __future__ import annotations

import re
from typing import ClassVar

from ..base import RAILS, Rail, RailContext, Verdict

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


@RAILS.register("pii_redactor")
class PiiRedactor(Rail):
    name: ClassVar[str] = "pii_redactor"
    description = "Blocks replies that contain an email address or phone number."

    def check(self, ctx: RailContext) -> Verdict:
        if EMAIL.search(ctx.text) or PHONE.search(ctx.text):
            return Verdict.block("The reply contains personal contact details.", 0.4)
        return Verdict.ok()
