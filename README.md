# Agent Guardrails & Monitoring — "Token Vault" Workshop

> **Break it. Understand why. Build it stronger.**
> A hands-on Sunday-meetup workshop on AI guardrails, authorization, and observability, played as a CTF-style heist.

Every level has an AI guard protecting a **fake secret**. Players chat with the guard, try to get the secret out, and paste it into the flag box to crack the vault. Each level adds a new guardrail. After each crack, the game shows what worked, how a real system should defend against it, and the guard's full configuration.

Everything runs locally with one click. With no API key and no internet, an offline "gullible guard" plays the guards, so the game always starts. Add a Claude API key or a local Ollama model for real LLM guards.

---

## Table of Contents

1. [Quick start](#quick-start)
2. [What players see](#what-players-see)
3. [The levels](#the-five-challenges)
4. [How it works](#how-it-works)
5. [Choosing the guard's brain](#choosing-the-guards-brain)
6. [Monitoring with Langfuse](#monitoring-with-langfuse)
7. [Extending the game](#extending-the-game)
8. [Command reference](#command-reference)
9. [Folder map](#folder-map)
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
- **Host panel:** unlock all challenges, approve or deny any approval requests, and reset scores.

---

## The five challenges

1. **Key Vault:** a desk assistant that can read files. Its prompt says to keep things confidential; its file reader does not check.
2. **Policy Desk:** a returns assistant that only answers policy questions. A topic check stops everything else. The policy file has an internal appendix.
3. **Poisoned Ticket:** a summariser that reads a support ticket. The ticket contains a note that tells the guard to open another file.
4. **Roleplay Override:** an audit desk assistant with an override code. Simple checks catch direct requests; a roleplay gets through.
5. **Customer Records:** a support lookup. An output check blocks emails and phone numbers, but a support token passes.

Every vault is open from the start. Read [docs/GUARDRAILS.md](docs/GUARDRAILS.md) to see which check stops what.

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

Key design rules, which the challenges teach:

- **Rails run outside the model.** Each rail is a small Python class; each challenge lists which rails run and with what settings.
- **Security decisions live in tools, in code.** `vault_read` checks access itself: by the role the model claims (flawed, level 5), by host approval (level 8), or by the player's session role (correct, level 12).
- **Nothing real is reachable.** The shell and the file system are simulated in `vault_heist/tools/`.

### Tech stack

| Layer | Choice | Why |
|---|---|---|
| Guard pipeline | **LangGraph** | Explicit nodes for rails, the model, and tools; each node is a span |
| Guardrails | Built-in Python rails, plus an optional **NVIDIA NeMo Guardrails** adapter | Built-ins are readable and editable; NeMo plugs in as one more rail |
| Multi-agent players | **CrewAI** (optional) | Attacker and negotiator crews that play challenges by themselves |
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
| `ollama` | A local model (default `llama3.2`). Models without tool support still work on the challenges that need no tools |
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
uv run vault-heist new-level my_challenge      # creates challenges/my_challenge.yaml
```

- **Rails:** one class with `check(ctx) -> Verdict`. Register with `@RAILS.register("name")`.
- **Tools:** one class with `run(args, ctx) -> str` and a JSON schema. Register with `@TOOLS.register("name")`.
- **Challenges:** YAML in `challenges/`. `challenges/_TEMPLATE.yaml` documents every field. They reload on save.
- **LLM providers:** register a class with `@PROVIDERS.register("name")` in `vault_heist/llm/`.
- **Look and feel:** colors and fonts are CSS variables at the top of `web/css/theme.css`.

A broken extension file is logged and skipped, so the game keeps running. `extensions/` ships with an example rail, tool, and level.

---

## Command reference

On Windows use `play.bat <command>`; anywhere, `uv run vault-heist <command>` works once set up.

| Command | What it does |
|---|---|
| `vault-heist` or `vault-heist serve` | Start the game (`--port`, `--host`, `--no-browser`) |
| `vault-heist doctor` | Check Python, packages, keys, Ollama, Langfuse, rails, tools, and challenges |
| `vault-heist attack [--level ID] [-v]` | Fire the attack library (`config/attacks.yaml`) at levels and report leaks |
| `vault-heist crew --level ID [--mode attacker\|negotiator]` | Let a CrewAI crew play a level (needs the `crew` extra and a real model) |
| `vault-heist new-rail NAME` | Scaffold a guardrail in `extensions/rails/` |
| `vault-heist new-level NAME` | Scaffold a challenge in `challenges/` |
| `uv run pytest` | Run the tests, including a solve of every level with the offline guard |

---

## Folder map

Read this first. Each top-level folder has one job.

```
Token-Vault/
├── challenges/          THE FIVE GAMES. One YAML file per challenge.
│                        Each file says: who the guard is, its prompt, which checks it uses,
│                        which tools it can call, its hints, and its lesson.
├── sandbox/             FAKE FILES the guard can read through its tools (customers, policies,
│                        tickets, desk notes). Nothing here is real. See sandbox/README.md.
├── vault_heist/         THE ENGINE (Python). You rarely need to edit it to add a challenge.
│   ├── app.py           the web API and page routes
│   ├── pipeline/        the order of checks: input, model, tools, output (LangGraph)
│   ├── rails/           the guardrails (the checks), one small class each
│   ├── tools/           what the guard can call: read_file, customer_lookup, and others
│   ├── llm/             model providers: NVIDIA, Anthropic, Ollama, and an offline mock
│   ├── tracing/         the trace log and the Langfuse link
│   └── game/store.py    the local database: players, solves, feedback
├── web/                 THE BROWSER APP (plain HTML, CSS and JavaScript, no build step)
├── config/settings.yaml THE SETTINGS: model, prices, unlocking, server
├── docs/GUARDRAILS.md   how the checks work, in plain words
├── .claude/skills/      SKILLS for the coding assistant (Langfuse, design review)
├── tests/               automated tests
├── archive/             old material kept on this machine only (not in git)
└── data/                local runtime data (database, trace log). Git-ignored.
```

To add a challenge, copy `challenges/_TEMPLATE.yaml`. To add a check, copy one class in
`vault_heist/rails/`. To change what the guard can read, change `sandbox/`.

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
