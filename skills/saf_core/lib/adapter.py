"""SAFAdapter protocol — the lifecycle contract for framework adapters."""

from typing import Protocol

from skills.saf_core.lib.context import SAFContext
from skills.saf_core.lib.host import SAFHost


class SAFAdapter(Protocol):
    """Contract documenting how framework adapters integrate SAF.

    An adapter's responsibilities:
      1. Call pipeline.process() on pre-message lifecycle events
      2. Render SAFContext into the framework's context-injection format
      3. Parse action markers from the agent's response
      4. Call pipeline.record_action() on post-message lifecycle events

    Adapters are thin glue. The deterministic logic lives in saf_core.pipeline;
    the adapter only translates between framework-specific events and the
    pipeline's function calls.
    """

    host: SAFHost

    def on_bootstrap(self) -> SAFContext:
        """Called at agent session start. Runs the pipeline with empty message.

        Used to give the agent a baseline briefing (temporal context, pending
        actions) before any user input arrives.
        """
        ...

    def on_pre_message(self, message: str) -> SAFContext:
        """Called when a user message arrives, before the LLM processes it.

        Runs the full pipeline (Steps 0-3) and returns the SAFContext that
        the adapter should render and inject into the agent's context.
        """
        ...

    def on_post_message(self, agent_response: str) -> None:
        """Called after the agent's LLM generates a response.

        Parses action markers (e.g., <saf-action id="..." status="..."/>)
        from the response and writes them to the ledger via
        pipeline.record_action().
        """
        ...

    def render_briefing(self, context: SAFContext) -> str:
        """Renders a SAFContext as a framework-native briefing.

        For OpenClaw this is a markdown bootstrap file. For LangChain it
        would be a SystemMessage. The format is adapter-specific but the
        content is always derived from the SAFContext.
        """
        ...
