# SAF Architecture — The North Star

This document is the authoritative source of truth for how SAF is designed
and why. It is the "north star" for all future development: every new
feature, refactor, or adapter must align with the principles described
here. If a proposed change violates these principles, either the principles
need explicit revision or the change needs to be rethought.

**Audience:** Contributors (human or LLM) extending SAF, maintainers,
adapter authors, and anyone trying to understand why SAF is structured
the way it is.

---

## 1. What is SAF?

SAF (Situation Awareness Framework) is a **deterministic controller** that
sits between a user's messages and an LLM-powered agent. It solves three
problems that plague production agent systems:

1. **Temporal drift** — the agent loses track of what time it is in the
   user's actual life, leading to responses like "good morning" at 11pm.

2. **Proactive spam** — the agent repeats the same briefing across
   restarts because it has no persistent memory of what it already said
   today.

3. **Context bloat** — flat memory retrieval dumps everything into the
   context window, slowing responses and drowning the LLM in irrelevant
   information.

SAF's solution:

- **Step 0 (Temporal Gate)** — mandatory sync with the system clock
  before every turn. The LLM never generates time; it's provided by code.
- **Domain Topologies** — memory is structured under
  `memory/domains/<name>/` and SAF routes each message to relevant
  domains via keyword matching.
- **Physical Deduplication** — a persistent JSON ledger tracks what's
  been done today. Dedup is enforced at the code level, not by LLM
  judgment.
- **Relevance Gate** — rules filter proactive actions against the user's
  current state (vacation mode, focus mode, etc.).

SAF is **framework-agnostic**. The core logic lives in `saf_core/` and
can be used with any agentic system. `saf_openclaw/` is the first
reference adapter; writing adapters for other frameworks is documented
in [`ADAPTERS.md`](ADAPTERS.md).

---

## 2. The Deterministic vs Agentic Boundary

**This is the most important concept in SAF.** Misunderstanding it leads
directly to bad design decisions.

SAF's pipeline is **100% deterministic**. Every step reads the clock, a
config file, or the ledger, and applies pure Python logic. No LLM calls.
No external services. No network I/O. The same inputs always produce the
same outputs.

The agent is **100% agentic**. It calls LLMs, reads files using its own
tools, spawns sub-agents, reasons, and generates responses.

SAF and the agent communicate through a narrow, well-defined interface:
SAF produces a `SAFContext` (metadata and instructions); the agent
consumes it and acts on it.

### Why this matters

- **Anti-hallucination.** The LLM cannot lie about time, cannot fake
  dedup state, cannot "reason around" the relevance gate. Every
  deterministic value is beyond its reach.
- **Testability.** Every SAF step is a pure function that can be unit
  tested with no mocks beyond temp files.
- **Portability.** SAF has zero LLM dependencies, so it works with any
  framework, any model, any runtime.
- **Performance.** No LLM calls in SAF means no tokens spent on routing,
  no latency added to the critical path.

### The Step Table

```
┌────┬────────────────────┬───────────────┬─────────────────────────────┐
│ #  │ Step               │ Owner         │ What it does                │
├────┼────────────────────┼───────────────┼─────────────────────────────┤
│ 0  │ TEMPORAL           │ DETERMINISTIC │ Read system clock +         │
│    │                    │   (saf_core)  │ user-state.json. Returns    │
│    │                    │               │ utc, local, phase, day_type │
├────┼────────────────────┼───────────────┼─────────────────────────────┤
│ 1  │ ACTION EVALUATION  │ DETERMINISTIC │ Filter proactive-actions    │
│    │                    │   (saf_core)  │ registry by trigger conds.  │
│    │                    │               │ Returns applicable actions  │
├────┼────────────────────┼───────────────┼─────────────────────────────┤
│ 2  │ DEDUP LOOKUP       │ DETERMINISTIC │ Read collective-ledger.json │
│    │                    │   (saf_core)  │ Returns today's actions     │
├────┼────────────────────┼───────────────┼─────────────────────────────┤
│ 3  │ RELEVANCE GATE     │ DETERMINISTIC │ Apply user-state rules      │
│    │                    │   (saf_core)  │ (mode, suppressions) +      │
│    │                    │               │ dedup. Returns blocked and  │
│    │                    │               │ available actions           │
├────┼────────────────────┼───────────────┼─────────────────────────────┤
│ 4  │ DOMAIN ROUTING     │ DETERMINISTIC │ Regex match message vs      │
│    │                    │   (saf_core)  │ router-config.json. Merge   │
│    │                    │               │ with action-sourced domains │
├────┼────────────────────┼───────────────┼─────────────────────────────┤
│    │ ═══ HANDOFF ═══    │               │                             │
├────┼────────────────────┼───────────────┼─────────────────────────────┤
│ 5  │ DOMAIN LOADING     │ AGENTIC       │ Agent reads files SAF       │
│    │                    │   (agent)     │ pointed to, using its own   │
│    │                    │               │ tools or sub-agents         │
├────┼────────────────────┼───────────────┼─────────────────────────────┤
│ 6  │ REASONING          │ AGENTIC       │ Agent's LLM processes       │
│    │                    │   (agent)     │ loaded context + user msg   │
├────┼────────────────────┼───────────────┼─────────────────────────────┤
│    │ ═══ HANDBACK ═══   │               │                             │
├────┼────────────────────┼───────────────┼─────────────────────────────┤
│ 7  │ LEDGER WRITE       │ DETERMINISTIC │ Parse agent response for    │
│    │                    │   (saf_core)  │ <saf-action/> tags, append  │
│    │                    │               │ to collective-ledger.json   │
└────┴────────────────────┴───────────────┴─────────────────────────────┘
```

Steps 0–4 and 7 run in `saf_core.pipeline`. Steps 5–6 run in the agent.
The adapter (e.g., `saf_openclaw`) is the thin glue that connects them.

---

## 3. The Pipeline (Data Flow)

The entire pipeline is exposed through two functions in
`skills/saf_core/lib/pipeline.py`:

```python
def process(message: str, host: SAFHost) -> SAFContext: ...
def record_action(action_id: str, status: str, host: SAFHost) -> None: ...
```

That's it. Two functions. One for the pre-message flow (Steps 0–4), one
for the post-message flow (Step 7).

### `process()` — the pre-message orchestrator

```
Input:
  - message: str              (the user's message text)
  - host: SAFHost             (adapter-provided workspace + logging)

Execution:
  0. Read system clock → temporal.get_temporal_context()
  1. Filter proactive-actions.json → actions.get_applicable_actions()
  2. Read ledger → ledger.get_today_actions(workspace)
  3. Apply user-state rules → relevance.check_relevance()
     + dedup partition → blocked_actions + available_actions
  4. Regex match → router.get_relevant_domains(message)
     + scan domain directories for .md files (no content reads)
  5. Build instruction strings for the agent

Output:
  SAFContext {
    temporal: { ... },               # Step 0 output
    dedup: { already_done_today },   # Step 2 output
    candidate_domains: [ ... ],      # Step 4 output
    blocked_actions: { ... },        # Step 3 output
    available_actions: [ ... ],      # Step 3 output
    agent_instructions: [ ... ],     # Derived from all of the above
  }
```

### `record_action()` — the post-message logger

```
Input:
  - action_id: str            (identifier like "morning_briefing")
  - status: str               ("sent", "skipped", etc.)
  - host: SAFHost

Execution:
  1. Open memory/shared/collective-ledger.json (atomic write via .tmp)
  2. Set actions[action_id] = { agent, timestamp, context: {status} }
  3. Rename .tmp → final path

Output: None
```

---

## 4. The `SAFContext` Schema

`SAFContext` is a frozen dataclass defined in
`skills/saf_core/lib/context.py`. It is the **only** thing SAF returns to
adapters.

```python
@dataclass(frozen=True)
class SAFContext:
    temporal: Dict[str, Any]
    dedup: Dict[str, List[str]]
    candidate_domains: List[DomainCandidate]
    blocked_actions: Dict[str, str]
    agent_instructions: List[str]
```

### Field reference

**`temporal`** — Output of `temporal.get_temporal_context()`:
```python
{
    "utc_time": "2026-04-05T10:30:00+00:00",
    "timezone": "Europe/Berlin",
    "local_time": "2026-04-05T12:30:00+02:00",
    "hour": 12,
    "day_phase": "MORNING",
    "day_of_week": "Sunday",
    "day_type": "rest_day",
    "iso_date": "2026-04-05",
}
```

**`dedup`** — Ledger state for today:
```python
{
    "already_done_today": ["morning_briefing"],
    "last_updated": "2026-04-05T10:15:00Z",
}
```

**`candidate_domains`** — List of `DomainCandidate` dataclasses:
```python
[
    DomainCandidate(
        name="work",
        path="memory/domains/work",
        files=["setup.md", "meetings.md"],
        reason='matched message: "schedule"',
    )
]
```

Note: `files` contains **filenames only**, not contents. The agent is
responsible for loading them.

**`blocked_actions`** — `{action_id: reason}` dict of actions the agent
must not execute. Possible reason values:
- `"already_done_daily"` — action already executed today (ledger dedup)
- `"already_done_weekly"` — action already executed this ISO week
- `"already_done_today"` — ad-hoc action found in today's ledger
- `"blocked_by_mode:<mode>"` — action's `skip_modes` includes the
  current user mode (e.g., `"blocked_by_mode:vacation"`)
- `"suppressed_by_user"` — action ID listed in `suppressed_actions`
  in user-state.json

```python
{
    "morning_briefing": "blocked_by_mode:vacation",
    "weekly_review": "already_done_weekly",
}
```

**`agent_instructions`** — Human-readable strings the adapter renders
into its briefing format. These are the "imperative mood" instructions
the agent should follow:
```python
[
    "Load the relevant domain files (work) using your file tools before responding.",
    "For large domains, consider spawning a sub-agent to explore and summarize.",
    'If you execute a proactive action, tag it in your response: <saf-action id="<action_id>" status="sent"/>',
]
```

### What is NOT in SAFContext

- File contents (the agent loads them)
- LLM responses (SAF never calls LLMs)
- Tool definitions (not SAF's concern)
- User preferences beyond what user-state.json already captures
- Sub-agent definitions

---

## 5. Integration Model (How an Agent Talks to SAF)

SAF has **no runtime of its own**. It is a library. The adapter is
responsible for calling SAF at the right lifecycle events.

### The Three Lifecycle Events

```
┌─────────────────────────────────────────────────────────────────────┐
│                       AGENT SESSION LIFECYCLE                       │
│                                                                     │
│  ┌─────────────────────┐                                            │
│  │ 1. SESSION START    │                                            │
│  │    agent:bootstrap  │─→ adapter.on_bootstrap()                   │
│  └─────────────────────┘      → pipeline.process("", host)          │
│                               → write SAF_BRIEFING.md               │
│                               → add to bootstrapFiles               │
│  ┌─────────────────────┐                                            │
│  │ 2. USER MESSAGE     │                                            │
│  │    message:received │─→ adapter.on_pre_message(msg)              │
│  └─────────────────────┘      → pipeline.process(msg, host)         │
│                               → overwrite SAF_BRIEFING.md           │
│                                                                     │
│  ┌─────────────────────┐                                            │
│  │ 3. LLM RESPONDS     │                                            │
│  │    (agent runtime)  │─→ [SAF not involved]                       │
│  └─────────────────────┘   Agent reads briefing, loads files,       │
│                            calls LLM, generates response            │
│                                                                     │
│  ┌─────────────────────┐                                            │
│  │ 4. BEFORE DELIVERY  │                                            │
│  │    message:pre-send │─→ adapter.on_post_message(response)        │
│  └─────────────────────┘      → parse <saf-action/> tags            │
│                               → pipeline.record_action() for each   │
└─────────────────────────────────────────────────────────────────────┘
```

### Per-Turn Sequence Diagram

```
User              Agent            Adapter           saf_core.pipeline    Filesystem
 │                  │                 │                     │                 │
 │  "schedule?"     │                 │                     │                 │
 ├─────────────────>│                 │                     │                 │
 │                  │                 │                     │                 │
 │                  │ message:received│                     │                 │
 │                  ├────────────────>│                     │                 │
 │                  │                 │ process(msg, host)  │                 │
 │                  │                 ├────────────────────>│                 │
 │                  │                 │                     │ read clock      │
 │                  │                 │                     │ read ledger     │
 │                  │                 │                     ├────────────────>│
 │                  │                 │                     │<────────────────┤
 │                  │                 │                     │ match keywords  │
 │                  │                 │                     │ scan domains    │
 │                  │                 │                     ├────────────────>│
 │                  │                 │                     │<────────────────┤
 │                  │                 │   SAFContext        │                 │
 │                  │                 │<────────────────────┤                 │
 │                  │                 │                     │                 │
 │                  │                 │ write SAF_BRIEFING.md                 │
 │                  │                 ├──────────────────────────────────────>│
 │                  │                 │                                       │
 │                  │<────────────────┤ (bootstrapFiles now contains briefing)│
 │                  │                                                         │
 │                  │ Reads SAF_BRIEFING.md at prompt assembly                │
 │                  │<────────────────────────────────────────────────────────┤
 │                  │ Reads memory/domains/work/*.md using its own tools      │
 │                  │<────────────────────────────────────────────────────────┤
 │                  │                                                         │
 │                  │ [LLM call: user msg + briefing + domain files]          │
 │                  │                                                         │
 │                  │ LLM response: "Your 9am... <saf-action id='work_ctx'/>" │
 │                  │                                                         │
 │                  │ message:pre-send                                        │
 │                  ├────────────────>│                                       │
 │                  │                 │ on_post_message(response)             │
 │                  │                 │   parses <saf-action/> tags           │
 │                  │                 │   record_action("work_ctx", "sent")   │
 │                  │                 ├──────────────────────────────────────>│
 │                  │                 │                  write ledger         │
 │                  │                 │<──────────────────────────────────────┤
 │                  │<────────────────┤                                       │
 │                  │                                                         │
 │  "Your 9am..."   │                                                         │
 │<─────────────────┤                                                         │
```

---

## 6. File Layout

```
<workspace_root>/
├── memory/
│   ├── shared/                              # SAF-owned state
│   │   ├── user-state.json                  # timezone, phases, work days
│   │   ├── router-config.json               # domain keyword mappings
│   │   ├── collective-ledger.json           # dedup ledger (auto-maintained)
│   │   └── runtime/
│   │       └── SAF_BRIEFING.md              # regenerated per turn
│   │
│   └── domains/                             # USER-owned content
│       ├── work/
│       │   ├── setup.md
│       │   └── meetings.md
│       ├── family/
│       │   └── ...
│       └── (whatever domains saf-init created)
│
└── skills/
    ├── saf_core/                            # Framework-agnostic library
    │   └── lib/
    │       ├── pipeline.py
    │       ├── context.py
    │       ├── host.py
    │       ├── adapter.py
    │       ├── temporal.py
    │       ├── router.py
    │       ├── ledger.py
    │       ├── relevance.py
    │       └── domains.py
    │
    └── saf_openclaw/                        # OpenClaw reference adapter
        ├── SKILL.md
        ├── adapter.py
        ├── renderer.py
        ├── install.py
        └── hooks/
            ├── saf-bootstrap/
            ├── saf-pre-message/
            └── saf-post-message/
```

### Ownership rules

- **`memory/shared/*.json`** — owned by SAF. Adapters and user tools may
  read but should not write directly. Use `pipeline.record_action()` for
  ledger updates.
- **`memory/shared/runtime/SAF_BRIEFING.md`** — owned by the adapter.
  Regenerated on every turn. Do not edit.
- **`memory/domains/**/*.md`** — owned by the user (and, eventually, by
  Issue #21 knowledge-compilation features). SAF reads filenames only.
- **`skills/saf_core/`** — owned by the SAF project. Framework-agnostic.
  No LLM imports, no framework imports.
- **`skills/saf_*/`** (adapters) — owned by adapter authors. Each adapter
  lives in its own package.

---

## 7. OpenClaw Reference Integration

The `saf_openclaw` adapter implements the `SAFAdapter` protocol and wires
SAF into OpenClaw's native hook system. It serves as the canonical
example for writing new adapters.

### Components

- **`adapter.py`** — `OpenClawAdapter` class with four methods matching
  the protocol, plus OpenClaw-specific helpers (`write_briefing`,
  `briefing_path`).
- **`renderer.py`** — Converts `SAFContext` into a markdown briefing
  with 6 sections (temporal, domains, already-done, pending, blocked,
  instructions).
- **`hooks/saf-bootstrap/`** — Fires on `agent:bootstrap`. Writes the
  initial briefing and mutates `event.context.bootstrapFiles`.
- **`hooks/saf-pre-message/`** — Fires on `message:received`. Refreshes
  the briefing with per-turn routing.
- **`hooks/saf-post-message/`** — Fires on `message:pre-send`. Parses
  action tags and records them to the ledger.
- **`install.py`** — Copies hooks to `~/.openclaw/hooks/` and optionally
  runs `saf-init` if the workspace doesn't exist.

### Why `bootstrapFiles`?

OpenClaw injects a set of markdown files into every system prompt
(`AGENTS.md`, `SOUL.md`, `HEARTBEAT.md`, etc.). The `agent:bootstrap`
hook can mutate `context.bootstrapFiles` to add more paths. This is the
only documented mechanism for getting content into an OpenClaw LLM's
prompt, so SAF uses it.

The alternative (hypothetical mid-turn prompt injection) is not yet
supported by OpenClaw; GitHub issue [#11618](https://github.com/openclaw/openclaw/issues/11618)
requests it. If it lands, a future version of the adapter could inject
fresher context per turn. For now, the briefing is rewritten on every
`message:received` and OpenClaw re-reads bootstrap files on each LLM
call, which achieves the same effect.

---

## 8. Self-Improvement Engine

SAF includes a **Self-Improvement Engine** that enables the agent to
audit and improve its own domain memory and configuration. This merges
two concerns: behavioral regressions (learning from past mistakes) and
knowledge maintenance (staleness, contradictions, indexing).

### Architecture

The engine follows SAF's core principle: **deterministic where possible,
agentic only where necessary.**

- `saf_core/lib/self_review.py` builds the review context, validates
  configs, and manages snapshots — all deterministic, no LLM calls.
- The **agent** reads the review protocol, identifies issues, writes
  fixes using its own tools, and runs validation to verify its changes.
- SAF provides a **snapshot/restore** safety net for config files.

### Two Triggering Mechanisms

**Proactive action (per-conversation, lightweight):**
- `knowledge_audit` action registered in `proactive-actions.json`
- Triggers weekly (Mondays by default)
- Limited to domain files and `_index.md` — cannot modify config files
- Agent reads protocol from `memory/domains/_system/`

**Cron/scheduled (headless, full):**
- `python3 -m skills.saf_core.self_review_cli --workspace /path --runner openclaw`
- Full audit: staleness, contradictions, gaps, regressions, indexes
- Can modify config files (with snapshot protection)
- Uses `SelfReviewRunner` adapter protocol — agent-agnostic

### Validation Layer

`validate_workspace()` checks config file integrity:
- `proactive-actions.json`: required fields, valid frequencies, trigger schema
- `user-state.json`: valid timezone, work_days, phases, mode
- `router-config.json`: valid domain → keyword mappings

Exposed as an agent-callable CLI:
```
python3 -m skills.saf_core.validate --workspace /path
# Exits 0 if valid, 1 if errors. JSON output to stdout.
```

### Snapshot Safety Net

Before a full review, `snapshot_configs()` backs up all config files to
`memory/domains/_system/.snapshot/`. If the agent breaks configs (fails
validation), `restore_snapshot()` rolls back. If the agent session
crashes, the next review detects the stale snapshot and restores it.

### The `_system` Domain

```
memory/domains/_system/
    review-queue.md           — items needing user input
    last-review-summary.md    — agent's summary of last review
    .snapshot/                — config backups (transient)
```

The `_` prefix means the pipeline's domain routing skips it. It is
invisible to normal conversations.

---

## 9. Extending SAF

### Writing a new adapter

See [`ADAPTERS.md`](ADAPTERS.md) for the full tutorial. In summary:

1. Create a new package `skills/saf_<framework>/`
2. Implement `SAFHost` (workspace path, logging)
3. Implement `SAFAdapter` (lifecycle methods + renderer)
4. Write tests using a stub host
5. Document in a `README.md` or `SKILL.md`

### Adding a new pipeline step

If you need to add logic that SAF should run deterministically before
the agent sees a message:

1. Create a new module in `skills/saf_core/lib/` (e.g., `regressions.py`)
2. Add a function called by `pipeline.process()` between existing steps
3. Add a field to `SAFContext` if the step produces new output
4. Update the renderer in each adapter to surface the new field
5. Add tests covering the new step in isolation and as part of the pipeline

### Modifying `SAFContext`

`SAFContext` is a stable contract. Adding fields is OK (adapters that
don't use them simply ignore them). Removing or renaming fields is a
breaking change and requires a major version bump of the adapter
protocol.

---

## 10. Non-Goals

SAF is explicitly **not**:

- **An agent framework.** SAF does not orchestrate LLM calls, manage
  conversations, handle tool use, or define personas. Use OpenClaw,
  LangChain, AutoGPT, or your own framework for that.

- **A prompt-engineering library.** SAF does not generate or optimize
  prompts. The briefing markdown is the only "prompt" SAF produces, and
  it's pure metadata, not instructions to the LLM about how to think.

- **A RAG system.** SAF does not chunk documents, embed text, or
  retrieve by vector similarity. Domain routing is keyword-based and
  returns paths; the agent handles loading and any further retrieval.

- **A vector database.** No embeddings. No semantic search. No
  similarity scores. SAF's routing is deterministic regex matching.

- **A tool-calling router.** SAF does not decide which tools an agent
  should call. It only decides which memory domains are relevant.

- **An LLM wrapper.** SAF never calls an LLM. Every line of code in
  `saf_core/` runs without network access or external services.

- **A replacement for the agent's memory.** SAF augments the agent's
  existing memory with temporal awareness, dedup, and domain routing.
  It does not store conversation history, user preferences beyond
  config, or long-term knowledge.

If you find yourself wanting SAF to do any of the above, you're
probably looking for a different layer of the stack.

---

## Version History

- **v1** (issue #5) — Initial pipeline + protocols + OpenClaw adapter

Future versions will be recorded here with the issue number that
delivered them and a one-line summary.
