"""Collective ledger — cross-turn/cross-agent action deduplication."""

import time
from datetime import date

from skills.saf_core.lib import paths
from skills.saf_core.lib.fs import load_json, save_json

# Kept as a module-level constant for backward compat with existing tests
LEDGER_PATH = paths.LEDGER_FILE

FREQ_DAILY = "daily"
FREQ_WEEKLY = "weekly"

def _empty_ledger():
    """Returns a fresh empty ledger dict."""
    return {"last_updated": "", "actions": {}}


def _load_ledger(workspace_root=None):
    """Load the ledger from disk, returning empty defaults if absent."""
    path = paths.resolve(paths.LEDGER_FILE, workspace_root)
    return load_json(path, default=_empty_ledger())


def _resolve_today(today_iso):
    """Resolve today_iso, falling back to temporal context if None."""
    if today_iso is not None:
        return today_iso
    # Import locally to avoid a circular dependency with temporal.py
    from skills.saf_core.lib.temporal import get_temporal_context
    return get_temporal_context()["iso_date"]


def sync_action(agent_id, action_id, context=None, workspace_root=None, origin=None):
    """Records an action in the collective ledger.

    Atomic write: temp file + rename, so concurrent readers never see
    a partial ledger.
    """
    path = paths.resolve(paths.LEDGER_FILE, workspace_root)
    ledger = load_json(path, default=_empty_ledger())

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry = {
        "agent": agent_id,
        "timestamp": now,
        "context": context,
    }
    if origin:
        entry["origin"] = origin
    ledger["actions"][action_id] = entry
    ledger["last_updated"] = now
    save_json(path, ledger)
    return True


def get_today_actions(workspace_root=None, today_iso=None):
    """Returns today's actions from the ledger for dedup checks.

    today_iso: the "today" boundary to check against (YYYY-MM-DD format).
    If None, uses the local date from temporal context, which aligns
    dedup with the user's perceived day rather than UTC.
    """
    today_iso = _resolve_today(today_iso)
    ledger = _load_ledger(workspace_root)

    already_done = [
        action_id
        for action_id, entry in ledger.get("actions", {}).items()
        if _is_today(entry.get("timestamp", ""), today_iso)
    ]
    return {
        "already_done_today": already_done,
        "last_updated": ledger.get("last_updated", ""),
    }


def is_action_done(action_id, frequency=FREQ_DAILY, workspace_root=None,
                   today_iso=None, _ledger=None):
    """Check if an action has been completed within its frequency window.

    frequency:
        FREQ_DAILY  — done today (same date boundary as get_today_actions)
        FREQ_WEEKLY — done this ISO week

    _ledger: optional pre-loaded ledger dict to avoid redundant disk reads
    when called in a loop (e.g. from pipeline.process).

    Returns True if the action should be considered already handled.
    """
    today_iso = _resolve_today(today_iso)
    ledger = _ledger if _ledger is not None else _load_ledger(workspace_root)

    entry = ledger.get("actions", {}).get(action_id)
    if entry is None:
        return False

    timestamp = entry.get("timestamp", "")

    if frequency == FREQ_WEEKLY:
        return _is_same_iso_week(timestamp, today_iso)
    return _is_today(timestamp, today_iso)


def _is_today(timestamp_str, today_iso):
    """Checks if an ISO timestamp falls on the given local date.

    Ledger timestamps are stored in UTC; the caller provides the local
    date boundary. This is a conservative check: it treats a ledger
    entry as "today" if its UTC timestamp's date prefix matches the
    local today. This is slightly permissive at day boundaries but
    errs toward preventing duplicates rather than risking them.
    """
    return timestamp_str.startswith(today_iso)


def _is_same_iso_week(timestamp_str, today_iso):
    """Check if a UTC timestamp falls in the same ISO week as today_iso."""
    ts_date_str = timestamp_str[:10]
    if len(ts_date_str) != 10:
        return False
    try:
        ts_date = date.fromisoformat(ts_date_str)
        today_date = date.fromisoformat(today_iso)
    except ValueError:
        return False
    return ts_date.isocalendar()[:2] == today_date.isocalendar()[:2]
