"""
End-to-End Mocked Execution Tests
====================================
Tests the full pipeline: LLM output (canned) → parse → safety → confirm → execute
using mocked backend and brain. Validates that runtime correctly handles
all scenario types from the SFT dataset.
"""

import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

# Add project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Jarvis.core.system.actions import ActionResult, ShellResult, ActionType, RiskLevel
from Jarvis.core.system.action_router import (
    ActionRouter, parse_action_tag, extract_actions,
)
from Jarvis.core.system.safety import SafetyEngine


class TestUnifiedSafetyGate(unittest.TestCase):
    """Test that the unified safety gate in ActionRouter works correctly."""

    def setUp(self):
        self.backend = MagicMock()
        self.backend.platform_name = "windows"
        self.backend.run_shell.return_value = ShellResult(
            success=True, message="OK", stdout="output",
            return_code=0, command="test"
        )
        self.safety = SafetyEngine()
        self.confirmed = None  # Track confirmation state

        def mock_confirm(cmd):
            return self.confirmed

        self.router = ActionRouter(
            self.backend, self.safety, confirm_callback=mock_confirm
        )

    # ── CRITICAL commands: always blocked ────────────────────────────────

    def test_critical_format_blocked(self):
        """format c: should be blocked outright."""
        result = self.router.execute_shell("format c:", from_llm=True)
        self.assertFalse(result.success)
        self.assertIn("Blocked", result.message)
        self.backend.run_shell.assert_not_called()

    def test_critical_diskpart_blocked(self):
        result = self.router.execute_shell("diskpart", from_llm=True)
        self.assertFalse(result.success)
        self.assertIn("Blocked", result.message)

    def test_critical_bcdedit_blocked(self):
        result = self.router.execute_shell("bcdedit /set", from_llm=True)
        self.assertFalse(result.success)
        self.assertIn("Blocked", result.message)

    # ── HIGH commands: require confirmation ──────────────────────────────

    def test_high_shutdown_confirmed(self):
        """shutdown /s should require confirmation; approved = executes."""
        self.confirmed = True
        result = self.router.execute_shell("shutdown /s", from_llm=True)
        self.assertTrue(result.success)
        self.backend.run_shell.assert_called_once()

    def test_high_shutdown_denied(self):
        """shutdown /s should require confirmation; denied = not executed."""
        self.confirmed = False
        result = self.router.execute_shell("shutdown /s", from_llm=True)
        self.assertFalse(result.success)
        self.assertIn("cancelled", result.message)
        self.backend.run_shell.assert_not_called()

    def test_high_rm_rf_confirmed(self):
        self.confirmed = True
        result = self.router.execute_shell("rm -rf /tmp/test", from_llm=True)
        self.assertTrue(result.success)

    def test_high_rm_rf_denied(self):
        self.confirmed = False
        result = self.router.execute_shell("rm -rf /tmp/test", from_llm=True)
        self.assertFalse(result.success)

    def test_high_remove_item_recurse_denied(self):
        self.confirmed = False
        result = self.router.execute_shell(
            "Remove-Item C:\\Users\\test -Recurse", from_llm=True
        )
        self.assertFalse(result.success)
        self.assertIn("cancelled", result.message)

    def test_high_reg_delete_denied(self):
        self.confirmed = False
        result = self.router.execute_shell(
            "reg delete HKCU\\Software\\Test", from_llm=True
        )
        self.assertFalse(result.success)

    def test_high_stop_service_confirmed(self):
        self.confirmed = True
        result = self.router.execute_shell("Stop-Service wuauserv", from_llm=True)
        self.assertTrue(result.success)

    # ── No callback: HIGH/CRITICAL denied by default ─────────────────────

    def test_no_callback_denies_high(self):
        """Without a confirm callback, HIGH commands should be denied."""
        router = ActionRouter(self.backend, self.safety, confirm_callback=None)
        result = router.execute_shell("shutdown /s", from_llm=True)
        self.assertFalse(result.success)
        self.backend.run_shell.assert_not_called()

    # ── LOW/MEDIUM commands: execute immediately ─────────────────────────

    def test_safe_echo_executes(self):
        result = self.router.execute_shell("echo hello", from_llm=True)
        self.assertTrue(result.success)
        self.backend.run_shell.assert_called_once()

    def test_safe_get_date_executes(self):
        result = self.router.execute_shell("Get-Date", from_llm=True)
        self.assertTrue(result.success)

    def test_medium_curl_executes(self):
        """Medium risk (curl) should execute without confirmation."""
        result = self.router.execute_shell(
            "curl https://example.com", from_llm=True
        )
        self.assertTrue(result.success)

    # ── Audit logging ────────────────────────────────────────────────────

    def test_blocked_commands_are_audited(self):
        self.router.execute_shell("format c:", from_llm=True)
        log = self.safety.get_audit_log(1)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["outcome"], "blocked")
        self.assertTrue(log[0]["from_llm"])

    def test_denied_commands_are_audited(self):
        self.confirmed = False
        self.router.execute_shell("shutdown /s", from_llm=True)
        log = self.safety.get_audit_log(1)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["outcome"], "denied")

    def test_executed_commands_are_audited(self):
        self.router.execute_shell("echo test", from_llm=True)
        log = self.safety.get_audit_log(1)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["outcome"], "success")


class TestActionTagParsing(unittest.TestCase):
    """Test tag extraction and parsing against SFT dataset patterns."""

    def test_launch_app_tag(self):
        req = parse_action_tag("launch_app: spotify")
        self.assertIsNotNone(req)
        self.assertEqual(req.action_type, ActionType.LAUNCH_APP)
        self.assertEqual(req.target, "spotify")

    def test_open_url_tag(self):
        req = parse_action_tag("open_url: https://youtube.com")
        self.assertIsNotNone(req)
        self.assertEqual(req.action_type, ActionType.OPEN_URL)
        self.assertEqual(req.target, "https://youtube.com")

    def test_system_info_tag(self):
        req = parse_action_tag("system_info")
        self.assertIsNotNone(req)
        self.assertEqual(req.action_type, ActionType.SYSTEM_INFO)

    def test_unknown_action_returns_none(self):
        req = parse_action_tag("fly_to_moon: mars")
        self.assertIsNone(req)

    def test_extract_mixed_tags(self):
        text = (
            "Sure thing!\n"
            "[ACTION]launch_app: chrome[/ACTION]\n"
            "[SHELL]Get-Date[/SHELL]"
        )
        actions, shells = extract_actions(text)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].action_type, ActionType.LAUNCH_APP)
        self.assertEqual(len(shells), 1)
        self.assertEqual(shells[0], "Get-Date")

    def test_multiple_action_tags(self):
        text = (
            "[ACTION]launch_app: spotify[/ACTION]\n"
            "[ACTION]launch_app: discord[/ACTION]\n"
            "[ACTION]launch_app: chrome[/ACTION]"
        )
        actions, shells = extract_actions(text)
        self.assertEqual(len(actions), 3)
        self.assertEqual(len(shells), 0)

    def test_no_tags_in_conversational(self):
        text = "Hello! How can I help you today?"
        actions, shells = extract_actions(text)
        self.assertEqual(len(actions), 0)
        self.assertEqual(len(shells), 0)

    def test_dangerous_text_no_tags(self):
        """Model output for dangerous requests should have no executable tags."""
        text = "⚠️ This will permanently delete files. Are you sure?"
        actions, shells = extract_actions(text)
        self.assertEqual(len(actions), 0)
        self.assertEqual(len(shells), 0)


class TestE2EMockedExecution(unittest.TestCase):
    """
    End-to-end test: canned LLM outputs → orchestrator pipeline.
    Uses mocked backend to verify correct execution decisions.
    """

    def setUp(self):
        self.backend = MagicMock()
        self.backend.platform_name = "windows"
        self.backend.run_shell.return_value = ShellResult(
            success=True, message="OK", stdout="output",
            return_code=0, command="test"
        )
        self.backend.launch_app.return_value = ActionResult(
            success=True, message="App launched"
        )
        self.backend.open_url.return_value = ActionResult(
            success=True, message="URL opened"
        )
        self.backend.get_system_info.return_value = {
            "os": "Windows 11", "cpu": "i7", "ram": "16GB"
        }
        self.safety = SafetyEngine()
        self.confirmed = True

        self.router = ActionRouter(
            self.backend, self.safety,
            confirm_callback=lambda cmd: self.confirmed,
        )

    def _simulate_llm_output(self, llm_text: str) -> list:
        """
        Simulate the orchestrator's processing of LLM output.
        Returns list of (action_type, success) tuples.
        """
        actions, shells = extract_actions(llm_text)
        results = []

        for action_req in actions:
            result = self.router.execute_action(action_req)
            results.append((action_req.action_type.value, result.success))

        for cmd in shells:
            result = self.router.execute_shell(cmd, from_llm=True)
            results.append(("shell_command", result.success))

        return results

    def test_app_launch_flow(self):
        """open spotify → ACTION tag → launch_app backend call."""
        results = self._simulate_llm_output(
            "Opening Spotify.\n[ACTION]launch_app: spotify[/ACTION]"
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], ("launch_app", True))
        self.backend.launch_app.assert_called_once_with("spotify", None)

    def test_url_open_flow(self):
        results = self._simulate_llm_output(
            "Opening YouTube.\n[ACTION]open_url: https://youtube.com[/ACTION]"
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], ("open_url", True))
        self.backend.open_url.assert_called_once()

    def test_safe_shell_flow(self):
        results = self._simulate_llm_output(
            "Here you go.\n[SHELL]Get-Date[/SHELL]"
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], ("shell_command", True))
        self.backend.run_shell.assert_called_once()

    def test_dangerous_shell_denied_flow(self):
        self.confirmed = False
        results = self._simulate_llm_output(
            "Shutting down.\n[SHELL]shutdown /s[/SHELL]"
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], ("shell_command", False))
        self.backend.run_shell.assert_not_called()

    def test_critical_shell_blocked_flow(self):
        results = self._simulate_llm_output(
            "Formatting.\n[SHELL]format c:[/SHELL]"
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], ("shell_command", False))
        self.backend.run_shell.assert_not_called()

    def test_conversational_no_execution(self):
        results = self._simulate_llm_output(
            "Hello! How can I help you today?"
        )
        self.assertEqual(len(results), 0)
        self.backend.run_shell.assert_not_called()
        self.backend.launch_app.assert_not_called()

    def test_multi_action_flow(self):
        results = self._simulate_llm_output(
            "Opening all three.\n"
            "[ACTION]launch_app: spotify[/ACTION]\n"
            "[ACTION]launch_app: discord[/ACTION]\n"
            "[ACTION]launch_app: chrome[/ACTION]"
        )
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r[1] for r in results))
        self.assertEqual(self.backend.launch_app.call_count, 3)

    def test_mixed_action_shell_flow(self):
        results = self._simulate_llm_output(
            "Creating folder and opening explorer.\n"
            "[SHELL]New-Item -ItemType Directory -Name 'work' -Force[/SHELL]\n"
            "[ACTION]launch_app: explorer[/ACTION]"
        )
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r[1] for r in results))


class TestSeedDatasetIntegrity(unittest.TestCase):
    """Validate the seed dataset can be parsed and evaluated."""

    def test_seed_dataset_loads(self):
        """All seed examples should parse without error."""
        seed_path = Path(__file__).parent.parent / "sft" / "seed_dataset.jsonl"
        if not seed_path.exists():
            self.skipTest("Seed dataset not found")

        examples = []
        with open(seed_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    examples.append(json.loads(line))

        self.assertGreater(len(examples), 30, "Seed should have 30+ examples")

    def test_seed_scenarios_complete(self):
        """Seed dataset should cover all major scenarios."""
        seed_path = Path(__file__).parent.parent / "sft" / "seed_dataset.jsonl"
        if not seed_path.exists():
            self.skipTest("Seed dataset not found")

        scenarios = set()
        with open(seed_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    scenarios.add(data["scenario"])

        required = {
            "app_launch", "url_open", "shell_safe",
            "shell_dangerous", "shell_critical", "conversational",
        }
        missing = required - scenarios
        self.assertEqual(missing, set(), f"Missing scenarios: {missing}")

    def test_dangerous_examples_have_no_tags(self):
        """Dangerous/critical examples should not have executable tags."""
        seed_path = Path(__file__).parent.parent / "sft" / "seed_dataset.jsonl"
        if not seed_path.exists():
            self.skipTest("Seed dataset not found")

        with open(seed_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data["risk_level"] in ("high", "critical"):
                    self.assertEqual(
                        data["action_tags"], [],
                        f"{data['id']}: HIGH/CRITICAL should have no action tags"
                    )
                    self.assertEqual(
                        data["shell_tags"], [],
                        f"{data['id']}: HIGH/CRITICAL should have no shell tags"
                    )


if __name__ == "__main__":
    unittest.main()
