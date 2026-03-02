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
    r"(?:```(?:[a-zA-Z]*)?\s*)?\[\s*ACTION\s*\](.*?)\s*\[\s*/\s*ACTION\s*\](?:\s*```)?", re.DOTALL | re.IGNORECASE
)

# Legacy: [SHELL]command[/SHELL]
SHELL_TAG_PATTERN = re.compile(
    r"(?:```(?:[a-zA-Z]*)?\s*)?\[\s*SHELL\s*\](.*?)\s*\[\s*/\s*SHELL\s*\](?:\s*```)?", re.DOTALL | re.IGNORECASE
)

# New: [EXEC_CODE]python_code[/EXEC_CODE]
EXEC_CODE_TAG_PATTERN = re.compile(
    r"(?:```(?:python)?\s*)?\[\s*EXEC_CODE\s*\](.*?)\s*\[\s*/\s*EXEC_CODE\s*\](?:\s*```)?", re.DOTALL | re.IGNORECASE
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
        "new_tab": ActionType.OPEN_URL,   # Alias for opening a URL/browser
        "search": ActionType.OPEN_URL,    # Redirect to Google search
        "shell": ActionType.SHELL_COMMAND,
        "run": ActionType.SHELL_COMMAND,
        "system_info": ActionType.SYSTEM_INFO,
        "sysinfo": ActionType.SYSTEM_INFO,
        "notify": ActionType.NOTIFICATION,
        "notification": ActionType.NOTIFICATION,
        "play_music": ActionType.PLAY_MUSIC,
        "music": ActionType.PLAY_MUSIC,
        "play": ActionType.PLAY_MUSIC,
        "exec_code": ActionType.EXEC_CODE,
        "coding": ActionType.EXEC_CODE,
        "code_exec": ActionType.EXEC_CODE,
        "search_system": ActionType.SEARCH_SYSTEM,
    }

    action_type = type_map.get(action_str)
    if action_type is None:
        logger.warning("Unknown action type: '%s'", action_str)
        return None

    # Handle 'search' alias by formatting into a Google URL
    if action_str == "search":
        from urllib.parse import quote
        target = f"https://www.google.com/search?q={quote(target)}"

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
    Extract [ACTION], [SHELL], and [EXEC_CODE] tags from an LLM response.

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

    # Parse [EXEC_CODE] tags
    for match in EXEC_CODE_TAG_PATTERN.finditer(llm_response):
        code = match.group(1).strip()
        if code:
            actions.append(ActionRequest(
                action_type=ActionType.EXEC_CODE,
                target=code,
                raw_text=f"exec_code: {code[:30]}..."
            ))

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
        # 1. Assess base risk for this action type
        risk = self.safety.assess_action(request.action_type)
        
        # 2. Block RED tier actions (CRITICAL)
        if risk == RiskLevel.CRITICAL:
            msg = f"Action blocked (RED tier): {request.action_type.value}"
            logger.warning(msg)
            self.safety.log_action(
                action_type=request.action_type.value,
                target=request.target,
                risk=risk,
                outcome="blocked",
                from_llm=True,
            )
            return ActionResult(
                success=False,
                message=msg,
                error="Action blocked by safety policy.",
                action_type=request.action_type.value,
                risk_level=risk.value,
            )

        # 3. Require confirmation for YELLOW tier actions (MEDIUM/HIGH)
        if risk in (RiskLevel.MEDIUM, RiskLevel.HIGH):
            desc = f"Action: {request.action_type.value} -> {request.target[:50]}"
            approved = self._request_confirmation(desc, f"Tier: YELLOW ({risk.value})")
            if not approved:
                logger.info("Action denied by user: %s", request.action_type.value)
                self.safety.log_action(
                    action_type=request.action_type.value,
                    target=request.target,
                    risk=risk,
                    outcome="denied",
                    from_llm=True,
                )
                return ActionResult(
                    success=False,
                    message=f"Action cancelled (requires confirmation): {request.action_type.value}",
                    error="User denied",
                    action_type=request.action_type.value,
                    risk_level=risk.value,
                )

        handlers = {
            ActionType.LAUNCH_APP:    self._handle_launch_app,
            ActionType.OPEN_URL:      self._handle_open_url,
            ActionType.SHELL_COMMAND: self._handle_shell,
            ActionType.SYSTEM_INFO:   self._handle_system_info,
            ActionType.NOTIFICATION:  self._handle_notification,
            ActionType.PLAY_MUSIC:    self._handle_play_music,
            ActionType.EXEC_CODE:     self._handle_exec_code,
            ActionType.SEARCH_SYSTEM: self._handle_search_system,
            ActionType.FILE_READ:     self._handle_file_read,
            ActionType.FILE_WRITE:    self._handle_file_write,
            ActionType.FILE_LIST:     self._handle_file_list,
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
            target=request.target[:100], # Truncate for log
            risk=RiskLevel(result.risk_level) if result.risk_level else risk,
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

        Safety pipeline (3-Tier Sandbox):
          1. RED (CRITICAL) → always blocked
          2. YELLOW (MEDIUM/HIGH) → requires user confirmation
          3. GREEN (LOW) → execute directly
        """
        risk, risk_desc = self.safety.assess_command(command)

        # 1. Block RED tier commands (CRITICAL)
        if risk == RiskLevel.CRITICAL:
            logger.warning("Command blocked (RED): %s — %s", command, risk_desc)
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

        # 2. Require confirmation for YELLOW tier commands (MEDIUM/HIGH)
        if risk in (RiskLevel.MEDIUM, RiskLevel.HIGH):
            approved = self._request_confirmation(command, f"Tier: YELLOW ({risk.value}) - {risk_desc}")
            if not approved:
                logger.info("Command denied by user: %s", command)
                self.safety.log_action(
                    action_type=ActionType.SHELL_COMMAND.value,
                    target=command,
                    risk=risk,
                    outcome="denied",
                    from_llm=from_llm,
                )
                return ShellResult(
                    success=False,
                    message=f"Command cancelled (requires confirmation): `{command}`",
                    error=f"User denied: {risk_desc}",
                    command=command,
                    action_type=ActionType.SHELL_COMMAND.value,
                    risk_level=risk.value,
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

    def _handle_exec_code(self, request: ActionRequest) -> ActionResult:
        """Handle EXEC_CODE actions."""
        # Note: Confirmation is now centralized in execute_action()
        return self.backend.exec_python(request.target)

    def _handle_file_read(self, request: ActionRequest) -> ActionResult:
        """Handle FILE_READ actions."""
        return self.backend.read_file(request.target)

    def _handle_file_write(self, request: ActionRequest) -> ActionResult:
        """Handle FILE_WRITE actions."""
        content = request.args[0] if request.args else ""
        return self.backend.write_file(request.target, content)

    def _handle_file_list(self, request: ActionRequest) -> ActionResult:
        """Handle FILE_LIST actions."""
        return self.backend.list_dir(request.target)

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

    def _handle_play_music(self, request: ActionRequest) -> ActionResult:
        """
        Handle PLAY_MUSIC actions.

        Intent pipeline:
          1. Parse the platform (spotify / youtube) and the song query.
          2. Build the appropriate URI/URL that opens the app AND searches.
          3. Execute — so user hears the song, not just opens an app.
        """
        from urllib.parse import quote

        raw = request.target.strip()
        if not raw:
            return ActionResult(
                success=False,
                message="I need a song or query to search for, sir.",
                error="Empty query",
                action_type=ActionType.MEDIA_SEARCH_FAILED,
            )

        raw_lower = raw.lower()

        # Noise words to strip from the search query
        _NOISE = [
            "play", "search", "find", "look up", "on spotify", "on youtube",
            "in spotify", "in youtube", "spotify", "youtube", "music", "song",
            "a song", "the song", "video", "the video",
        ]

        # Detect platform
        use_youtube = any(p in raw_lower for p in ["youtube", "video", "watch"])

        # Build clean query by stripping noise from original (case-insensitive)
        clean = raw
        for noise in _NOISE:
            clean = re.sub(rf"\b{re.escape(noise)}\b", "", clean, flags=re.IGNORECASE)
        # Collapse multiple spaces
        clean = " ".join(clean.split()).strip()

        if not clean:
            clean = raw  # Fallback if everything was stripped

        # ── YouTube pipeline ──────────────────────────────────────────────
        if use_youtube:
            url = f"https://www.youtube.com/results?search_query={quote(clean)}"
            logger.info("PLAY_MUSIC → YouTube search: %s", url)
            result = self.backend.open_url(url)
            result.message = f"Searching YouTube for '{clean}'."
            return result

        # ── Spotify pipeline ──────────────────────────────────────────────
        # The spotify:search: URI opens Spotify and auto-fills the search bar.
        # os.startfile handles this URI scheme on Windows.
        spotify_uri = f"spotify:search:{quote(clean)}"
        logger.info("PLAY_MUSIC → Spotify URI: %s", spotify_uri)
        try:
            import os as _os
            _os.startfile(spotify_uri)
            return ActionResult(
                success=True,
                message=f"Searching Spotify for '{clean}'.",
                output=f"Launched: {spotify_uri}",
                action_type=ActionType.PLAY_MUSIC,
                risk_level=RiskLevel.LOW,
            )
        except FileNotFoundError:
            # Spotify not installed — fall back to web player
            logger.warning("Spotify URI failed (not installed?), falling back to web player")
            url = f"https://open.spotify.com/search/{quote(clean)}"
            result = self.backend.open_url(url)
            result.message = f"Spotify doesn't appear to be installed. Opening the web player and searching for '{clean}'."
            return result
        except Exception as e:
            logger.error("Spotify launch failed: %s", e)
            return ActionResult(
                success=False,
                message=f"Couldn't open Spotify: {e}",
                error=str(e),
                action_type=ActionType.MEDIA_SEARCH_FAILED,
            )

    def _handle_search_system(self, request: ActionRequest) -> ActionResult:
        """Handle SEARCH_SYSTEM actions."""
        query = request.target.strip()
        if not query:
            return ActionResult(
                success=False,
                message="What should I search for, sir?",
                error="Empty query",
                action_type=ActionType.MEDIA_SEARCH_FAILED, # Using this for search errors
            )
            
        # For now, redirect to a local file search via PowerShell if backend doesn't have it
        # In a real implementation, this would call self.backend.search_system(query)
        cmd = f"Get-ChildItem -Path $env:USERPROFILE -Filter '*{query}*' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 10 | Format-Table Name, Directory"
        return self.execute_shell(cmd, from_llm=True)

    # ── Utilities ───────────────────────────────────────────────────────

    def is_dangerous(self, command: str) -> bool:
        """Quick check: is this command HIGH or CRITICAL risk?"""
        return self.safety.is_dangerous(command)
