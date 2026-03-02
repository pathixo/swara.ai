
import unittest
import sys
import os
import time
from PyQt6.QtCore import QCoreApplication, QTimer

# Add project root to sys.path explicitly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Jarvis.output.tts import TTS

class TestTTS(unittest.TestCase):
    def test_signal_emission(self):
        # Create QCoreApplication for event loop
        app = QCoreApplication.instance()
        if not app:
            app = QCoreApplication(sys.argv)
            
        tts = TTS()
        
        self.signal_received = False
        self.received_path = ""
        
        def on_audio_generated(path):
            self.signal_received = True
            self.received_path = path
            app.quit() # Stop event loop when signal received
            
        tts.audio_generated.connect(on_audio_generated)
        
        # Mock the async method
        async def mock_speak_async(text):
            # Simulate work
            output_file = os.path.abspath("test_audio.mp3")
            # Emission happens here, which posts event to main thread loop
            tts.audio_generated.emit(output_file)
        
        # Patch the method on the instance
        # We need to ensure _run_speak uses this mock
        # But _run_speak calls self._speak_async
        tts._speak_async = mock_speak_async
        
        # Start the thread
        tts.speak("Testing signal")
        
        # Run event loop with timeout
        QTimer.singleShot(2000, app.quit) # Timeout after 2s
        app.exec()
        
        self.assertTrue(self.signal_received, "Signal was not received within timeout")
        self.assertTrue(self.received_path.endswith("test_audio.mp3"))

if __name__ == '__main__':
    unittest.main()
