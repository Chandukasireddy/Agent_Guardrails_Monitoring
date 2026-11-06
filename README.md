# Agent Guardrails & Monitoring — "Vault Heist" Workshop

> **Break it. Understand why. Build it stronger.**
> A hands-on Sunday-meetup workshop on AI guardrails, authorization, and observability, played as a CTF-style heist.

Every level has an AI guard protecting a **fake secret**. Players chat with the guard, try to get the secret out, and paste it into the flag box to crack the vault. Each level adds a new guardrail. After each crack, the game shows what worked, how a real system should defend against it, and the guard's full configuration.

Everything runs locally with one click. With no API key and no internet, an offline "gullible guard" plays the guards, so the game always starts. Add a Claude API key or a local Ollama model for real LLM guards.

---

## Table of Contents

1. [Quick start](#quick-start)
2. [What players see](#what-players-see)
3. [The levels](#the-levels)
4. [How it works](#how-it-works)
5. [Choosing the guard's brain](#choosing-the-guards-brain)
6. [Monitoring with Langfuse](#monitoring-with-langfuse)
7. [Extending the game](#extending-the-game)
8. [Command reference](#command-reference)
9. [Repository layout](#repository-layout)
10. [Running the workshop](#running-the-workshop)
11. [Safety rules for the sandbox](#safety-rules-for-the-sandbox)
12. [GitHub setup](#github-setup)
13. [Roadmap](#roadmap)
14. [License](#license)

---

## Quick start

**Windows:** double-click `play.bat`.

**macOS / Linux:**

```bash
./play.sh
```

That's it. The first run installs [uv](https://docs.astral.sh/uv/), which installs Python 3.12 and every package, creates `.env`, starts the game, and opens `http://localhost:8000` in your browser. Later runs start in a few seconds. Nothing needs to be installed beforehand.

The terminal prints three links:

| Page | URL | Who |
|---|---|---|
| Game | `http://localhost:8000` | Players |
| Scoreboard | `http://localhost:8000/scoreboard` | The projector |
| Host panel | `http://localhost:8000/host` | The host (needs the PIN printed in the terminal) |

To let other laptops on the same Wi-Fi join, set `VAULT_HOST=0.0.0.0` in `.env` and share your machine's IP address.

**Docker** (if you prefer it):

```bash
docker compose up --build
```

**Optional extras** (Langfuse, NeMo Guardrails, CrewAI):

```bash
play.bat --all
```

On macOS / Linux: `./play.sh --all`. NeMo Guardrails may need C++ build tools on Windows; the game works without it.

---

## What players see

- **Level map:** 13 vaults, each with a character, a subtitle, and points. Levels unlock one by one (the host can unlock all).
- **Level screen:**
  - The guard's character card and mission briefing.
  - The list of **defenses** on the level: which rails run and which tools the guard has.
  - A **chat** with the guard. Blocked replies show which rail stopped them and why.
  - A **live pipeline** that lights up each step of every request: input rails, the model, tool calls, tool rails, output rails. Blocked steps flash red.
  - A **tripwire meter** that rises as the guardrails get suspicious.
  - A **🔍 trace** on every reply, with each span, its input, output, and timing.
  - A **flag box** and **hints** (each hint costs 10% of the level's points).
- **Vault cracked:** confetti, points, an attack card ("what worked"), a defense card ("how to defend"), and the guard's real system prompt and rail settings.
- **Attack bingo:** a board of attack techniques to tick off as players use them.
- **Scoreboard:** a big-screen leaderboard with teams, attacks fired, block rate, and a live feed of cracks.
- **Host panel:** approve or deny requests for the Human in the Loop level, change player roles for Fort Knox, unlock all levels, and reset scores.

---

## The levels

| # | Level | Guard | New defense | What players learn |
|---|---|---|---|---|
| 0 | Say Hello | Pip the Intern 🐣 | None | How the game, flags, and traces work |
| 1 | The Open Door | Doris 🚪 | None | Models leak whatever is in their context |
| 2 | The Polite Guard | Sir Reginald 🎩 | "Never reveal" in the prompt | A system prompt is not a security boundary |
| 3 | The Keyword Bouncer | Bruno 🕶️ | Keyword filter, injection filter | Word lists are easy to bypass (stories, acrostics) |
| 4 | The Output Inspector | Inspector Ivy 🔍 | Exact-match output scanner | Encodings and spacing slip past exact matching |
| 5 | The Role Check | Clerk Clara 📋 | Vault tool with a role check | Identity from the conversation can't be trusted |
| 6 | The Grandma Problem | Gentle Gus 🧸 | Pressure detector, normalized scanner | Social engineering works on models; base64 still slips through |
| 7 | The Tool Tripwire | Librarian Lou 📚 | Tool allow list | Path traversal through an "allowed" tool |
| 8 | Human in the Loop | Officer Opal 👮 | Human approval from the host | The human approver can be persuaded too |
| 9 | The Command Shell | Terminal Tess 💻 | Command text filter | Wildcards expand after the filter runs |
| 10 | Layered Defense | Captain Bastion 🏰 | Every rail plus an LLM judge | Chunking defeats whole-secret scanners |
| 11 | The GPU Bazaar | Haggle Hank 🛒 | Price floors in code | Negotiate a $20,000 GPU to $17,000 or less with honest leverage; name-dropping is blocked |
| 12 | Fort Knox | Warden Vex 🔐 | Authorization from the login session | The right design: nothing typed in chat can open it |

Every level is a YAML file in `config/levels/`. The secrets all start with `FAKE-`.

---

## How it works

```
Browser (web/)                       FastAPI (vault_heist/app.py)
  chat, pipeline, meter  ──HTTP──▶     │
                                       ▼
                         LangGraph guard pipeline (vault_heist/pipeline/graph.py)
                         ┌───────────────────────────────────────────────┐
  player message ──▶     │ input rails ──blocked──▶ refusal               │
                         │     │                                          │
                         │     ▼                                          │
                         │ guard (LLM) ──tool calls──▶ tool rails + tools │
                         │     ▲                          │ (authz in code)│
                         │     └──────────────────────────┘               │
                         │     ▼                                          │
                         │ output rails ──blocked──▶ refusal              │
                         └───────────────────────────────────────────────┘
                                       │
          Tracer: local traces (in-game 🔍 view, data/traces.jsonl) + Langfuse (optional)
          Store:  SQLite (data/vault_heist.db) for players, scores, approvals
```

Key design rules, which the levels teach:

- **Rails run outside the model.** Each rail is a small Python class; levels list which rails run and with what settings.
- **Security decisions live in tools, in code.** `vault_read` checks access itself: by the role the model claims (flawed, level 5), by host approval (level 8), or by the player's session role (correct, level 12).
- **Nothing real is reachable.** The shell and the file system are simulated in `vault_heist/tools/`.

### Tech stack

| Layer | Choice | Why |
|---|---|---|
| Guard pipeline | **LangGraph** | Explicit nodes for rails, the model, and tools; each node is a span |
| Guardrails | Built-in Python rails, plus an optional **NVIDIA NeMo Guardrails** adapter | Built-ins are readable and editable; NeMo plugs in as one more rail |
| Multi-agent players | **CrewAI** (optional) | Attacker and negotiator crews that play levels by themselves |
| Observability | Local traces, plus optional **Langfuse** | The in-game trace view works offline; Langfuse adds dashboards |
| Models | **Claude** (Anthropic SDK), **Ollama** local models, or the offline mock guard | Works with a cloud key, a small local model, or nothing at all |
| Backend | **FastAPI** + SQLite | One process, one port, no database server |
| Front end | Plain HTML, CSS, and JavaScript modules, no build step | Edit a file, refresh the browser. Easy for anyone (or a small LLM) to change |
| Setup | **uv** via `play.bat` / `play.sh`, or Docker | One click from a bare machine |

The README's earlier plan used Next.js for the front end. The build-free front end replaced it so the whole game runs as one Python process with no Node.js install, which keeps setup to one click.

---

## Choosing the guard's brain

Set `LLM_PROVIDER` in `.env`:

| Value | What happens |
|---|---|
| `auto` (default) | Claude if `ANTHROPIC_API_KEY` is set, else Ollama if it is running with the configured model, else the offline mock guard |
| `anthropic` | Claude. Defaults: `claude-opus-5-5` for guards, `claude-haiku-5-5` for the LLM judge rail, effort `low` |
| `ollama` | A local model (default `llama3.2`). Models without tool support still work on the non-tool levels |
| `mock` | The offline gullible guard. Deterministic, free, and good for testing |

The Claude provider turns on Anthropic's server-side fallback for refused requests (`anthropic_fallbacks` in `config/settings.yaml`). Change models and effort in `config/settings.yaml` or `.env`.

Cost control: each player is rate-limited (20 messages a minute by default, `rate_limit_per_minute`).

---

## Monitoring with Langfuse

Every turn is always traced locally: open the 🔍 on any reply. To also send traces to Langfuse:

1. Install the extra: `uv sync --extra langfuse` (or `play.bat --all`).
2. Create a project in [Langfuse Cloud](https://cloud.langfuse.com) or a [self-hosted Langfuse](https://langfuse.com/self-hosting).
3. Put the keys in `.env`: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL`.

Each turn becomes a trace named `vault-heist:<level>`, grouped by session (player and level), with one observation per rail (`guardrail`), model call (`generation`), and tool call (`tool`). Blocks are marked as warnings, so the Langfuse dashboard shows which rails fire most.

---

## Extending the game

Everything is a plugin. See [extensions/README.md](extensions/README.md) for the full guide.

```bash
uv run vault-heist new-rail profanity_filter   # creates extensions/rails/profanity_filter.py
uv run vault-heist new-level my_level          # creates extensions/levels/my_level.yaml
```

- **Rails:** one class with `check(ctx) -> Verdict`. Register with `@RAILS.register("name")`.
- **Tools:** one class with `run(args, ctx) -> str` and a JSON schema. Register with `@TOOLS.register("name")`.
- **Levels:** YAML. `config/levels/_TEMPLATE.yaml` documents every field. Levels reload on save.
- **LLM providers:** register a class with `@PROVIDERS.register("name")` in `vault_heist/llm/`.
- **Look and feel:** colors and fonts are CSS variables at the top of `web/css/theme.css`.

A broken extension file is logged and skipped, so the game keeps running. `extensions/` ships with an example rail, tool, and level.

---

## Command reference

On Windows use `play.bat <command>`; anywhere, `uv run vault-heist <command>` works once set up.

| Command | What it does |
|---|---|
| `vault-heist` or `vault-heist serve` | Start the game (`--port`, `--host`, `--no-browser`) |
| `vault-heist doctor` | Check Python, packages, keys, Ollama, Langfuse, rails, tools, and levels |
| `vault-heist attack [--level ID] [-v]` | Fire the attack library (`config/attacks.yaml`) at levels and report leaks |
| `vault-heist crew --level ID [--mode attacker\|negotiator]` | Let a CrewAI crew play a level (needs the `crew` extra and a real model) |
| `vault-heist new-rail NAME` | Scaffold a guardrail in `extensions/rails/` |
| `vault-heist new-level NAME` | Scaffold a level in `extensions/levels/` |
| `uv run pytest` | Run the tests, including a solve of every level with the offline guard |

---

## Repository layout

```
Agent_Guardrails_Monitoring/
├── play.bat / play.sh        # one-click setup and start
├── setup.bat                 # Windows setup only
├── Dockerfile, docker-compose.yml
├── pyproject.toml, uv.lock   # Python project (managed by uv)
├── .env.example              # keys and settings
├── config/
│   ├── settings.yaml         # server, model, and game settings
│   ├── attacks.yaml          # attack library (bingo board + attack runner)
│   └── levels/               # one YAML file per level, plus _TEMPLATE.yaml
├── vault_heist/              # the Python package
│   ├── app.py                # FastAPI: game API, host API, static pages
│   ├── cli.py                # vault-heist command
│   ├── config.py             # settings and level loading
│   ├── pipeline/graph.py     # LangGraph guard pipeline
│   ├── rails/                # built-in guardrails and the NeMo adapter
│   ├── tools/                # vault, notes, simulated shell, approvals, pricing desk
│   ├── llm/                  # Claude, Ollama, and offline mock providers
│   ├── tracing/              # local traces and Langfuse
│   ├── game/store.py         # SQLite: players, scores, approvals
│   └── crews/                # attack runner and CrewAI crews
├── web/                      # build-free front end (HTML, CSS, JS modules)
├── extensions/               # participant plugins: rails, tools, levels
├── guardrails/nemo/          # sample NeMo Guardrails config
├── tests/                    # pytest suite
└── data/                     # runtime data (git-ignored)
```

---

## Running the workshop

### Before the day

- Run `play.bat` (or `./play.sh`) once on the host machine with internet, so everything is downloaded.
- Decide the guard brain: a Claude key for the best experience, Ollama for offline, or the mock guard as a fallback.
- Optional: set `HOST_PIN` in `.env` so the PIN doesn't change between runs.
- Run `vault-heist doctor` and `vault-heist attack` to check everything.

### A two-hour Sunday

| Time | Segment | What happens |
|---|---|---|
| 0:00–0:10 | Welcome | Explain the vault, the guards, and the rules. Show the scoreboard on the projector. |
| 0:10–0:20 | Tutorial | Everyone cracks level 0 and opens a trace. |
| 0:20–0:55 | Levels 1–4 | Prompt-level defenses. Host reveals each defense card after the first crack. |
| 0:55–1:05 | Break | Leaderboard, bingo check, and an award for the most creative attack. |
| 1:05–1:35 | Levels 5–10 | Authorization, tools, human approval, shell, layered defense. Host handles approvals live. |
| 1:35–1:50 | Build | Teams write a new rail with `new-rail` and add it to a level. |
| 1:50–2:00 | Showcase | Each team shows one attack and one defense. Fort Knox and the GPU Bazaar are bonus rounds. |

### Host tips

- On Human in the Loop, read the approval reasons aloud before deciding. The room learns how persuasion works on humans.
- For Fort Knox, a player can only win by convincing you to make them an admin on the host panel.
- After a level, use "Behind the curtain" on the cracked screen to show the real configuration.

---

## Safety rules for the sandbox

- **All secrets are fake** and start with `FAKE-`.
- **No real systems are reachable.** The shell and file system are simulated; no command ever runs on the machine.
- **No real personal data** is used.
- **Rate limits** per player protect the API budget.
- **Players attack this sandbox only.** The workshop never teaches attacks against real third-party systems.
- **API keys stay in `.env`**, which is git-ignored.

---

## GitHub setup

The project is managed with the GitHub CLI (`gh`). The repository is public at `Chandukasireddy/Agent_Guardrails_Monitoring`.

```bash
gh auth status
gh repo clone Chandukasireddy/Agent_Guardrails_Monitoring
gh issue create --title "Level 3 bypass found" --body "Steps to reproduce..."
gh pr create --fill
```

Branch names:

- `main` is always playable.
- `level/<number>-<name>` for new levels, for example `level/13-indirect-injection`.
- `rail/<name>` for new guardrails.
- `workshop/<date>` for content tied to a specific Sunday.

---

## Roadmap

- [x] Levels 0–12 playable end to end, including human approval and the negotiation bonus
- [x] Live pipeline view, tripwire meter, trace viewer, scoreboard, host panel, attack bingo
- [x] Claude, Ollama, and offline mock guards
- [x] Langfuse tracing, NeMo Guardrails adapter, CrewAI crews (optional extras)
- [x] One-click setup on Windows, macOS, and Linux; Docker
- [ ] An indirect prompt-injection level (a document with hidden instructions)
- [ ] Slides for each Sunday (Slidev)
- [ ] Recorded walkthrough and write-up

---

## License

To be decided (MIT suggested for the code). All vault data is fake and for education only.
