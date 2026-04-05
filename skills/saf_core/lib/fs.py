"""Shared filesystem utilities for SAF.

Centralizes the two patterns that appear in multiple modules:
  - atomic writes (write to .tmp, then rename)
  - JSON read with graceful fallback to a default

Using these helpers eliminates duplication and ensures consistent behavior.
"""

import json
import os


def atomic_write(path, content):
    """Writes content to path atomically via a .tmp file + rename.

    Creates parent directories as needed. On failure, the original file
    is left untouched.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(content)
    os.rename(tmp_path, path)


def load_json(path, default=None):
    """Loads JSON from path, returning default if the file doesn't exist."""
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    """Saves data as pretty-printed JSON atomically."""
    atomic_write(path, json.dumps(data, indent=2))
