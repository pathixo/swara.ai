"""
Safety Engine — Command Risk Assessment & Filtering
=====================================================
Centralizes all security logic for OS interactions:
  - Risk scoring for shell commands
  - Destructive command detection
  - Configurable blocklist / allowlist
  - Audit logging of all actions
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from Jarvis.core.system.actions import ActionType, RiskLevel

logger = logging.getLogger("jarvis.safety")


# ─────────────────────── Risk Patterns ──────────────────────────────────────

@dataclass
class RiskPattern:
    """A regex pattern that maps to a risk level."""
    pattern: str
    risk: RiskLevel
    description: str


# Commands that could destroy data or modify the system dangerously
RISK_PATTERNS: list[RiskPattern] = [
    # CRITICAL — data destruction, system-level changes
    RiskPattern(r"format\s+[a-z]:", RiskLevel.CRITICAL, "Disk format"),
    RiskPattern(r"diskpart", RiskLevel.CRITICAL, "Disk partitioning"),
    RiskPattern(r"bcdedit", RiskLevel.CRITICAL, "Boot configuration edit"),
    RiskPattern(r"cipher\s+/w:", RiskLevel.CRITICAL, "Secure disk wipe"),
    RiskPattern(r"sfc\s+/scannow", RiskLevel.HIGH, "System file checker"),

    # HIGH — deletes files or modifies registry
    RiskPattern(r"remove-item\s+.*-recurse", RiskLevel.HIGH, "Recursive file deletion"),
    RiskPattern(r"rm\s+-rf", RiskLevel.HIGH, "Recursive force delete"),
    RiskPattern(r"del\s+/[sS]", RiskLevel.HIGH, "Recursive delete"),
    RiskPattern(r"reg\s+delete", RiskLevel.HIGH, "Registry deletion"),
    RiskPattern(r"reg\s+add", RiskLevel.HIGH, "Registry modification"),
    RiskPattern(r"shutdown\s+/[sSpP]", RiskLevel.HIGH, "System shutdown/restart"),
    RiskPattern(r"stop-service", RiskLevel.HIGH, "Service stop"),
    RiskPattern(r"Set-ExecutionPolicy", RiskLevel.HIGH, "Execution policy change"),
    RiskPattern(r"netsh\s+advfirewall", RiskLevel.HIGH, "Firewall modification"),

    # MEDIUM — network, process control, environment changes
    RiskPattern(r"invoke-webrequest|curl|wget", RiskLevel.MEDIUM, "Network download"),
    RiskPattern(r"Invoke-Expression|iex", RiskLevel.HIGH, "Dynamic code execution"),
    RiskPattern(r"stop-process|taskkill", RiskLevel.MEDIUM, "Process termination"),
    RiskPattern(r"set-itemproperty", RiskLevel.MEDIUM, "Property modification"),
    RiskPattern(r"new-service", RiskLevel.MEDIUM, "Service creation"),
    RiskPattern(r"runas\s*/", RiskLevel.HIGH, "Privilege escalation"),
    RiskPattern(r"net\s+user\s+\S+\s+\S+\s*/add", RiskLevel.HIGH, "User account creation"),
]


# ─────────────────────── Safety Engine ──────────────────────────────────────

class SafetyEngine:
    """
    Evaluates the risk level of commands and actions.
    Provides allow/block decisions and audit logging.
    """

    def __init__(self):
        self._blocklist: list[str] = []      # Exact command strings to always block
        self._allowlist: list[str] = []      # Patterns to always allow (override risk)
        self._audit_log: list[dict] = []     # In-memory audit trail
        self._max_audit = 200                # Max entries to keep

    # ── Risk Assessment ─────────────────────────────────────────────────

    def assess_command(self, command: str) -> tuple[RiskLevel, str]:
        """
        Assess the risk level of a shell command.

        Returns:
            (RiskLevel, description of why it was flagged).
        """
        cmd_lower = command.strip().lower()

        # Check allowlist first
        for pattern in self._allowlist:
            if re.search(pattern, cmd_lower, re.IGNORECASE):
                return RiskLevel.LOW, "Allowlisted"

        # Check blocklist
        for blocked in self._blocklist:
            if blocked.lower() in cmd_lower:
                return RiskLevel.CRITICAL, f"Blocklisted: {blocked}"

        # Check risk patterns
        highest_risk = RiskLevel.LOW
        highest_desc = "No risk patterns matched"

        for rp in RISK_PATTERNS:
            if re.search(rp.pattern, command, re.IGNORECASE):
                if self._risk_rank(rp.risk) > self._risk_rank(highest_risk):
                    highest_risk = rp.risk
                    highest_desc = rp.description

        return highest_risk, highest_desc

    def is_dangerous(self, command: str) -> bool:
        """Quick check: is this command HIGH or CRITICAL risk?"""
        risk, _ = self.assess_command(command)
        return risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def should_block(self, command: str) -> tuple[bool, str]:
        """
        Determine if a command should be blocked outright.

        Returns:
            (should_block: bool, reason: str)
        """
        risk, desc = self.assess_command(command)
        if risk == RiskLevel.CRITICAL:
            return True, f"Blocked (CRITICAL): {desc}"
        return False, desc

    def should_confirm(self, command: str) -> tuple[bool, str]:
        """
        Determine if a command needs user confirmation.

        Returns:
            (needs_confirmation: bool, reason: str)
        """
        risk, desc = self.assess_command(command)
        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return True, f"Requires confirmation ({risk.value}): {desc}"
        return False, desc

    # ── Action-Type Risk Defaults ───────────────────────────────────────

    def assess_action(self, action_type: ActionType) -> RiskLevel:
        """
        Default risk level for an action type.
        Shell commands get further assessment via assess_command().
        """
        defaults = {
            ActionType.LAUNCH_APP:     RiskLevel.LOW,
            ActionType.OPEN_URL:       RiskLevel.LOW,
            ActionType.SHELL_COMMAND:  RiskLevel.MEDIUM,   # further assessed
            ActionType.FILE_READ:      RiskLevel.LOW,
            ActionType.FILE_WRITE:     RiskLevel.MEDIUM,
            ActionType.FILE_LIST:      RiskLevel.LOW,
            ActionType.SYSTEM_INFO:    RiskLevel.LOW,
            ActionType.NOTIFICATION:   RiskLevel.LOW,
        }
        return defaults.get(action_type, RiskLevel.MEDIUM)

    # ── Audit Log ───────────────────────────────────────────────────────

    def log_action(
        self,
        action_type: str,
        target: str,
        risk: RiskLevel,
        outcome: str,
        from_llm: bool = False,
    ) -> None:
        """Record an action in the audit log."""
        import time
        entry = {
            "timestamp": time.time(),
            "action_type": action_type,
            "target": target,
            "risk": risk.value,
            "outcome": outcome,
            "from_llm": from_llm,
        }
        self._audit_log.append(entry)
        if len(self._audit_log) > self._max_audit:
            self._audit_log = self._audit_log[-self._max_audit:]

        logger.info(
            "AUDIT | %s | target=%s | risk=%s | outcome=%s | llm=%s",
            action_type, target[:60], risk.value, outcome, from_llm,
        )

    def get_audit_log(self, limit: int = 20) -> list[dict]:
        """Return the most recent audit entries."""
        return self._audit_log[-limit:]

    # ── Configuration ───────────────────────────────────────────────────

    def add_to_blocklist(self, command: str) -> None:
        """Add a command string to the permanent blocklist."""
        self._blocklist.append(command)

    def add_to_allowlist(self, pattern: str) -> None:
        """Add a regex pattern to the allowlist (overrides risk assessment)."""
        self._allowlist.append(pattern)

    # ── Internal ────────────────────────────────────────────────────────

    @staticmethod
    def _risk_rank(level: RiskLevel) -> int:
        """Numeric rank for comparison."""
        return {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }.get(level, 0)
