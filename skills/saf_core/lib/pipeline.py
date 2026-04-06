"""The SAF pipeline — stateless orchestration of deterministic steps.

This is the single entry point for framework adapters. It chains the
existing SAF modules (temporal, router, ledger) into a typed sequence
and returns a SAFContext.

Architectural guarantees enforced by this module:
  - NEVER calls an LLM
  - NEVER reads domain file contents (only lists filenames)
  - NEVER mutates state except through explicit record_action() calls
  - Stateless: same inputs + same workspace state = same output
"""

import os
from typing import List

from skills.saf_core.lib import actions, ledger, paths, router, temporal
from skills.saf_core.lib.context import DomainCandidate, ProactiveAction, SAFContext
from skills.saf_core.lib.host import SAFHost

SAF_AGENT_ID = "saf"


def process(message: str, host: SAFHost) -> SAFContext:
    """Runs Steps 0-4 of the SAF pipeline and returns the full SAFContext.

    Steps:
      0. Temporal context (system clock + user-state.json)
      1. Action evaluation (filter registry by trigger conditions)
      2. Dedup lookup (frequency-aware, read collective-ledger.json)
      3. Domain routing (merge message-matched + action-sourced domains)
      4. Relevance gate (compute blocked + available actions)

    Returns a SAFContext the adapter renders for the agent.
    """
    workspace = host.workspace_root()

    # Step 0: temporal
    temporal_ctx = temporal.get_temporal_context()
    today_iso = temporal_ctx["iso_date"]

    # Step 1: action evaluation — which registry actions apply right now?
    applicable = actions.get_applicable_actions(temporal_ctx, workspace)

    # Step 2: dedup lookup — single ledger read shared across all checks
    ledger_data = ledger._load_ledger(workspace)
    dedup = ledger.get_today_actions(
        workspace_root=workspace,
        today_iso=today_iso,
    )

    # Step 3: partition applicable actions into available vs blocked
    available: List[ProactiveAction] = []
    blocked: dict = {}

    for action in applicable:
        if ledger.is_action_done(action.id, action.frequency,
                                 today_iso=today_iso, _ledger=ledger_data):
            blocked[action.id] = f"already_done_{action.frequency}"
        else:
            available.append(action)

    # Also block anything in today's ledger not already covered (ad-hoc actions)
    for action_id in dedup.get("already_done_today", []):
        if action_id not in blocked:
            blocked[action_id] = "already_done_today"

    # Step 4: domain routing — union message-matched + action-sourced domains
    message_domains = router.get_relevant_domains(message)
    action_domains = [d for a in available for d in a.domains]
    all_domain_names = list(dict.fromkeys(message_domains + action_domains))

    candidate_domains = _resolve_domain_files(
        all_domain_names, message, workspace, host,
    )

    instructions = _build_instructions(candidate_domains, blocked, available)

    return SAFContext(
        temporal=temporal_ctx,
        dedup=dedup,
        candidate_domains=candidate_domains,
        blocked_actions=blocked,
        available_actions=available,
        agent_instructions=instructions,
    )


def record_action(action_id: str, status: str, host: SAFHost,
                   origin: str = None) -> None:
    """Step 6: persist an executed action to the ledger."""
    ledger.sync_action(
        agent_id=SAF_AGENT_ID,
        action_id=action_id,
        context={"status": status},
        workspace_root=host.workspace_root(),
        origin=origin,
    )


def _resolve_domain_files(
    domain_names: List[str],
    message: str,
    workspace_root: str,
    host: SAFHost,
) -> List[DomainCandidate]:
    """Converts domain names into DomainCandidate records with file listings.

    Reads directory listings only — never file contents. Domains whose
    directories don't exist are skipped with a debug log.
    """
    candidates: List[DomainCandidate] = []
    for name in domain_names:
        if name == router.GENERAL_DOMAIN:
            continue
        domain_path = paths.domain_path(name, workspace_root)
        if not os.path.isdir(domain_path):
            host.log("debug", f"domain directory not found: {domain_path}")
            continue
        files = sorted(
            f for f in os.listdir(domain_path)
            if f.endswith(".md") and not f.startswith("_")
        )
        candidates.append(
            DomainCandidate(
                name=name,
                path=paths.resolve(os.path.join(paths.DOMAINS_DIR, name)),
                files=files,
                reason=f"matched message: {_describe_match(message)}",
            )
        )
    return candidates


def _describe_match(message: str) -> str:
    """Produces a short description of why a domain matched."""
    snippet = message.strip()[:60]
    if len(message) > 60:
        snippet += "..."
    return f'"{snippet}"' if snippet else "(empty message)"


def _build_instructions(
    candidates: List[DomainCandidate],
    blocked: dict,
    available: List[ProactiveAction],
) -> List[str]:
    """Composes human-readable instructions for the agent."""
    instructions: List[str] = []

    if candidates:
        domain_list = ", ".join(c.name for c in candidates)
        instructions.append(
            f"Load the relevant domain files ({domain_list}) using your file tools before responding."
        )
        instructions.append(
            "For large domains, consider spawning a sub-agent to explore and summarize."
        )
    else:
        instructions.append(
            "No specific domains matched this message — rely on general conversational context."
        )

    if available:
        action_list = ", ".join(a.id for a in available)
        instructions.append(
            f"Available proactive actions you may execute: {action_list}."
        )

    if blocked:
        blocked_list = ", ".join(blocked.keys())
        instructions.append(
            f"Do not execute these already-completed actions: {blocked_list}."
        )

    instructions.append(
        'If you execute a proactive action, tag it in your response: '
        '<saf-action id="<action_id>" status="sent"/>'
    )

    return instructions
