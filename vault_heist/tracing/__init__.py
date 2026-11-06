"""Tracing: every turn is recorded locally (for the in-game trace view) and,
when Langfuse keys are set, mirrored to Langfuse.

Usage inside the pipeline:

    with tracer.turn(player, level, user_text) as trace:
        with trace.span("input_rails", kind="guardrail", input=text) as span:
            span.end(output="ok", status="pass")
"""

from __future__ import annotations

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

    _lf_client: Any = None

    @contextmanager
    def span(self, name: str, kind: str = "span", input: Any = None, **meta: Any) -> Iterator[Span]:
        span = Span(name=name, kind=kind, input=input, meta=dict(meta))
        self.spans.append(span)
        with ExitStack() as stack:
            lf_obs = None
            if self._lf_client is not None:
                try:
                    lf_obs = stack.enter_context(
                        self._lf_client.start_as_current_observation(
                            name=name, as_type=kind if kind in LANGFUSE_KINDS else "span", input=input
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
                            session_id=f"{player.get('token', '')[:8]}:{level}",
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

    def flush(self) -> None:
        if self.langfuse is not None:
            try:
                self.langfuse.flush()
            except Exception:  # noqa: BLE001
                pass
