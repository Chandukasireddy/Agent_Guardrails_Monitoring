# Extensions

Everything in this folder plugs into the game without changing core code. The game loads it at startup, and level files reload as soon as you save them.

| Folder | What goes here | Picked up |
|---|---|---|
| `rails/` | Python files with new guardrails | At startup |
| `tools/` | Python files with new tools the guard can call | At startup |
| `levels/` | YAML files with new levels | Immediately, on save |

A broken file is logged and skipped, so one mistake never stops the game.

## Add a guardrail

```bash
uv run vault-heist new-rail profanity_filter
```

This creates `rails/profanity_filter.py`. A rail is one class with one method:

```python
@RAILS.register("profanity_filter")
class ProfanityFilter(Rail):
    description = "One line, shown in the UI."
    defaults = {"words": ["darn"]}

    def check(self, ctx: RailContext) -> Verdict:
        # ctx.stage: "input", "output" or "tool"
        # ctx.text: the text to check; ctx.level, ctx.player, ctx.provider also available
        if any(w in ctx.text.lower() for w in self.params["words"]):
            return Verdict.block("Watch your language.")
        return Verdict.ok()
```

Then list it in a level, with any parameters:

```yaml
input_rails:
  - name: profanity_filter
    params: {words: [darn, heck]}
```

Restart the game to load a new rail file.

## Add a tool

Copy `tools/example_coin_flip.py`. A tool has a `description`, an `input_schema` (JSON Schema for its arguments), and `run(args, ctx)` that returns text. Put security decisions in `run`: the model only asks, the tool decides.

## Add a level

```bash
uv run vault-heist new-level my_level
```

This copies `config/levels/_TEMPLATE.yaml`, which documents every field. Keep the `FAKE-` prefix on secrets.

## Ideas for workshop extensions

- An authorization layer that checks time of day or team membership.
- A rail that counts how many times a player asked about the vault and slows them down.
- A rail that calls an external moderation API.
- A NeMo Guardrails flow (see `guardrails/nemo/`) plugged in with the `nemo` rail.
- A level where the guard summarizes a document that hides an instruction (indirect prompt injection).
