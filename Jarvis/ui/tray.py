from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush
from PyQt6.QtCore import pyqtSignal, Qt

class JarvisTrayIcon(QSystemTrayIcon):
    """
    System Tray Icon for Jarvis.
    Handles background operation and context menu.
    """
    # Signals to Main/Orchestrator
    on_show_window = pyqtSignal()
    on_toggle_listening = pyqtSignal()
    on_quit_app = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setToolTip("Jarvis AI - Online")
        
        # Context Menu
        self.menu = QMenu()
        
        self.action_show = self.menu.addAction("Show Jarvis")
        self.action_show.triggered.connect(self.on_show_window.emit)
        
        self.menu.addSeparator()
        
        self.action_listen = self.menu.addAction("Pause Listening")
        self.action_listen.setCheckable(True)
        self.action_listen.setChecked(True)
        self.action_listen.triggered.connect(self.on_toggle_listening.emit)
        
        self.menu.addSeparator()
        
        self.action_quit = self.menu.addAction("Quit Jarvis")
        self.action_quit.triggered.connect(self.on_quit_app.emit)
        
        self.setContextMenu(self.menu)
        
        # Activates on double click
        self.activated.connect(self.on_activated)
        
        # Initial Icon (Cyan = Idle)
        self.update_icon("idle")
        
        self.show()

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.on_show_window.emit()

    def update_icon(self, state):
        """
        Draw a dynamic tray icon based on state.
        States: idle, listening, processing, paused
        """
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Colors
        if state == "listening":
            color = QColor(0, 255, 120)  # Green
        elif state == "processing":
            color = QColor(200, 50, 255) # Magenta
        elif state == "paused":
            color = QColor(255, 50, 50)  # Red
        else: # idle
            color = QColor(0, 255, 255)  # Cyan
            
        # Draw Circle
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        # Center circle with some padding
        painter.drawEllipse(10, 10, 44, 44)
        
        # If paused, draw X or slash? Just red is fine for now.
        
        painter.end()
        
        self.setIcon(QIcon(pixmap))
        
        if state == "listening":
            self.setToolTip("Jarvis AI - Listening")
        elif state == "paused":
            self.action_listen.setText("Resume Listening")
            self.action_listen.setChecked(False)
            self.setToolTip("Jarvis AI - Paused")
        else:
            self.action_listen.setText("Pause Listening")
            self.action_listen.setChecked(True)
            self.setToolTip(f"Jarvis AI - {state.title()}")
