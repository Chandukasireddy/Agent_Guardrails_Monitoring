"""The FastAPI app: game API, host controls, and the static web UI."""

from __future__ import annotations

import logging
import secrets
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .config import (
    CHALLENGES_DIR,
    CONFIG_DIR,
    CUSTOM_CHECKS_DIR,
    DATA_DIR,
    TOOLS_CUSTOM_DIR,
    WEB_DIR,
    Level,
    Settings,
    get_settings,
    load_attack_library,
    load_levels,
)
from .game.store import Store
from .llm import LLMProvider, make_provider
from .pipeline import GuardPipeline
from guardrails import RAILS
from guardrails.text import normalize
from .registry import load_extension_modules
from .tools import TOOLS
from .tracing import Tracer

log = logging.getLogger(__name__)


class JoinBody(BaseModel):
    name: str
    team: str = "Solo"


DEMO_USERS = ("admin", "intern", "customer")

class ChatBody(BaseModel):
    message: str


class FlagBody(BaseModel):
    flag: str


class FeedbackBody(BaseModel):
    trace_id: str
    vote: int  # 1 = thumbs up, -1 = thumbs down
    comment: str = ""


class DecisionBody(BaseModel):
    approve: bool


class RoleBody(BaseModel):
    role: str


class GameState:
    """Everything the API needs, in one place. Levels reload when their files change."""

    def __init__(self, settings: Settings, provider: LLMProvider | None, db_path: Path | str) -> None:
        self.settings = settings
        self.extensions = {
            kind: load_extension_modules(folder) for kind, folder in (("rails", CUSTOM_CHECKS_DIR), ("tools", TOOLS_CUSTOM_DIR))
        }
        self.provider = provider or make_provider(settings.llm)
        self.store = Store(db_path)
        self.tracer = Tracer(DATA_DIR / "traces.jsonl" if str(db_path) != ":memory:" else None)
        self.pipeline = GuardPipeline(self.provider, self.store, settings.game)
        self.host_pin = settings.host_pin or f"{secrets.randbelow(10**6):06d}"
        self.conversations: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.meters: dict[tuple[str, str], float] = defaultdict(float)
        self.hints_used: dict[tuple[str, str], int] = defaultdict(int)
        self.recent: dict[str, deque[float]] = defaultdict(deque)
        self._levels: dict[str, Level] = {}
        self._levels_stamp = -1.0
        self._lock = threading.Lock()

    # -- levels -----------------------------------------------------------
    def _stamp(self) -> float:
        files = list(CHALLENGES_DIR.glob("*.yaml"))
        return max((f.stat().st_mtime for f in files), default=0.0) + len(files)

    def levels(self) -> dict[str, Level]:
        stamp = self._stamp()
        if stamp != self._levels_stamp:
            with self._lock:
                self._levels = load_levels()
                self._levels_stamp = stamp
                log.info("Loaded %d levels", len(self._levels))
        return self._levels

    def level(self, level_id: str) -> Level:
        level = self.levels().get(level_id)
        if not level:
            raise HTTPException(404, f"No level '{level_id}'")
        return level

    def unlocked(self, player: dict[str, Any]) -> set[str]:
        ids = list(self.levels())
        if not self.settings.game.progressive_unlock or self.store.get_flag("unlock_all") == "1":
            return set(ids)
        solved = self.store.solved_levels(player["token"])
        open_ids = set()
        for i, level_id in enumerate(ids):
            if i == 0 or ids[i - 1] in solved or level_id in solved:
                open_ids.add(level_id)
        return open_ids

    def rate_ok(self, token: str) -> bool:
        window = self.recent[token]
        now = time.time()
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.settings.game.rate_limit_per_minute:
            return False
        window.append(now)
        return True


def _rail_info(specs: list[Any]) -> list[dict[str, str]]:
    out = []
    for spec in specs:
        desc = RAILS.get(spec.name).description if spec.name in RAILS else "(unknown rail)"
        out.append({"name": spec.name, "description": desc, "label": spec.label, "explain": spec.explain})
    return out


def level_public(state: GameState, level: Level, player: dict[str, Any] | None) -> dict[str, Any]:
    token = player["token"] if player else ""
    solved = bool(player) and level.id in state.store.solved_levels(token)
    data: dict[str, Any] = {
        "id": level.id,
        "order": level.order,
        "title": level.title,
        "subtitle": level.subtitle,
        "points": level.points,
        "character": level.character.model_dump(exclude={"refusals"}),
        "briefing": level.briefing,
        "rails": {
            "input": _rail_info(level.input_rails),
            "output": _rail_info(level.output_rails),
            "tool": _rail_info(level.tool_rails),
        },
        "tools": level.tools,
        "starters": level.starters,
        "hints_total": len(level.hints),
        "hints": level.hints[: state.hints_used[(token, level.id)]] if player else [],
        "solved": solved,
        "unlocked": bool(player) and level.id in state.unlocked(player),
        "attempts": state.store.attempts(token, level.id) if player else 0,
    }
    if solved:
        data["lesson"] = level.lesson.model_dump()
        data["reveal"] = {
            "system_prompt": level.render_system_prompt(),
            "rails": {
                "input": [s.model_dump() for s in level.input_rails],
                "output": [s.model_dump() for s in level.output_rails],
                "tool": [s.model_dump() for s in level.tool_rails],
            },
            "authz": level.authz,
            "source": level.source,
        }
    return data


def create_app(
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
    db_path: Path | str | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    state = GameState(settings, provider, db_path or DATA_DIR / "vault_heist.db")

    @asynccontextmanager
    async def lifespan(_: FastAPI):  # type: ignore[no-untyped-def]
        yield
        state.tracer.flush()

    app = FastAPI(title="Token Vault", version=__version__, lifespan=lifespan)
    app.state.game = state

    # -- auth helpers -----------------------------------------------------
    def player_dep(x_player_token: str = Header(default="")) -> dict[str, Any]:
        player = state.store.get_player(x_player_token) if x_player_token else None
        if not player:
            raise HTTPException(401, "Join the game first.")
        return player

    def host_dep(x_host_pin: str = Header(default="")) -> None:
        if not secrets.compare_digest(x_host_pin, state.host_pin):
            raise HTTPException(403, "Wrong host PIN.")

    # -- pages ------------------------------------------------------------
    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")


    @app.get("/host", include_in_schema=False)
    def host_page() -> FileResponse:
        return FileResponse(WEB_DIR / "host.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    # -- public API -------------------------------------------------------
    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return {
            "version": __version__,
            "provider": state.provider.describe(),
            "provider_name": state.provider.name,
            "langfuse": state.tracer.langfuse_enabled,
            "levels": len(state.levels()),
            "rails": RAILS.names(),
            "tools": TOOLS.names(),
            "extensions": state.extensions,
        }

    @app.post("/api/join")
    def join(body: JoinBody) -> dict[str, Any]:
        if not body.name.strip():
            raise HTTPException(400, "Pick a name.")
        return state.store.create_player(body.name, body.team)

    @app.post("/api/demo/{user}")
    def demo_user(user: str) -> dict[str, Any]:
        """Sign in as one of the three demo users. Same laptop, separate progress."""
        key = user.strip().lower()
        if key not in DEMO_USERS:
            raise HTTPException(404, "There are only three demo users: admin, intern and customer.")
        name = key.capitalize()
        return state.store.find_player(name, "Demo") or state.store.create_player(name, "Demo")

    @app.get("/api/me")
    def me(player: dict = Depends(player_dep)) -> dict[str, Any]:
        return {**player, "points": state.store.points(player["token"])}

    @app.post("/api/feedback")
    def feedback(body: FeedbackBody, player: dict = Depends(player_dep)) -> dict[str, Any]:
        trace = state.tracer.get(body.trace_id)
        if not trace or trace.player != player["name"]:
            raise HTTPException(404, "That reply is not one of yours.")
        vote = 1 if body.vote > 0 else -1
        state.store.record_feedback(body.trace_id, player["token"], trace.level, vote, body.comment)
        scored = state.tracer.score(trace.langfuse_trace_id, 1.0 if vote > 0 else 0.0, body.comment)
        return {"ok": True, "vote": vote, "sent_to_langfuse": scored}

    @app.get("/api/levels")
    def levels(player: dict = Depends(player_dep)) -> list[dict[str, Any]]:
        return [level_public(state, lv, player) for lv in state.levels().values()]

    @app.get("/api/levels/{level_id}")
    def level_detail(level_id: str, player: dict = Depends(player_dep)) -> dict[str, Any]:
        data = level_public(state, state.level(level_id), player)
        data["history"] = [
            {"role": m["role"], "content": m.get("content", "")}
            for m in state.conversations.get((player["token"], level_id), [])
            if m["role"] in ("user", "assistant") and m.get("content")
        ]
        data["meter"] = state.meters[(player["token"], level_id)]
        data["feedback"] = state.store.feedback_for(player["token"], level_id)
        return data

    @app.post("/api/levels/{level_id}/chat")
    def chat(level_id: str, body: ChatBody, player: dict = Depends(player_dep)) -> dict[str, Any]:
        level = state.level(level_id)
        if level_id not in state.unlocked(player):
            raise HTTPException(403, "This level is still locked. Solve the previous one first.")
        text = body.message.strip()
        if not text:
            raise HTTPException(400, "Say something.")
        if len(text) > settings.game.max_message_chars:
            raise HTTPException(400, f"Keep it under {settings.game.max_message_chars} characters.")
        if not state.rate_ok(player["token"]):
            raise HTTPException(429, "Slow down! The guard needs a breather. Try again in a minute.")

        key = (player["token"], level_id)
        history = state.conversations.get(key, [])
        with state.tracer.turn(player, level_id, text) as trace:
            result = state.pipeline.run(level, player, history, text, trace)
        state.conversations[key] = result.history
        state.store.record_attempt(player["token"], level_id, result.status == "blocked")
        meter = min(1.0, state.meters[key] * 0.6 + result.suspicion)
        state.meters[key] = meter
        return {
            "reply": result.reply,
            "status": result.status,
            "blocked_by": result.blocked_by,
            "reason": result.reason,
            "events": result.events,
            "meter": round(meter, 2),
            "trace_id": result.trace_id,
            "langfuse_url": trace.langfuse_url,
            "leak": level.secret in result.reply,
        }

    @app.post("/api/levels/{level_id}/reset")
    def reset(level_id: str, player: dict = Depends(player_dep)) -> dict[str, str]:
        state.conversations.pop((player["token"], level_id), None)
        state.meters.pop((player["token"], level_id), None)
        return {"status": "reset"}

    @app.post("/api/levels/{level_id}/hint")
    def hint(level_id: str, player: dict = Depends(player_dep)) -> dict[str, Any]:
        level = state.level(level_id)
        key = (player["token"], level_id)
        state.hints_used[key] = min(len(level.hints), state.hints_used[key] + 1)
        return {"hints": level.hints[: state.hints_used[key]], "total": len(level.hints)}

    @app.post("/api/levels/{level_id}/flag")
    def submit_flag(level_id: str, body: FlagBody, player: dict = Depends(player_dep)) -> dict[str, Any]:
        level = state.level(level_id)
        # Forgiving match: case, spaces and dashes don't matter (acrostics lose the dashes).
        if not body.flag.strip() or normalize(body.flag) != normalize(level.secret):
            return {"correct": False, "message": "That's not it. The vault stays shut."}
        attempts = state.store.attempts(player["token"], level_id)
        hints = state.hints_used[(player["token"], level_id)]
        points = level.points + (level.points // 4 if attempts <= 3 else 0) - (level.points // 10) * hints
        points = max(points, level.points // 4)
        first = state.store.record_solve(player["token"], level_id, points)
        return {
            "correct": True,
            "first_time": first,
            "points": points if first else 0,
            "message": "VAULT CRACKED!" if first else "Already cracked. Still impressive.",
            "level": level_public(state, level, player),
        }

    @app.get("/api/traces/{trace_id}")
    def trace(trace_id: str, player: dict = Depends(player_dep)) -> dict[str, Any]:
        t = state.tracer.get(trace_id)
        if not t:
            raise HTTPException(404, "Trace not found (traces are kept for the last 500 turns).")
        return t.public()

    @app.get("/api/scoreboard")
    def scoreboard() -> dict[str, Any]:
        board = state.store.scoreboard()
        titles = {lv.id: lv.title for lv in state.levels().values()}
        for r in board["recent"]:
            r["level_title"] = titles.get(r["level"], r["level"])
        board["levels"] = len(titles)
        return board

    @app.get("/api/attacks")
    def attacks() -> list[dict[str, Any]]:
        return load_attack_library()

    # -- host API ---------------------------------------------------------
    @app.get("/api/host/overview", dependencies=[Depends(host_dep)])
    def host_overview() -> dict[str, Any]:
        return {
            "players": state.store.players(),
            "approvals": state.store.approvals(),
            "unlock_all": state.store.get_flag("unlock_all") == "1",
            "provider": state.provider.describe(),
        }

    @app.post("/api/host/approvals/{approval_id}", dependencies=[Depends(host_dep)])
    def decide(approval_id: str, body: DecisionBody) -> dict[str, str]:
        state.store.decide_approval(approval_id, body.approve)
        return {"status": "approved" if body.approve else "denied"}

    @app.post("/api/host/players/{token}/role", dependencies=[Depends(host_dep)])
    def set_role(token: str, body: RoleBody) -> dict[str, str]:
        state.store.set_role(token, body.role if body.role in ("guest", "staff", "admin") else "guest")
        return {"status": "ok"}

    @app.post("/api/host/unlock_all", dependencies=[Depends(host_dep)])
    def unlock_all(body: DecisionBody) -> dict[str, bool]:
        state.store.set_flag("unlock_all", "1" if body.approve else "0")
        return {"unlock_all": body.approve}

    @app.post("/api/host/reset_scores", dependencies=[Depends(host_dep)])
    def reset_scores() -> dict[str, str]:
        state.store.reset_scores()
        state.conversations.clear()
        state.meters.clear()
        return {"status": "reset"}

    return app
