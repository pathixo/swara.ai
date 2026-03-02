"""
Test 2: Full app without Listener/Audio (isolate crash to UI+Orchestrator+TTS)
"""
import sys
import os
import threading
import logging

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QMetaObject, Qt, Q_ARG
from Jarvis.ui.window import MainWindow
from Jarvis.core.orchestrator import Orchestrator
from Jarvis.output.tts import TTS


class Worker(QObject):
    output_ready = pyqtSignal(str)

def main():
    app = QApplication(sys.argv)
    
    orchestrator = Orchestrator()
    tts = TTS()
    worker = Worker()
    
    window = MainWindow()
    window.show()

    worker.output_ready.connect(window.append_terminal_output)

    def on_command_input(command_text):
        window.append_terminal_output(f"Processing: {command_text}")
        
        def process():
            try:
                response = orchestrator.process_command(command_text)
                print(f"Got response: {response[:80]}...")
                # Use signal for thread-safe UI update
                worker.output_ready.emit(f"Response: {response}")
                # Skip TTS for this test
                # tts.speak(response)
            except Exception as e:
                print(f"Process Error: {e}")
                worker.output_ready.emit(f"Error: {e}")
        
        threading.Thread(target=process, daemon=True).start()

    window.terminal.command_signal.connect(on_command_input)
    
    # NO listener, NO audio
    print("Test 2 launched. Type a command...")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
