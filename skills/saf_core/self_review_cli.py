"""CLI entry point for headless SAF self-review (cron/scheduled).

Usage:
    python3 -m skills.saf_core.self_review_cli --workspace /path --runner openclaw

The runner argument selects the SelfReviewRunner adapter that executes
the review prompt in a specific agent runtime.
"""

import argparse
import json
import os
import sys

from skills.saf_core.lib.self_review import execute_self_review
from skills.saf_core.lib.host import SAFHost


class CLIHost:
    """Minimal SAFHost for CLI usage."""

    def __init__(self, workspace_root):
        self._root = os.path.abspath(workspace_root)

    def workspace_root(self):
        return self._root

    def log(self, level, message):
        print(f"[saf-review:{level}] {message}", file=sys.stderr)


def _get_runner(runner_name):
    """Load the named SelfReviewRunner adapter."""
    if runner_name == "openclaw":
        from skills.saf_openclaw.self_review_runner import OpenClawReviewRunner
        return OpenClawReviewRunner()
    raise ValueError(f"Unknown runner: {runner_name}")


def main():
    parser = argparse.ArgumentParser(
        description="Run a headless SAF self-review",
    )
    parser.add_argument(
        "--workspace", default=os.getcwd(),
        help="Path to the workspace root (default: cwd)",
    )
    parser.add_argument(
        "--runner", required=True,
        help="SelfReviewRunner adapter name (e.g., 'openclaw')",
    )
    parser.add_argument(
        "--mode", default="full", choices=["lightweight", "full"],
        help="Review mode (default: full)",
    )
    args = parser.parse_args()

    host = CLIHost(args.workspace)
    runner = _get_runner(args.runner)
    config = {"review_mode": args.mode}

    result = execute_self_review(runner, host, config)

    output = {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
    }
    print(json.dumps(output, indent=2))
    sys.exit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
