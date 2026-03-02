import math
import random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import (QPainter, QBrush, QColor, QRadialGradient,
                         QConicalGradient, QPen, QLinearGradient)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF


class ThinkingOrb(QWidget):
    """
    Premium animated orb with state-dependent visual effects:
    - Idle/Waiting: Calm breathing cyan glow
    - Listening: Pulsing green with ripple rings
    - Processing: Fast spinning magenta with particle trails
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Animation state
        self.angle = 0.0
        self.pulse = 0.0
        self.pulse_dir = 1
        self.ripple_radius = 0.0
        self.particles = []
        self.state = "waiting"

        # Colors
        self.primary = QColor(0, 255, 255)      # Cyan
        self.secondary = QColor(0, 100, 200)     # Deep blue

        # Animation timer - 60fps
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    def set_state(self, state_name):
        """Thread-safe state change (called via signal)."""
        self.state = state_name
        if state_name == "listening":
            self.primary = QColor(0, 255, 120)       # Vibrant green
            self.secondary = QColor(0, 180, 80)
            self.ripple_radius = 0.0
        elif state_name == "processing":
            self.primary = QColor(200, 50, 255)       # Purple-magenta
            self.secondary = QColor(255, 0, 150)
            self._spawn_particles()
        else:  # waiting
            self.primary = QColor(0, 255, 255)        # Cyan
            self.secondary = QColor(0, 100, 200)

    def _tick(self):
        """Main animation tick."""
        # Rotation
        speed = 8.0 if self.state == "processing" else 2.0
        self.angle = (self.angle + speed) % 360

        # Breathing pulse
        pulse_speed = 0.06 if self.state == "processing" else 0.025
        self.pulse += pulse_speed * self.pulse_dir
        if self.pulse >= 1.0:
            self.pulse_dir = -1
        elif self.pulse <= 0.0:
            self.pulse_dir = 1

        # Ripple for listening
        if self.state == "listening":
            self.ripple_radius += 1.5
            if self.ripple_radius > 120:
                self.ripple_radius = 0.0

        # Update particles
        if self.state == "processing":
            for p in self.particles:
                p['r'] += p['speed']
                p['a'] += p['rot']
                p['life'] -= 0.02
            self.particles = [p for p in self.particles if p['life'] > 0]
            if len(self.particles) < 15:
                self._spawn_particles()

        self.update()

    def _spawn_particles(self):
        """Spawn orbiting particles."""
        for _ in range(5):
            self.particles.append({
                'r': random.uniform(20, 40),
                'a': random.uniform(0, 360),
                'speed': random.uniform(0.3, 1.0),
                'rot': random.uniform(2, 6),
                'size': random.uniform(2, 5),
                'life': 1.0
            })

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        base_radius = min(w, h) / 2 - 20
        if base_radius < 20:
            base_radius = 20

        # Pulsing radius
        pulse_amount = base_radius * 0.08 * self.pulse
        radius = base_radius + pulse_amount

        # === Outer Glow ===
        glow_radius = radius * 1.6
        glow_grad = QRadialGradient(cx, cy, glow_radius)
        glow_color = QColor(self.primary)
        glow_color.setAlpha(int(40 + 20 * self.pulse))
        glow_grad.setColorAt(0, glow_color)
        glow_grad.setColorAt(0.5, QColor(self.primary.red(), self.primary.green(), self.primary.blue(), 10))
        glow_grad.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow_grad))
        painter.drawEllipse(QPointF(cx, cy), glow_radius, glow_radius)

        # === Ripple rings (listening state) ===
        if self.state == "listening" and self.ripple_radius > 0:
            for i in range(3):
                rr = self.ripple_radius - i * 30
                if rr > 0:
                    alpha = max(0, int(100 - rr * 0.8))
                    ring_color = QColor(self.primary.red(), self.primary.green(), self.primary.blue(), alpha)
                    pen = QPen(ring_color, 2)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(QPointF(cx, cy), rr, rr)

        # === Particle trails (processing state) ===
        if self.state == "processing":
            for p in self.particles:
                px = cx + p['r'] * math.cos(math.radians(p['a']))
                py = cy + p['r'] * math.sin(math.radians(p['a']))
                alpha = int(200 * p['life'])
                pc = QColor(self.primary.red(), self.primary.green(), self.primary.blue(), alpha)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(pc))
                painter.drawEllipse(QPointF(px, py), p['size'], p['size'])

        # === Main Orb (conical gradient) ===
        conical = QConicalGradient(cx, cy, self.angle)
        conical.setColorAt(0.0, self.primary)
        conical.setColorAt(0.25, self.secondary)
        conical.setColorAt(0.5, self.primary)
        conical.setColorAt(0.75, self.secondary)
        conical.setColorAt(1.0, self.primary)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(conical))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # === Inner highlight (depth effect) ===
        inner_grad = QRadialGradient(cx - radius * 0.2, cy - radius * 0.3, radius * 0.8)
        highlight = QColor(255, 255, 255, int(60 + 30 * self.pulse))
        inner_grad.setColorAt(0, highlight)
        inner_grad.setColorAt(0.4, QColor(255, 255, 255, 10))
        inner_grad.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(inner_grad))
        painter.drawEllipse(QPointF(cx, cy), radius * 0.9, radius * 0.9)

        # === Core bright spot ===
        core_grad = QRadialGradient(cx, cy, radius * 0.3)
        core_color = QColor(255, 255, 255, int(80 + 40 * self.pulse))
        core_grad.setColorAt(0, core_color)
        core_grad.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QPointF(cx, cy), radius * 0.3, radius * 0.3)

        painter.end()
