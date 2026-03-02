
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

try:
    print(f"Current Dir: {current_dir}")
    print(f"Parent Dir: {parent_dir}")
    print(f"Sys Path: {sys.path}")
    
    from Jarvis.ui.window import MainWindow
    from Jarvis.core.orchestrator import Orchestrator
    from Jarvis.output.tts import TTS
    from Jarvis.input.listener import Listener
    from Jarvis.input.audio_capture import AudioCapture
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    import numpy
    from Jarvis.core.tools import Tools
    t = Tools() # Verify init and sandbox creation
    print("Imports success! Tools initialized.")
except ImportError as e:
    print(f"Import Error: {e}")
except Exception as e:
    print(f"Other Error: {e}")
