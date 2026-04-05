---
name: saf-pre-message
description: >
  Refreshes the SAF briefing with per-turn context. Fires on message:received.
  Routes the incoming message to relevant domains, re-checks the ledger for
  dedup status, and overwrites memory/shared/runtime/SAF_BRIEFING.md so the
  agent sees up-to-date instructions before it responds.
event: message:received
handler: handler.py
---

# saf-pre-message

Fires on `message:received`. Runs `OpenClawAdapter.on_pre_message(message)`
with the user's message text, which executes the full SAF pipeline:

1. **Step 0** — temporal context (clock + user-state.json)
2. **Step 1** — dedup lookup (collective-ledger.json)
3. **Step 2** — domain routing (regex match against router-config.json)
4. **Step 3** — relevance gate (apply rules)

Then renders the updated SAFContext as markdown and overwrites the
briefing file atomically (`.tmp` + rename). OpenClaw re-reads bootstrap
files before each LLM call, so the agent sees the fresh briefing.

The briefing tells the agent:
- Which domain files to load for this specific message
- Which actions are blocked (already done today)
- How to tag executed actions (`<saf-action id="..." status="..."/>`)
