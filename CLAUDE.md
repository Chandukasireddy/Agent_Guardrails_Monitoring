# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

The repository contains only `README.md` and no code yet. There is no build, lint, or test tooling, and no package manifests, so there are no commands to run. Do not invent them. When the scaffold is added, update this section with the real commands.

## Project intent

This is a Sunday-workshop template: a CTF-style game called "Vault Heist" where participants try to get fake secrets out of an LLM guard, and each level adds one guardrail. The README is the source of truth for the level list, the attack and defense cards, and the scoring rules.

The planned architecture, as described in `README.md` and not yet built:

- **Guard pipeline (LangGraph):** input rails, then the guard agent, then tool gates and authorization, then output rails. Authorization is deterministic code in `backend/vault/`. The model never holds a real secret.
- **Guardrails (NVIDIA NeMo Guardrails):** input, output, dialog, and tool rails written in Colang under `guardrails/`.
- **Multi-agent crews (CrewAI):** an attacker crew for red-team mode and a buyer and seller crew for the optional negotiation module, under `backend/crews/`. These stay separate from the core LangGraph pipeline.
- **Observability (Langfuse, self-hosted via Docker):** every turn is traced, and each rail decision is a span.
- **Front end (Next.js, TypeScript, Tailwind, shadcn/ui):** game UI with a React Flow pipeline view, under `web/`.
- **Backend (FastAPI, Python):** streams replies to the front end, under `backend/`.

## Constraints to keep in mind

- All secrets in the vault are fake and labeled as fake. The shell challenge is simulated and must never run real commands.
- The participant-facing sandbox must not reach real systems or real personal data.
- Keep the guard's security decisions in code, not in prompts. A system prompt is not a security boundary, and the levels exist to show why.
- The git remote is the public repo `Chandukasireddy/Agent_Guardrails_Monitoring`. Do not push changes without the user asking.
