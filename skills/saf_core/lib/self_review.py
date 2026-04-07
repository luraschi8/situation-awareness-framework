"""Self-Improvement Engine — workspace auditing, validation, and snapshot safety.

Deterministic module that supports the agent's self-review cycle:
  - build_review_context(): scan workspace state for the review prompt
  - validate_workspace(): check config file integrity after agent changes
  - snapshot_configs() / restore_snapshot(): safety net for config changes
  - render_review_prompt(): fill protocol template with workspace state
  - execute_self_review(): orchestrate a full headless review via adapter

This module never calls an LLM. The agent does all reasoning and file
modifications; this module prepares the context and validates results.
"""

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Protocol

from skills.saf_core.lib import paths
from skills.saf_core.lib.fs import load_json, save_json
from skills.saf_core.lib.host import SAFHost
from skills.saf_core.lib.ledger import FREQ_DAILY, FREQ_WEEKLY


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DomainAuditInfo:
    """Metadata about a domain directory for the review prompt."""
    name: str
    path: str
    files: List[str]
    file_mtimes: Dict[str, str]  # filename → ISO date
    has_index: bool


@dataclass(frozen=True)
class ReviewContext:
    """Deterministic workspace snapshot passed to the review prompt template."""
    timestamp: str
    workspace_root: str
    review_mode: str  # "lightweight" or "full"
    domains: List[DomainAuditInfo]
    ledger_summary: Dict[str, Any]
    staleness_threshold_days: int
    last_review_timestamp: str


@dataclass(frozen=True)
class ValidationResult:
    """Output of validate_workspace()."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STALENESS_DAYS = 30

SNAPSHOT_META_FILE = "meta.json"

# Config files that get snapshotted / validated
CONFIG_FILES = [
    paths.PROACTIVE_ACTIONS_FILE,
    paths.USER_STATE_FILE,
    paths.ROUTER_CONFIG_FILE,
]


# ---------------------------------------------------------------------------
# build_review_context
# ---------------------------------------------------------------------------

def _collect_domain_info(workspace_root):
    """Scan memory/domains/ and collect audit info per domain."""
    domains_dir = paths.resolve(paths.DOMAINS_DIR, workspace_root)
    if not os.path.isdir(domains_dir):
        return []

    result = []
    for name in sorted(os.listdir(domains_dir)):
        domain_path = os.path.join(domains_dir, name)
        if not os.path.isdir(domain_path):
            continue

        files = sorted(
            f for f in os.listdir(domain_path)
            if os.path.isfile(os.path.join(domain_path, f))
            and not f.startswith(".")
        )

        file_mtimes = {}
        for f in files:
            fpath = os.path.join(domain_path, f)
            mtime = os.path.getmtime(fpath)
            file_mtimes[f] = datetime.fromtimestamp(
                mtime, tz=timezone.utc,
            ).strftime("%Y-%m-%d")

        has_index = "_index.md" in files

        result.append(DomainAuditInfo(
            name=name,
            path=domain_path,
            files=files,
            file_mtimes=file_mtimes,
            has_index=has_index,
        ))
    return result


def _load_ledger_info(workspace_root):
    """Extract action patterns and last review timestamp from the ledger."""
    ledger = load_json(
        paths.resolve(paths.LEDGER_FILE, workspace_root),
        default={"actions": {}},
    )
    actions = ledger.get("actions", {})

    summary = {
        "total_actions_recorded": len(actions),
        "action_ids": sorted(actions.keys()),
        "last_updated": ledger.get("last_updated", ""),
    }

    audit_entry = actions.get("knowledge_audit")
    last_review = audit_entry.get("timestamp", "") if audit_entry else ""

    return summary, last_review


def build_review_context(workspace_root, config=None):
    """Scan workspace and build a ReviewContext for the protocol template.

    config: optional dict with overrides (review_mode, staleness_threshold_days).
    """
    config = config or {}
    ledger_summary, last_review_ts = _load_ledger_info(workspace_root)

    return ReviewContext(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        workspace_root=workspace_root,
        review_mode=config.get("review_mode", "full"),
        domains=_collect_domain_info(workspace_root),
        ledger_summary=ledger_summary,
        staleness_threshold_days=config.get(
            "staleness_threshold_days", DEFAULT_STALENESS_DAYS,
        ),
        last_review_timestamp=last_review_ts,
    )


# ---------------------------------------------------------------------------
# validate_workspace
# ---------------------------------------------------------------------------

def _validate_proactive_actions(workspace_root):
    """Validate proactive-actions.json schema."""
    errors = []
    warnings = []
    path = paths.resolve(paths.PROACTIVE_ACTIONS_FILE, workspace_root)
    data = load_json(path, default=None)

    if data is None:
        return errors, warnings  # file doesn't exist, that's fine

    if not isinstance(data, dict):
        errors.append("proactive-actions.json: root must be an object")
        return errors, warnings

    actions = data.get("actions", {})
    if not isinstance(actions, dict):
        errors.append("proactive-actions.json: 'actions' must be an object")
        return errors, warnings

    valid_frequencies = {FREQ_DAILY, FREQ_WEEKLY}
    valid_trigger_keys = {"phase", "day_type", "day_of_week", "requires"}

    for action_id, action_def in actions.items():
        prefix = f"proactive-actions.json: action '{action_id}'"

        if not isinstance(action_def, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        if "description" not in action_def:
            errors.append(f"{prefix}: missing 'description'")

        freq = action_def.get("frequency", FREQ_DAILY)
        if freq not in valid_frequencies:
            errors.append(f"{prefix}: invalid frequency '{freq}'")

        trigger = action_def.get("trigger", {})
        if not isinstance(trigger, dict):
            errors.append(f"{prefix}: 'trigger' must be an object")
        else:
            unknown_keys = set(trigger.keys()) - valid_trigger_keys
            if unknown_keys:
                warnings.append(f"{prefix}: unknown trigger keys {unknown_keys}")

            if "phase" in trigger and not isinstance(trigger["phase"], list):
                errors.append(f"{prefix}: trigger.phase must be a list")

            if "day_of_week" in trigger:
                dow = trigger["day_of_week"]
                if not isinstance(dow, list):
                    errors.append(f"{prefix}: trigger.day_of_week must be a list")
                elif not all(isinstance(d, int) and 0 <= d <= 6 for d in dow):
                    errors.append(f"{prefix}: trigger.day_of_week values must be ints 0-6")

        if "skip_modes" in action_def:
            if not isinstance(action_def["skip_modes"], list):
                errors.append(f"{prefix}: 'skip_modes' must be a list")

        if "enabled" in action_def:
            if not isinstance(action_def["enabled"], bool):
                errors.append(f"{prefix}: 'enabled' must be a boolean")

    return errors, warnings


def _validate_user_state(workspace_root):
    """Validate user-state.json schema."""
    errors = []
    warnings = []
    path = paths.resolve(paths.USER_STATE_FILE, workspace_root)
    data = load_json(path, default=None)

    if data is None:
        return errors, warnings

    if not isinstance(data, dict):
        errors.append("user-state.json: root must be an object")
        return errors, warnings

    if "timezone" in data:
        tz = data["timezone"]
        if not isinstance(tz, str) or not tz:
            errors.append("user-state.json: 'timezone' must be a non-empty string")
        else:
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(tz)
            except (KeyError, Exception):
                errors.append(f"user-state.json: invalid timezone '{tz}'")

    if "work_days" in data:
        wd = data["work_days"]
        if not isinstance(wd, list):
            errors.append("user-state.json: 'work_days' must be a list")
        elif not all(isinstance(d, int) and 0 <= d <= 6 for d in wd):
            errors.append("user-state.json: 'work_days' values must be ints 0-6")

    if "phases" in data:
        phases = data["phases"]
        if not isinstance(phases, dict):
            errors.append("user-state.json: 'phases' must be an object")
        else:
            for phase_name, bounds in phases.items():
                if not isinstance(bounds, list) or len(bounds) != 2:
                    errors.append(
                        f"user-state.json: phase '{phase_name}' must be [start, end]"
                    )
                elif not all(isinstance(h, int) and 0 <= h <= 24 for h in bounds):
                    errors.append(
                        f"user-state.json: phase '{phase_name}' hours must be ints 0-24"
                    )

    if "mode" in data and not isinstance(data["mode"], str):
        errors.append("user-state.json: 'mode' must be a string")

    if "suppressed_actions" in data:
        if not isinstance(data["suppressed_actions"], list):
            errors.append("user-state.json: 'suppressed_actions' must be a list")

    return errors, warnings


def _validate_router_config(workspace_root):
    """Validate router-config.json schema."""
    errors = []
    warnings = []
    path = paths.resolve(paths.ROUTER_CONFIG_FILE, workspace_root)
    data = load_json(path, default=None)

    if data is None:
        return errors, warnings

    if not isinstance(data, dict):
        errors.append("router-config.json: root must be an object")
        return errors, warnings

    for domain_name, keywords in data.items():
        if not isinstance(keywords, list):
            errors.append(
                f"router-config.json: domain '{domain_name}' must map to a list"
            )
        elif not all(isinstance(k, str) and k for k in keywords):
            errors.append(
                f"router-config.json: domain '{domain_name}' keywords must be "
                "non-empty strings"
            )

    return errors, warnings


def validate_workspace(workspace_root):
    """Deterministic validation of SAF workspace config integrity.

    Returns a ValidationResult with errors (blocking) and warnings.
    """
    all_errors = []
    all_warnings = []

    for validator in (_validate_proactive_actions,
                      _validate_user_state,
                      _validate_router_config):
        errs, warns = validator(workspace_root)
        all_errors.extend(errs)
        all_warnings.extend(warns)

    return ValidationResult(
        valid=len(all_errors) == 0,
        errors=all_errors,
        warnings=all_warnings,
    )


# ---------------------------------------------------------------------------
# Snapshot / Restore
# ---------------------------------------------------------------------------

def snapshot_configs(workspace_root):
    """Copy config files to _system/.snapshot/ as a safety net.

    Returns the snapshot timestamp.
    """
    snapshot_dir = paths.resolve(paths.SNAPSHOT_DIR, workspace_root)
    os.makedirs(snapshot_dir, exist_ok=True)

    for config_rel in CONFIG_FILES:
        src = paths.resolve(config_rel, workspace_root)
        if os.path.exists(src):
            dst = os.path.join(snapshot_dir, os.path.basename(config_rel))
            shutil.copy2(src, dst)

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    meta_path = os.path.join(snapshot_dir, SNAPSHOT_META_FILE)
    save_json(meta_path, {"timestamp": ts})
    return ts


def has_stale_snapshot(workspace_root):
    """Check if a snapshot directory exists (agent never completed)."""
    snapshot_dir = paths.resolve(paths.SNAPSHOT_DIR, workspace_root)
    meta_path = os.path.join(snapshot_dir, SNAPSHOT_META_FILE)
    return os.path.exists(meta_path)


def restore_snapshot(workspace_root):
    """Restore config files from snapshot. Returns True if restored."""
    snapshot_dir = paths.resolve(paths.SNAPSHOT_DIR, workspace_root)
    if not has_stale_snapshot(workspace_root):
        return False

    shared_dir = paths.resolve(paths.SHARED_DIR, workspace_root)
    for config_rel in CONFIG_FILES:
        basename = os.path.basename(config_rel)
        src = os.path.join(snapshot_dir, basename)
        if os.path.exists(src):
            dst = os.path.join(shared_dir, basename)
            shutil.copy2(src, dst)

    cleanup_snapshot(workspace_root)
    return True


def cleanup_snapshot(workspace_root):
    """Remove the snapshot directory after successful review."""
    snapshot_dir = paths.resolve(paths.SNAPSHOT_DIR, workspace_root)
    if os.path.isdir(snapshot_dir):
        shutil.rmtree(snapshot_dir)


# ---------------------------------------------------------------------------
# Render review prompt
# ---------------------------------------------------------------------------

def render_review_prompt(review_ctx, template_path=None):
    """Fill the protocol template with ReviewContext data.

    template_path: absolute path to the template. If None, uses the
    default template location relative to workspace_root.
    """
    if template_path is None:
        template_path = paths.resolve(
            paths.SELF_REVIEW_TEMPLATE, review_ctx.workspace_root,
        )

    with open(template_path, "r") as f:
        template = f.read()

    # Build domain audit table
    domain_lines = []
    try:
        review_date = datetime.strptime(review_ctx.timestamp[:10], "%Y-%m-%d")
    except ValueError:
        review_date = None

    for d in review_ctx.domains:
        stale_files = []
        if review_date:
            for fname, mdate in d.file_mtimes.items():
                try:
                    mdate_obj = datetime.strptime(mdate, "%Y-%m-%d")
                    age_days = (review_date - mdate_obj).days
                    if age_days >= review_ctx.staleness_threshold_days:
                        stale_files.append(f"{fname} ({age_days}d old)")
                except ValueError:
                    pass

        index_status = "yes" if d.has_index else "NO"
        stale_note = f" — stale: {', '.join(stale_files)}" if stale_files else ""
        domain_lines.append(
            f"| {d.name} | {len(d.files)} | {index_status} | "
            f"{', '.join(d.files)}{stale_note} |"
        )

    if domain_lines:
        domain_table = (
            "| Domain | Files | Index | Contents |\n"
            "|--------|-------|-------|----------|\n"
            + "\n".join(domain_lines)
        )
    else:
        domain_table = "_No domains found._"

    # Build ledger patterns
    ls = review_ctx.ledger_summary
    ledger_lines = []
    if ls.get("action_ids"):
        ledger_lines.append(f"Recorded actions: {', '.join(ls['action_ids'])}")
    if ls.get("last_updated"):
        ledger_lines.append(f"Last ledger update: {ls['last_updated']}")
    ledger_patterns = "\n".join(ledger_lines) if ledger_lines else "_No ledger data._"

    # Permission block based on review mode
    if review_ctx.review_mode == "lightweight":
        permissions = (
            "**Lightweight mode — limited permissions:**\n"
            "- You may create/update domain files and `_index.md` files\n"
            "- You may write to `memory/domains/_system/review-queue.md`\n"
            "- Do NOT modify proactive-actions.json, user-state.json, "
            "or router-config.json"
        )
    else:
        permissions = (
            "**Full mode — extended permissions:**\n"
            "- You may create/update domain files and `_index.md` files\n"
            "- You may modify proactive-actions.json (triggers, skip_modes, "
            "add/remove actions)\n"
            "- You may modify user-state.json (suppressed_actions, mode)\n"
            "- You may modify router-config.json (keywords)\n"
            "- You may write to `memory/domains/_system/review-queue.md`\n\n"
            "After EVERY config file change, run:\n"
            "```\n"
            f"python3 -m skills.saf_core.validate --workspace "
            f"{review_ctx.workspace_root}\n"
            "```\n"
            "If validation fails, fix the issue or revert your change."
        )

    # Fill placeholders
    replacements = {
        "{{ timestamp }}": review_ctx.timestamp,
        "{{ last_review_timestamp }}": review_ctx.last_review_timestamp or "never",
        "{{ staleness_threshold_days }}": str(review_ctx.staleness_threshold_days),
        "{{ domain_audit_table }}": domain_table,
        "{{ ledger_patterns }}": ledger_patterns,
        "{{ workspace_root }}": review_ctx.workspace_root,
        "{{ review_mode }}": review_ctx.review_mode,
        "{{ permissions }}": permissions,
    }

    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    return result


# ---------------------------------------------------------------------------
# SelfReviewRunner protocol + orchestrator
# ---------------------------------------------------------------------------

class SelfReviewRunner(Protocol):
    """Adapter interface for executing a review prompt in an agent runtime."""

    def run_review(self, prompt: str, workspace_root: str) -> str:
        """Execute the review prompt. Returns the agent's full response."""
        ...


def execute_self_review(runner, host, config=None):
    """Full headless self-review orchestration. Called by cron runners.

    1. Checks for / restores stale snapshots from crashed prior runs
    2. Snapshots current configs
    3. Builds review context and prompt
    4. Delegates to runner (agentic — agent validates its own changes)
    5. Post-review validation as safety net
    6. Cleans up or restores snapshot based on result
    """
    workspace = host.workspace_root()
    config = config or {}

    # Safety: restore stale snapshot from a crashed prior run
    if has_stale_snapshot(workspace):
        restore_snapshot(workspace)
        host.log("warn", "Restored configs from stale snapshot of a prior run")

    # Snapshot current state
    snapshot_configs(workspace)

    # Build context and prompt
    review_ctx = build_review_context(workspace, config)
    prompt = render_review_prompt(review_ctx)

    # Agent executes (agentic — runs validation itself, iterates)
    response = runner.run_review(prompt, workspace)

    # Post-review: final validation as safety net
    result = validate_workspace(workspace)
    if not result.valid:
        restore_snapshot(workspace)
        host.log(
            "error",
            f"Review left invalid configs, restored snapshot: {result.errors}",
        )
    else:
        cleanup_snapshot(workspace)

    return result
