"""Centralized SAF filesystem paths.

All paths are relative to the workspace root. Adapters pass the workspace
root explicitly to functions that need it, avoiding cwd-dependent behavior.
"""

import os

MEMORY_DIR = "memory"
DOMAINS_DIR = os.path.join(MEMORY_DIR, "domains")
SHARED_DIR = os.path.join(MEMORY_DIR, "shared")
RUNTIME_DIR = os.path.join(SHARED_DIR, "runtime")

LEDGER_FILE = os.path.join(SHARED_DIR, "collective-ledger.json")
PROACTIVE_ACTIONS_FILE = os.path.join(SHARED_DIR, "proactive-actions.json")
ROUTER_CONFIG_FILE = os.path.join(SHARED_DIR, "router-config.json")
USER_STATE_FILE = os.path.join(SHARED_DIR, "user-state.json")
BRIEFING_FILE = os.path.join(RUNTIME_DIR, "SAF_BRIEFING.md")


def resolve(relative_path, workspace_root=None):
    """Resolves a memory-relative path against a workspace root.

    If workspace_root is None, returns the path unchanged (cwd-relative).
    """
    if workspace_root:
        return os.path.join(workspace_root, relative_path)
    return relative_path


def domain_path(domain_name, workspace_root=None):
    """Returns the path to a specific domain directory."""
    return resolve(os.path.join(DOMAINS_DIR, domain_name), workspace_root)
