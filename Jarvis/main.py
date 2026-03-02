import sys
import os
import threading
import logging
import traceback

# Add parent directory to sys.path FIRST (before any Jarvis imports)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Setup Logging
from Jarvis.config import LOGS_DIR
log_file = os.path.join(LOGS_DIR, "crash.log")
logging.basicConfig(
    filename=log_file,
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    traceback.print_exception(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtMultimedia import QMediaPlayer
from Jarvis.ui.window import MainWindow
from Jarvis.ui.tray import JarvisTrayIcon
from Jarvis.core.orchestrator import Orchestrator
from Jarvis.core import colors as clr
from Jarvis.output.tts import TTS
from Jarvis.input.listener import Listener


class Worker(QObject):
    """Thread-safe bridge for UI updates from background threads."""
    output_ready  = pyqtSignal(str)
    execute_ready = pyqtSignal(str, str)   # command, output
    stream_begin  = pyqtSignal()           # LLM stream starting
    stream_token  = pyqtSignal(str)        # individual streamed token
    stream_end    = pyqtSignal()           # LLM stream finished
    confirm_request = pyqtSignal(str)     # command text


def main():
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # Keep running when window hides

        worker = Worker()

        window = MainWindow()
        # Don't show immediately if we want silent start, but generally show on launch
        window.show()

        tts = TTS()
        # Listener (fully autonomous)
        listener = Listener()

        orchestrator = Orchestrator(worker=worker, tts=tts, listener=listener)

        # System Tray
        tray = JarvisTrayIcon()
        
        # Connect Tray Signals
        tray.on_show_window.connect(window.show)
        tray.on_show_window.connect(window.activateWindow)
        tray.on_quit_app.connect(app.quit)
        
        def toggle_listening():
            is_paused = listener.toggle_pause()
            # Loop handled in listener, state emitted automatically
            
        tray.on_toggle_listening.connect(toggle_listening)
        
        # Connect Listener state to Tray Icon
        listener.state_changed.connect(tray.update_icon, Qt.ConnectionType.QueuedConnection)

        # Thread-safe UI connections
        worker.output_ready.connect(window.append_terminal_output, Qt.ConnectionType.QueuedConnection)
        worker.stream_begin.connect(window.on_stream_begin, Qt.ConnectionType.QueuedConnection)
        worker.stream_token.connect(window.on_stream_chunk, Qt.ConnectionType.QueuedConnection)
        worker.stream_end.connect(window.on_stream_end, Qt.ConnectionType.QueuedConnection)
        
        # Listener signals -> UI (crash-safe)
        listener.state_changed.connect(window.orb.set_state, Qt.ConnectionType.QueuedConnection)
        listener.state_changed.connect(window.update_status, Qt.ConnectionType.QueuedConnection)

        # Pause listener while TTS is speaking so it doesn't hear itself
        def on_tts_start():
            listener.set_processing(True)

        def on_tts_done(status):
            if status == QMediaPlayer.MediaStatus.EndOfMedia:
                listener.set_processing(False)

        window.player.playbackStateChanged.connect(
            lambda state: listener.set_processing(state == QMediaPlayer.PlaybackState.PlayingState)
        )

        def on_command_input(command_text):
            """Handle commands from terminal or voice."""

            def process():
                try:
                    import time as _t
                    t0 = _t.time()

                    _streamed = [False]

                    def on_begin():
                        _streamed[0] = True
                        worker.stream_begin.emit()

                    response = orchestrator.process_command(
                        command_text,
                        token_callback=lambda t: worker.stream_token.emit(t),
                        begin_callback=on_begin,
                    )
                    t1 = _t.time()

                    if _streamed[0]:
                        worker.stream_end.emit()
                    else:
                        # Non-streamed response (meta-commands etc.) — show in UI
                        worker.output_ready.emit(f"Response: {response}")

                    # TTS
                    if response and not response.startswith("Error"):
                        listener.set_processing(True)
                        clr.print_debug(f"  TTS generating...")
                        tts.speak(response)
                        t2 = _t.time()
                        clr.print_debug(f"  TTS ready in {t2-t1:.2f}s")
                    clr.print_debug(f"  Total: {_t.time()-t0:.2f}s")
                    print(clr.divider())
                except Exception as e:
                    logging.error(f"Process Error: {e}", exc_info=True)
                    clr.print_error(str(e))
                    worker.stream_end.emit()
                    worker.output_ready.emit(f"Error: {e}")

            threading.Thread(target=process, daemon=True).start()

        # Connect voice commands to orchestrator (SINGLE connection)
        listener.command_received.connect(on_command_input, Qt.ConnectionType.QueuedConnection)

        # Connect GUI typed commands to orchestrator (same pipeline as voice)
        window.command_submitted.connect(on_command_input, Qt.ConnectionType.QueuedConnection)

        # TTS audio playback
        tts.audio_generated.connect(window.play_audio, Qt.ConnectionType.QueuedConnection)

        # Start autonomous listening
        listener.start()

        # Command Confirmation Logic
        confirm_event = threading.Event()
        confirm_result = {"approved": False}

        def on_confirm_response(approved):
            confirm_result["approved"] = approved
            confirm_event.set()

        window.confirm_response.connect(on_confirm_response)

        def request_confirmation(command):
            confirm_result["approved"] = False
            confirm_event.clear()
            worker.confirm_request.emit(command)
            confirm_event.wait() # Wait for UI to set the event
            return confirm_result["approved"]

        orchestrator._confirm_callback = request_confirmation
        
        # Connect UI request to window
        worker.confirm_request.connect(window.show_confirmation_dialog)

        sys.exit(app.exec())

    except Exception as e:
        logging.error("Main Loop Crash", exc_info=True)
        traceback.print_exc()


if __name__ == "__main__":
    main()
