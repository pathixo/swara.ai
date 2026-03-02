"""
System Backend — Abstract OS Interface
========================================
Defines the abstract base class that ALL OS interactions must go through.
Concrete implementations (WindowsBackend, future LinuxBackend, etc.)
inherit from this and provide platform-specific logic.

No code in Jarvis should ever call subprocess, os.startfile, or similar
OS primitives directly — everything routes through a SystemBackend.
"""

from abc import ABC, abstractmethod
from typing import Optional

from Jarvis.core.system.actions import ActionResult, ShellResult


class SystemBackend(ABC):
    """
    Abstract base class for OS interactions.

    Every platform implements this interface. The rest of Jarvis only
    talks to SystemBackend — never to the OS directly.
    """

    # ── Application Management ──────────────────────────────────────────

    @abstractmethod
    def launch_app(
        self,
        app_name: str,
        args: Optional[list[str]] = None,
    ) -> ActionResult:
        """
        Launch an application by its logical name.

        The backend should resolve the name via the AppRegistry first,
        then fall back to OS-level discovery if not found.

        Args:
            app_name: Canonical or alias name (e.g. "chrome", "spotify").
            args:     Optional arguments to pass to the application.

        Returns:
            ActionResult with success/failure info.
        """
        ...

    @abstractmethod
    def open_url(self, url: str) -> ActionResult:
        """
        Open a URL in the system's default web browser.

        Args:
            url: Full URL including protocol (https://...).

        Returns:
            ActionResult.
        """
        ...

    # ── Shell Execution ─────────────────────────────────────────────────

    @abstractmethod
    def run_shell(
        self,
        command: str,
        timeout: int = 30,
        cwd: Optional[str] = None,
        from_llm: bool = False,
    ) -> ShellResult:
        """
        Execute a shell command and return structured output.

        Args:
            command:  The command string to execute.
            timeout:  Max seconds before killing the process.
            cwd:      Working directory (None = default).
            from_llm: True if command originated from LLM output.

        Returns:
            ShellResult with stdout, stderr, return code, etc.
        """
        ...

    # ── File System ─────────────────────────────────────────────────────

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """Check whether a file or directory exists at the given path."""
        ...

    @abstractmethod
    def list_dir(self, path: str) -> ActionResult:
        """
        List contents of a directory.

        Returns:
            ActionResult where output contains newline-separated filenames.
        """
        ...

    @abstractmethod
    def read_file(self, path: str) -> ActionResult:
        """
        Read and return the text content of a file.

        Returns:
            ActionResult where output contains the file content.
        """
        ...

    @abstractmethod
    def write_file(self, path: str, content: str) -> ActionResult:
        """
        Write content to a file (creates or overwrites).

        Returns:
            ActionResult.
        """
        ...

    # ── System Information ──────────────────────────────────────────────

    @abstractmethod
    def get_system_info(self) -> dict:
        """
        Return a dictionary of system information.

        Expected keys: os, version, hostname, cpu, memory_gb, username.
        """
        ...

    @abstractmethod
    def get_env(self, key: str, default: str = "") -> str:
        """Read an environment variable."""
        ...

    # ── Notifications ───────────────────────────────────────────────────

    @abstractmethod
    def notify(self, title: str, message: str) -> ActionResult:
        """
        Show an OS-native notification/toast.

        Args:
            title:   Notification title.
            message: Notification body text.

        Returns:
            ActionResult.
        """
        ...

    # ── Platform Info ───────────────────────────────────────────────────

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform identifier (e.g. 'windows', 'linux', 'macos')."""
        ...

    @property
    @abstractmethod
    def shell_name(self) -> str:
        """Return the default shell name (e.g. 'powershell', 'bash')."""
        ...
