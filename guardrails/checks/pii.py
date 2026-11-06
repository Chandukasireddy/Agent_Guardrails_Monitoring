"""Output check: blocks replies that contain an email address or a phone number."""

from __future__ import annotations

import re
from typing import ClassVar

from ..base import CHECKS, Check, CheckContext, Verdict

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


@CHECKS.register("pii_redactor")
class PiiRedactor(Check):
    name: ClassVar[str] = "pii_redactor"
    description = "Blocks replies that contain an email address or phone number."

    def check(self, ctx: CheckContext) -> Verdict:
        if EMAIL.search(ctx.text) or PHONE.search(ctx.text):
            return Verdict.block("The reply contains personal contact details.", 0.4)
        return Verdict.ok()
