"""Players, solves, attempts, and approvals in a local SQLite file (data/vault_heist.db)."""

from __future__ import annotations

import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    token TEXT PRIMARY KEY, name TEXT NOT NULL, team TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'guest', created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    player TEXT NOT NULL, level TEXT NOT NULL, ts REAL NOT NULL, blocked INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS solves (
    player TEXT NOT NULL, level TEXT NOT NULL, ts REAL NOT NULL, points INTEGER NOT NULL,
    PRIMARY KEY (player, level)
);
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY, player TEXT NOT NULL, level TEXT NOT NULL, action TEXT NOT NULL,
    reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS flags (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT NOT NULL, player TEXT NOT NULL,
    level TEXT NOT NULL, vote INTEGER NOT NULL, comment TEXT NOT NULL DEFAULT '', ts REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)

    def _q(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._db.execute(sql, args)
            self._db.commit()
            return [dict(r) for r in cur.fetchall()]

    # -- players ----------------------------------------------------------
    def create_player(self, name: str, team: str) -> dict[str, Any]:
        token = secrets.token_urlsafe(16)
        self._q(
            "INSERT INTO players (token, name, team, created) VALUES (?, ?, ?, ?)",
            (token, name.strip()[:40] or "Anonymous", team.strip()[:40] or "Solo", time.time()),
        )
        return self.get_player(token)  # type: ignore[return-value]

    def get_player(self, token: str) -> dict[str, Any] | None:
        rows = self._q("SELECT * FROM players WHERE token = ?", (token,))
        return rows[0] if rows else None

    def find_player(self, name: str, team: str) -> dict[str, Any] | None:
        rows = self._q("SELECT * FROM players WHERE name = ? AND team = ? ORDER BY created LIMIT 1", (name, team))
        return rows[0] if rows else None

    def set_role(self, token: str, role: str) -> None:
        self._q("UPDATE players SET role = ? WHERE token = ?", (role, token))

    def players(self) -> list[dict[str, Any]]:
        return self._q("SELECT token, name, team, role FROM players ORDER BY created")

    # -- progress ---------------------------------------------------------
    def record_feedback(self, trace_id: str, player: str, level: str, vote: int, comment: str) -> None:
        self._q(
            "INSERT INTO feedback (trace_id, player, level, vote, comment, ts) VALUES (?, ?, ?, ?, ?, ?)",
            (trace_id, player, level, vote, comment[:1000], time.time()),
        )

    def feedback_for(self, player: str, level: str) -> dict[str, dict[str, Any]]:
        rows = self._q("SELECT trace_id, vote, comment FROM feedback WHERE player = ? AND level = ? ORDER BY id", (player, level))
        return {r["trace_id"]: r for r in rows}

    def points(self, player: str) -> int:
        rows = self._q("SELECT COALESCE(SUM(points), 0) AS p FROM solves WHERE player = ?", (player,))
        return int(rows[0]["p"])

    def record_attempt(self, player: str, level: str, blocked: bool) -> None:
        self._q("INSERT INTO attempts VALUES (?, ?, ?, ?)", (player, level, time.time(), int(blocked)))

    def attempts(self, player: str, level: str) -> int:
        return self._q("SELECT COUNT(*) AS n FROM attempts WHERE player = ? AND level = ?", (player, level))[0]["n"]

    def record_solve(self, player: str, level: str, points: int) -> bool:
        """Returns True the first time a player solves a level."""
        if self._q("SELECT 1 FROM solves WHERE player = ? AND level = ?", (player, level)):
            return False
        self._q("INSERT INTO solves VALUES (?, ?, ?, ?)", (player, level, time.time(), points))
        return True

    def solved_levels(self, player: str) -> set[str]:
        return {r["level"] for r in self._q("SELECT level FROM solves WHERE player = ?", (player,))}

    def scoreboard(self) -> dict[str, Any]:
        players = self._q(
            """SELECT p.name, p.team, COALESCE(SUM(s.points), 0) AS points, COUNT(s.level) AS solved,
                      MAX(s.ts) AS last
               FROM players p LEFT JOIN solves s ON s.player = p.token
               GROUP BY p.token ORDER BY points DESC, last ASC"""
        )
        teams: dict[str, dict[str, Any]] = {}
        for p in players:
            t = teams.setdefault(p["team"], {"team": p["team"], "points": 0, "members": 0})
            t["points"] += p["points"]
            t["members"] += 1
        stats = self._q("SELECT COUNT(*) AS attempts, COALESCE(SUM(blocked), 0) AS blocked FROM attempts")[0]
        recent = self._q(
            """SELECT p.name, p.team, s.level, s.points, s.ts FROM solves s
               JOIN players p ON p.token = s.player ORDER BY s.ts DESC LIMIT 8"""
        )
        return {
            "players": players,
            "teams": sorted(teams.values(), key=lambda t: -t["points"]),
            "stats": stats,
            "recent": recent,
        }

    def reset_scores(self) -> None:
        self._q("DELETE FROM solves")
        self._q("DELETE FROM attempts")

    # -- approvals --------------------------------------------------------
    def create_approval(self, player: str, level: str, action: str, reason: str) -> dict[str, Any]:
        approval_id = "apr-" + secrets.token_hex(3)
        self._q(
            "INSERT INTO approvals (id, player, level, action, reason, ts) VALUES (?, ?, ?, ?, ?, ?)",
            (approval_id, player, level, action, reason, time.time()),
        )
        return self.get_approval(approval_id)  # type: ignore[return-value]

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        rows = self._q("SELECT * FROM approvals WHERE id = ?", (approval_id.strip().lower(),))
        return rows[0] if rows else None

    def decide_approval(self, approval_id: str, approve: bool) -> None:
        self._q("UPDATE approvals SET status = ? WHERE id = ?", ("approved" if approve else "denied", approval_id))

    def approvals(self) -> list[dict[str, Any]]:
        return self._q(
            """SELECT a.*, p.name AS player_name, p.team FROM approvals a
               LEFT JOIN players p ON p.token = a.player ORDER BY a.ts DESC LIMIT 50"""
        )

    # -- flags (host switches) ---------------------------------------------
    def get_flag(self, key: str, default: str = "") -> str:
        rows = self._q("SELECT value FROM flags WHERE key = ?", (key,))
        return rows[0]["value"] if rows else default

    def set_flag(self, key: str, value: str) -> None:
        self._q("INSERT OR REPLACE INTO flags VALUES (?, ?)", (key, value))
