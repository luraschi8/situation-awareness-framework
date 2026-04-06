"""Temporal Awareness Gate (Step 0) — mandatory time synchronization."""

import copy
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from skills.saf_core.lib.domains import (
    DEFAULT_PHASES,
    DEFAULT_TIMEZONE,
    DEFAULT_WORK_DAYS,
    USER_STATE_PATH,
)


def load_user_state():
    """Loads user state from config file, returning defaults for missing fields."""
    state = {}
    if os.path.exists(USER_STATE_PATH):
        with open(USER_STATE_PATH, 'r') as f:
            state = json.load(f)
    return {
        "timezone": state.get("timezone", DEFAULT_TIMEZONE),
        "work_days": state.get("work_days", copy.copy(DEFAULT_WORK_DAYS)),
        "phases": state.get("phases", copy.deepcopy(DEFAULT_PHASES)),
    }


def _resolve_phase(hour, phases):
    """Determines the day phase for a given hour (0-23)."""
    for phase_name, (start, end) in phases.items():
        if start <= end:
            # Normal range (e.g., MORNING: [6, 12])
            if start <= hour < end:
                return phase_name
        else:
            # Wrap-around range (e.g., ACTIVE: [18, 6] means 18-23 and 0-5)
            if hour >= start or hour < end:
                return phase_name
    return "UNKNOWN"


def get_temporal_context(_now_override=None):
    """
    The Temporal Awareness Gate. Returns the current temporal context
    derived from the system clock and user configuration.

    _now_override: inject a specific UTC datetime for testing only.
    """
    utc_now = _now_override if _now_override is not None else datetime.now(timezone.utc)
    user_state = load_user_state()

    tz = ZoneInfo(user_state["timezone"])
    local_now = utc_now.astimezone(tz)

    return {
        "utc_time": utc_now.isoformat(),
        "timezone": user_state["timezone"],
        "local_time": local_now.isoformat(),
        "hour": local_now.hour,
        "day_phase": _resolve_phase(local_now.hour, user_state["phases"]),
        "day_of_week": local_now.strftime("%A"),
        "day_type": "workday" if local_now.weekday() in user_state["work_days"] else "rest_day",
        "iso_date": local_now.strftime("%Y-%m-%d"),
        "weekday_number": local_now.weekday(),
    }
