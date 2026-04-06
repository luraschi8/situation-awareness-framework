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
python3 -m unittest tests.test_temporal
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

Creates the `memory/domains/` directory structure with archetype-based domain folders. Prompts for archetype selection, timezone, and work days interactively. Generates `memory/shared/router-config.json` and `memory/shared/user-state.json`.

## Architecture

### Processing Pipeline

Orchestrated by `skills/saf_core/lib/pipeline.py`. See `docs/ARCHITECTURE.md` for the full walkthrough.

**Deterministic steps (run in `saf_core.pipeline`, no LLM calls):**

0. **Temporal Gate** — `temporal.py` syncs with system clock. Resolves timezone, day phase, day type. Configured via `memory/shared/user-state.json`.
1. **Dedup Lookup** — `ledger.py::get_today_actions()` reads `memory/shared/collective-ledger.json`.
2. **Domain Routing** — `router.py::get_relevant_domains()` regex-matches message against `memory/shared/router-config.json`.
3. **Relevance Gate** — `relevance.py` + pipeline rules produce blocked_actions.

**Agentic steps (run in the agent runtime):**

4. **Domain Loading** — Agent reads the files SAF pointed to, using its own Read tool or sub-agents.
5. **Reasoning** — Agent's LLM processes loaded context + user message.

**Deterministic again:**

6. **Ledger Write** — Adapter parses `<saf-action id="..." status="..."/>` tags from response, calls `pipeline.record_action()`.

The entire framework is accessible through two functions: `pipeline.process(message, host)` and `pipeline.record_action(id, status, host)`. Framework adapters (`saf_openclaw`, future `saf_langchain`, etc.) implement the `SAFHost` and `SAFAdapter` protocols to bridge SAF into their framework's lifecycle events.

### Key Directories

- `skills/saf_core/lib/` — Framework-agnostic core. Pipeline, protocols, deterministic steps. **Never imports from any framework.**
- `skills/saf_openclaw/` — OpenClaw reference adapter. Hooks, renderer, install script.
- `templates/` — Bootstrap artifacts: `HEARTBEAT.md`, `daily-actions.json`, `saf-init`
- `docs/` — Architecture and adapter author guide
- `tests/` — Unit tests using `unittest`

### Core Design Principles

- **Temporal integrity over reasoning** — System clock is the sole source of truth for time. Agents cannot simulate or hallucinate future timestamps, even if instructed to.
- **Deterministic security before LLM** — Cryptographic validation runs as code (Layer 0), not as LLM reasoning. No prompt can bypass it.
- **Physical deduplication** — Persistent JSON ledgers prevent repeated briefings. Atomic writes use `.tmp` + rename pattern.
- **Domain topologies** — Memory is organized into `memory/domains/[domain]/` rather than flat retrieval, enabling intent-scoped context injection.

### Multi-Agent Coordination (v3+)

Cross-agent deduplication uses `collective-ledger.json` (managed by `ledger.py`). A lead agent (Jarvis) holds the SAF as single source of truth and delegates domain fragments to sub-agents. Full multi-agent coordination is tracked in #13.

### External Interoperability (v4 / SAF-EX)

Cryptographic identity system aligned with W3C DIDs, Google A2A envelope patterns, and MCP. Agent identity stored in `memory/shared/my-identity.json` (0o600 permissions). Trusted agents registered in `memory/shared/trusted-agents.json`.

## Documentation Map

**Start here:**
- `docs/ARCHITECTURE.md` — The north star. How SAF is designed and why. Deterministic vs agentic boundary, pipeline steps, integration model. **Read this first.**
- `docs/ADAPTERS.md` — How to write a SAF adapter for any agentic framework. Includes a LangChain walkthrough.

**Historical specs (kept for context, some features are future work):**
- `ARCH_SPEC.md` — Original state machine logic, validation rules, day phase definitions
- `SAF_V3_COORDINATOR_SPEC.md` — Coordinator era architecture, lead agent protocol, compute pyramid
- `SAF_V4_EX_BLUEPRINT.md` — SAF-EX interoperability protocol, cognitive immunity
- `CRYPTO_SPEC.md` — Cryptographic protocols, threat model, standards alignment
- `CRYPTO_IMMUNITY_FINAL_REPORT.md` — Security validation results
- `MAESTRO_AUDIT_PLAN.md` — Audit procedures and testing plan
