# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Plain HTML, CSS, and JavaScript modules, served as static files by the FastAPI app. No build step. The user chose this so the workshop needs no install beyond the Python project.

## Users

Workshop participants: students and meetup attendees playing together in a room, usually on their own laptops, led by a facilitator who projects the scoreboard. Some play alone. Their job is to break a guard's defenses, learn why each defense held or failed, and move through the vaults in order.

## Product Purpose

Token Vault is a CTF-style game that teaches AI guardrails, authorization, and observability by letting players attack a chatbot guard that protects a fake secret. Each vault adds one defense. Success means players both enjoy the play and leave understanding that security decisions belong in code, not in prompts.

## Positioning

Players do the attacking. The game shows the guard's live pipeline (which check passed or stopped each message) and links every turn to a trace, so the lesson is visible in the same screen where the attack happened.

## Operating Context

Run from a terminal with `uv run token-vault serve`. Players join from browsers on the same network. A host panel approves human-in-the-loop requests and resets scores. A big-screen scoreboard shows the live leaderboard. Optional Langfuse tracing is available for facilitators.

## Capabilities and Constraints

- Guard model: NVIDIA-hosted model through an OpenAI-compatible API, or Anthropic, Ollama, or an offline mock guard.
- The API key limit is 40 requests per minute, shared by the whole room; the game enforces it.
- Levels are YAML files; authorization is enforced in tool code, not prompts.
- All secrets must be fake and start with `FAKE-`.
- Undecided: none of the visual direction is decided; that belongs to new-work.

## Product Principles

- Enjoyment comes first: a player should want to try the next attack.
- Every outcome is explained: a blocked message names the defense that stopped it.
- The sandbox never touches real systems or real data.
- Facilitators can run a room without reading documentation.
