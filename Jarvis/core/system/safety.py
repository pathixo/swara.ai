"""
Safety Engine — Command Risk Assessment & Filtering
=====================================================
Centralizes all security logic for OS interactions using a 3-Tier Sandbox:

Tier RED (CRITICAL):
    - Blocked by default.
    - Includes registry edits, BIOS, format drives, shutdown, user account changes.
    - Matches RiskLevel.CRITICAL.

Tier YELLOW (MEDIUM/HIGH):
    - Requires user confirmation before execution.
    - Includes file writes, directory creation, arbitrary shell commands, killing processes.
    - Matches RiskLevel.MEDIUM and RiskLevel.HIGH.

Tier GREEN (LOW):
    - Auto-executes.
    - Includes app launch, URL open, system info, web search, media play, reading files.
    - Matches RiskLevel.LOW.
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
    # RED (CRITICAL) — data destruction, system-level changes (Blocked)
    RiskPattern(r"format\s+[a-z]:", RiskLevel.CRITICAL, "Disk format"),
    RiskPattern(r"diskpart", RiskLevel.CRITICAL, "Disk partitioning"),
    RiskPattern(r"bcdedit", RiskLevel.CRITICAL, "Boot configuration edit"),
    RiskPattern(r"cipher\s+/w:", RiskLevel.CRITICAL, "Secure disk wipe"),
    RiskPattern(r"Format-Volume", RiskLevel.CRITICAL, "Disk format (PowerShell)"),
    RiskPattern(r"Clear-Disk", RiskLevel.CRITICAL, "Disk wipe"),
    RiskPattern(r"reg\s+delete", RiskLevel.CRITICAL, "Registry deletion"),
    RiskPattern(r"reg\s+add", RiskLevel.CRITICAL, "Registry modification"),
    RiskPattern(r"shutdown\s+/[sSpP]", RiskLevel.CRITICAL, "System shutdown/restart"),
    RiskPattern(r"net\s+user\s+\S+\s+\S+\s*/add", RiskLevel.CRITICAL, "User account creation"),

    # YELLOW (HIGH) — major modifications (Requires Confirmation)
    RiskPattern(r"remove-item\s+.*-recurse", RiskLevel.HIGH, "Recursive file deletion"),
    RiskPattern(r"rm\s+-rf", RiskLevel.HIGH, "Recursive force delete"),
    RiskPattern(r"del\s+/[sS]", RiskLevel.HIGH, "Recursive delete"),
    RiskPattern(r"sfc\s+/scannow", RiskLevel.HIGH, "System file checker"),
    RiskPattern(r"stop-service", RiskLevel.HIGH, "Service stop"),
    RiskPattern(r"Set-ExecutionPolicy", RiskLevel.HIGH, "Execution policy change"),
    RiskPattern(r"netsh\s+advfirewall", RiskLevel.HIGH, "Firewall modification"),
    RiskPattern(r"Set-Service", RiskLevel.HIGH, "Service modification"),
    RiskPattern(r"Disable-WindowsOptionalFeature", RiskLevel.HIGH, "Windows feature removal"),
    RiskPattern(r"Invoke-Expression|iex", RiskLevel.HIGH, "Dynamic code execution"),
    RiskPattern(r"-(enc|encodedcommand)\b", RiskLevel.HIGH, "Encoded PowerShell command"),
    RiskPattern(r"wsl\b", RiskLevel.HIGH, "WSL Subsystem execution"),
    RiskPattern(r"powershell.*-ep\s+bypass", RiskLevel.HIGH, "PowerShell execution policy bypass"),
    RiskPattern(r"(certutil|bitsadmin|mshta|wmic|cscript|wscript)\b", RiskLevel.HIGH, "Windows LOLBin execution"),
    RiskPattern(r"runas\s*/", RiskLevel.HIGH, "Privilege escalation"),

    # YELLOW (MEDIUM) — network, process control, environment changes (Requires Confirmation)
    RiskPattern(r"(?:invoke-webrequest|curl|wget).*\|\s*(?:iex|invoke-expression)", RiskLevel.CRITICAL, "Web request piped to execute"),
    RiskPattern(r"invoke-webrequest|curl|wget", RiskLevel.MEDIUM, "Network download"),
    RiskPattern(r"stop-process|taskkill", RiskLevel.MEDIUM, "Process termination"),
    RiskPattern(r"set-itemproperty", RiskLevel.MEDIUM, "Property modification"),
    RiskPattern(r"new-service", RiskLevel.MEDIUM, "Service creation"),
]

# Paths that are strictly off-limits for non-read operations
SENSITIVE_PATHS = [
    r"C:\\Windows",
    r"C:\\Program Files",
    r"C:\\Program Files \(x86\)",
    r"C:\\Users\\.*\\AppData\\Local\\Microsoft\\Windows",
    r"C:\\Users\\.*\\NTUSER\.DAT",
    r"\\Device\\",
    r"\\\\.\b",
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
        self._max_audit = 500                # Max entries to keep
        self._execution_timestamps = []      # For rate limiting
        
        # Load persistent logs
        self._load_audit_log()

    def _load_audit_log(self):
        """Load recent entries from the persistent audit log."""
        import json
        import os
        from Jarvis.config import LOGS_DIR
        audit_file = os.path.join(LOGS_DIR, "audit.jsonl")
        
        if not os.path.exists(audit_file):
            return
            
        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-self._max_audit:]:
                    try:
                        self._audit_log.append(json.loads(line))
                    except:
                        continue
        except Exception as e:
            logger.error("Failed to load persistent audit log: %s", e)

    # ── Risk Assessment ─────────────────────────────────────────────────

    def assess_command(self, command: str) -> tuple[RiskLevel, str]:
        """
        Assess the risk level of a shell command.

        Returns:
            (RiskLevel, description of why it was flagged).
        """
        cmd_lower = command.strip().lower()

        # 1. Check sensitive paths
        for path_pat in SENSITIVE_PATHS:
            if re.search(path_pat, command, re.IGNORECASE):
                # Reads are generally okay, but modifications are RED (CRITICAL)
                is_read_only = re.search(r"^(get-childitem|ls|dir|type|cat|get-content|test-path)\b", cmd_lower)
                if not is_read_only:
                    return RiskLevel.CRITICAL, f"Sensitive path access: {path_pat}"

        # 2. Check allowlist
        for pattern in self._allowlist:
            if re.search(pattern, cmd_lower, re.IGNORECASE):
                return RiskLevel.LOW, "Allowlisted"

        # 3. Check blocklist
        for blocked in self._blocklist:
            if blocked.lower() in cmd_lower:
                return RiskLevel.CRITICAL, f"Blocklisted: {blocked}"

        # 4. Check risk patterns
        highest_risk = RiskLevel.LOW
        highest_desc = "No risk patterns matched"

        for rp in RISK_PATTERNS:
            if re.search(rp.pattern, command, re.IGNORECASE):
                if self._risk_rank(rp.risk) > self._risk_rank(highest_risk):
                    highest_risk = rp.risk
                    highest_desc = rp.description

        return highest_risk, highest_desc

    def is_dangerous(self, command: str) -> bool:
        """Quick check: is this command in the YELLOW or RED tier?"""
        risk, _ = self.assess_command(command)
        return risk in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)

    def should_block(self, command: str) -> tuple[bool, str]:
        """
        Determine if a command should be blocked outright (RED tier).

        Returns:
            (should_block: bool, reason: str)
        """
        import time
        now = time.time()
        self._execution_timestamps = [t for t in self._execution_timestamps if now - t < 10.0]
        if len(self._execution_timestamps) >= 8:
            return True, "Blocked: Rate limit exceeded (too many commands in quick succession)"
        self._execution_timestamps.append(now)

        risk, desc = self.assess_command(command)
        if risk == RiskLevel.CRITICAL:
            return True, f"Blocked (RED - CRITICAL): {desc}"
        return False, desc

    def should_confirm(self, command: str) -> tuple[bool, str]:
        """
        Determine if a command needs user confirmation (YELLOW tier).

        Returns:
            (needs_confirmation: bool, reason: str)
        """
        risk, desc = self.assess_command(command)
        if risk in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL):
            tier = "RED" if risk == RiskLevel.CRITICAL else "YELLOW"
            return True, f"Requires confirmation ({tier} - {risk.value}): {desc}"
        return False, desc

    # ── Action-Type Risk Defaults ───────────────────────────────────────

    def assess_action(self, action_type: ActionType) -> RiskLevel:
        """
        Default risk level for an action type.
        Shell commands get further assessment via assess_command().
        """
        defaults = {
            ActionType.LAUNCH_APP:     RiskLevel.LOW,      # GREEN
            ActionType.OPEN_URL:       RiskLevel.LOW,      # GREEN
            ActionType.SHELL_COMMAND:  RiskLevel.MEDIUM,   # YELLOW (further assessed)
            ActionType.FILE_READ:      RiskLevel.LOW,      # GREEN
            ActionType.FILE_WRITE:     RiskLevel.MEDIUM,   # YELLOW
            ActionType.FILE_LIST:      RiskLevel.LOW,      # GREEN
            ActionType.SYSTEM_INFO:    RiskLevel.LOW,      # GREEN
            ActionType.NOTIFICATION:   RiskLevel.LOW,      # GREEN
            ActionType.PLAY_MUSIC:     RiskLevel.LOW,      # GREEN
            ActionType.EXEC_CODE:      RiskLevel.HIGH,     # YELLOW
            ActionType.SEARCH_SYSTEM:  RiskLevel.LOW,      # GREEN
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
        import json
        from pathlib import Path

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

        # Persistence to audit.jsonl
        try:
            from Jarvis.config import LOGS_DIR
            import os
            audit_file = os.path.join(LOGS_DIR, "audit.jsonl")
            with open(audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error("Failed to write audit log to disk: %s", e)

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
