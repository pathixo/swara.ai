"""
Windows Backend — Windows-Specific OS Implementation
======================================================
Concrete implementation of SystemBackend for Windows.
Handles all Windows-specific subprocess calls, app launching,
file operations, and system queries.

This is the ONLY file that should contain Windows-specific code.
"""

import logging
import os
import platform
import subprocess
import webbrowser
from typing import Optional

from Jarvis.core.system.actions import ActionResult, ShellResult, ActionType, RiskLevel
from Jarvis.core.system.backend import SystemBackend
from Jarvis.core.system.app_registry import AppRegistry, AppEntry

logger = logging.getLogger("jarvis.windows_backend")


class WindowsBackend(SystemBackend):
    """
    Windows-specific implementation of the SystemBackend.

    All PowerShell/cmd subprocess calls are centralized here.
    """

    def __init__(self, app_registry: Optional[AppRegistry] = None):
        self._app_registry = app_registry or AppRegistry()
        logger.info("WindowsBackend initialized | apps=%d", self._app_registry.count)

    # ── Application Management ──────────────────────────────────────────

    def launch_app(
        self,
        app_name: str,
        args: Optional[list[str]] = None,
    ) -> ActionResult:
        """
        Launch an application by name, resolving through the AppRegistry.

        Priority:
        1. AppRegistry lookup (exact + fuzzy match)
        2. Direct Start-Process fallback for unknown apps
        """
        # Try registry first
        entry = self._app_registry.resolve(app_name)
        if entry:
            return self._launch_registered_app(entry, args)

        # Fallback: try launching directly via Start-Process
        logger.info("App '%s' not in registry, trying direct launch", app_name)
        return self._launch_direct(app_name, args)

    def _launch_registered_app(
        self,
        entry: AppEntry,
        args: Optional[list[str]] = None,
    ) -> ActionResult:
        """Launch a registered app using its configured method."""
        try:
            target = entry.launch_target
            method = entry.launch_method

            if method == "url":
                # Open in default browser
                webbrowser.open(target)
                return ActionResult(
                    success=True,
                    message=f"Opening {entry.display_name}.",
                    output=f"Opened URL: {target}",
                    action_type=ActionType.LAUNCH_APP,
                    risk_level=RiskLevel.LOW,
                )

            elif method == "uri":
                # URI scheme (spotify:, calculator:, ms-settings:, etc.)
                os.startfile(target)
                return ActionResult(
                    success=True,
                    message=f"Opening {entry.display_name}.",
                    output=f"Launched URI: {target}",
                    action_type=ActionType.LAUNCH_APP,
                    risk_level=RiskLevel.LOW,
                )

            elif method == "exe":
                # Executable launch via Start-Process
                cmd_parts = ["powershell", "-NoProfile", "-NonInteractive",
                             "-Command", f"Start-Process '{target}'"]
                if args:
                    arg_str = " ".join(f"'{a}'" for a in args)
                    cmd_parts = ["powershell", "-NoProfile", "-NonInteractive",
                                 "-Command", f"Start-Process '{target}' -ArgumentList {arg_str}"]

                subprocess.Popen(
                    cmd_parts,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                return ActionResult(
                    success=True,
                    message=f"Opening {entry.display_name}.",
                    output=f"Launched: {target}",
                    action_type=ActionType.LAUNCH_APP,
                    risk_level=RiskLevel.LOW,
                )

            else:
                return ActionResult(
                    success=False,
                    message=f"Unknown launch method '{method}' for {entry.display_name}.",
                    error=f"Unsupported launch_method: {method}",
                    action_type=ActionType.LAUNCH_APP,
                )

        except FileNotFoundError:
            return ActionResult(
                success=False,
                message=f"{entry.display_name} doesn't appear to be installed.",
                error=f"FileNotFoundError launching {entry.launch_target}",
                action_type=ActionType.LAUNCH_APP,
            )
        except Exception as e:
            logger.error("Failed to launch %s: %s", entry.display_name, e)
            return ActionResult(
                success=False,
                message=f"Error opening {entry.display_name}: {e}",
                error=str(e),
                action_type=ActionType.LAUNCH_APP,
            )

    def _launch_direct(
        self,
        app_name: str,
        args: Optional[list[str]] = None,
    ) -> ActionResult:
        """Fallback: try launching by name directly via Start-Process."""
        try:
            cmd = f"Start-Process '{app_name}'"
            if args:
                arg_str = " ".join(f"'{a}'" for a in args)
                cmd = f"Start-Process '{app_name}' -ArgumentList {arg_str}"

            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return ActionResult(
                success=True,
                message=f"Attempting to open {app_name}.",
                output=f"Direct launch: {cmd}",
                action_type=ActionType.LAUNCH_APP,
                risk_level=RiskLevel.MEDIUM,
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Could not find or open '{app_name}'.",
                error=str(e),
                action_type=ActionType.LAUNCH_APP,
            )

    # ── URL Opening ─────────────────────────────────────────────────────

    def open_url(self, url: str) -> ActionResult:
        """Open a URL in the default browser."""
        try:
            # Ensure URL has a protocol
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"

            webbrowser.open(url)
            return ActionResult(
                success=True,
                message=f"Opening {url}.",
                output=f"Opened: {url}",
                action_type=ActionType.OPEN_URL,
                risk_level=RiskLevel.LOW,
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to open URL: {url}",
                error=str(e),
                action_type=ActionType.OPEN_URL,
            )

    # ── Shell Execution ─────────────────────────────────────────────────

    def run_shell(
        self,
        command: str,
        timeout: int = 30,
        cwd: Optional[str] = None,
        from_llm: bool = False,
    ) -> ShellResult:
        """
        Execute a command in PowerShell and return structured output.

        This method centralizes ALL subprocess.run calls for shell commands.
        """
        logger.info("Shell exec%s: %s", " (from LLM)" if from_llm else "", command)

        try:
            shell_args = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]

            # WSL routing
            if command.startswith("wsl -- "):
                shell_args = ["wsl", "--", command[7:]]

            result = subprocess.run(
                shell_args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            # Filter PowerShell noise from stderr
            if stderr and self._is_ps_noise(stderr):
                stderr = ""

            # Build combined output
            output = stdout
            error = ""
            if stderr:
                error = stderr
                if not output:
                    output = f"Error: {stderr}"
                else:
                    output += f"\nError: {stderr}"

            if not output:
                output = "Command executed."

            success = result.returncode == 0 and not error

            return ShellResult(
                success=success,
                message=output if len(output) <= 300 else output[:300] + "... (truncated)",
                output=output,
                stdout=stdout,
                stderr=stderr,
                error=error,
                return_code=result.returncode,
                command=command,
                action_type=ActionType.SHELL_COMMAND,
                risk_level=RiskLevel.MEDIUM,
            )

        except subprocess.TimeoutExpired:
            return ShellResult(
                success=False,
                message=f"Command timed out after {timeout} seconds.",
                error="TimeoutExpired",
                timed_out=True,
                command=command,
                action_type=ActionType.SHELL_COMMAND,
            )
        except FileNotFoundError:
            return ShellResult(
                success=False,
                message="Error: PowerShell not found. Is it installed?",
                error="PowerShell not found",
                command=command,
                action_type=ActionType.SHELL_COMMAND,
            )
        except Exception as e:
            logger.error("Shell execution error: %s", e)
            return ShellResult(
                success=False,
                message=f"Shell Error: {e}",
                error=str(e),
                command=command,
                action_type=ActionType.SHELL_COMMAND,
            )

    @staticmethod
    def _is_ps_noise(stderr: str) -> bool:
        """Filter out non-error PowerShell stderr output."""
        import re
        noise_patterns = [
            r"^WARNING:",
            r"^VERBOSE:",
            r"^DEBUG:",
            r"^ProgressPreference",
        ]
        for pattern in noise_patterns:
            if re.search(pattern, stderr, re.IGNORECASE):
                return True
        return False

    # ── File System ─────────────────────────────────────────────────────

    def file_exists(self, path: str) -> bool:
        """Check if a file or directory exists."""
        return os.path.exists(path)

    def list_dir(self, path: str) -> ActionResult:
        """List contents of a directory."""
        try:
            if not os.path.exists(path):
                return ActionResult(
                    success=False,
                    message=f"Directory not found: {path}",
                    error="Path does not exist",
                    action_type=ActionType.FILE_LIST,
                )
            entries = os.listdir(path)
            return ActionResult(
                success=True,
                message=f"Found {len(entries)} items.",
                output="\n".join(entries),
                action_type=ActionType.FILE_LIST,
                risk_level=RiskLevel.LOW,
            )
        except PermissionError:
            return ActionResult(
                success=False,
                message=f"Access denied: {path}",
                error="PermissionError",
                action_type=ActionType.FILE_LIST,
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Error listing directory: {e}",
                error=str(e),
                action_type=ActionType.FILE_LIST,
            )

    def read_file(self, path: str) -> ActionResult:
        """Read text content of a file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return ActionResult(
                success=True,
                message=f"Read {len(content)} characters.",
                output=content,
                action_type=ActionType.FILE_READ,
                risk_level=RiskLevel.LOW,
            )
        except FileNotFoundError:
            return ActionResult(
                success=False,
                message=f"File not found: {path}",
                error="FileNotFoundError",
                action_type=ActionType.FILE_READ,
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Error reading file: {e}",
                error=str(e),
                action_type=ActionType.FILE_READ,
            )

    def write_file(self, path: str, content: str) -> ActionResult:
        """Write content to a file (creates parent dirs if needed)."""
        try:
            parent = os.path.dirname(path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return ActionResult(
                success=True,
                message=f"File written: {os.path.basename(path)}",
                output=f"Wrote {len(content)} characters to {path}",
                action_type=ActionType.FILE_WRITE,
                risk_level=RiskLevel.MEDIUM,
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Error writing file: {e}",
                error=str(e),
                action_type=ActionType.FILE_WRITE,
            )

    # ── System Information ──────────────────────────────────────────────

    def get_system_info(self) -> dict:
        """Return system information dictionary."""
        import psutil
        mem = psutil.virtual_memory()
        return {
            "os": platform.system(),
            "version": platform.version(),
            "release": platform.release(),
            "hostname": platform.node(),
            "cpu": platform.processor() or "Unknown",
            "cpu_count": os.cpu_count(),
            "memory_total_gb": round(mem.total / (1024**3), 1),
            "memory_available_gb": round(mem.available / (1024**3), 1),
            "username": os.getenv("USERNAME", "Unknown"),
            "architecture": platform.machine(),
        }

    def get_env(self, key: str, default: str = "") -> str:
        """Read an environment variable."""
        return os.getenv(key, default)

    # ── Notifications ───────────────────────────────────────────────────

    def notify(self, title: str, message: str) -> ActionResult:
        """Show a Windows toast notification via PowerShell."""
        try:
            # Use PowerShell BurntToast or built-in notification
            ps_script = (
                f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                f"ContentType = WindowsRuntime] > $null; "
                f"$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                f"[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                f"$text = $template.GetElementsByTagName('text'); "
                f"$text.Item(0).AppendChild($template.CreateTextNode('{title}')) > $null; "
                f"$text.Item(1).AppendChild($template.CreateTextNode('{message}')) > $null; "
                f"$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
                f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Jarvis').Show($toast)"
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return ActionResult(
                success=True,
                message="Notification sent.",
                action_type=ActionType.NOTIFICATION,
                risk_level=RiskLevel.LOW,
            )
        except Exception as e:
            logger.warning("Notification failed: %s", e)
            return ActionResult(
                success=False,
                message=f"Notification error: {e}",
                error=str(e),
                action_type=ActionType.NOTIFICATION,
            )

    # ── Platform Metadata ───────────────────────────────────────────────

    @property
    def platform_name(self) -> str:
        return "windows"

    @property
    def shell_name(self) -> str:
        return "powershell"
