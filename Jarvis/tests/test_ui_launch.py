
import sys
import os
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Add project root to sys.path explicitly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"Project Root added to path: {project_root}")
from Jarvis.ui.window import MainWindow

class TestUILaunch(unittest.TestCase):
    def test_launch_window(self):
        """
        Test that the main window launches without error and closes after a short delay.
        """
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        
        self.assertTrue(window.isVisible())
        self.assertEqual(window.windowTitle(), "Jarvis AI")
        
        # Close the window after 1 second to finish the test
        QTimer.singleShot(1000, app.quit)
        
        # Run the event loop
        app.exec()

if __name__ == '__main__':
    unittest.main()
