import re

GENERAL_DOMAIN = "general"

DOMAIN_KEYWORDS = {
    "work": ["meeting", "job", "office", "deadline", "report"],
    "family": ["family", "kids", "school", "gym", "health"],
    "projects": ["project", "cryptography", "coding", "deploy"],
    "infrastructure": ["server", "network", "home", "lights", "blinds"],
}


def _word_match(keyword, text):
    """Checks if keyword appears as a whole word in text."""
    return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))


def get_relevant_domains(message):
    """Determines which memory domains to inject based on message intent."""
    msg = message.lower()
    domains = [
        domain
        for domain, keywords in DOMAIN_KEYWORDS.items()
        if any(_word_match(k, msg) for k in keywords)
    ]
    return domains if domains else [GENERAL_DOMAIN]
