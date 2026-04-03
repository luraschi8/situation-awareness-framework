def check_relevance(action, user_state):
    # Simplified Relevance Gate logic
    mode = user_state.get("override_mode")
    if mode == "vacation" and action == "weekly_menu":
        return False
    return True
