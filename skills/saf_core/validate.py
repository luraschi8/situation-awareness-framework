"""CLI entry point for SAF workspace validation.

Usage:
    python3 -m skills.saf_core.validate --workspace /path/to/workspace

Exits 0 if valid, 1 if errors. Prints JSON result to stdout so the
agent can parse it programmatically.
"""

import argparse
import json
import os
import sys

from skills.saf_core.lib.self_review import validate_workspace


def main():
    parser = argparse.ArgumentParser(
        description="Validate SAF workspace config integrity",
    )
    parser.add_argument(
        "--workspace", default=os.getcwd(),
        help="Path to the workspace root (default: cwd)",
    )
    args = parser.parse_args()

    result = validate_workspace(args.workspace)

    output = {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
    }
    print(json.dumps(output, indent=2))

    sys.exit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
