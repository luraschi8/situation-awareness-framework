---
name: saf-bootstrap
description: >
  Writes the initial SAF briefing file and registers it in bootstrapFiles
  so the agent always starts a session with current temporal context,
  ledger state, and instructions. Fires on agent:bootstrap.
event: agent:bootstrap
handler: handler.py
---

# saf-bootstrap

Fires on `agent:bootstrap`. Runs `OpenClawAdapter.on_bootstrap()` to build
an initial SAFContext (with empty message — no keyword routing yet),
renders it as a markdown briefing, writes it to
`memory/shared/runtime/SAF_BRIEFING.md`, and appends the path to
`event.context.bootstrapFiles` so OpenClaw includes it in the system prompt.

The briefing contains:
- Current timezone, day phase, day type
- Already-done-today actions (from ledger)
- Blocked actions (dedup rules)
- Instructions for the agent (how to tag executed actions)

It does **not** contain domain routing yet (no message to route against).
That happens in `saf-pre-message` on each incoming message.
