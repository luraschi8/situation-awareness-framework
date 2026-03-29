# SAF Architecture Specification (v2.1)

This document consolidates the technical findings and validation reports of the Jarvis Situation Awareness Framework.

## 1. Problem Statement
Most LLM agents operate in a temporal vacuum. RAG (Retrieval-Augmented Generation) provides historical context but fails to provide **situational context**.

## 2. Technical Architecture

### 2.1 The Heartbeat State Machine
Dividing the user's day into 6 distinct phases:
- `NIGHT_WATCH` (00:00-07:59): Silent mode.
- `MORNING_PRIME` (08:00-10:59): High-priority briefing window.
- `MIDDAY_OPS`: Active support.
- `AFTERNOON_OPS`: Accountability and follow-up.
- `EVENING_WIND`: Summary and tomorrow prep.
- `NIGHT_EXTRACT`: Maintenance only.

### 2.2 Relevance Gate (Cognitive Filtering)
Before executing any allowed action, SAF performs a dynamic relevance check:
- **Rule:** `Action.Relevance(User.CurrentLocation, User.CurrentMode)`
- **Behavior:** If an action is deemed contextually irrelevant (e.g., shopping lists during vacations), it is suppressed. If relevance is ambiguous, the agent is instructed to ask the user once.

### 2.3 Ghost State Prevention
SAF implements a **"Reality Over Tools"** protocol. If a tool (e.g., Calendar) shows a "Ghost State" (an event that should be cancelled but the API doesn't support deletion), the agent prioritizes the physical memory logs over the tool data.

## 3. Validation Report (Stress Test 2026-03-29)
- **Deduplication:** 100% success rate across 100 heartbeat cycles.
- **Temporal Sync:** Successfully handled CET -> CEST transition and cross-timezone (Madrid/NYC/Tokyo) simulations.
