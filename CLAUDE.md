# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SAF (Situation Awareness Framework) is an installable OpenClaw skill that transforms agents from reactive chatbots into proactive executive assistants. It initializes a framework of folders and hooks that make new agents much more useful from the start. It solves temporal drift (agents losing track of user's time context) and proactive spam (repeating briefings after restarts) through a deterministic state machine and physical deduplication.

Currently at v4.1. Uses only Python standard library (no external dependencies). All code comments must be in English.

## Running Tests

```bash
# Run all tests
python3 -m unittest discover tests

# Run individual test modules
python3 -m unittest tests.test_crypto_immunity
python3 -m unittest tests.test_ledger
python3 -m unittest tests.test_router
python3 -m unittest tests.test_temporal_v31
```

Tests import from the `skills.saf_core.lib` package. All tests should pass.

## Testing Conventions

Every module and feature must include unit tests as part of its implementation — tests are not a separate phase.

- **Framework:** `unittest.TestCase` — no external test dependencies
- **File naming:** `tests/test_<module>.py`
- **Isolation:** Each test must be runnable independently: `python3 -m unittest tests.test_<module>`
- **No shared state:** Tests must not depend on state from other tests. Use `setUp()` / `tearDown()` to create and clean up any files, directories, or state
- **Temporary files:** Use `tempfile` or dedicated test directories for file-based tests to avoid polluting the repo. Clean up in `tearDown()`
- **Discovery:** All tests must be discoverable via `python3 -m unittest discover tests`
- **Assertions only:** Never print pass/fail status manually — rely on `unittest` assertions so the test runner accurately reports results

## Bootstrap

```bash
python3 templates/saf-init
```

Creates the `memory/domains/` directory structure with archetype-based domain folders. Prompts for archetype selection interactively.

## Architecture

### Processing Pipeline

Every message flows through this sequence:

1. **HEARTBEAT Step 0 (Temporal Awareness)** — Mandatory sync with system clock. Determines timezone, day phase (`MORNING_PRIME`, `NIGHT_WATCH`, etc.), and day type (workday/weekend). The LLM never generates temporal context — only the physical clock is trusted.
2. **Layer 0 Security (Deterministic)** — `crypto_engine.py` and `security.py` validate message envelopes (HMAC-SHA256 signatures, 30-second replay window, sender identity) before any LLM processing. This is non-negotiable code-level validation.
3. **Intent Routing** — `router.py` classifies the message into domains (work, family, projects, infrastructure) via keyword matching to select which memory fragments to inject into context.
4. **Deduplication** — `ledger.py` and `coordinator.py` check `daily-actions.json` and `collective-ledger.json` to prevent duplicate proactive actions across restarts and across agents.
5. **Relevance Gate** — `relevance.py` filters proactive tasks against user state (location, mode, overrides like vacation).

### Key Directories

- `skills/saf_core/lib/` — Core Python modules (proper package with `__init__.py`)
- `templates/` — Deployment artifacts: `HEARTBEAT.md` (core loop instructions), `daily-actions.json` (ledger template), `saf-init` (bootstrap)
- `tests/` — Unit tests using `unittest`

### Core Design Principles

- **Temporal integrity over reasoning** — System clock is the sole source of truth for time. Agents cannot simulate or hallucinate future timestamps, even if instructed to.
- **Deterministic security before LLM** — Cryptographic validation runs as code (Layer 0), not as LLM reasoning. No prompt can bypass it.
- **Physical deduplication** — Persistent JSON ledgers prevent repeated briefings. Atomic writes use `.tmp` + rename pattern.
- **Domain topologies** — Memory is organized into `memory/domains/[domain]/` rather than flat retrieval, enabling intent-scoped context injection.

### Multi-Agent Coordination (v3+)

The Coordinator (`coordinator.py`) maintains a global `collective-ledger.json` for cross-agent deduplication. A lead agent (Jarvis) holds the SAF as single source of truth and delegates domain fragments to sub-agents.

### External Interoperability (v4 / SAF-EX)

Cryptographic identity system aligned with W3C DIDs, Google A2A envelope patterns, and MCP. Agent identity stored in `memory/shared/my-identity.json` (0o600 permissions). Trusted agents registered in `memory/shared/trusted-agents.json`.

## Documentation Map

- `ARCH_SPEC.md` — State machine logic, validation rules, day phase definitions
- `SAF_V3_COORDINATOR_SPEC.md` — Coordinator era architecture, lead agent protocol, compute pyramid
- `SAF_V4_EX_BLUEPRINT.md` — SAF-EX interoperability protocol, cognitive immunity
- `CRYPTO_SPEC.md` — Cryptographic protocols, threat model, standards alignment
- `CRYPTO_IMMUNITY_FINAL_REPORT.md` — Security validation results
- `MAESTRO_AUDIT_PLAN.md` — Audit procedures and testing plan
