"""Settings and level loading.

Settings come from ``config/settings.yaml``; any value can be overridden with
an environment variable (see ``.env.example``). Levels are YAML files in
``config/levels/`` and ``extensions/levels/``.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
EXTENSIONS_DIR = ROOT / "extensions"
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"

log = logging.getLogger(__name__)
load_dotenv(ROOT / ".env")


class LLMSettings(BaseModel):
    provider: str = "auto"  # auto | anthropic | ollama | mock
    anthropic_model: str = "claude-opus-5-5"
    anthropic_judge_model: str = "claude-haiku-5-5"
    anthropic_effort: str = "low"
    anthropic_fallbacks: bool = True
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    max_tokens: int = 16000
    timeout_seconds: float = 60.0


class GameSettings(BaseModel):
    progressive_unlock: bool = True
    max_tool_rounds: int = 3
    max_message_chars: int = 2000
    rate_limit_per_minute: int = 20


class Settings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    open_browser: bool = True
    host_pin: str = ""
    llm: LLMSettings = Field(default_factory=LLMSettings)
    game: GameSettings = Field(default_factory=GameSettings)


# Environment variable -> path inside Settings.
ENV_OVERRIDES: dict[str, tuple[str, ...]] = {
    "VAULT_HOST": ("host",),
    "VAULT_PORT": ("port",),
    "VAULT_OPEN_BROWSER": ("open_browser",),
    "HOST_PIN": ("host_pin",),
    "LLM_PROVIDER": ("llm", "provider"),
    "ANTHROPIC_MODEL": ("llm", "anthropic_model"),
    "ANTHROPIC_JUDGE_MODEL": ("llm", "anthropic_judge_model"),
    "ANTHROPIC_EFFORT": ("llm", "anthropic_effort"),
    "OLLAMA_URL": ("llm", "ollama_url"),
    "OLLAMA_MODEL": ("llm", "ollama_model"),
    "PROGRESSIVE_UNLOCK": ("game", "progressive_unlock"),
}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    raw: dict[str, Any] = {}
    path = CONFIG_DIR / "settings.yaml"
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for env, keys in ENV_OVERRIDES.items():
        value = os.environ.get(env)
        if value in (None, ""):
            continue
        target = raw
        for key in keys[:-1]:
            target = target.setdefault(key, {})
        target[keys[-1]] = value
    return Settings.model_validate(raw)


class RailSpec(BaseModel):
    """One guardrail in a level: ``name`` from the rail registry plus its params."""

    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class Character(BaseModel):
    name: str = "The Guard"
    avatar: str = "🛡️"
    color: str = "#38bdf8"
    tagline: str = ""
    refusals: list[str] = Field(default_factory=lambda: ["Nice try. The vault stays shut."])


class Lesson(BaseModel):
    attack: str = ""
    defense: str = ""


class Level(BaseModel):
    """A level, loaded from YAML. See ``config/levels/_TEMPLATE.yaml`` for every field."""

    id: str
    order: int
    title: str
    subtitle: str = ""
    points: int = 100
    character: Character = Field(default_factory=Character)
    briefing: str = ""
    secret: str
    system_prompt: str
    vault_items: dict[str, str] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)
    authz: str = "none"  # none | claimed_role | session_role | approval
    input_rails: list[RailSpec] = Field(default_factory=list)
    output_rails: list[RailSpec] = Field(default_factory=list)
    tool_rails: list[RailSpec] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)
    lesson: Lesson = Field(default_factory=Lesson)
    settings: dict[str, Any] = Field(default_factory=dict)
    source: str = ""

    def render_system_prompt(self) -> str:
        items = ", ".join(self.all_vault_items()) or "none"
        return self.system_prompt.format(
            secret=self.secret, guard=self.character.name, vault_items=items
        )

    def all_vault_items(self) -> dict[str, str]:
        items = {"master_key": self.secret}
        items.update(self.vault_items)
        return items


def _level_files() -> list[Path]:
    files = sorted((CONFIG_DIR / "levels").glob("*.yaml"))
    files += sorted((EXTENSIONS_DIR / "levels").glob("*.yaml"))
    return [f for f in files if not f.name.startswith("_")]


def load_levels() -> dict[str, Level]:
    levels: dict[str, Level] = {}
    for path in _level_files():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            level = Level.model_validate({**data, "source": path.relative_to(ROOT).as_posix()})
        except Exception as exc:  # noqa: BLE001 - a broken level must not stop the game
            log.error("Skipping level file %s: %s", path.name, exc)
            continue
        if level.id in levels:
            log.warning("Level id '%s' in %s overrides an earlier file", level.id, path.name)
        levels[level.id] = level
    return dict(sorted(levels.items(), key=lambda kv: (kv[1].order, kv[0])))


def load_attack_library() -> list[dict[str, Any]]:
    path = CONFIG_DIR / "attacks.yaml"
    if not path.exists():
        return []
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("attacks", [])
