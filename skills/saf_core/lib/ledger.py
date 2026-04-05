"""Collective ledger — cross-turn/cross-agent action deduplication."""

import time

from skills.saf_core.lib import paths
from skills.saf_core.lib.fs import load_json, save_json

# Kept as a module-level constant for backward compat with existing tests
LEDGER_PATH = paths.LEDGER_FILE


def sync_action(agent_id, action_id, context=None, workspace_root=None):
    """Records an action in the collective ledger.

    Atomic write: temp file + rename, so concurrent readers never see
    a partial ledger.
    """
    path = paths.resolve(paths.LEDGER_FILE, workspace_root)
    ledger = load_json(path, default={"last_updated": "", "actions": {}})

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ledger["actions"][action_id] = {
        "agent": agent_id,
        "timestamp": now,
        "context": context,
    }
    ledger["last_updated"] = now
    save_json(path, ledger)
    return True


def get_today_actions(workspace_root=None, today_iso=None):
    """Returns today's actions from the ledger for dedup checks.

    today_iso: the "today" boundary to check against (YYYY-MM-DD format).
    If None, uses the local date from temporal context, which aligns
    dedup with the user's perceived day rather than UTC.
    """
    if today_iso is None:
        # Import locally to avoid a circular dependency with temporal.py
        from skills.saf_core.lib.temporal import get_temporal_context
        today_iso = get_temporal_context()["iso_date"]

    path = paths.resolve(paths.LEDGER_FILE, workspace_root)
    ledger = load_json(path, default={"last_updated": "", "actions": {}})

    already_done = [
        action_id
        for action_id, entry in ledger.get("actions", {}).items()
        if _is_today(entry.get("timestamp", ""), today_iso)
    ]
    return {
        "already_done_today": already_done,
        "last_updated": ledger.get("last_updated", ""),
    }


def _is_today(timestamp_str, today_iso):
    """Checks if an ISO timestamp falls on the given local date.

    Ledger timestamps are stored in UTC; the caller provides the local
    date boundary. This is a conservative check: it treats a ledger
    entry as "today" if its UTC timestamp's date prefix matches the
    local today. This is slightly permissive at day boundaries but
    errs toward preventing duplicates rather than risking them.
    """
    return timestamp_str.startswith(today_iso)
