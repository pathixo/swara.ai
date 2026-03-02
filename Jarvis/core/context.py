"""
Context Module — Task-Aware Context Management
================================================
Gathers and manages environmental context to help the LLM understand
the user's project, system, and state.
"""

import os
import logging
import platform
from typing import Optional

from Jarvis.core.system import get_backend, SystemBackend

logger = logging.getLogger("jarvis.context")


class ContextManager:
    """
    Gathers environmental context for injection into LLM prompts.
    Provides info about the current directory, project structure, and system.
    """

    def __init__(self, backend: Optional[SystemBackend] = None):
        self._backend = backend or get_backend()
        self.workspace_root = os.path.abspath(os.getcwd())
        logger.info("ContextManager initialized | root=%s", self.workspace_root)

    def get_full_context(self) -> str:
        """
        Gathers all available context into a single formatted string.
        """
        sections = [
            self._get_system_section(),
            self._get_directory_section(),
            self._get_project_structure_section(),
        ]
        return "\n\n".join(sections)

    def _get_system_section(self) -> str:
        """System-level context (OS, User, etc.)."""
        try:
            info = self._backend.get_system_info()
        except Exception:
            info = {}
        return (
            "## System Context\n"
            f"- OS: {info.get('os', 'Unknown')} {info.get('version', '')}\n"
            f"- Hostname: {info.get('hostname', 'Unknown')}\n"
            f"- User: {info.get('username', 'Unknown')}\n"
            f"- Platform: {platform.system()} ({platform.machine()})"
        )

    def _get_directory_section(self) -> str:
        """Current working directory context."""
        cwd = os.getcwd()
        return (
            "## Directory Context\n"
            f"- Current Working Directory: `{cwd}`\n"
            f"- Workspace Root: `{self.workspace_root}`"
        )

    def _get_project_structure_section(self) -> str:
        """Brief overview of files in the current directory."""
        try:
            items = os.listdir(".")
            # Filter out hidden files and common ignore folders
            ignored = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", ".idea", ".vscode"}
            filtered = [f for f in items if f not in ignored and not f.startswith(".")]

            # Limit to top 20 items to save tokens
            preview = filtered[:20]
            files_str = "\n".join([f"- {f}" for f in preview])

            count_str = f" (showing {len(preview)} of {len(filtered)} items)" if len(filtered) > 20 else ""

            return "## Project Structure Preview" + count_str + "\n" + files_str
        except Exception as e:
            return f"## Project Structure Preview\n- Error gathering file list: {e}"

    def update_root(self, path: str):
        """Update the perceived workspace root."""
        if os.path.exists(path):
            self.workspace_root = os.path.abspath(path)
