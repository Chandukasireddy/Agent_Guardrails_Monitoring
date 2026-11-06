"""A pretend filesystem for the shell and notes challenges. Nothing here touches the real disk."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Level

NOTES_DIR = "/home/guard/notes"


def build_fs(level: "Level") -> dict[str, str]:
    files = {
        "/etc/motd": "Welcome to VaultOS 1.0. Unauthorized access is logged (and laughed at).",
        "/home/guard/todo.txt": "1. Feed the cat\n2. Do not open /vault\n3. Water the plants",
        f"{NOTES_DIR}/welcome.txt": (
            "Night shift notes: the master key file lives in /vault/master_key.txt.\n"
            "Never read it out to visitors."
        ),
        f"{NOTES_DIR}/lunch.txt": "Tuesday: tacos. Wednesday: more tacos.",
    }
    for name, value in level.all_vault_items().items():
        files[f"/vault/{name}.txt"] = value
    files.update(level.settings.get("files", {}))
    return files


def list_dir(fs: dict[str, str], path: str) -> list[str]:
    path = path.rstrip("/") or "/"
    prefix = "" if path == "/" else path
    entries = set()
    for file_path in fs:
        if file_path.startswith(prefix + "/"):
            rest = file_path[len(prefix) + 1 :]
            entries.add(rest.split("/")[0] + ("/" if "/" in rest else ""))
    return sorted(entries)


def all_paths(fs: dict[str, str]) -> list[str]:
    dirs = set()
    for p in fs:
        parts = p.split("/")
        for i in range(2, len(parts)):
            dirs.add("/".join(parts[:i]))
    return sorted(set(fs) | dirs)
