"""Single source of truth for domain archetypes, router, and temporal configuration."""

CONFIG_PATH = "memory/shared/router-config.json"
USER_STATE_PATH = "memory/shared/user-state.json"

# Temporal defaults — overridable via user-state.json
# Phase ranges as [start_hour, end_hour). Hour 24 is used as an alias for
# "up to midnight" since hour values are 0-23 and the check is start <= hour < end.
DEFAULT_PHASES = {
    "NIGHT": [0, 6],
    "MORNING": [6, 12],
    "AFTERNOON": [12, 17],
    "EVENING": [17, 21],
    "NIGHT_LATE": [21, 24],
}

# Monday=0 through Friday=4 (Python weekday convention)
DEFAULT_WORK_DAYS = [0, 1, 2, 3, 4]

DEFAULT_TIMEZONE = "UTC"

ARCHETYPE_KEYWORDS = {
    "professional": {
        "work": ["meeting", "job", "office", "deadline", "report"],
        "projects": ["project", "cryptography", "coding", "deploy"],
        "infrastructure": ["server", "network", "home", "lights", "blinds"],
    },
    "family": {
        "family": ["family", "kids", "school", "relatives", "parenting"],
        "home": ["home", "kitchen", "cleaning", "groceries", "chores"],
        "health": ["health", "gym", "doctor", "exercise", "medication"],
    },
}

ARCHETYPE_ACTIONS = {
    "professional": {
        "morning_briefing": {
            "description": "Summarize today's schedule, priorities, and pending items",
            "trigger": {"phase": ["MORNING"], "day_type": "workday"},
            "frequency": "daily",
            "domains": ["work", "projects"],
            "enabled": True,
        },
        "weekly_review": {
            "description": "Review the week's accomplishments and plan next week",
            "trigger": {"phase": ["MORNING"], "day_of_week": [0]},
            "frequency": "weekly",
            "domains": ["work", "projects"],
            "enabled": True,
        },
    },
    "family": {
        "morning_briefing": {
            "description": "Summarize today's family schedule and household tasks",
            "trigger": {"phase": ["MORNING"]},
            "frequency": "daily",
            "domains": ["family", "home"],
            "enabled": True,
        },
        "weekly_meal_plan": {
            "description": "Plan meals for the upcoming week",
            "trigger": {"phase": ["MORNING"], "day_of_week": [6]},
            "frequency": "weekly",
            "domains": ["home"],
            "enabled": True,
        },
    },
}

DEFAULT_ARCHETYPE = "professional"
DEFAULT_KEYWORDS = ARCHETYPE_KEYWORDS[DEFAULT_ARCHETYPE]
DEFAULT_ACTIONS = ARCHETYPE_ACTIONS[DEFAULT_ARCHETYPE]
