import json
import os
import time

LEDGER_PATH = "memory/shared/collective-ledger.json"

def sync_action(agent_id, action_id, context=None):
    """
    Records an action in the Global Ledger to prevent inter-agent redundancy.
    """
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    ledger = {"last_updated": "", "actions": {}}
    
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, 'r') as f:
            ledger = json.load(f)
            
    ledger["actions"][action_id] = {
        "agent": agent_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "context": context
    }
    ledger["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    with open(LEDGER_PATH + ".tmp", 'w') as f:
        json.dump(ledger, f, indent=2)
    os.rename(LEDGER_PATH + ".tmp", LEDGER_PATH)
    return True
