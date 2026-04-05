#!/usr/bin/env python3
"""Installer for the SAF OpenClaw adapter.

Usage:
    python3 skills/saf_openclaw/install.py [--target ~/.openclaw/hooks]

Copies the three SAF hooks into the OpenClaw hooks directory and
(optionally) runs the SAF workspace bootstrap if memory/ is missing.
"""

import argparse
import os
import shutil
import subprocess
import sys

HOOKS_SOURCE = os.path.join(os.path.dirname(__file__), "hooks")
DEFAULT_HOOK_TARGET = os.path.expanduser("~/.openclaw/hooks")
HOOK_NAMES = ["saf-bootstrap", "saf-pre-message", "saf-post-message"]


def install(target_dir: str, run_bootstrap: bool) -> int:
    """Installs SAF hooks into the target directory. Returns 0 on success."""
    if not os.path.isdir(HOOKS_SOURCE):
        print(f"ERROR: hooks source directory not found: {HOOKS_SOURCE}")
        return 1

    os.makedirs(target_dir, exist_ok=True)

    for hook_name in HOOK_NAMES:
        src = os.path.join(HOOKS_SOURCE, hook_name)
        dst = os.path.join(target_dir, hook_name)
        if os.path.exists(dst):
            print(f"[skip] {hook_name} already installed at {dst}")
            continue
        shutil.copytree(src, dst)
        print(f"[ok]   installed {hook_name} → {dst}")

    if run_bootstrap and not os.path.isdir("memory/domains"):
        print("\nNo SAF workspace detected. Running saf-init...\n")
        result = subprocess.run(["python3", "templates/saf-init"])
        if result.returncode != 0:
            print("WARNING: saf-init did not complete successfully.")
            return result.returncode

    print("\nSAF OpenClaw adapter installed.")
    print("Enable the hooks with: openclaw hooks enable saf-bootstrap saf-pre-message saf-post-message")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Install SAF hooks into OpenClaw")
    parser.add_argument(
        "--target",
        default=DEFAULT_HOOK_TARGET,
        help=f"Target hooks directory (default: {DEFAULT_HOOK_TARGET})",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Skip running saf-init even if memory/ is missing",
    )
    args = parser.parse_args()
    return install(args.target, run_bootstrap=not args.skip_bootstrap)


if __name__ == "__main__":
    sys.exit(main())
