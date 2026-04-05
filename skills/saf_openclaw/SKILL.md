---
name: saf
description: >
  Situation Awareness Framework (SAF) — a deterministic controller that
  gives OpenClaw agents temporal awareness, domain-scoped context injection,
  cross-session deduplication, and relevance filtering. SAF runs a
  code-level pipeline before every message (no LLM calls) and injects a
  markdown briefing into the agent's bootstrap files so the LLM always
  knows what time it is, which memory domains are relevant, and which
  proactive actions have already been completed today.
metadata:
  openclaw:
    emoji: "🕐"
    requires:
      bins: ["python3"]
    os: ["darwin", "linux"]
    homepage: "https://github.com/luraschi8/agent-situation-awareness-framework"
---

# SAF — Situation Awareness Framework

SAF transforms an OpenClaw agent from a reactive chatbot into a proactive
executive assistant by adding five architectural layers:

1. **Temporal Awareness** — mandatory sync with the system clock before
   every message. Resolves timezone, day phase (MORNING/AFTERNOON/EVENING/
   NIGHT/NIGHT_LATE), day type (workday/rest_day). Configurable per user.

2. **Domain Topologies** — memory is organized under `memory/domains/<name>/`
   rather than flat. SAF routes each message to the relevant domains via
   keyword matching and tells the agent which files to load.

3. **Physical Deduplication** — a persistent ledger (`collective-ledger.json`)
   tracks which proactive actions have been executed today, preventing
   the agent from re-sending the same briefing across restarts.

4. **Relevance Gate** — user-state rules filter proactive actions based
   on current mode (vacation, focus, etc.), location, and time of day.

5. **Cryptographic Identity** — (future) Ed25519 keys for agent-to-agent
   trust and verification.

## How SAF Integrates with OpenClaw

SAF installs as a **skill + three hooks**:

- `saf-bootstrap` hook fires on `agent:bootstrap`, writes the initial
  SAF briefing to `memory/shared/runtime/SAF_BRIEFING.md`, and mutates
  `context.bootstrapFiles` so it appears in every system prompt.

- `saf-pre-message` hook fires on `message:received`, refreshes the
  briefing with per-turn context (which domains match the current
  message, which actions are still pending).

- `saf-post-message` hook fires on `message:pre-send`, parses
  `<saf-action id="..." status="..."/>` tags from the agent's response,
  and records them to the ledger for future dedup checks.

## Installation

```bash
python3 skills/saf_openclaw/install.py
```

This:
1. Runs `saf-init` if no workspace exists (prompts for timezone,
   archetype, work days).
2. Copies the three hooks into `~/.openclaw/hooks/`.
3. Enables them via `openclaw hooks enable`.

## Configuration Files

All SAF state lives under the workspace `memory/` directory:

- `memory/shared/user-state.json` — timezone, work days, phase boundaries
- `memory/shared/router-config.json` — domain keyword mappings
- `memory/shared/collective-ledger.json` — dedup ledger (auto-maintained)
- `memory/shared/runtime/SAF_BRIEFING.md` — auto-generated per turn (do not edit)
- `memory/domains/<name>/*.md` — user domain content (SAF reads filenames only)

## The Deterministic vs Agentic Boundary

**SAF never calls an LLM.** Everything inside `saf_core.pipeline` is pure
Python: clock reads, JSON reads/writes, regex matching, rule evaluation.
The agent's LLM is responsible for:
- Loading the domain files SAF points to (using OpenClaw's Read tool)
- Reasoning over the loaded context
- Generating responses
- Deciding which proactive actions to execute

This separation ensures SAF cannot hallucinate time, cannot fake dedup
state, and cannot be "reasoned around" by the agent. See
`docs/ARCHITECTURE.md` for the full architectural north star.
