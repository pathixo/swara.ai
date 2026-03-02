
import unittest
import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Jarvis.ui.window import MainWindow


class TestTerminalInteraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create QApplication instance if it doesn't exist
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_command_submitted_signal(self):
        """Test that MainWindow.command_submitted signal works."""
        window = MainWindow()
        received = []
        window.command_submitted.connect(lambda text: received.append(text))

        # Simulate submitting a command via the input field
        if hasattr(window, "command_input"):
            window.command_input.setText("help")
            window.command_input.returnPressed.emit()
            self.assertEqual(received, ["help"])

    def test_append_terminal_output(self):
        """Test that append_terminal_output doesn't crash."""
        window = MainWindow()
        try:
            window.append_terminal_output("This is a response")
        except AttributeError as e:
            self.fail(f"append_terminal_output raised AttributeError: {e}")


if __name__ == "__main__":
    unittest.main()
