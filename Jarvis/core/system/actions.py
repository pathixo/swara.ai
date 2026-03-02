"""
Actions Module — Structured Action & Result Types
===================================================
Defines the data structures used throughout the OS Abstraction Layer:
  - ActionType:  Enum of supported action categories
  - RiskLevel:   Security classification for commands
  - ActionResult: Standardized return type for all OS operations
  - ShellResult:  Extended result for shell command execution
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ─────────────────────── Action Types ───────────────────────────────────────

class ActionType(str, Enum):
    """Categories of OS interactions."""
    LAUNCH_APP     = "launch_app"
    OPEN_URL       = "open_url"
    SHELL_COMMAND  = "shell_command"
    FILE_READ      = "file_read"
    FILE_WRITE     = "file_write"
    FILE_LIST      = "file_list"
    SYSTEM_INFO    = "system_info"
    NOTIFICATION   = "notification"


class RiskLevel(str, Enum):
    """Security classification for actions."""
    LOW      = "low"       # Read-only, informational
    MEDIUM   = "medium"    # Creates/modifies files, launches apps
    HIGH     = "high"      # Deletes files, modifies system settings
    CRITICAL = "critical"  # Format disk, registry edits, shutdown


# ─────────────────────── Action Results ─────────────────────────────────────

@dataclass
class ActionResult:
    """
    Standardized return type for all OS operations.
    Every method in SystemBackend returns one of these.
    """
    success: bool
    message: str                    # Human-readable summary (for TTS)
    output: str = ""               # Raw output (for display / LLM feedback)
    error: str = ""                # Error details if failed
    action_type: str = ""          # Which ActionType produced this
    risk_level: str = "low"        # Risk classification applied

    def __str__(self) -> str:
        if self.success:
            return self.output if self.output else self.message
        return self.error if self.error else self.message


@dataclass
class ShellResult(ActionResult):
    """
    Extended result for shell command execution.
    Adds return code, stdout/stderr separation.
    """
    return_code: int = -1
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    command: str = ""              # The command that was executed


# ─────────────────────── Action Request ─────────────────────────────────────

@dataclass
class ActionRequest:
    """
    Parsed action request from LLM output.
    Produced by parsing [ACTION]...[/ACTION] tags.
    """
    action_type: ActionType
    target: str                     # App name, URL, command, path, etc.
    args: list[str] = field(default_factory=list)
    raw_text: str = ""             # Original tag content for logging
