"""SAFHost protocol — the minimal contract adapters implement for saf_core."""

from typing import Protocol


class SAFHost(Protocol):
    """Contract that framework adapters implement for saf_core to operate.

    SAF core calls these methods to resolve filesystem paths and emit
    structured logs. Nothing else. This minimal surface is what keeps
    SAF pure and portable across frameworks.
    """

    def workspace_root(self) -> str:
        """Returns the absolute path to the directory containing memory/."""
        ...

    def log(self, level: str, message: str) -> None:
        """Framework-native logging.

        level: one of 'debug', 'info', 'warn', 'error'
        """
        ...
