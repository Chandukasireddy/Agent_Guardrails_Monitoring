"""The guardrail contract: what a check receives, what it returns, and where checks register.

A check is a small class with one method, ``check(ctx) -> Verdict``. Register it
with ``@CHECKS.register("my_check")`` and list it in a challenge's YAML under
``input_checks``, ``output_checks`` or ``tool_checks``. Parameters in the YAML
are passed to the constructor and available as ``self.params``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from token_vault.registry import Registry

if TYPE_CHECKING:
    from token_vault.config import Level
    from token_vault.llm import LLMProvider


@dataclass
class CheckContext:
    stage: str  # "input", "output" or "tool"
    text: str  # the user's message, the guard's reply, or the tool call as text
    level: "Level"
    player: dict[str, Any]
    provider: "LLMProvider"
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Verdict:
    allowed: bool = True
    reason: str = ""
    suspicion: float = 0.0  # 0..1, feeds the tripwire meter in the UI

    @classmethod
    def ok(cls, suspicion: float = 0.0) -> "Verdict":
        return cls(True, "", suspicion)

    @classmethod
    def block(cls, reason: str, suspicion: float = 1.0) -> "Verdict":
        return cls(False, reason, suspicion)


class Check:
    name: ClassVar[str] = "check"
    #: One-line description shown in the UI pipeline view.
    description: ClassVar[str] = ""
    #: Default parameters; YAML params override these.
    defaults: ClassVar[dict[str, Any]] = {}

    def __init__(self, **params: Any) -> None:
        self.params = {**self.defaults, **params}

    def check(self, ctx: CheckContext) -> Verdict:  # pragma: no cover - interface
        raise NotImplementedError


CHECKS: Registry[Check] = Registry("check")
