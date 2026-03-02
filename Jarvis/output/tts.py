import asyncio
import edge_tts
import threading
import os
from PyQt6.QtCore import QObject, pyqtSignal
from Jarvis.config import TTS_VOICE


class TTS(QObject):
    audio_generated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._voice = TTS_VOICE
        self._rate = "+15%"

    # ── Voice Control ────────────────────────────────────────────────────

    def set_voice(self, voice_id: str) -> None:
        """Change the TTS voice (e.g., 'en-GB-RyanNeural')."""
        self._voice = voice_id

    def set_rate(self, rate: str) -> None:
        """Change the TTS rate (e.g., '+10%', '-5%')."""
        self._rate = rate

    def get_voice(self) -> str:
        """Return the current TTS voice ID."""
        return self._voice

    # ── Speech Synthesis ─────────────────────────────────────────────────

    def speak(self, text):
        """
        Synthesizes speech from text using Edge TTS.
        Function is non-blocking (runs in thread).
        """
        threading.Thread(target=self._run_speak, args=(text,), daemon=True).start()

    def _run_speak(self, text):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._speak_async(text))
            loop.close()
        except Exception as e:
            print(f"TTS Error: {e}")

    async def _speak_async(self, text):
        # Truncate long responses for TTS (speak only first ~200 chars)
        if len(text) > 250:
            text = text[:250] + "..."

        communicate = edge_tts.Communicate(text, self._voice, rate=self._rate)
        output_file = os.path.abspath("temp_tts.mp3")
        await communicate.save(output_file)

        self.audio_generated.emit(output_file)

