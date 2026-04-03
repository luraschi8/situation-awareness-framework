"""Single source of truth for domain archetypes and router configuration."""

CONFIG_PATH = "memory/shared/router-config.json"

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

DEFAULT_ARCHETYPE = "professional"
DEFAULT_KEYWORDS = ARCHETYPE_KEYWORDS[DEFAULT_ARCHETYPE]
