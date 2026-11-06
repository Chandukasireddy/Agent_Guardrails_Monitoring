"""Red-team runner: fires attacks at a level and reports which ones got through.

Works with any provider, including the offline mock. Attacks come from
``config/attacks.yaml``; with a real model you can also ask it to invent more.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..config import Level, get_settings, load_attack_library
from ..game.store import Store
from ..llm import LLMProvider, make_provider
from ..pipeline import GuardPipeline
from ..rails.text_utils import decoded_variants, normalize
from ..tracing import Tracer


@dataclass
class AttackOutcome:
    attack: str
    message: str
    status: str
    blocked_by: str
    leaked: bool
    reply: str


def leaked(secret: str, reply: str) -> bool:
    return any(normalize(secret) in normalize(v) for v in decoded_variants(reply))


class Sandbox:
    """A throwaway game (in-memory database) for running attacks from the command line."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        settings = get_settings()
        self.provider = provider or make_provider(settings.llm)
        self.store = Store(":memory:")
        self.tracer = Tracer(None)
        self.pipeline = GuardPipeline(self.provider, self.store, settings.game)
        self.player = self.store.create_player("red-team-bot", "Red Team")

    def send(self, level: Level, message: str, history: list[dict[str, Any]] | None = None):  # type: ignore[no-untyped-def]
        with self.tracer.turn(self.player, level.id, message) as trace:
            return self.pipeline.run(level, self.player, history or [], message, trace)


def run_attacks(level: Level, sandbox: Sandbox | None = None, on_result: Callable[[AttackOutcome], None] | None = None) -> list[AttackOutcome]:
    sandbox = sandbox or Sandbox()
    outcomes = []
    for attack in load_attack_library():
        for message in attack.get("examples", []):
            result = sandbox.send(level, message)
            outcome = AttackOutcome(
                attack=attack.get("name", "?"),
                message=message,
                status=result.status,
                blocked_by=result.blocked_by,
                leaked=result.status != "blocked" and leaked(level.secret, result.reply),
                reply=result.reply,
            )
            outcomes.append(outcome)
            if on_result:
                on_result(outcome)
    return outcomes
