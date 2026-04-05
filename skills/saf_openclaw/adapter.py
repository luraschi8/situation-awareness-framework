"""OpenClaw reference adapter implementing the SAFAdapter protocol.

Wires saf_core.pipeline into OpenClaw's hook lifecycle:
  - agent:bootstrap → on_bootstrap() → write initial briefing
  - message:received → on_pre_message() → refresh briefing
  - message:pre-send → on_post_message() → parse action tags, record to ledger
"""

import os
import re

from skills.saf_core.lib import paths, pipeline
from skills.saf_core.lib.context import SAFContext
from skills.saf_core.lib.fs import atomic_write
from skills.saf_openclaw.renderer import render_briefing

ACTION_TAG_PATTERN = re.compile(
    r'<saf-action\s+id="([^"]+)"\s+status="([^"]+)"\s*/?>'
)


class OpenClawHost:
    """Implements SAFHost for OpenClaw.

    Resolves the workspace root from the OPENCLAW_WORKSPACE environment
    variable at construction time, falling back to the current working
    directory.
    """

    def __init__(self, workspace_root=None):
        self._root = workspace_root or os.environ.get(
            "OPENCLAW_WORKSPACE", os.getcwd()
        )

    def workspace_root(self) -> str:
        return self._root

    def log(self, level: str, message: str) -> None:
        # OpenClaw hooks emit logs via stdout; the hook runner scopes them
        print(f"[saf-openclaw:{level}] {message}")


class OpenClawAdapter:
    """OpenClaw implementation of the SAFAdapter protocol."""

    def __init__(self, host=None):
        self.host = host or OpenClawHost()

    def on_bootstrap(self) -> SAFContext:
        return pipeline.process("", self.host)

    def on_pre_message(self, message: str) -> SAFContext:
        return pipeline.process(message, self.host)

    def on_post_message(self, agent_response: str) -> None:
        for action_id, status in _parse_action_tags(agent_response):
            pipeline.record_action(action_id, status, self.host)

    def render_briefing(self, context: SAFContext) -> str:
        return render_briefing(context)

    def briefing_path(self) -> str:
        return paths.resolve(paths.BRIEFING_FILE, self.host.workspace_root())

    def write_briefing(self, context: SAFContext) -> str:
        path = self.briefing_path()
        atomic_write(path, self.render_briefing(context))
        return path


def _parse_action_tags(text: str):
    """Extracts (action_id, status) pairs from <saf-action/> tags in text."""
    return ACTION_TAG_PATTERN.findall(text)
