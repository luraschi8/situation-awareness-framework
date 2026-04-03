def route_intent(message):
    """
    Determines which memory domains to inject based on intent.
    """
    msg = message.lower()
    mapping = {
        "work": ["meeting", "job", "office", "deadline", "report"],
        "family": ["family", "kids", "school", "gym", "health"],
        "projects": ["project", "cryptography", "coding", "deploy"],
        "infrastructure": ["server", "network", "home", "lights", "blinds"]
    }
    
    active_domains = []
    for domain, keywords in mapping.items():
        if any(k in msg for k in keywords):
            active_domains.append(domain)
            
    return active_domains if active_domains else ["general"]
