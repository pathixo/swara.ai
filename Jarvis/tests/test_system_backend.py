"""
Test Suite — OS Abstraction Layer
===================================
Tests for AppRegistry, SafetyEngine, ActionRouter,
TagStreamFilter, and action tag parsing.
"""

import pytest
import os
import json
from unittest.mock import MagicMock, patch

# ── Import the modules under test ──
from Jarvis.core.system.actions import (
    ActionResult, ShellResult, ActionRequest, ActionType, RiskLevel,
)
from Jarvis.core.system.app_registry import AppRegistry, AppEntry
from Jarvis.core.system.safety import SafetyEngine
from Jarvis.core.system.action_router import (
    ActionRouter, parse_action_tag, extract_actions,
)


# ════════════════════════════════════════════════════════════════════════════
#  App Registry Tests
# ════════════════════════════════════════════════════════════════════════════

class TestAppRegistry:
    """Tests for AppRegistry name resolution."""

    @pytest.fixture
    def registry(self):
        """Load the real bundled app registry."""
        return AppRegistry()

    def test_exact_match(self, registry):
        """Canonical name should resolve."""
        entry = registry.resolve("chrome")
        assert entry is not None
        assert entry.display_name == "Google Chrome"

    def test_alias_match(self, registry):
        """Alias should resolve to canonical app."""
        entry = registry.resolve("google chrome")
        assert entry is not None
        assert entry.name == "chrome"

    def test_case_insensitive(self, registry):
        """Resolution is case-insensitive."""
        entry = registry.resolve("SPOTIFY")
        assert entry is not None
        assert entry.name == "spotify"

    def test_fuzzy_match(self, registry):
        """Close misspellings should fuzzy-match."""
        entry = registry.resolve("notepa")  # missing 'd'
        assert entry is not None
        assert entry.name == "notepad"

    def test_unknown_app(self, registry):
        """Unknown apps return None."""
        entry = registry.resolve("xyznonexistent_app_12345")
        assert entry is None

    def test_launch_method_types(self, registry):
        """Verify different launch methods are present."""
        assert registry.resolve("chrome").launch_method == "exe"
        assert registry.resolve("spotify").launch_method == "uri"
        assert registry.resolve("instagram").launch_method == "url"

    def test_categories(self, registry):
        """Registry should have multiple categories."""
        cats = registry.categories()
        assert "browser" in cats
        assert "media" in cats
        assert "system" in cats

    def test_list_by_category(self, registry):
        """Should return apps in a specific category."""
        browsers = registry.list_by_category("browser")
        assert len(browsers) >= 3
        names = [b.name for b in browsers]
        assert "chrome" in names

    def test_count(self, registry):
        """Registry should have 50+ apps."""
        assert registry.count >= 50

    def test_custom_registry_path(self, tmp_path):
        """Test loading from a custom JSON file."""
        custom = {
            "test_app": {
                "display_name": "Test Application",
                "aliases": ["tester"],
                "launch_method": "exe",
                "launch_target": "test.exe",
                "process_name": "test.exe",
                "category": "test",
            }
        }
        path = tmp_path / "custom_apps.json"
        path.write_text(json.dumps(custom))

        reg = AppRegistry(str(path))
        assert reg.count == 1
        assert reg.resolve("tester").display_name == "Test Application"


# ════════════════════════════════════════════════════════════════════════════
#  Safety Engine Tests
# ════════════════════════════════════════════════════════════════════════════

class TestSafetyEngine:
    """Tests for SafetyEngine risk assessment."""

    @pytest.fixture
    def safety(self):
        return SafetyEngine()

    # ── Dangerous commands ──

    def test_format_command_critical(self, safety):
        risk, desc = safety.assess_command("format C:")
        assert risk == RiskLevel.CRITICAL

    def test_diskpart_critical(self, safety):
        risk, _ = safety.assess_command("diskpart")
        assert risk == RiskLevel.CRITICAL

    def test_recursive_delete_high(self, safety):
        risk, _ = safety.assess_command("Remove-Item C:\\temp -Recurse")
        assert risk == RiskLevel.HIGH

    def test_registry_delete_high(self, safety):
        risk, _ = safety.assess_command("reg delete HKLM\\Software\\Test")
        assert risk == RiskLevel.HIGH

    def test_iex_high(self, safety):
        risk, _ = safety.assess_command("Invoke-Expression $code")
        assert risk == RiskLevel.HIGH

    def test_shutdown_high(self, safety):
        risk, _ = safety.assess_command("shutdown /s /t 0")
        assert risk == RiskLevel.HIGH

    # ── Safe commands ──

    def test_safe_dir_list(self, safety):
        risk, _ = safety.assess_command("Get-ChildItem C:\\Users")
        assert risk == RiskLevel.LOW

    def test_safe_date(self, safety):
        risk, _ = safety.assess_command("Get-Date")
        assert risk == RiskLevel.LOW

    def test_safe_echo(self, safety):
        risk, _ = safety.assess_command("echo hello")
        assert risk == RiskLevel.LOW

    # ── Blocking / confirmation ──

    def test_should_block_critical(self, safety):
        blocked, reason = safety.should_block("format C:")
        assert blocked is True

    def test_should_not_block_safe(self, safety):
        blocked, _ = safety.should_block("Get-Date")
        assert blocked is False

    def test_should_confirm_high(self, safety):
        needs, _ = safety.should_confirm("shutdown /s")
        assert needs is True

    def test_is_dangerous(self, safety):
        assert safety.is_dangerous("rm -rf /") is True
        assert safety.is_dangerous("Get-Date") is False

    # ── Blocklist / allowlist ──

    def test_blocklist(self, safety):
        safety.add_to_blocklist("evil_command")
        risk, _ = safety.assess_command("evil_command --force")
        assert risk == RiskLevel.CRITICAL

    def test_allowlist_overrides(self, safety):
        safety.add_to_allowlist(r"shutdown")
        risk, _ = safety.assess_command("shutdown /s")
        assert risk == RiskLevel.LOW  # Allowlisted

    # ── Audit logging ──

    def test_audit_log(self, safety):
        safety.log_action("shell_command", "test_cmd", RiskLevel.LOW, "success")
        log = safety.get_audit_log()
        assert len(log) == 1
        assert log[0]["target"] == "test_cmd"

    # ── Action type defaults ──

    def test_action_type_defaults(self, safety):
        assert safety.assess_action(ActionType.LAUNCH_APP) == RiskLevel.LOW
        assert safety.assess_action(ActionType.SHELL_COMMAND) == RiskLevel.MEDIUM


# ════════════════════════════════════════════════════════════════════════════
#  Action Tag Parsing Tests
# ════════════════════════════════════════════════════════════════════════════

class TestActionTagParsing:
    """Tests for parsing [ACTION] tags."""

    def test_parse_launch_app(self):
        req = parse_action_tag("launch_app: spotify")
        assert req.action_type == ActionType.LAUNCH_APP
        assert req.target == "spotify"

    def test_parse_open_url(self):
        req = parse_action_tag("open_url: https://google.com")
        assert req.action_type == ActionType.OPEN_URL
        assert req.target == "https://google.com"

    def test_parse_system_info(self):
        req = parse_action_tag("system_info")
        assert req.action_type == ActionType.SYSTEM_INFO

    def test_parse_notification(self):
        req = parse_action_tag("notification: Hello | World")
        assert req.action_type == ActionType.NOTIFICATION
        assert req.target == "Hello"
        assert req.args == ["World"]

    def test_parse_shell_via_action(self):
        req = parse_action_tag("shell: Get-Date")
        assert req.action_type == ActionType.SHELL_COMMAND
        assert req.target == "Get-Date"

    def test_parse_unknown_returns_none(self):
        req = parse_action_tag("invalid_type: foo")
        assert req is None

    def test_parse_empty_returns_none(self):
        req = parse_action_tag("")
        assert req is None

    def test_aliases(self):
        """Alternative action type names should work."""
        assert parse_action_tag("open: chrome").action_type == ActionType.LAUNCH_APP
        assert parse_action_tag("browse: https://x.com").action_type == ActionType.OPEN_URL
        assert parse_action_tag("run: dir").action_type == ActionType.SHELL_COMMAND


class TestExtractActions:
    """Tests for extracting both [ACTION] and [SHELL] tags."""

    def test_extract_shell_only(self):
        text = "Here you go.\n[SHELL]Get-Date[/SHELL]"
        actions, shells = extract_actions(text)
        assert len(actions) == 0
        assert shells == ["Get-Date"]

    def test_extract_action_only(self):
        text = "Opening Chrome.\n[ACTION]launch_app: chrome[/ACTION]"
        actions, shells = extract_actions(text)
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.LAUNCH_APP
        assert len(shells) == 0

    def test_extract_mixed(self):
        text = (
            "Let me do both.\n"
            "[ACTION]launch_app: spotify[/ACTION]\n"
            "[SHELL]Get-Date[/SHELL]"
        )
        actions, shells = extract_actions(text)
        assert len(actions) == 1
        assert len(shells) == 1

    def test_extract_none(self):
        actions, shells = extract_actions("Just a plain response.")
        assert len(actions) == 0
        assert len(shells) == 0

    def test_extract_multiple_shells(self):
        text = "[SHELL]cmd1[/SHELL] then [SHELL]cmd2[/SHELL]"
        _, shells = extract_actions(text)
        assert shells == ["cmd1", "cmd2"]


# ════════════════════════════════════════════════════════════════════════════
#  Tag Stream Filter Tests
# ════════════════════════════════════════════════════════════════════════════

class TestTagStreamFilter:
    """Tests for _TagStreamFilter real-time tag stripping."""

    def _get_filter(self):
        # Import the private class
        from Jarvis.core.orchestrator import _TagStreamFilter
        return _TagStreamFilter()

    def test_plain_text_passes_through(self):
        f = self._get_filter()
        result = f.feed("Hello, world!")
        result += f.flush()
        assert result == "Hello, world!"

    def test_shell_tag_stripped(self):
        f = self._get_filter()
        result = ""
        for ch in "Hi. [SHELL]Get-Date[/SHELL] Done.":
            result += f.feed(ch)
        result += f.flush()
        assert "[SHELL]" not in result
        assert "Get-Date" not in result
        assert f.shell_commands == ["Get-Date"]

    def test_action_tag_stripped(self):
        f = self._get_filter()
        result = ""
        for ch in "Opening. [ACTION]launch_app: chrome[/ACTION] Done.":
            result += f.feed(ch)
        result += f.flush()
        assert "[ACTION]" not in result
        assert "launch_app" not in result
        assert f.action_commands == ["launch_app: chrome"]

    def test_mixed_tags(self):
        f = self._get_filter()
        text = "A [SHELL]cmd1[/SHELL] B [ACTION]launch_app: x[/ACTION] C"
        result = ""
        for ch in text:
            result += f.feed(ch)
        result += f.flush()
        assert "A" in result and "B" in result and "C" in result
        assert f.shell_commands == ["cmd1"]
        assert f.action_commands == ["launch_app: x"]


# ════════════════════════════════════════════════════════════════════════════
#  Action Router Tests
# ════════════════════════════════════════════════════════════════════════════

class TestActionRouter:
    """Tests for ActionRouter dispatch logic."""

    @pytest.fixture
    def mock_backend(self):
        backend = MagicMock()
        backend.platform_name = "windows"
        backend.shell_name = "powershell"
        return backend

    @pytest.fixture
    def router(self, mock_backend):
        return ActionRouter(mock_backend)

    def test_execute_shell_delegates(self, router, mock_backend):
        """Shell commands should be delegated to backend.run_shell."""
        mock_backend.run_shell.return_value = ShellResult(
            success=True, message="OK", output="OK",
            stdout="OK", stderr="", return_code=0, command="dir",
        )
        result = router.execute_shell("dir")
        mock_backend.run_shell.assert_called_once()
        assert result.success

    def test_dangerous_command_blocked(self, router):
        """Dangerous commands should be blocked."""
        result = router.execute_shell("format C:", from_llm=True)
        assert result.success is False
        assert "Blocked" in result.message

    def test_execute_action_launch_app(self, router, mock_backend):
        """Launch app actions should call backend.launch_app."""
        mock_backend.launch_app.return_value = ActionResult(
            success=True, message="Opened Chrome",
        )
        req = ActionRequest(
            action_type=ActionType.LAUNCH_APP,
            target="chrome",
        )
        result = router.execute_action(req)
        mock_backend.launch_app.assert_called_once_with("chrome", None)
        assert result.success

    def test_execute_action_open_url(self, router, mock_backend):
        """Open URL actions should call backend.open_url."""
        mock_backend.open_url.return_value = ActionResult(
            success=True, message="Opened URL",
        )
        req = ActionRequest(
            action_type=ActionType.OPEN_URL,
            target="https://google.com",
        )
        result = router.execute_action(req)
        mock_backend.open_url.assert_called_once_with("https://google.com")

    def test_execute_action_system_info(self, router, mock_backend):
        """System info actions should call backend.get_system_info."""
        mock_backend.get_system_info.return_value = {
            "os": "Windows", "hostname": "test",
        }
        req = ActionRequest(action_type=ActionType.SYSTEM_INFO, target="")
        result = router.execute_action(req)
        assert result.success
        assert "Windows" in result.output

    def test_is_dangerous_helper(self, router):
        """is_dangerous should proxy to safety engine."""
        assert router.is_dangerous("format C:") is True
        assert router.is_dangerous("Get-Date") is False


# ════════════════════════════════════════════════════════════════════════════
#  ActionResult / ShellResult Tests
# ════════════════════════════════════════════════════════════════════════════

class TestActionResult:
    def test_str_success_with_output(self):
        r = ActionResult(success=True, message="OK", output="file list here")
        assert str(r) == "file list here"

    def test_str_success_no_output(self):
        r = ActionResult(success=True, message="Done")
        assert str(r) == "Done"

    def test_str_failure_with_error(self):
        r = ActionResult(success=False, message="Failed", error="Not found")
        assert str(r) == "Not found"

    def test_shell_result_inherits(self):
        r = ShellResult(
            success=True, message="OK", output="output",
            stdout="stdout", stderr="", return_code=0, command="dir",
        )
        assert r.return_code == 0
        assert r.command == "dir"
        assert isinstance(r, ActionResult)
