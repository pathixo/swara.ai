import sys
import threading
import pyaudio
import wave
import os
import time
import numpy as np
import logging
from PyQt6.QtCore import QObject, pyqtSignal
from Jarvis.config import PORCUPINE_ACCESS_KEY
from Jarvis.input.audio_processor import AudioProcessor


class Listener(QObject):
    """
    Fully autonomous voice listener with VAD.
    Always listening — detects speech via energy threshold,
    records until silence, transcribes, emits command.
    """
    state_changed = pyqtSignal(str)
    command_received = pyqtSignal(str)

    SPEECH_THRESHOLD = 450
    SILENCE_THRESHOLD = 300
    SILENCE_DURATION = 0.4
    MIN_SPEECH_DURATION = 0.25
    MAX_DURATION = 15.0

    RATE = 16000
    CHANNELS = 1
    CHUNK = 1024
    FORMAT = pyaudio.paInt16

    def __init__(self):
        super().__init__()
        self.listening = False
        self.manual_pause = False
        self.model = None
        self.model_lock = threading.Lock()
        self._is_processing = False
        self._pa = None
        self._stream = None
        
        # Audio processor for wave visualization
        self.audio_processor = AudioProcessor(
            sample_rate=self.RATE,
            fft_size=512,
            num_bands=32
        )

    def start(self):
        self.listening = True
        threading.Thread(target=self._preload_model, daemon=True).start()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop(self):
        self.listening = False
        self._close_stream()

    def set_processing(self, is_processing):
        self._is_processing = is_processing
        # Only emit state if not manually paused
        if not self.manual_pause:
             self.state_changed.emit("processing" if is_processing else "waiting")

    def toggle_pause(self):
        """Manual toggle for user pause command."""
        self.manual_pause = not self.manual_pause
        if self.manual_pause:
            self.state_changed.emit("paused")
        else:
            self.state_changed.emit("waiting")
        return self.manual_pause
    
    def get_audio_spectrum(self):
        """
        Get the current audio frequency spectrum (32 normalized bands).
        
        Returns:
            np.ndarray: 32 frequency bins normalized to 0.0-1.0 range
        """
        return self.audio_processor.get_spectrum()
    
    def get_audio_spectrum_from_queue(self, timeout=0.01):
        """
        Get spectrum from queue without blocking.
        
        Args:
            timeout: Timeout in seconds (default: 0.01)
            
        Returns:
            np.ndarray or None: Spectrum data if available
        """
        return self.audio_processor.get_spectrum_from_queue(timeout=timeout)

    def _open_stream(self):
        """Open the microphone stream."""
        try:
            if self._pa is None:
                self._pa = pyaudio.PyAudio()
            if self._stream is None or not self._stream.is_active():
                self._stream = self._pa.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK
                )
            return True
        except Exception as e:
            print(f"Mic open error: {e}")
            return False

    def _close_stream(self):
        """Close the microphone stream safely."""
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None
        except Exception:
            self._stream = None

    def _preload_model(self):
        """Start persistent transcription worker subprocess."""
        import subprocess
        worker_path = os.path.join(os.path.dirname(__file__), "transcribe_worker.py")
        print("[STT] Starting persistent worker...")
        try:
            self._worker = subprocess.Popen(
                [sys.executable, worker_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            # Wait for "ready" signal
            import json
            ready_line = self._worker.stdout.readline().strip()
            if ready_line:
                data = json.loads(ready_line)
                print(f"[STT] Worker ready (model loaded in {data.get('load_time', '?')}s)")
            else:
                print("[STT] Warning: worker didn't send ready signal")
        except Exception as e:
            print(f"[STT] Worker start error: {e}")
            self._worker = None

    def _transcribe(self, frames):
        """Save audio to WAV and transcribe via persistent worker."""
        import json
        t_start = time.time()
        filename = os.path.join(os.path.dirname(__file__), "command.wav")

        try:
            pa = pyaudio.PyAudio()
            sample_width = pa.get_sample_size(self.FORMAT)
            pa.terminate()

            wf = wave.open(filename, 'wb')
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(sample_width)
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(frames))
            wf.close()
            t_save = time.time()
            print(f"[STT] WAV saved ({os.path.getsize(filename)} bytes, {t_save - t_start:.2f}s)")
        except Exception as e:
            print(f"[STT] WAV save error: {e}")
            return

        # Send to persistent worker
        if not hasattr(self, '_worker') or self._worker is None or self._worker.poll() is not None:
            print("[STT] Worker not running, restarting...")
            self._preload_model()
            if self._worker is None:
                return

        try:
            print("[STT] Transcribing...")
            self._worker.stdin.write(filename + "\n")
            self._worker.stdin.flush()

            result_line = self._worker.stdout.readline().strip()
            t_transcribe = time.time()

            if not result_line:
                print("[STT] Empty response from worker")
                return

            data = json.loads(result_line)
            if data.get("error"):
                print(f"[STT] Error: {data['error']}")
                return

            text = data.get("text", "").strip()
            stt_time = data.get("time", 0)
            total = t_transcribe - t_start
            print(f"[STT] '{text}' (stt={stt_time}s, total={total:.2f}s)")

            if text and len(text) > 2:
                print(f">>> COMMAND: {text}")
                self.command_received.emit(text)
            else:
                print(f"[STT] Filtered: '{text}'")

        except Exception as e:
            print(f"[STT] Error: {e}")
            logging.error(f"STT Error: {e}", exc_info=True)



    def _listen_loop(self):
        try:
            if not self._open_stream():
                print("Cannot open microphone. Text-only mode.")
                return

            print("Autonomous listener active.")
            self.state_changed.emit("waiting")

            while self.listening:
                try:
                    if self._is_processing or self.manual_pause:
                        time.sleep(0.1)
                        continue

                    if self._stream is None or not self._stream.is_active():
                        if not self._open_stream():
                            time.sleep(1)
                            continue

                    try:
                        data = self._stream.read(self.CHUNK, exception_on_overflow=False)
                    except Exception:
                        time.sleep(0.05)
                        continue

                    if not data:
                        time.sleep(0.05)
                        continue

                    # Voice Activity Detection
                    try:
                        audio_data = np.frombuffer(data, dtype=np.int16)
                        rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
                        
                        # Process audio for visualization (non-blocking)
                        try:
                            self.audio_processor.process_chunk(data)
                        except Exception as e:
                            # Don't let audio processing errors affect listening
                            pass
                    except Exception:
                        continue

                    if rms > self.SPEECH_THRESHOLD:
                        self.state_changed.emit("listening")
                        frames = self._record_until_silence(data)
                        if frames:
                            # CLOSE stream before transcribing to avoid native code conflict
                            self._close_stream()
                            self.state_changed.emit("processing")
                            self._transcribe(frames)
                            # Reopen stream after transcription
                            self._open_stream()
                        self.state_changed.emit("waiting")

                except Exception as e:
                    if "Input overflow" not in str(e):
                        print(f"Listen loop error: {e}")
                    time.sleep(0.05)

        except Exception as e:
            print(f"Listener CRITICAL: {e}")
            logging.error(f"Listener CRITICAL: {e}", exc_info=True)

    def _record_until_silence(self, initial_chunk):
        """Record speech until silence is detected."""
        frames = [initial_chunk]
        start_time = time.time()
        silence_start = None

        while True:
            try:
                data = self._stream.read(self.CHUNK, exception_on_overflow=False)
            except Exception:
                break

            if not data:
                break

            frames.append(data)
            elapsed = time.time() - start_time

            # Process audio for visualization (non-blocking)
            try:
                self.audio_processor.process_chunk(data)
            except Exception:
                pass

            if elapsed > self.MAX_DURATION:
                break

            try:
                audio_data = np.frombuffer(data, dtype=np.int16)
                rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
            except Exception:
                rms = 0

            if rms < self.SILENCE_THRESHOLD:
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start > self.SILENCE_DURATION:
                    break
            else:
                silence_start = None

        duration = time.time() - start_time
        print(f"Recorded: {duration:.1f}s, {len(frames)} chunks")

        if duration < self.MIN_SPEECH_DURATION or len(frames) < 5:
            print("Too short, skipping.")
            return None

        return frames
