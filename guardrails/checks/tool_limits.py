"""Tool checks: which tools may run, and which arguments they may carry."""

from __future__ import annotations

import re

from ..base import CHECKS, Check, CheckContext, Verdict


@CHECKS.register("tool_allowlist")
class ToolAllowlist(Check):
    description = "Only lets the guard call tools on an allow list."
    defaults = {"allow": []}

    def check(self, ctx: CheckContext) -> Verdict:
        if ctx.tool_name not in self.params["allow"]:
            return Verdict.block(f"Tool '{ctx.tool_name}' is not on the allow list.", 0.6)
        return Verdict.ok()


@CHECKS.register("arg_guard")
class ArgGuard(Check):
    """Tool check: blocks tool arguments that match deny patterns (a naive path filter)."""

    description = "Blocks tool calls whose arguments mention forbidden paths or words."
    defaults = {"tools": [], "deny": [r"vault", r"secret"]}

    def check(self, ctx: CheckContext) -> Verdict:
        if self.params["tools"] and ctx.tool_name not in self.params["tools"]:
            return Verdict.ok()
        joined = " ".join(str(v) for v in ctx.tool_args.values())
        for pattern in self.params["deny"]:
            if re.search(pattern, joined, re.IGNORECASE):
                return Verdict.block(f"Argument matches the deny pattern '{pattern}'.", 0.7)
        return Verdict.ok()
