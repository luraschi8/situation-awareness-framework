def get_relevant_domains(message):
    msg = message.lower()
    if "meeting" in msg or "deadline" in msg:
        return ["work"]
    if "family" in msg or "kids" in msg or "school" in msg:
        return ["family"]
    return ["work", "family", "personal_projects", "infrastructure"]
