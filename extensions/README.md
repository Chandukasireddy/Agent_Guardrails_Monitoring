# Extensions

Plugins for the game that do not belong to a single part of it. The game loads this folder at startup,
without changing core code.

| Folder | What goes here | Picked up |
|---|---|---|
| `tools/` | Python files with new tools the guard can call | At startup |

Guardrails have their own folder: see [guardrails/README.md](../guardrails/README.md), which includes
`guardrails/custom/` for your own checks. Challenges live in [challenges/](../challenges/).

A broken file is logged and skipped, so one mistake never stops the game.

## Add a tool

Copy `tools/example_coin_flip.py`. A tool has a `description`, an `input_schema` (JSON Schema for its
arguments), and `run(args, ctx)` that returns text. Put security decisions in `run`: the model only asks,
the tool decides.

## Add a challenge

```bash
uv run vault-heist new-level my_challenge
```

This creates `challenges/my_challenge.yaml`, copied from `challenges/_TEMPLATE.yaml`, which documents every field.
Keep the `FAKE-` prefix on secrets.

## Ideas for workshop extensions

- An authorization layer that checks time of day or team membership.
- A check that counts how many times a player asked about the vault and slows them down.
- A check that calls an external moderation API.
- A NeMo Guardrails flow, plugged in with the `nemo` check (see `guardrails/adapters/nemo_config/`).
- A challenge where the guard summarizes a document that hides an instruction (indirect prompt injection).
