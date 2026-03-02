
import pytest
from unittest.mock import MagicMock, patch
import subprocess

from Jarvis.core.system.actions import ActionType, ActionResult, ShellResult
from Jarvis.core.system.windows import WindowsBackend
from Jarvis.core.system.action_router import ActionRouter, ActionRequest

class TestErrorTaxonomy:
    @pytest.fixture
    def backend(self):
        return WindowsBackend()

    @pytest.fixture
    def router(self, backend):
        return ActionRouter(backend)

    def test_app_not_found_error(self, backend):
        """Test that launching a non-existent app returns APP_NOT_FOUND."""
        with patch('subprocess.run') as mock_run:
            # Mock Get-Command and Get-ChildItem to return nothing
            mock_run.return_value = MagicMock(stdout="", returncode=1)
            
            with patch('subprocess.Popen') as mock_popen:
                # Mock Popen to fail too (or just not be called)
                mock_popen.side_effect = Exception("Not found")
                
                result = backend.launch_app("non_existent_app_xyz")
                assert result.success is False
                assert result.action_type == ActionType.APP_NOT_FOUND

    def test_code_exec_error_shell(self, backend):
        """Test that a failing shell command returns CODE_EXEC_ERROR."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="Error message", returncode=1)
            
            result = backend.run_shell("invalid_command")
            assert result.success is False
            assert result.action_type == ActionType.CODE_EXEC_ERROR

    def test_code_exec_error_python(self, backend):
        """Test that failing python code returns CODE_EXEC_ERROR."""
        # Using a really simple failing script
        result = backend.exec_python("import sys; sys.exit(1)")
        assert result.success is False
        assert result.action_type == ActionType.CODE_EXEC_ERROR

    def test_media_search_failed_empty(self, router):
        """Test that empty music query returns MEDIA_SEARCH_FAILED."""
        req = ActionRequest(ActionType.PLAY_MUSIC, "")
        result = router.execute_action(req)
        assert result.success is False
        assert result.action_type == ActionType.MEDIA_SEARCH_FAILED

    def test_media_search_failed_search_system(self, router):
        """Test that empty search_system query returns MEDIA_SEARCH_FAILED."""
        req = ActionRequest(ActionType.SEARCH_SYSTEM, "")
        result = router.execute_action(req)
        assert result.success is False
        assert result.action_type == ActionType.MEDIA_SEARCH_FAILED
