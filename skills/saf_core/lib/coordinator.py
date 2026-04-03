import json
import os

LEDGER_PATH = "memory/shared/collective-ledger.json"

def log_global_action(agent_id, action_id, status="completed"):
    try:
        if os.path.exists(LEDGER_PATH):
            with open(LEDGER_PATH, 'r') as f:
                ledger = json.load(f)
        else:
            ledger = {"actions": {}}
        
        ledger["actions"][action_id] = {
            "agent": agent_id,
            "timestamp": "2026-03-30T16:30:00Z",
            "status": status
        }
        
        with open(LEDGER_PATH + ".tmp", 'w') as f:
            json.dump(ledger, f, indent=2)
        os.rename(LEDGER_PATH + ".tmp", LEDGER_PATH)
        return True
    except Exception:
        return False
