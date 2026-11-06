# Poisoned Ticket: guardrails

File: `guardrails.yaml`. Each check here is listed by name, with its label and its one-line explanation.

## What to notice

- No guardrail sits in front of this challenge. The ticket text is returned by a tool, and the guard treats it as instructions.
- Whether the guard follows the note is decided by its prompt, not by a check.
