
import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to sys.path explicitly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Jarvis.core.orchestrator import Orchestrator
from Jarvis.core.system.actions import ShellResult


def _make_mock_persona(name="witty", display_name="Witty JARVIS",
                       description="British wit", voice="en-GB-RyanNeural",
                       tts_rate="+10%", system_prompt="You are Jarvis"):
    """Create a mock PersonaProfile."""
    p = MagicMock()
    p.name = name
    p.display_name = display_name
    p.description = description
    p.voice = voice
    p.tts_rate = tts_rate
    p.system_prompt = system_prompt
    return p


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        # Patch Brain and get_backend to avoid real LLM/OS calls during tests
        with patch("Jarvis.core.orchestrator.Brain"), \
             patch("Jarvis.core.orchestrator.get_backend") as mock_get_backend:
            # Set up mock backend
            mock_backend = MagicMock()
            mock_backend.platform_name = "windows"
            mock_backend.shell_name = "powershell"
            # Default shell result for any command
            mock_backend.run_shell.return_value = ShellResult(
                success=True, message="hello", output="hello",
                stdout="hello", stderr="", return_code=0, command="echo hello",
            )
            mock_get_backend.return_value = mock_backend

            self.orchestrator = Orchestrator()
            self.mock_backend = mock_backend

            # Set up mock brain with sensible defaults
            self.orchestrator.brain = MagicMock()
            self.orchestrator.brain.settings = MagicMock()
            self.orchestrator.brain.settings.system_prompt = "You are Jarvis"

            # Mock persona system
            mock_persona = _make_mock_persona()
            self.orchestrator.brain.personas = MagicMock()
            self.orchestrator.brain.personas.get_active.return_value = mock_persona
            self.orchestrator.brain.personas.get_active_name.return_value = "witty"
            self.orchestrator.brain.personas.list_all.return_value = [
                mock_persona,
                _make_mock_persona("professional", "Professional", "No-nonsense", "en-US-GuyNeural"),
            ]

            # Mock TTS
            self.orchestrator.tts = MagicMock()
            self.orchestrator.tts.get_voice.return_value = "en-GB-RyanNeural"

    def test_empty_command(self):
        response = self.orchestrator.process_command("")
        self.assertEqual(response, "")

    def test_shell_command_routing(self):
        """'dir' should route directly to shell execution."""
        if os.name == 'nt':
            response = self.orchestrator.process_command("dir")
            # Should contain some output (not route to LLM)
            self.assertTrue(len(response) > 0)

    def test_llm_routing(self):
        """Natural language should route to Brain."""
        self.orchestrator.brain.generate_response = MagicMock(
            return_value="The sky is blue because of Rayleigh scattering."
        )
        response = self.orchestrator.process_command("Explain why the sky is blue")
        self.orchestrator.brain.generate_response.assert_called_once()
        self.assertIn("Rayleigh scattering", response)

    def test_llm_with_shell_tags(self):
        """LLM response with [SHELL] tags should trigger execution."""
        self.orchestrator.brain.generate_response = MagicMock(
            return_value="Here you go.\n[SHELL]echo hello[/SHELL]"
        )
        response = self.orchestrator.process_command("say hello in console")
        self.assertIn("Here you go", response)

    def test_llm_status_command(self):
        self.orchestrator.brain.get_status = MagicMock(return_value={
            "provider": "ollama",
            "model": "gemma:2b",
            "persona": "Witty JARVIS",
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 512,
            "timeout": 60,
            "system_prompt_preview": "You are Jarvis",
            "memory_messages": 0,
            "health": "connected",
        })

        response = self.orchestrator.process_command("llm status")
        self.assertIn("Brain Status", response)
        self.assertIn("gemma:2b", response)
        self.assertIn("connected", response)
        self.assertIn("Witty JARVIS", response)

    def test_llm_set_temperature_command(self):
        self.orchestrator.brain.set_option = MagicMock(
            return_value=(True, "temperature set to 1.1.")
        )
        response = self.orchestrator.process_command("llm set temperature 1.1")
        self.orchestrator.brain.set_option.assert_called_once_with("temperature", "1.1")
        self.assertIn("temperature set to 1.1", response)

    def test_llm_use_model_command(self):
        self.orchestrator.brain.set_model = MagicMock(
            return_value=(True, "Model set to 'llama3:latest'.")
        )
        response = self.orchestrator.process_command("llm use llama3:latest")
        self.orchestrator.brain.set_model.assert_called_once_with("llama3:latest")
        self.assertIn("llama3:latest", response)

    def test_llm_models_command(self):
        self.orchestrator.brain.list_local_models = MagicMock(
            return_value=(True, ["gemma:2b", "llama3:latest"])
        )
        response = self.orchestrator.process_command("llm models")
        self.assertIn("Available models", response)
        self.assertIn("gemma:2b", response)

    def test_provider_switch_command(self):
        self.orchestrator.brain.set_provider = MagicMock(
            return_value=(True, "Provider switched to 'gemini'.")
        )
        response = self.orchestrator.process_command("llm provider gemini")
        self.orchestrator.brain.set_provider.assert_called_once_with("gemini")
        self.assertIn("gemini", response)

    def test_llm_reset_command(self):
        self.orchestrator.brain.reset_settings = MagicMock(
            return_value="Brain settings, memory, and persona reset to defaults."
        )
        response = self.orchestrator.process_command("llm reset")
        self.assertIn("reset", response.lower())

    def test_clear_memory_command(self):
        self.orchestrator.brain.clear_memory = MagicMock(
            return_value="Conversation memory cleared."
        )
        response = self.orchestrator.process_command("clear memory")
        self.assertIn("memory cleared", response.lower())

    def test_dangerous_command_blocked(self):
        """Dangerous commands from LLM should be blocked."""
        self.orchestrator.brain.generate_response = MagicMock(
            return_value="Formatting drive.\n[SHELL]format c:[/SHELL]"
        )
        response = self.orchestrator.process_command("format my drive")
        self.assertIn("Blocked", response)

    def test_brain_alias_works(self):
        """'brain status' should work the same as 'llm status'."""
        self.orchestrator.brain.get_status = MagicMock(return_value={
            "provider": "gemini",
            "model": "gemini-2.0-flash",
            "persona": "Professional",
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 512,
            "timeout": 60,
            "system_prompt_preview": "You are Jarvis",
            "memory_messages": 5,
            "health": "connected",
        })
        response = self.orchestrator.process_command("brain status")
        self.assertIn("Brain Status", response)

    # ── Persona Tests ────────────────────────────────────────────────────

    def test_persona_list_command(self):
        """'persona list' should list available personas."""
        response = self.orchestrator.process_command("persona list")
        self.assertIn("Available Personas", response)
        self.assertIn("Witty JARVIS", response)
        self.assertIn("Professional", response)

    def test_persona_set_command(self):
        """'persona set professional' should switch persona."""
        self.orchestrator.brain.set_persona = MagicMock(
            return_value=(True, "Persona switched to 'Professional'.", "en-US-GuyNeural")
        )
        prof = _make_mock_persona("professional", "Professional", "No-nonsense", "en-US-GuyNeural")
        self.orchestrator.brain.personas.get_active.return_value = prof

        response = self.orchestrator.process_command("persona set professional")
        self.assertIn("Professional", response)
        self.orchestrator.brain.set_persona.assert_called_once_with("professional")
        self.orchestrator.tts.set_voice.assert_called_with("en-US-GuyNeural")

    def test_persona_status_command(self):
        """'persona status' should show current persona."""
        response = self.orchestrator.process_command("persona status")
        self.assertIn("Witty JARVIS", response)
        self.assertIn("en-GB-RyanNeural", response)

    def test_persona_reset_command(self):
        """'persona reset' should reset to witty."""
        self.orchestrator.brain.personas.reset.return_value = "Persona reset to 'Witty JARVIS'."
        response = self.orchestrator.process_command("persona reset")
        self.assertIn("Witty JARVIS", response)

    def test_voice_set_command(self):
        """'voice set en-US-GuyNeural' should change voice."""
        response = self.orchestrator.process_command("voice set en-US-GuyNeural")
        self.orchestrator.tts.set_voice.assert_called_with("en-US-GuyNeural")
        self.assertIn("en-US-GuyNeural", response)

    def test_voice_list_command(self):
        """'voice list' should show recommended voices."""
        response = self.orchestrator.process_command("voice list")
        self.assertIn("Recommended Voices", response)
        self.assertIn("en-GB-RyanNeural", response)

    # ── Shell Control Tests ──────────────────────────────────────────────

    def test_shell_status_command(self):
        response = self.orchestrator.process_command("shell status")
        self.assertIn("Shell Settings", response)
        self.assertIn("Confirmation Mode: OFF", response)
        self.assertIn("WSL Sandbox Mode:  OFF", response)

    def test_shell_confirmation_toggle(self):
        response = self.orchestrator.process_command("shell confirmation on")
        self.assertTrue(self.orchestrator.confirmation_mode)
        self.assertIn("turned ON", response)
        
        response = self.orchestrator.process_command("shell confirmation off")
        self.assertFalse(self.orchestrator.confirmation_mode)
        self.assertIn("turned OFF", response)

    def test_shell_wsl_toggle(self):
        response = self.orchestrator.process_command("shell wsl on")
        self.assertTrue(self.orchestrator.wsl_mode)
        self.assertIn("turned ON", response)
        
        response = self.orchestrator.process_command("shell wsl off")
        self.assertFalse(self.orchestrator.wsl_mode)
        self.assertIn("turned OFF", response)

    def test_shell_confirmation_logic(self):
        """If confirmation mode is ON, command should wait for callback."""
        from Jarvis.core.system.actions import ShellResult

        self.orchestrator.confirmation_mode = True
        mock_callback = MagicMock(return_value=False)
        self.orchestrator._confirm_callback = mock_callback
        
        response = self.orchestrator.process_command("echo hello")
        mock_callback.assert_called_with("echo hello")
        self.assertIn("cancelled by user", response)
        
        # When approved, command executes via mocked backend
        mock_callback.return_value = True
        self.mock_backend.run_shell.return_value = ShellResult(
            success=True, message="OK", output="hello", stdout="hello",
            return_code=0, command="echo hello",
        )
        response = self.orchestrator.process_command("echo hello")
        self.assertIn("hello", response)


if __name__ == '__main__':
    unittest.main()

