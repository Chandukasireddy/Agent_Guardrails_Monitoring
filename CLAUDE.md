# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"Vault Heist" is a CTF-style workshop game: players chat with LLM guards to extract fake secrets, and each level adds a guardrail. It is a Python package (`vault_heist/`) served by FastAPI, with a build-free web front end in `web/`. `README.md` describes the levels, the workshop format, and the user-facing setup.

## Commands

Dependencies are managed with uv (`pyproject.toml`, `uv.lock`, Python 3.12 from `.python-version`).

```bash
uv sync                                   # install (add --extra langfuse|nemo|crew or --all-extras)
uv run vault-heist serve --no-browser     # run the game on http://localhost:8000
uv run vault-heist doctor                 # check packages, keys, providers, levels
uv run vault-heist attack -v              # fire config/attacks.yaml at every level
uv run pytest                             # all tests
uv run pytest -k gpu_bazaar               # one test (by name match)
```

`play.bat` / `play.sh` are the end-user one-click launchers (install uv, `uv sync`, copy `.env.example`, start). `setup.bat` is the install half for Windows. Batch files must keep CRLF line endings (`.gitattributes`). There is no linter configured.

Tests use the offline mock guard (`LLM_PROVIDER=mock` behaviour) and an in-memory database, so they need no API key or network.

## Architecture

- **Request flow:** `app.py` `/api/levels/{id}/chat` → `Tracer.turn()` → `GuardPipeline.run()` in `pipeline/graph.py`. The LangGraph graph is `input_rails → guard → (tools → guard)* → output_rails`. Each node appends UI events (consumed by `web/js/views/play.js` to animate the pipeline) and opens a trace span.
- **Plugins via registries** (`registry.py`): `RAILS` (`rails/base.py`), `TOOLS` (`tools/base.py`), `PROVIDERS` (`llm/base.py`). Levels reference rails and tools by registered name. Files in `extensions/rails` and `extensions/tools` are imported at startup; broken files are logged and skipped.
- **Levels** are YAML in `config/levels/` and `extensions/levels/` (files starting with `_` are ignored), validated by the `Level` model in `config.py`, and reloaded automatically when files change. `system_prompt` supports `{secret}`, `{guard}`, `{vault_items}`.
- **LLM providers** share a neutral message format (see `llm/base.py`). The Anthropic provider sends assistant `raw` content blocks back unchanged and folds tool results and follow-up user text into one user turn; keep conversation history append-only. `make_provider` falls back to the mock if a provider fails to start.
- **Mock guard** (`llm/mock_provider.py`) finds the secret with the regex `FAKE-[A-Z0-9-]+` in the system prompt and reacts to attack keywords. Level solvability tests in `tests/test_levels.py` depend on its behaviour; changing it or a level's rails can break those solutions.
- **Authorization lives in tools**, not prompts: `vault_read` implements the `authz` modes (`none`, `claimed_role`, `approval`, `session_role`); `make_offer` enforces price floors. The shell and file system are simulated in `tools/fakefs.py`.
- **State:** `game/store.py` (SQLite at `data/vault_heist.db`: players, attempts, solves, approvals, host flags). Conversations, tripwire meters, and hint counts are in memory in `GameState`.
- **Tracing** (`tracing/__init__.py`): always local (last 500 turns, plus `data/traces.jsonl`); mirrored to Langfuse only when `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are set and the package is installed. Tracing errors must never break a turn.
- **Settings:** `config/settings.yaml`, overridable by the env vars in `ENV_OVERRIDES` (`config.py`), loaded from `.env`.

## Constraints

- Every secret is fake and must start with `FAKE-`. The shell challenge must never execute real commands.
- Keep the participant sandbox away from real systems and real personal data.
- Teach that security decisions belong in code, not prompts; new levels should keep that lesson.
- The git remote is the public repo `Chandukasireddy/Agent_Guardrails_Monitoring`. Do not push without the user asking.
