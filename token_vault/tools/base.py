"""The tool contract.

A tool has a name, a description, a JSON schema for its arguments, and a
``run(args, ctx)`` method that returns text. Register it with
``@TOOLS.register("my_tool")`` and list it under ``tools:`` in a challenge.

Security decisions (who may read what) belong in ``run``, in code. The model
only asks; the tool decides.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from ..llm import ToolSpec
from ..registry import Registry

if TYPE_CHECKING:
    from ..config import Level
    from ..game.database import Database


@dataclass
class ToolContext:
    level: "Level"
    player: dict[str, Any]
    store: "Database"


class Tool:
    name: ClassVar[str] = "tool"
    description: ClassVar[str] = ""
    input_schema: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    def run(self, args: dict[str, Any], ctx: ToolContext) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    @classmethod
    def spec(cls) -> ToolSpec:
        return ToolSpec(name=cls.name, description=cls.description, input_schema=cls.input_schema)


TOOLS: Registry[Tool] = Registry("tool")
