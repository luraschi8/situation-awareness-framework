import json
import os
import re

from skills.saf_core.lib.domains import CONFIG_PATH, DEFAULT_KEYWORDS

GENERAL_DOMAIN = "general"


def load_domain_keywords():
    """Loads domain keywords from config file, falling back to defaults."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return DEFAULT_KEYWORDS


def _word_match(keyword, text):
    """Checks if keyword appears as a whole word in text."""
    return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))


def get_relevant_domains(message, domain_keywords=None):
    """Determines which memory domains to inject based on message intent."""
    if domain_keywords is None:
        domain_keywords = load_domain_keywords()
    msg = message.lower()
    domains = [
        domain
        for domain, keywords in domain_keywords.items()
        if any(_word_match(k, msg) for k in keywords)
    ]
    return domains if domains else [GENERAL_DOMAIN]
