# Writing a SAF Adapter

This guide walks you through building a SAF adapter for any agentic
framework. It assumes you've read [`ARCHITECTURE.md`](ARCHITECTURE.md)
and understand the deterministic/agentic boundary.

**Estimated effort:** ~100–200 lines of code for a working adapter, plus
tests.

---

## 1. What is an Adapter?

An adapter is the **thin glue** between a specific agentic framework and
SAF's framework-agnostic core. Its job is to:

1. Call `saf_core.pipeline.process()` at the right lifecycle events
2. Render the resulting `SAFContext` into the framework's native
   context-injection format (a system message, a bootstrap file, a
   callback payload, etc.)
3. Parse action tags from the agent's response
4. Call `saf_core.pipeline.record_action()` to log executed actions

The adapter **does not**:

- Call LLMs (the pipeline is deterministic; the framework handles LLMs)
- Load domain file contents (the agent does that with its own tools)
- Implement routing, dedup, or temporal logic (that's in `saf_core`)
- Modify the agent's response text (it only observes and logs)

If your adapter ends up longer than ~200 lines, you're probably doing
too much. Push logic down into `saf_core`.

---

## 2. The Two Protocols

Both are defined in `skills/saf_core/lib/`:

### `SAFHost` — what you provide to SAF

```python
from typing import Protocol

class SAFHost(Protocol):
    def workspace_root(self) -> str: ...
    def log(self, level: str, message: str) -> None: ...
```

SAF only needs to know the absolute filesystem path where `memory/`
lives, and a way to emit structured log messages. That's it. Your
`SAFHost` implementation is usually 10–20 lines.

### `SAFAdapter` — what you implement for the framework

```python
from typing import Protocol
from skills.saf_core.lib.context import SAFContext

class SAFAdapter(Protocol):
    host: SAFHost

    def on_bootstrap(self) -> SAFContext: ...
    def on_pre_message(self, message: str) -> SAFContext: ...
    def on_post_message(self, agent_response: str) -> None: ...
    def render_briefing(self, context: SAFContext) -> str: ...
```

Each method maps to a framework lifecycle event. The first two return a
`SAFContext` (adapter is expected to call `pipeline.process()` and
return the result). The third calls `pipeline.record_action()` for each
parsed tag. The fourth converts a `SAFContext` to the framework's
native format.

---

## 3. Step-by-Step: Building a LangChain Adapter (Example)

Let's walk through writing a hypothetical LangChain adapter to illustrate
the pattern. LangChain's lifecycle hooks live in its `BaseCallbackHandler`
interface.

### Step 1: Package structure

```
skills/saf_langchain/
├── __init__.py
├── adapter.py          # SAFAdapter + SAFHost implementations
├── renderer.py         # SAFContext → SystemMessage
└── callback.py         # LangChain BaseCallbackHandler bridge
```

### Step 2: Implement `SAFHost`

```python
# skills/saf_langchain/adapter.py
import os
import logging

class LangChainHost:
    def __init__(self, workspace_root: str):
        self._root = os.path.abspath(workspace_root)
        self._logger = logging.getLogger("saf.langchain")

    def workspace_root(self) -> str:
        return self._root

    def log(self, level: str, message: str) -> None:
        getattr(self._logger, level)(message)
```

Twelve lines. Done.

### Step 3: Implement the renderer

LangChain doesn't use bootstrap files; it uses `SystemMessage` objects.
So the renderer converts `SAFContext` into a string suitable for a
system message.

```python
# skills/saf_langchain/renderer.py
from skills.saf_core.lib.context import SAFContext

def render_as_system_message(ctx: SAFContext) -> str:
    parts = []
    t = ctx.temporal
    parts.append(f"Current time: {t['day_of_week']} {t['iso_date']} "
                 f"({t['day_phase']}, {t['day_type']})")

    if ctx.candidate_domains:
        parts.append("\nRelevant memory domains (load these with your "
                     "file tools):")
        for domain in ctx.candidate_domains:
            parts.append(f"  - {domain.path}/")
            for filename in domain.files:
                parts.append(f"      {filename}")

    if ctx.dedup.get("already_done_today"):
        done = ", ".join(ctx.dedup["already_done_today"])
        parts.append(f"\nAlready done today (do not repeat): {done}")

    if ctx.agent_instructions:
        parts.append("\nInstructions:")
        for i, inst in enumerate(ctx.agent_instructions, 1):
            parts.append(f"  {i}. {inst}")

    return "\n".join(parts)
```

### Step 4: Implement the adapter

```python
# skills/saf_langchain/adapter.py (continued)
from skills.saf_core.lib import pipeline
from skills.saf_core.lib.context import SAFContext
from skills.saf_langchain.renderer import render_as_system_message

ACTION_TAG_PATTERN = re.compile(
    r'<saf-action\s+id="([^"]+)"\s+status="([^"]+)"\s*/?>'
)

class LangChainAdapter:
    def __init__(self, workspace_root: str):
        self.host = LangChainHost(workspace_root)

    def on_bootstrap(self) -> SAFContext:
        return pipeline.process("", self.host)

    def on_pre_message(self, message: str) -> SAFContext:
        return pipeline.process(message, self.host)

    def on_post_message(self, agent_response: str) -> None:
        for action_id, status in ACTION_TAG_PATTERN.findall(agent_response):
            pipeline.record_action(action_id, status, self.host)

    def render_briefing(self, context: SAFContext) -> str:
        return render_as_system_message(context)
```

Thirty lines including imports.

### Step 5: Wire into LangChain

LangChain uses `BaseCallbackHandler` for lifecycle events. We need to:
1. Hook `on_chain_start` to call `on_pre_message()` and prepend the
   system message
2. Hook `on_chain_end` to call `on_post_message()`

```python
# skills/saf_langchain/callback.py
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import SystemMessage
from skills.saf_langchain.adapter import LangChainAdapter

class SAFCallbackHandler(BaseCallbackHandler):
    def __init__(self, workspace_root: str):
        self.adapter = LangChainAdapter(workspace_root)

    def on_chain_start(self, serialized, inputs, **kwargs):
        message = inputs.get("input", "")
        ctx = self.adapter.on_pre_message(message)
        briefing = self.adapter.render_briefing(ctx)
        # Inject as a system message at position 0
        if "messages" in inputs:
            inputs["messages"].insert(0, SystemMessage(content=briefing))

    def on_chain_end(self, outputs, **kwargs):
        response = outputs.get("output", "")
        self.adapter.on_post_message(response)
```

### Step 6: Use it

```python
from langchain.chains import ConversationChain
from skills.saf_langchain.callback import SAFCallbackHandler

chain = ConversationChain(
    llm=my_llm,
    callbacks=[SAFCallbackHandler(workspace_root="./my_saf_workspace")],
)

chain.run("What's on my schedule?")
```

The chain now automatically gets temporal awareness, domain routing, and
dedup on every turn.

---

## 4. Common Gotchas

### Don't call LLMs inside the adapter's pre-message path

If you add an LLM call inside `on_pre_message()`, you've defeated the
entire point of SAF's deterministic guarantees. The pipeline must stay
pure. If you want LLM-powered routing, that's a separate feature to add
to `saf_core` later (see issue #21) — not something to slip into an
adapter.

### Do parse action tags even if the response has no tags

`on_post_message()` should call `pipeline.record_action()` zero or more
times depending on how many tags are in the response. A response with
zero tags is normal — the adapter should be a graceful no-op in that
case.

### Do use atomic writes for any files you create

If your adapter writes a briefing file (as `saf_openclaw` does), use
the `.tmp` + rename pattern to avoid leaving partial files on failure:

```python
tmp = path + ".tmp"
with open(tmp, "w") as f:
    f.write(content)
os.rename(tmp, path)
```

### Don't re-implement routing, temporal, or dedup logic

If you catch yourself writing keyword-matching logic in your adapter,
stop. That belongs in `saf_core.router`. Adapters are glue, not
reimplementations. Always call `pipeline.process()` and consume its
output.

### Handle missing config gracefully

SAF core already handles missing `user-state.json` and
`router-config.json` (falls back to defaults). Your adapter should not
assume they exist. If you need to verify, use the install script pattern
from `saf_openclaw/install.py`: check `memory/domains/` and run
`saf-init` if missing.

---

## 5. Checklist for a Production-Ready Adapter

Before considering your adapter done, verify:

- [ ] Implements both `SAFHost` and `SAFAdapter` protocols
- [ ] Renders `SAFContext` into framework-native format
- [ ] Parses `<saf-action id="..." status="..."/>` tags correctly
- [ ] Calls `pipeline.record_action()` for each tag
- [ ] Handles empty messages (bootstrap case)
- [ ] Handles zero-tag responses (normal case)
- [ ] Handles missing `memory/shared/` (falls back to defaults)
- [ ] Has its own test suite using a stub host and temp workspace
- [ ] All tests are runnable in isolation via
      `python3 -m unittest tests.test_saf_<framework>`
- [ ] No LLM calls anywhere in the adapter
- [ ] No duplicated logic from `saf_core` (routing, temporal, dedup)
- [ ] Documented in the repo with a README or SKILL.md
- [ ] Install/setup instructions included

---

## 6. Reference Implementation

The canonical reference is `skills/saf_openclaw/`. Read it top to bottom
to see every piece of the contract in action. Key files:

- `adapter.py` — `OpenClawAdapter` + `OpenClawHost` implementations
- `renderer.py` — Markdown briefing generator
- `hooks/*/handler.py` — Hook entry points for each lifecycle event
- `install.py` — Installation script

Tests are in:

- `tests/test_saf_openclaw_adapter.py`
- `tests/test_saf_openclaw_renderer.py`

If you're stuck, the OpenClaw adapter probably answers your question.

---

## 7. Getting Your Adapter Merged

If you'd like your adapter to live in the main SAF repository:

1. Open an issue describing the framework you're targeting and your
   integration approach
2. Write the adapter following this guide
3. Ensure your test suite passes (`python3 -m unittest discover tests`)
4. Submit a pull request that includes:
   - The adapter package
   - The test file
   - A brief `README.md` in the adapter directory
   - Any documentation updates (e.g., mention in `ARCHITECTURE.md` §7)

Adapters for popular frameworks (LangChain, AutoGen, LlamaIndex,
Semantic Kernel, etc.) are especially welcome.
