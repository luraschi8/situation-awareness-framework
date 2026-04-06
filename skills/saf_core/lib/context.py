"""Data structures returned by saf_core.pipeline."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class ProactiveAction:
    """A proactive action the agent could execute right now.

    Built from the proactive-actions.json registry, filtered by trigger
    conditions in the current temporal context.
    """

    id: str
    description: str
    domains: List[str] = field(default_factory=list)
    frequency: str = "daily"
    requires_trigger: str = ""


@dataclass(frozen=True)
class DomainCandidate:
    """A domain SAF identified as relevant for the current turn.

    Contains paths and filenames only — never file contents. The agent is
    responsible for reading the actual files using its own tools.
    """
    name: str
    path: str
    files: List[str]
    reason: str


@dataclass(frozen=True)
class SAFContext:
    """Output of pipeline.process(). Metadata and instructions only.

    This is what SAF hands back to the adapter. The adapter renders it
    into the framework's native context-injection format (for OpenClaw:
    a markdown briefing file; for other frameworks: whatever works).

    Frozen so that downstream code cannot mutate pipeline output.
    """
    temporal: Dict[str, Any]
    dedup: Dict[str, List[str]]
    candidate_domains: List[DomainCandidate] = field(default_factory=list)
    blocked_actions: Dict[str, str] = field(default_factory=dict)
    available_actions: List[ProactiveAction] = field(default_factory=list)
    agent_instructions: List[str] = field(default_factory=list)
