"""
Visuals Module — Voice Wave Visualizer
=======================================
Replaces the animated orb with a dynamic, multi-bar voice waveform.
States:
  - waiting:    Idle slow breathing wave in cyan
  - listening:  Active taller bars reacting to "microphone" input (simulated)
  - processing: Fast, bright magenta/purple waves
  - speaking:   Smooth flowing light-blue wave for TTS output
"""

import math
import random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen, QBrush
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF


# Keep the old name as an alias so existing imports don't break
ThinkingOrb = None  # Will be replaced at bottom of file


class VoiceWave(QWidget):
    """
    Premium animated voice waveform with state-dependent visual effects.

    States:
      waiting    — calm sine wave, soft cyan glow
      listening  — tall reactive bars, vivid green
      processing — fast choppy wave, magenta/purple
      speaking   — smooth flowing wave, electric blue
    """

    NUM_BARS = 32           # Number of waveform bars
    BAR_SPACING_RATIO = 0.5 # Gap between bars as fraction of bar width

    # Per-state colour palettes  (top, bottom)
    _PALETTES = {
        "waiting":    (QColor(0, 255, 255, 200),   QColor(0, 100, 200, 60)),
        "listening":  (QColor(0, 255, 120, 220),   QColor(0, 160, 80, 80)),
        "processing": (QColor(220, 60, 255, 230),  QColor(255, 0, 150, 80)),
        "speaking":   (QColor(0, 180, 255, 220),   QColor(0, 80, 200, 80)),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 120)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.state = "waiting"
        self._phase = 0.0        # Phase offset for sine motion
        self._tick_count = 0
        # Per-bar heights (0.0 → 1.0) for smooth interpolation
        self._heights = [0.0] * self.NUM_BARS
        self._targets = [0.0] * self.NUM_BARS

        # External audio data (if provided)
        self._external_spectrum = None

        # Glow pulse
        self._glow_pulse = 0.0
        self._glow_dir = 1

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)  # 60 fps

    # ── Public API ──────────────────────────────────────────────────────

    def set_state(self, state_name: str):
        """Switch visual state. Called from the main thread."""
        valid = ("waiting", "listening", "processing", "speaking")
        self.state = state_name if state_name in valid else "waiting"

    def set_spectrum(self, spectrum):
        """
        Pass real-time frequency data to the visualizer.
        
        Args:
            spectrum: np.ndarray of 32 normalized (0.0-1.0) values
        """
        self._external_spectrum = spectrum

    # ── Animation ────────────────────────────────────────────────────────

    def _tick(self):
        self._tick_count += 1

        # Phase speed — how fast the wave scrolls
        phase_speed = {
            "waiting":    0.04,
            "listening":  0.09,
            "processing": 0.18,
            "speaking":   0.07,
        }.get(self.state, 0.04)
        self._phase += phase_speed

        # Recompute target heights
        self._compute_targets()

        # Smooth interpolation toward targets
        lerp = 0.18 if self.state in ("processing", "listening") else 0.10
        for i in range(self.NUM_BARS):
            self._heights[i] += (self._targets[i] - self._heights[i]) * lerp

        # Glow pulse
        glow_speed = 0.04 if self.state in ("processing", "speaking") else 0.018
        self._glow_pulse += glow_speed * self._glow_dir
        if self._glow_pulse >= 1.0:
            self._glow_dir = -1
        elif self._glow_pulse <= 0.0:
            self._glow_dir = 1

        self.update()

    def _compute_targets(self):
        """Compute target bar heights based on current state."""
        n = self.NUM_BARS

        if self.state == "waiting":
            # Slow, smooth, shallow sine — like breathing
            for i in range(n):
                t = self._phase + (i / n) * math.pi * 2
                self._targets[i] = 0.12 + 0.12 * math.sin(t)

        elif self.state == "listening":
            # REAL audio input if available, else fallback to simulated
            if self._external_spectrum is not None:
                # Use provided frequency bands directly
                for i in range(n):
                    # We have 32 bands, so map 1:1 if possible
                    # _external_spectrum length should match self.NUM_BARS
                    if i < len(self._external_spectrum):
                        # Add a tiny bit of sine floor to keep it 'alive' when quiet
                        floor = 0.05 + 0.03 * math.sin(self._phase + i/2)
                        self._targets[i] = max(floor, self._external_spectrum[i])
                    else:
                        self._targets[i] = 0.05
            else:
                # Fallback multi-harmonic active wave — simulates mic input
                for i in range(n):
                    t = self._phase + (i / n) * math.pi * 2
                    base = 0.3 * math.sin(t) + 0.2 * math.sin(t * 2 + 0.5)
                    noise = 0.15 * math.sin(t * 5 + self._tick_count * 0.1)
                    self._targets[i] = max(0.05, 0.5 + base + noise)

        elif self.state == "processing":
            # Fast choppy / glitchy wave
            for i in range(n):
                t = self._phase * 2 + (i / n) * math.pi * 3.5
                glitch = random.gauss(0, 0.08) if random.random() < 0.1 else 0
                self._targets[i] = max(0.05,
                    0.45 + 0.40 * math.sin(t) + 0.15 * math.sin(t * 3) + glitch
                )

        elif self.state == "speaking":
            # Smooth flowing multi-harmonic — TTS output waveform
            for i in range(n):
                t = self._phase + (i / n) * math.pi * 2
                self._targets[i] = max(0.06,
                    0.35 + 0.28 * math.sin(t) + 0.12 * math.sin(t * 2 + 1)
                )

    # ── Paint ────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        palette_top, palette_bot = self._PALETTES.get(
            self.state, self._PALETTES["waiting"]
        )

        # Total bar width (including spacing)
        n = self.NUM_BARS
        total_gap_ratio = self.BAR_SPACING_RATIO
        bar_w = w / (n + (n - 1) * total_gap_ratio)
        gap_w = bar_w * total_gap_ratio

        center_y = h / 2

        for i in range(n):
            bar_h = max(3.0, self._heights[i] * h * 0.85)
            x = i * (bar_w + gap_w)
            y = center_y - bar_h / 2

            # Fill gradient top→bottom using state palette
            grad = QLinearGradient(x, y, x, y + bar_h)
            top = QColor(palette_top)
            top.setAlpha(max(60, min(240, int(180 + 60 * self._heights[i]))))
            bot = QColor(palette_bot)
            bot.setAlpha(max(30, int(80 * self._heights[i])))
            grad.setColorAt(0.0, top)
            grad.setColorAt(1.0, bot)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))

            # Rounded capsule shape
            radius = bar_w / 2
            painter.drawRoundedRect(
                QRectF(x, y, bar_w, bar_h), radius, radius
            )

            # Subtle glow behind each bar
            glow_alpha = int(20 + 15 * self._glow_pulse)
            glow = QColor(palette_top)
            glow.setAlpha(glow_alpha)
            painter.setBrush(QBrush(glow))
            painter.drawRoundedRect(
                QRectF(x - 1, y - 2, bar_w + 2, bar_h + 4), radius + 1, radius + 1
            )

        painter.end()


# ── Backward-compat alias ─────────────────────────────────────────────────────
# So any code that still does `from Jarvis.output.visuals import ThinkingOrb`
# receives the new VoiceWave widget instead without needing code changes.
ThinkingOrb = VoiceWave
