"""
Action Router — Central Action Dispatch Hub
==============================================
Receives parsed actions from the orchestrator and routes them
to the appropriate SystemBackend method + SafetyEngine checks.

Handles both structured [ACTION] tags and legacy [SHELL] tags.
"""

import logging
import re
from typing import Optional

from Jarvis.core.system.actions import (
    ActionResult, ShellResult, ActionType, ActionRequest, RiskLevel,
)
from Jarvis.core.system.backend import SystemBackend
from Jarvis.core.system.safety import SafetyEngine

logger = logging.getLogger("jarvis.action_router")


# ─────────────────────── Action Tag Parsing ─────────────────────────────────

# [ACTION]launch_app: spotify[/ACTION]
# [ACTION]open_url: https://google.com[/ACTION]
# [ACTION]system_info[/ACTION]
ACTION_TAG_PATTERN = re.compile(
    r"\[ACTION\](.*?)\[/ACTION\]", re.DOTALL
)

# Legacy: [SHELL]command[/SHELL]
SHELL_TAG_PATTERN = re.compile(
    r"\[SHELL\](.*?)\[/SHELL\]", re.DOTALL
)


def parse_action_tag(content: str) -> Optional[ActionRequest]:
    """
    Parse the inner content of an [ACTION] tag.

    Supported formats:
        launch_app: spotify
        open_url: https://example.com
        system_info
        notification: title | message
    """
    content = content.strip()
    if not content:
        return None

    # Check for "type: target" format
    if ":" in content:
        parts = content.split(":", 1)
        action_str = parts[0].strip().lower()
        target = parts[1].strip()
    else:
        action_str = content.strip().lower()
        target = ""

    # Map string to ActionType
    type_map = {
        "launch_app": ActionType.LAUNCH_APP,
        "open_app": ActionType.LAUNCH_APP,
        "open": ActionType.LAUNCH_APP,
        "open_url": ActionType.OPEN_URL,
        "url": ActionType.OPEN_URL,
        "browse": ActionType.OPEN_URL,
        "shell": ActionType.SHELL_COMMAND,
        "run": ActionType.SHELL_COMMAND,
        "system_info": ActionType.SYSTEM_INFO,
        "sysinfo": ActionType.SYSTEM_INFO,
        "notify": ActionType.NOTIFICATION,
        "notification": ActionType.NOTIFICATION,
    }

    action_type = type_map.get(action_str)
    if action_type is None:
        logger.warning("Unknown action type: '%s'", action_str)
        return None

    # Parse args for notification (pipe-separated: title | message)
    args = []
    if action_type == ActionType.NOTIFICATION and "|" in target:
        parts = target.split("|", 1)
        target = parts[0].strip()
        args = [parts[1].strip()]

    return ActionRequest(
        action_type=action_type,
        target=target,
        args=args,
        raw_text=content,
    )


def extract_actions(llm_response: str) -> tuple[list[ActionRequest], list[str]]:
    """
    Extract both [ACTION] and [SHELL] tags from an LLM response.

    Returns:
        (action_requests, shell_commands) — both lists may be empty.
    """
    actions = []
    shells = []

    # Parse [ACTION] tags
    for match in ACTION_TAG_PATTERN.finditer(llm_response):
        req = parse_action_tag(match.group(1))
        if req:
            actions.append(req)

    # Parse [SHELL] tags (legacy compatibility)
    for match in SHELL_TAG_PATTERN.finditer(llm_response):
        cmd = match.group(1).strip()
        if cmd:
            shells.append(cmd)

    return actions, shells


# ─────────────────────── Action Router ──────────────────────────────────────

class ActionRouter:
    """
    Routes parsed actions to the appropriate SystemBackend method.
    Applies safety checks before execution.
    """

    def __init__(
        self,
        backend: SystemBackend,
        safety: Optional[SafetyEngine] = None,
        confirm_callback=None,
    ):
        self.backend = backend
        self.safety = safety or SafetyEngine()
        self._confirm_callback = confirm_callback  # callable(cmd) -> bool
        logger.info("ActionRouter initialized | platform=%s", backend.platform_name)

    # ── High-Level Dispatch ─────────────────────────────────────────────

    def execute_action(self, request: ActionRequest) -> ActionResult:
        """
        Execute a structured action request.

        Applies safety checks, dispatches to backend, and logs the audit.
        """
        # Safety check for the action type
        base_risk = self.safety.assess_action(request.action_type)

        handlers = {
            ActionType.LAUNCH_APP:    self._handle_launch_app,
            ActionType.OPEN_URL:      self._handle_open_url,
            ActionType.SHELL_COMMAND: self._handle_shell,
            ActionType.SYSTEM_INFO:   self._handle_system_info,
            ActionType.NOTIFICATION:  self._handle_notification,
        }

        handler = handlers.get(request.action_type)
        if not handler:
            return ActionResult(
                success=False,
                message=f"Unsupported action type: {request.action_type}",
                error="No handler",
            )

        result = handler(request)

        # Audit log
        self.safety.log_action(
            action_type=request.action_type.value,
            target=request.target,
            risk=RiskLevel(result.risk_level) if result.risk_level else base_risk,
            outcome="success" if result.success else "failure",
            from_llm=True,
        )

        return result

    def execute_shell(
        self,
        command: str,
        from_llm: bool = False,
        timeout: int = 30,
        cwd: Optional[str] = None,
    ) -> ShellResult:
        """
        Execute a shell command with unified safety gate.

        Safety pipeline (single source of truth):
          1. CRITICAL → always blocked
          2. HIGH/CRITICAL → requires user confirmation
          3. Otherwise → execute directly

        This is the main entry point for [SHELL] tag commands and
        direct shell commands from the orchestrator.
        """
        risk, risk_desc = self.safety.assess_command(command)

        # 1. Block CRITICAL commands outright
        if risk == RiskLevel.CRITICAL:
            logger.warning("Command blocked (CRITICAL): %s — %s", command, risk_desc)
            self.safety.log_action(
                action_type=ActionType.SHELL_COMMAND.value,
                target=command,
                risk=RiskLevel.CRITICAL,
                outcome="blocked",
                from_llm=from_llm,
            )
            return ShellResult(
                success=False,
                message=f"Blocked dangerous command: `{command}`. {risk_desc}",
                error=risk_desc,
                command=command,
                action_type=ActionType.SHELL_COMMAND.value,
                risk_level=RiskLevel.CRITICAL.value,
            )

        # 2. Require confirmation for HIGH-risk commands
        if risk == RiskLevel.HIGH:
            approved = self._request_confirmation(command, risk_desc)
            if not approved:
                logger.info("Command denied by user: %s", command)
                self.safety.log_action(
                    action_type=ActionType.SHELL_COMMAND.value,
                    target=command,
                    risk=RiskLevel.HIGH,
                    outcome="denied",
                    from_llm=from_llm,
                )
                return ShellResult(
                    success=False,
                    message=f"Command cancelled (requires confirmation): `{command}`",
                    error=f"User denied: {risk_desc}",
                    command=command,
                    action_type=ActionType.SHELL_COMMAND.value,
                    risk_level=RiskLevel.HIGH.value,
                )

        # 3. Execute
        result = self.backend.run_shell(
            command=command,
            timeout=timeout,
            cwd=cwd,
            from_llm=from_llm,
        )

        # Audit
        self.safety.log_action(
            action_type=ActionType.SHELL_COMMAND.value,
            target=command[:80],
            risk=risk,
            outcome="success" if result.success else "failure",
            from_llm=from_llm,
        )

        return result

    def _request_confirmation(self, command: str, reason: str) -> bool:
        """
        Ask for user confirmation via registered callback.
        Defaults to DENY if no callback is registered (safe fallback).
        """
        if self._confirm_callback:
            return self._confirm_callback(command)
        logger.warning(
            "No confirmation callback registered — denying dangerous command: %s",
            command,
        )
        return False  # Safe default: deny if no UI is available

    # ── Action Handlers ─────────────────────────────────────────────────

    def _handle_launch_app(self, request: ActionRequest) -> ActionResult:
        """Handle LAUNCH_APP actions."""
        return self.backend.launch_app(request.target, request.args or None)

    def _handle_open_url(self, request: ActionRequest) -> ActionResult:
        """Handle OPEN_URL actions."""
        return self.backend.open_url(request.target)

    def _handle_shell(self, request: ActionRequest) -> ActionResult:
        """Handle SHELL_COMMAND actions routed through [ACTION] tags."""
        return self.execute_shell(request.target, from_llm=True)

    def _handle_system_info(self, request: ActionRequest) -> ActionResult:
        """Handle SYSTEM_INFO actions."""
        try:
            info = self.backend.get_system_info()
            lines = [f"  {k}: {v}" for k, v in info.items()]
            output = "System Information:\n" + "\n".join(lines)
            return ActionResult(
                success=True,
                message=output,
                output=output,
                action_type=ActionType.SYSTEM_INFO,
                risk_level=RiskLevel.LOW,
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Error getting system info: {e}",
                error=str(e),
                action_type=ActionType.SYSTEM_INFO,
            )

    def _handle_notification(self, request: ActionRequest) -> ActionResult:
        """Handle NOTIFICATION actions."""
        title = request.target
        message = request.args[0] if request.args else ""
        return self.backend.notify(title, message)

    # ── Utilities ───────────────────────────────────────────────────────

    def is_dangerous(self, command: str) -> bool:
        """Quick check: is this command HIGH or CRITICAL risk?"""
        return self.safety.is_dangerous(command)
