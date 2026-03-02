"""
System Package — OS Abstraction Layer
=======================================
Provides a clean interface between Jarvis and the operating system.

Usage:
    from Jarvis.core.system import get_backend, ActionRouter

    backend = get_backend()
    router = ActionRouter(backend)
    result = router.execute_shell("dir")
"""

from Jarvis.core.system.actions import (
    ActionResult,
    ShellResult,
    ActionRequest,
    ActionType,
    RiskLevel,
)
from Jarvis.core.system.backend import SystemBackend
from Jarvis.core.system.windows import WindowsBackend
from Jarvis.core.system.app_registry import AppRegistry, AppEntry
from Jarvis.core.system.safety import SafetyEngine
from Jarvis.core.system.action_router import ActionRouter, extract_actions


def get_backend() -> SystemBackend:
    """
    Factory: return the correct SystemBackend for the current platform.
    Currently only Windows is supported.
    """
    import platform
    system = platform.system().lower()

    if system == "windows":
        return WindowsBackend()
    else:
        raise NotImplementedError(
            f"Platform '{system}' is not yet supported. "
            "Contributions welcome! Implement SystemBackend for your OS."
        )


__all__ = [
    "get_backend",
    "SystemBackend",
    "WindowsBackend",
    "ActionRouter",
    "ActionResult",
    "ShellResult",
    "ActionRequest",
    "ActionType",
    "RiskLevel",
    "AppRegistry",
    "AppEntry",
    "SafetyEngine",
    "extract_actions",
]
