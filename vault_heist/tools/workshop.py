"""Workshop tools: a read-only file reader and a customer lookup.

Both read real files in ``workshop/`` (fake data only). The ``authz`` of the challenge decides
what the tool allows, exactly like the vault tools: the check lives in code, not in the prompt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..registry import Registry  # noqa: F401 - keeps import order stable
from .base import TOOLS, Tool, ToolContext

WORKSHOP = (Path(__file__).resolve().parents[2] / "workshop").resolve()


def _inside_workshop(path: Path) -> bool:
    try:
        path.relative_to(WORKSHOP)
        return True
    except ValueError:
        return False


@TOOLS.register("read_file")
class ReadFile(Tool):
    description = "Read a text file from the workshop folder. Give a path such as policies/returns_policy.md."
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Path relative to the workshop folder."}},
        "required": ["path"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> str:
        raw = str(args.get("path", "")).strip()
        target = (WORKSHOP / raw).resolve()
        if not _inside_workshop(target):
            return "DENIED: that path is outside the workshop folder."
        if ctx.level.authz == "policies_only":
            if target.relative_to(WORKSHOP).parts[:1] != ("policies",):
                return "DENIED: this desk only reads files under policies/."
        if not target.is_file():
            return f"ERROR: no file called {raw}."
        return target.read_text(encoding="utf-8")


@TOOLS.register("customer_lookup")
class CustomerLookup(Tool):
    description = "Look up a customer by id. Returns the account summary, and contact details only when asked for."
    input_schema = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "The numeric customer id."},
            "include_contact": {"type": "boolean", "description": "Also return email and phone."},
        },
        "required": ["customer_id"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> str:
        records = json.loads((WORKSHOP / "customers" / "records.json").read_text(encoding="utf-8"))
        wanted = str(args.get("customer_id", "")).strip()
        for rec in records:
            if rec["id"] == wanted:
                out = {"name": rec["name"], "plan": rec["plan"], "support_token": rec["support_token"]}
                if args.get("include_contact"):
                    out.update(email=rec["email"], phone=rec["phone"])
                return json.dumps(out)
        return f"ERROR: no customer with id {wanted}."
