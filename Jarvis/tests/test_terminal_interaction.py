
import unittest
import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Jarvis.ui.terminal import Terminal

class TestTerminalInteraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create QApplication instance if it doesn't exist
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_append_output(self):
        terminal = Terminal()
        # Simulate typing a command
        QTest.keyClicks(terminal, "help")
        QTest.keyClick(terminal, Qt.Key.Key_Return)
        
        # Check if command signal was emitted? 
        # But we want to test 'append_output' which crashed.
        
        # Actually, let's call append_output directly as if response came back
        try:
            terminal.append_output("This is a response")
        except AttributeError as e:
            self.fail(f"append_output raised AttributeError: {e}")
        
        content = terminal.toPlainText()
        self.assertIn("This is a response", content)
        self.assertTrue(content.endswith("> "))

if __name__ == '__main__':
    unittest.main()
