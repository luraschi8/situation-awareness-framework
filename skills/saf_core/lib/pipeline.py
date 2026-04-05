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

from skills.saf_core.lib import ledger, paths, router, temporal
from skills.saf_core.lib.context import DomainCandidate, SAFContext
from skills.saf_core.lib.host import SAFHost

SAF_AGENT_ID = "saf"


def process(message: str, host: SAFHost) -> SAFContext:
    """Runs Steps 0-3 of the SAF pipeline and returns the full SAFContext.

    Steps:
      0. Temporal context (system clock + user-state.json)
      1. Dedup lookup (read collective-ledger.json)
      2. Domain routing (regex match against router-config.json)
      3. Relevance gate (apply rules to compute blocked actions)

    Returns a SAFContext the adapter renders for the agent.
    """
    workspace = host.workspace_root()

    # Step 0: temporal
    temporal_ctx = temporal.get_temporal_context()

    # Step 1: dedup lookup (aligned to user's local date, not UTC)
    dedup = ledger.get_today_actions(
        workspace_root=workspace,
        today_iso=temporal_ctx["iso_date"],
    )

    # Step 2: domain routing
    domain_names = router.get_relevant_domains(message)
    candidate_domains = _resolve_domain_files(domain_names, message, workspace, host)

    # Step 3: relevance gate — compute blocked actions
    blocked = _compute_blocked_actions(dedup)

    instructions = _build_instructions(candidate_domains, blocked)

    return SAFContext(
        temporal=temporal_ctx,
        dedup=dedup,
        candidate_domains=candidate_domains,
        blocked_actions=blocked,
        agent_instructions=instructions,
    )


def record_action(action_id: str, status: str, host: SAFHost) -> None:
    """Step 6: persist an executed action to the ledger."""
    ledger.sync_action(
        agent_id=SAF_AGENT_ID,
        action_id=action_id,
        context={"status": status},
        workspace_root=host.workspace_root(),
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


def _compute_blocked_actions(dedup: dict) -> dict:
    """Computes which actions must not be executed this turn.

    Today: blocks anything already in the ledger for today.
    Future: will also consult the relevance gate (#9) and behavioral
    regressions (#10).
    """
    return {
        action_id: "already_done_today"
        for action_id in dedup.get("already_done_today", [])
    }


def _build_instructions(
    candidates: List[DomainCandidate],
    blocked: dict,
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
