"""Proactive action registry — loads and evaluates trigger conditions.

The registry (proactive-actions.json) declares actions the agent can take
and the temporal conditions under which they apply. This module filters
the registry against the current temporal context and returns a list of
ProactiveAction objects for the pipeline to present to the agent.
"""

from skills.saf_core.lib import paths
from skills.saf_core.lib.context import ProactiveAction
from skills.saf_core.lib.fs import load_json
from skills.saf_core.lib.ledger import FREQ_DAILY


def load_actions(workspace_root=None):
    """Load the proactive action registry from disk.

    Returns the raw dict. If the file does not exist, returns an empty
    registry so callers never need to handle None.
    """
    path = paths.resolve(paths.PROACTIVE_ACTIONS_FILE, workspace_root)
    return load_json(path, default={"actions": {}})


def get_applicable_actions(temporal_ctx, workspace_root=None):
    """Filter the registry to actions whose triggers match right now.

    Trigger evaluation (all conditions AND together, missing = any):
      - phase:       temporal_ctx["day_phase"] in trigger["phase"]
      - day_type:    temporal_ctx["day_type"] == trigger["day_type"]
      - day_of_week: temporal_ctx["weekday_number"] in trigger["day_of_week"]
      - requires:    passed through on the ProactiveAction (agent decides)

    Returns List[ProactiveAction] sorted by action id for determinism.
    """
    registry = load_actions(workspace_root)
    result = []

    for action_id, action_def in registry.get("actions", {}).items():
        if not action_def.get("enabled", True):
            continue

        trigger = action_def.get("trigger", {})
        if not _matches_trigger(trigger, temporal_ctx):
            continue

        result.append(ProactiveAction(
            id=action_id,
            description=action_def.get("description", ""),
            domains=action_def.get("domains", []),
            frequency=action_def.get("frequency", FREQ_DAILY),
            requires_trigger=trigger.get("requires", ""),
        ))

    result.sort(key=lambda a: a.id)
    return result


def _matches_trigger(trigger, temporal_ctx):
    """Evaluate all trigger conditions. Missing conditions always match."""
    if "phase" in trigger:
        if temporal_ctx.get("day_phase") not in trigger["phase"]:
            return False

    if "day_type" in trigger:
        if temporal_ctx.get("day_type") != trigger["day_type"]:
            return False

    if "day_of_week" in trigger:
        if temporal_ctx.get("weekday_number") not in trigger["day_of_week"]:
            return False

    return True
