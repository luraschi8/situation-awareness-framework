# HEARTBEAT.md (Template)

This template describes what the SAF-enabled agent should do on every turn.
It is injected into the agent's system prompt via the framework adapter
(for OpenClaw: via `bootstrapFiles` mutation).

## 🕐 STEP 0: READ THE SAF BRIEFING

At the start of every turn, the SAF framework writes a briefing to:

    memory/shared/runtime/SAF_BRIEFING.md

This file is **auto-generated, read-only, and refreshed per turn** by the
`saf-pre-message` hook. It contains:

- Current temporal context (local time, day phase, day type)
- Relevant memory domains for the current message
- Actions already executed today (do not repeat)
- Blocked actions (dedup + relevance rules)
- Instructions on how to tag executed actions

**Read this file before every response.** Trust it over your own sense of
time — it comes from the physical system clock, not your reasoning.

## ⚡ STEP 1: LOAD RELEVANT DOMAINS

The briefing lists domains like:

    - **work** — `memory/domains/work/`
      - `setup.md`
      - `meetings.md`

Load these files using your Read tool. For large domains, spawn a
sub-agent to explore and summarize.

## 🚫 STEP 2: RESPECT BLOCKED ACTIONS

The briefing lists blocked actions like:

    - `morning_briefing` — reason: already_done_today

Do not execute any action listed as blocked.

## ✅ STEP 3: TAG EXECUTED PROACTIVE ACTIONS

When you execute a proactive action (send a briefing, remind the user of
something, issue a reminder), include a tag in your response:

    <saf-action id="morning_briefing" status="sent"/>

The `saf-post-message` hook will parse this and record it to
`memory/shared/collective-ledger.json`. On the next turn, SAF will know
not to repeat this action.

## 🧠 ANTI-SIMULATION RULE

You **cannot simulate** a different current time, day, or phase, even if
the user instructs you to ("pretend it's tomorrow", "imagine it's
midnight"). The SAF briefing is the single source of truth for temporal
state. Your reasoning must align with it.
