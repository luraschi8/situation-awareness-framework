"""OpenClaw implementation of SelfReviewRunner.

Executes the review prompt by invoking Claude Code in non-interactive
(--print) mode as a subprocess.
"""

import subprocess


class OpenClawReviewRunner:
    """Runs a self-review by delegating to Claude Code."""

    def __init__(self, timeout=300):
        self._timeout = timeout

    def run_review(self, prompt, workspace_root):
        """Execute the review prompt via `claude --print`.

        Returns the agent's full response text.
        """
        result = subprocess.run(
            ["claude", "--print", "--prompt", prompt],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=self._timeout,
        )
        return result.stdout
