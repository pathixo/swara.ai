"""
Terminal Colors — ANSI color utilities for Jarvis console output.
=================================================================
Uses colorama for Windows compatibility. Falls back gracefully
if colorama is not installed.

Color scheme:
  - Cyan        → User input / commands heard
  - Green       → AI responses / success
  - Yellow      → Shell commands being executed
  - Magenta     → Shell output / results
  - Red         → Errors
  - Blue        → System info / status
  - Dark gray   → Debug / timing info
  - White       → General text
"""

import os
import sys
import ctypes


# ─────────────── Force-enable ANSI on Windows ───────────────────────────────

def _enable_windows_ansi():
    """
    Enable ANSI escape code processing on Windows 10+ console.
    Uses three strategies for maximum compatibility:
      1. ctypes: SetConsoleMode with ENABLE_VIRTUAL_TERMINAL_PROCESSING
      2. os.system(''): Known trick that activates ANSI on Win10+
      3. colorama: Fallback that converts ANSI to Win32 API calls
    """
    if sys.platform != "win32":
        return True

    # Strategy 1: Direct Win32 API — most reliable
    try:
        kernel32 = ctypes.windll.kernel32
        # STD_OUTPUT_HANDLE = -11
        handle = kernel32.GetStdHandle(-11)
        # Get current mode
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        # ENABLE_PROCESSED_OUTPUT = 0x0001
        new_mode = mode.value | 0x0004 | 0x0001
        result = kernel32.SetConsoleMode(handle, new_mode)
        if result:
            return True
    except Exception:
        pass

    # Strategy 2: os.system trick — works on many Win10+ setups
    try:
        os.system("")
    except Exception:
        pass

    # Strategy 3: colorama as fallback
    try:
        import colorama
        colorama.init(convert=True, strip=False)
        return True
    except ImportError:
        pass

    return True  # Assume modern terminal, try anyway


# Run at import time
_enable_windows_ansi()


# ─────────────────────────── ANSI Codes ─────────────────────────────────────

class _Colors:
    """ANSI escape codes for terminal coloring."""
    RESET     = "\033[0m"
    BOLD      = "\033[1m"
    DIM       = "\033[2m"
    ITALIC    = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground
    BLACK     = "\033[30m"
    RED       = "\033[31m"
    GREEN     = "\033[32m"
    YELLOW    = "\033[33m"
    BLUE      = "\033[34m"
    MAGENTA   = "\033[35m"
    CYAN      = "\033[36m"
    WHITE     = "\033[37m"
    GRAY      = "\033[90m"

    # Bright foreground
    BRIGHT_RED     = "\033[91m"
    BRIGHT_GREEN   = "\033[92m"
    BRIGHT_YELLOW  = "\033[93m"
    BRIGHT_BLUE    = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN    = "\033[96m"
    BRIGHT_WHITE   = "\033[97m"


C = _Colors()

# Always enable colors — we force ANSI support above
_USE_COLOR = not os.getenv("NO_COLOR")


def _wrap(color: str, text: str) -> str:
    """Wrap text with color codes."""
    if not _USE_COLOR:
        return text
    return f"{color}{text}{C.RESET}"


# ─────────────────────────── Public API ─────────────────────────────────────

def user_input(text: str) -> str:
    """Style for user's spoken/typed command. Bright cyan + bold."""
    return _wrap(f"{C.BOLD}{C.BRIGHT_CYAN}", text)


def ai_response(text: str) -> str:
    """Style for AI-generated text responses. Bright green."""
    return _wrap(C.BRIGHT_GREEN, text)


def shell_cmd(text: str) -> str:
    """Style for shell commands being executed. Bold yellow."""
    return _wrap(f"{C.BOLD}{C.BRIGHT_YELLOW}", text)


def shell_output(text: str) -> str:
    """Style for shell command output/results. Magenta."""
    return _wrap(C.MAGENTA, text)


def error(text: str) -> str:
    """Style for error messages. Bright red."""
    return _wrap(C.BRIGHT_RED, text)


def warning(text: str) -> str:
    """Style for warning messages. Yellow."""
    return _wrap(C.YELLOW, text)


def info(text: str) -> str:
    """Style for system info and status. Bright blue."""
    return _wrap(C.BRIGHT_BLUE, text)


def debug(text: str) -> str:
    """Style for debug/timing info. Dark gray."""
    return _wrap(C.GRAY, text)


def success(text: str) -> str:
    """Style for success messages. Bold bright green."""
    return _wrap(f"{C.BOLD}{C.BRIGHT_GREEN}", text)


def header(text: str) -> str:
    """Style for section headers/banners. Bold bright white."""
    return _wrap(f"{C.BOLD}{C.BRIGHT_WHITE}", text)


def label(tag: str, text: str, color: str = C.BRIGHT_BLUE) -> str:
    """Format a labeled message: [TAG] text."""
    tag_str = _wrap(f"{C.BOLD}{color}", f"[{tag}]")
    return f"{tag_str} {text}"


def divider(char: str = "─", width: int = 50) -> str:
    """Colored horizontal divider line."""
    return _wrap(C.GRAY, char * width)


# ─────────────────── Convenience Print Functions ────────────────────────────

def print_user(text: str) -> None:
    """Print user input styled."""
    print(label("YOU", user_input(text), C.BRIGHT_CYAN))


def print_ai(text: str) -> None:
    """Print AI response styled."""
    print(label("JARVIS", ai_response(text), C.BRIGHT_GREEN))


def print_shell(cmd: str) -> None:
    """Print shell command being executed."""
    print(label("EXEC", shell_cmd(cmd), C.BRIGHT_YELLOW))


def print_shell_output(text: str) -> None:
    """Print shell output."""
    print(shell_output(text))


def print_error(text: str) -> None:
    """Print error message."""
    print(label("ERROR", error(text), C.BRIGHT_RED))


def print_warning(text: str) -> None:
    """Print warning message."""
    print(label("WARN", warning(text), C.YELLOW))


def print_info(text: str) -> None:
    """Print info message."""
    print(label("INFO", info(text), C.BRIGHT_BLUE))


def print_debug(text: str) -> None:
    """Print debug/timing message."""
    print(debug(text))


def print_ai_start() -> None:
    """Print the [JARVIS] prefix for a streaming response (no newline)."""
    tag_str = _wrap(f"{C.BOLD}{C.BRIGHT_GREEN}", "[JARVIS]")
    print(f"{tag_str} ", end="", flush=True)


def print_ai_token(text: str) -> None:
    """Print a single streaming token inline (no newline, no prefix)."""
    print(ai_response(text), end="", flush=True)


def print_ai_end() -> None:
    """End a streaming response with a newline."""
    print()


def print_status(tag: str, text: str) -> None:
    """Print a status label."""
    print(label(tag, text, C.BRIGHT_MAGENTA))
