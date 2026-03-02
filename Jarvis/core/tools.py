"""
Tools Module — Sandboxed File & Terminal Operations
=====================================================
Implements workspace-sandboxed file system and command operations.
Delegates all OS interactions through the SystemBackend abstraction.
"""

import os
from typing import Optional

from Jarvis.core.system.backend import SystemBackend


class Tools:
    """
    Implements local tools for file system and terminal operations.
    Enforces sandboxing within the 'workspace' directory.
    Delegates to SystemBackend for all OS interactions.
    """
    def __init__(self, backend: Optional[SystemBackend] = None):
        # Define workspace directory relative to project root
        self.workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../workspace"))
        if not os.path.exists(self.workspace_dir):
            os.makedirs(self.workspace_dir)
            print(f"Created workspace directory at: {self.workspace_dir}")

        # SystemBackend for OS operations (lazy-initialized if not provided)
        self._backend = backend

    @property
    def backend(self) -> SystemBackend:
        """Lazy-init backend if not provided at construction time."""
        if self._backend is None:
            from Jarvis.core.system import get_backend
            self._backend = get_backend()
        return self._backend

    def _is_safe_path(self, filepath):
        """
        Ensures the path is within the workspace directory.
        """
        try:
            # Resolve absolute path
            abs_path = os.path.abspath(os.path.join(self.workspace_dir, filepath))
            # Check if it starts with workspace_dir
            return abs_path.startswith(self.workspace_dir), abs_path
        except Exception:
            return False, None

    def execute_terminal_command(self, command):
        """
        Executes a shell command via SystemBackend and returns output.
        """
        result = self.backend.run_shell(command, cwd=self.workspace_dir)
        if result.success:
            return f"Output:\n{result.stdout}" if result.stdout else "Command executed."
        else:
            return f"Error:\n{result.error}" if result.error else f"Error:\n{result.message}"
    
    def list_files(self, directory="."):
        """
        Lists files in the specified directory (relative to workspace).
        """
        safe, abs_path = self._is_safe_path(directory)
        if not safe:
            return "Error: Access denied. Path is outside workspace."
            
        result = self.backend.list_dir(abs_path)
        if result.success:
            return result.output
        return f"Error listing files: {result.error}"
    
    def read_file(self, filepath):
        """
        Reads content of a text file (relative to workspace).
        """
        safe, abs_path = self._is_safe_path(filepath)
        if not safe:
            return "Error: Access denied. Path is outside workspace."

        result = self.backend.read_file(abs_path)
        if result.success:
            return result.output
        return f"Error reading file: {result.error}"

    def write_file(self, filepath, content):
        """
        Writes content to a file (relative to workspace). Overwrites if exists.
        """
        safe, abs_path = self._is_safe_path(filepath)
        if not safe:
            return "Error: Access denied. Path is outside workspace."

        result = self.backend.write_file(abs_path, content)
        if result.success:
            return f"File '{filepath}' written successfully."
        return f"Error writing file: {result.error}"
