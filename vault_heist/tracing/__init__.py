"""Tracing: every turn is recorded locally (for the in-game trace view) and,
when Langfuse keys are set, mirrored to Langfuse.

Usage inside the pipeline:

    with tracer.turn(player, level, user_text) as trace:
        with trace.span("input_rails", kind="guardrail", input=text) as span:
            span.end(output="ok", status="pass")
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from collections import OrderedDict
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

log = logging.getLogger(__name__)

LANGFUSE_KINDS = {"guardrail", "generation", "tool", "span", "agent", "chain"}


def session_id_for(player: dict[str, Any], level: str) -> str:
    """Group turns by player and level without exposing the player's token.

    The token is a bearer credential, so only a one-way hash of it leaves the process.
    """
    digest = hashlib.sha256(str(player.get("token", "")).encode("utf-8")).hexdigest()[:16]
    return f"{digest}:{level}"


def cost_usd(usage: Any, price_in: float, price_out: float) -> dict[str, float] | None:
    """Dollars for one model call: tokens times the configured price per million tokens.

    Passed to Langfuse as ``cost_details`` so the dashboard shows money even for models
    that Langfuse has no price for. Returns None when no price is configured.
    """
    if not isinstance(usage, dict) or not (price_in or price_out):
        return None
    cost_in = float(usage.get("input", 0) or 0) * price_in / 1_000_000
    cost_out = float(usage.get("output", 0) or 0) * price_out / 1_000_000
    return {"input": cost_in, "output": cost_out, "total": cost_in + cost_out}


def usage_details(usage: Any) -> dict[str, int] | None:
    """Map provider token usage ({"input": n, "output": m}) to Langfuse usage_details.

    Langfuse computes cost from these counts when the model name is in its price table.
    """
    if not isinstance(usage, dict):
        return None
    out = {k: int(usage[k]) for k in ("input", "output") if isinstance(usage.get(k), (int, float))}
    return out or None


@dataclass
class Span:
    name: str
    kind: str
    input: Any = None
    output: Any = None
    status: str = "ok"  # ok | pass | block | error
    meta: dict[str, Any] = field(default_factory=dict)
    start: float = field(default_factory=time.time)
    ms: float = 0.0

    _lf: Any = None

    def end(self, output: Any = None, status: str | None = None, **meta: Any) -> None:
        self.output = output if output is not None else self.output
        self.status = status or self.status
        self.meta.update(meta)

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("_lf", None)
        return data


@dataclass
class Trace:
    id: str
    player: str
    level: str
    input: str
    start: float = field(default_factory=time.time)
    spans: list[Span] = field(default_factory=list)
    output: str = ""
    status: str = "ok"
    langfuse_url: str = ""
    langfuse_trace_id: str = ""

    _lf_client: Any = None

    @contextmanager
    def span(
        self, name: str, kind: str = "span", input: Any = None, lf_input: Any = None, **meta: Any
    ) -> Iterator[Span]:
        """Open a span. ``lf_input`` (optional) is what Langfuse records as input when it
        differs from the short ``input`` shown in the in-game view, e.g. the full message
        list sent to a model, which Langfuse needs to show multi-turn sessions."""
        span = Span(name=name, kind=kind, input=input, meta=dict(meta))
        self.spans.append(span)
        with ExitStack() as stack:
            lf_obs = None
            if self._lf_client is not None:
                try:
                    lf_obs = stack.enter_context(
                        self._lf_client.start_as_current_observation(
                            name=name,
                            as_type=kind if kind in LANGFUSE_KINDS else "span",
                            input=lf_input if lf_input is not None else input,
                        )
                    )
                except Exception:  # noqa: BLE001 - tracing must never break the game
                    log.debug("Langfuse span failed", exc_info=True)
            t0 = time.perf_counter()
            try:
                yield span
            except Exception as exc:
                span.end(output=str(exc), status="error")
                raise
            finally:
                span.ms = round((time.perf_counter() - t0) * 1000, 1)
                if lf_obs is not None:
                    try:
                        lf_obs.update(
                            output=span.output,
                            metadata={**span.meta, "status": span.status},
                            level="WARNING" if span.status == "block" else ("ERROR" if span.status == "error" else "DEFAULT"),
                            status_message=span.meta.get("reason") or None,
                            model=span.meta.get("model"),
                            usage_details=usage_details(span.meta.get("usage")),
                            cost_details=span.meta.get("cost"),
                        )
                    except Exception:  # noqa: BLE001
                        log.debug("Langfuse update failed", exc_info=True)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "player": self.player,
            "level": self.level,
            "input": self.input,
            "output": self.output,
            "status": self.status,
            "start": self.start,
            "langfuse_url": self.langfuse_url,
            "spans": [s.public() for s in self.spans],
        }


class Tracer:
    def __init__(self, log_path: Path | None = None, keep: int = 500) -> None:
        self.log_path = log_path
        self.keep = keep
        self._traces: "OrderedDict[str, Trace]" = OrderedDict()
        self.langfuse = self._init_langfuse()

    @staticmethod
    def _init_langfuse() -> Any:
        if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
            return None
        try:
            from langfuse import get_client

            client = get_client()
            log.info("Langfuse tracing is on")
            return client
        except ImportError:
            log.warning("LANGFUSE keys are set but the package is missing. Run: uv sync --extra langfuse")
        except Exception:  # noqa: BLE001
            log.exception("Langfuse could not start; continuing with local traces only")
        return None

    @property
    def langfuse_enabled(self) -> bool:
        return self.langfuse is not None

    @contextmanager
    def turn(self, player: dict[str, Any], level: str, user_text: str) -> Iterator[Trace]:
        trace = Trace(id=uuid.uuid4().hex[:16], player=player.get("name", "?"), level=level, input=user_text)
        with ExitStack() as stack:
            if self.langfuse is not None:
                try:
                    from langfuse import propagate_attributes

                    stack.enter_context(
                        propagate_attributes(
                            user_id=f"{player.get('team', '')}/{player.get('name', '')}",
                            session_id=session_id_for(player, level),
                            environment=os.environ.get("LANGFUSE_TRACING_ENVIRONMENT", "workshop"),
                            tags=["vault-heist", level],
                            trace_name=f"vault-heist:{level}",
                        )
                    )
                    root = stack.enter_context(
                        self.langfuse.start_as_current_observation(name=f"turn:{level}", as_type="agent", input=user_text)
                    )
                    trace._lf_client = self.langfuse
                    try:
                        trace.langfuse_url = self.langfuse.get_trace_url() or ""
                        trace.langfuse_trace_id = self.langfuse.get_current_trace_id() or ""
                    except Exception:  # noqa: BLE001
                        trace.langfuse_url = ""
                except Exception:  # noqa: BLE001
                    log.debug("Langfuse root span failed", exc_info=True)
                    root = None
            else:
                root = None
            try:
                yield trace
            finally:
                if root is not None:
                    try:
                        root.update(output=trace.output, metadata={"status": trace.status})
                    except Exception:  # noqa: BLE001
                        pass
        self._store(trace)

    def _store(self, trace: Trace) -> None:
        self._traces[trace.id] = trace
        while len(self._traces) > self.keep:
            self._traces.popitem(last=False)
        if self.log_path:
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(trace.public(), default=str) + "\n")
            except OSError:
                log.debug("Could not write trace log", exc_info=True)

    def get(self, trace_id: str) -> Trace | None:
        return self._traces.get(trace_id)

    def score(self, lf_trace_id: str, value: float, comment: str = "") -> bool:
        """Send a human rating to Langfuse in two places so it is easy to find:

        - a score named ``user-feedback`` (Scores tab, dashboards, filters), and
        - a ``user-feedback`` event inside the trace tree, showing the vote and the note.
        """
        if self.langfuse is None or not lf_trace_id:
            return False
        vote = "thumbs up" if value >= 0.5 else "thumbs down"
        try:
            self.langfuse.create_score(
                name="user-feedback", value=value, trace_id=lf_trace_id,
                data_type="NUMERIC", comment=comment or None,
            )
            self.langfuse.create_event(
                trace_context={"trace_id": lf_trace_id},
                name="user-feedback",
                output={"vote": vote, "note": comment or ""},
                metadata={"vote_value": value, "source": "player"},
            )
            self.langfuse.flush()
            return True
        except Exception:  # noqa: BLE001 - feedback must never break the game
            log.debug("Langfuse feedback failed", exc_info=True)
            return False

    def flush(self) -> None:
        if self.langfuse is not None:
            try:
                self.langfuse.flush()
            except Exception:  # noqa: BLE001
                pass
