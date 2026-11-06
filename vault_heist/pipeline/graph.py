"""The guard pipeline, built with LangGraph.

    player message
        -> input_rails  --blocked--> END
        -> guard (LLM)  --tool calls--> tools (tool rails + authz) --> guard
        -> output_rails --blocked--> END (refusal shown instead)
        -> END

Every node writes a span to the trace and an event for the UI pipeline view.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from ..config import GameSettings, Level, RailSpec
from ..game.store import Store
from ..llm import LLMError, LLMProvider, ToolCall
from guardrails import Verdict, run_stage
from ..config import get_settings
from ..tools import TOOLS, ToolContext
from ..tracing import Trace, cost_usd

log = logging.getLogger(__name__)


def langfuse_messages(system: str, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The full message list the guard saw, in OpenAI-style role format.

    Langfuse uses this as a generation's input so each turn of a session shows the
    conversation so far, and tool calls can be matched to their results by id.
    """
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for m in history:
        role = m.get("role")
        if role == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": m.get("content") or ""}
            calls = m.get("tool_calls") or []
            if calls:
                msg["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.args, default=str)},
                    }
                    for c in calls
                ]
        elif role == "tool":
            msg = {"role": "tool", "tool_call_id": m.get("tool_call_id"), "name": m.get("name"), "content": m.get("content")}
        else:
            msg = {"role": role, "content": m.get("content")}
        messages.append(msg)
    return messages


class TurnState(TypedDict, total=False):
    level: Level
    player: dict[str, Any]
    trace: Trace
    user_text: str
    history: list[dict[str, Any]]
    events: list[dict[str, Any]]
    status: str  # ok | blocked | error
    blocked_by: str
    reason: str
    reply: str
    suspicion: float
    rounds: int
    pending: list[ToolCall]


@dataclass
class TurnResult:
    reply: str
    status: str
    blocked_by: str = ""
    reason: str = ""
    suspicion: float = 0.0
    events: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)


class GuardPipeline:
    def __init__(self, provider: LLMProvider, store: Store, game: GameSettings) -> None:
        self.provider = provider
        self.store = store
        self.game = game
        self.graph = self._build()

    # -- helpers ----------------------------------------------------------
    def _run_rails(
        self, state: TurnState, stage: str, specs: list[RailSpec], text: str, **tool: Any
    ) -> tuple[Verdict | None, str, list[dict[str, Any]], float]:
        """Run one stage of guardrails (see ``guardrails/runner.py``).

        Returns (blocking verdict or None, check name, events, max suspicion).
        """
        result = run_stage(
            stage,
            specs,
            text=text,
            level=state["level"],
            player=state["player"],
            provider=self.provider,
            trace=state["trace"],
            tool_name=tool.get("tool_name", ""),
            tool_args=tool.get("tool_args", {}),
        )
        return result.verdict, result.rail, result.events, result.suspicion

    def _refusal(self, level: Level) -> str:
        return random.choice(level.character.refusals or ["Nope."])

    # -- nodes ------------------------------------------------------------
    def input_rails(self, state: TurnState) -> dict[str, Any]:
        verdict, name, events, susp = self._run_rails(state, "input", state["level"].input_rails, state["user_text"])
        update: dict[str, Any] = {"events": state["events"] + events, "suspicion": susp}
        if verdict:
            update.update(status="blocked", blocked_by=name, reason=verdict.reason, reply=self._refusal(state["level"]))
        else:
            update["history"] = state["history"] + [{"role": "user", "content": state["user_text"]}]
        return update

    def guard(self, state: TurnState) -> dict[str, Any]:
        level = state["level"]
        tools = [TOOLS.get(name).spec() for name in level.tools if name in TOOLS]
        trace = state["trace"]
        with trace.span(
            "guard",
            kind="generation",
            input=state["history"][-1].get("content"),
            lf_input=langfuse_messages(level.render_system_prompt(), state["history"]),
        ) as span:
            try:
                reply = self.provider.chat(level.render_system_prompt(), state["history"], tools)
            except LLMError as exc:
                span.end(output=str(exc), status="error")
                event = {"stage": "guard", "name": self.provider.name, "status": "error", "reason": str(exc), "ms": span.ms}
                return {"status": "error", "reason": str(exc), "reply": f"⚠️ {exc}", "events": state["events"] + [event]}
            span.end(
                output=reply.text or [f"{c.name}({c.args})" for c in reply.tool_calls],
                status="ok",
                model=reply.model,
                usage=reply.usage,
                cost=cost_usd(
                    reply.usage,
                    get_settings().llm.price_input_per_million,
                    get_settings().llm.price_output_per_million,
                ),
                tool_calls=[c.name for c in reply.tool_calls],
            )
        history = state["history"] + [
            {"role": "assistant", "content": reply.text, "tool_calls": reply.tool_calls, "raw": reply.raw}
        ]
        detail = ", ".join(c.name for c in reply.tool_calls)
        event = {
            "stage": "guard",
            "name": reply.model or self.provider.name,
            "status": "refused" if reply.refused else "ok",
            "reason": f"wants to call: {detail}" if detail else "",
            "ms": span.ms,
        }
        text = reply.text if not reply.refused else "(The guard model refused to answer that.)"
        return {
            "history": history,
            "reply": text,
            "pending": reply.tool_calls,
            "events": state["events"] + [event],
        }

    def tools(self, state: TurnState) -> dict[str, Any]:
        level, history, events = state["level"], list(state["history"]), list(state["events"])
        susp = state.get("suspicion", 0.0)
        out_of_budget = state.get("rounds", 0) >= self.game.max_tool_rounds
        for call in state.get("pending", []):
            if out_of_budget:
                result, status, reason = "ERROR: tool budget for this message is used up.", "block", "budget"
            elif call.name not in level.tools or call.name not in TOOLS:
                result, status, reason = f"ERROR: tool '{call.name}' is not available here.", "block", "unknown tool"
            else:
                verdict, rail, rail_events, s = self._run_rails(
                    state, "tool", level.tool_rails, f"{call.name}({call.args})", tool_name=call.name, tool_args=call.args
                )
                events += rail_events
                susp = max(susp, s)
                if verdict:
                    result, status, reason = f"BLOCKED by {rail}: {verdict.reason}", "block", verdict.reason
                else:
                    with state["trace"].span(f"tool:{call.name}", kind="tool", input=call.args) as span:
                        try:
                            ctx = ToolContext(level=level, player=state["player"], store=self.store)
                            result = TOOLS.get(call.name)().run(call.args, ctx)
                        except Exception as exc:  # noqa: BLE001
                            log.exception("Tool %s crashed", call.name)
                            result = f"ERROR: the tool crashed ({exc})."
                        status = "block" if result.startswith(("DENIED", "ERROR", "REJECTED")) else "ok"
                        reason = result.split("\n")[0][:120] if status == "block" else ""
                        span.end(output=result, status=status)
            events.append({"stage": "tool", "name": call.name, "status": status, "reason": reason, "args": call.args})
            history.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": result})
        update: dict[str, Any] = {
            "history": history,
            "events": events,
            "rounds": state.get("rounds", 0) + 1,
            "pending": [],
            "suspicion": susp,
        }
        if out_of_budget:
            update["reply"] = state.get("reply") or "I got tangled up in my tools. Ask me again?"
        return update

    def output_rails(self, state: TurnState) -> dict[str, Any]:
        reply = state.get("reply") or "..."
        verdict, name, events, susp = self._run_rails(state, "output", state["level"].output_rails, reply)
        update: dict[str, Any] = {
            "events": state["events"] + events,
            "suspicion": max(state.get("suspicion", 0.0), susp),
            "status": "ok",
        }
        if verdict:
            update.update(status="blocked", blocked_by=name, reason=verdict.reason, reply=self._refusal(state["level"]))
        return update

    # -- routing ----------------------------------------------------------
    @staticmethod
    def _after_input(state: TurnState) -> str:
        return END if state.get("status") == "blocked" else "guard"

    def _after_guard(self, state: TurnState) -> str:
        if state.get("status") == "error":
            return END
        if state.get("pending"):
            return "tools"
        return "output_rails"

    def _after_tools(self, state: TurnState) -> str:
        return "output_rails" if state.get("rounds", 0) > self.game.max_tool_rounds else "guard"

    def _build(self):  # type: ignore[no-untyped-def]
        g = StateGraph(TurnState)
        g.add_node("input_rails", self.input_rails)
        g.add_node("guard", self.guard)
        g.add_node("tools", self.tools)
        g.add_node("output_rails", self.output_rails)
        g.add_edge(START, "input_rails")
        g.add_conditional_edges("input_rails", self._after_input, ["guard", END])
        g.add_conditional_edges("guard", self._after_guard, ["tools", "output_rails", END])
        g.add_conditional_edges("tools", self._after_tools, ["guard", "output_rails"])
        g.add_edge("output_rails", END)
        return g.compile()

    # -- entry point ------------------------------------------------------
    def run(self, level: Level, player: dict[str, Any], history: list[dict[str, Any]], user_text: str, trace: Trace) -> TurnResult:
        state: TurnState = {
            "level": level,
            "player": player,
            "trace": trace,
            "user_text": user_text,
            "history": list(history),
            "events": [],
            "status": "ok",
            "rounds": 0,
            "suspicion": 0.0,
        }
        final = self.graph.invoke(state, {"recursion_limit": 6 + 3 * self.game.max_tool_rounds})
        trace.output = final.get("reply", "")
        trace.status = final.get("status", "ok")
        return TurnResult(
            reply=final.get("reply", ""),
            status=final.get("status", "ok"),
            blocked_by=final.get("blocked_by", ""),
            reason=final.get("reason", ""),
            suspicion=final.get("suspicion", 0.0),
            events=final.get("events", []),
            trace_id=trace.id,
            history=final.get("history", history),
        )
