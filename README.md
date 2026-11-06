# Token Vault

A hands-on workshop on AI guardrails, authorization, and observability, played as a CTF-style heist.

Five AI guards each protect a **fake secret**. Players chat with a guard, find the way past its defenses,
and paste the secret into the vault box. Each challenge teaches one way attackers reach an AI system and
one defense that stops them.

Everything runs locally. With no API key and no internet, an offline mock guard plays the part, so the
game always starts.

---

## Contents

1. [Quick start](#quick-start)
2. [The five challenges](#the-five-challenges)
3. [Folder map](#folder-map)
4. [How the guardrails work](#how-the-guardrails-work)
5. [Configuration](#configuration)
6. [Commands](#commands)
7. [Monitoring with Langfuse](#monitoring-with-langfuse)
8. [Adding your own](#adding-your-own)
9. [Safety rules](#safety-rules)

---

## Quick start

You need [uv](https://docs.astral.sh/uv/), which installs Python 3.12 and every package for you.

```bash
uv sync                          # install everything (once)
uv run vault-heist serve         # start the game
```

Then open **http://localhost:8000**. The terminal prints a host PIN for the host panel.

Optional extras: `uv sync --extra langfuse` (tracing), `--extra nemo` (NeMo Guardrails), `--all-extras` for everything.

To let other laptops on the same network join, set `VAULT_HOST=0.0.0.0` in `.env` and share your IP address.

---

## The five challenges

Every challenge is open from the start. Pick any one. Each file in `challenges/` defines one.

| # | Challenge | Guard | What to break | Defense it teaches |
|---|---|---|---|---|
| 1 | **Key Vault** | Dana, a desk assistant | A file reader that can open any workshop file | Access rules belong in the tool, not the prompt |
| 2 | **Policy Desk** | Pat, a returns assistant | Questions about the policy only, with an internal appendix | A topic check is not a sensitivity check |
| 3 | **Poisoned Ticket** | Sam, a ticket summariser | A note inside a ticket that tells the guard to act | Tool output is data, not instructions |
| 4 | **Roleplay Override** | Robin, an audit desk | An override code, behind a story | Access follows who asks, not what the request pretends to be |
| 5 | **Customer Records** | Nia, a support lookup | A customer's support token | Output checks match patterns; they don't know every secret |

Each challenge's **route panel** shows every check a message passes through. Green means it got through;
red means a check stopped it, and the reason is written beside it.

---

## Folder map

```
Token-Vault/
├── challenges/          The five challenges, one YAML file each.
│                        _TEMPLATE.yaml documents every field.
├── guardrails/          Everything about guardrails: the checks, their stages,
│                        framework adapters, your own checks, and the guide (README.md).
├── sandbox/             Fake files the guard can read through its tools:
│                        customers, policies, tickets, and desk notes. Nothing here is real.
├── vault_heist/         The engine (Python).
│   ├── app.py           the web API and page routes
│   ├── cli.py           the vault-heist command
│   ├── config.py        loads settings and challenges
│   ├── pipeline/        the order of steps for one chat turn (LangGraph)
│   ├── tools/           what the guard can call: read_file, customer_lookup, and more
│   │   └── custom/      your own tools, loaded at startup
│   ├── llm/             model providers: NVIDIA, Anthropic, Ollama, and an offline mock
│   ├── crews/           the attack runner and optional CrewAI players
│   ├── tracing/         the local trace log and the Langfuse link
│   └── game/            the local database: players, solves, feedback
├── web/                 The browser app (HTML, CSS and JavaScript, no build step).
├── config/
│   ├── settings.yaml    server, model, prices, and unlocking
│   └── attacks.yaml     the attack library used by `vault-heist attack`
├── tests/               Automated tests (pytest).
├── .claude/skills/      Skills for the coding assistant (Langfuse, design review).
├── data/                Local runtime data: the database and trace log. Git-ignored.
├── pyproject.toml       the Python project and its dependencies
├── uv.lock              exact versions, so everyone gets the same packages
├── .python-version      the Python version uv uses (3.12)
├── .env.example         every setting you can put in `.env`
├── CLAUDE.md            notes for the coding assistant
└── PRODUCT.md           product context for the design skill
```

To add a challenge, copy `challenges/_TEMPLATE.yaml`. To add a check, see [guardrails/README.md](guardrails/README.md).

---

## How the guardrails work

A guardrail is a small Python check that allows or blocks text, in code, outside the model. Checks run at
three stages: on the visitor's message, on each tool call, and on the model's reply.

The full explanation, with a diagram, a table of every built-in check, and how to write your own, is in
**[guardrails/README.md](guardrails/README.md)**.

---

## Configuration

Settings come from three places, in this order: `config/settings.yaml`, then `.env` (copy `.env.example`),
then environment variables.

| Setting | Where | What it does |
|---|---|---|
| `NVIDIA_API_KEY` | `.env` | Key for the NVIDIA model. Never put it in a prompt. |
| `LLM_PROVIDER` | `.env` | `nvidia`, `anthropic`, `ollama` or `mock`. `auto` picks one. |
| `LLM_PRICE_INPUT_PER_M`, `LLM_PRICE_OUTPUT_PER_M` | `.env` | Dollars per million tokens, for cost tracking. |
| `LANGFUSE_*` | `.env` | Langfuse keys and URL. Leave empty to skip. |
| `progressive_unlock` | `config/settings.yaml` | `false` opens every challenge. `true` unlocks them one by one. |

---

## Commands

| Command | What it does |
|---|---|
| `uv run vault-heist serve` | Start the game on http://localhost:8000 |
| `uv run vault-heist doctor` | Check packages, keys, providers, guardrails, tools, and challenges |
| `uv run vault-heist attack -v` | Fire the attack library at every challenge |
| `uv run vault-heist crew` | Let CrewAI players attack by themselves (needs `--extra crew`) |
| `uv run vault-heist new-rail NAME` | Create a guardrail in `guardrails/custom/` |
| `uv run vault-heist new-level NAME` | Create a challenge in `challenges/` |
| `uv run pytest` | Run the tests (no API key or internet needed) |

---

## Monitoring with Langfuse

Set the three `LANGFUSE_*` keys in `.env`, then restart. Every chat turn becomes a trace with one step per
check, one per model call (with tokens and cost), and one per tool call. Thumbs and notes from players
appear inside the trace as `user-feedback`.

Traces are always kept locally too, in `data/traces.jsonl`.

---

## Adding your own

- **A guardrail:** `uv run vault-heist new-rail NAME`, then see [guardrails/README.md](guardrails/README.md).
- **A tool:** copy `vault_heist/tools/custom/example_coin_flip.py` into the same folder and edit it.
- **A challenge:** `uv run vault-heist new-level NAME`, then fill in the YAML.

A broken file in a custom folder is logged and skipped; the game keeps running.

---

## Safety rules

- **All secrets are fake** and start with `FAKE-`.
- **Players attack this sandbox only.** The workshop never teaches attacks against real third-party systems.
- **Never put real keys or personal data** in `sandbox/`, in `challenges/`, or in a commit. Real keys go in `.env`, which is git-ignored.
- **Security decisions belong in code**, not in prompts. That is the lesson of every challenge.

---

## License

See the repository. Licensed for workshop and educational use.
