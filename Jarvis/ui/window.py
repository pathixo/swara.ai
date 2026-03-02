import sys
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect, 
                             QSizePolicy, QApplication, QLineEdit, QTextEdit)
from PyQt6.QtCore import Qt, QTimer, QUrl, QSize, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QRadialGradient, QTextCursor, QTextCharFormat

from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from Jarvis.output.visuals import ThinkingOrb

class MainWindow(QMainWindow):
    """Main Jarvis window with thinking orb, status bar, and command input panel."""

    # Signal emitted when user submits a typed command
    command_submitted = pyqtSignal(str)
    # Signal emitted when user responds to a confirmation request
    confirm_response = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jarvis AI")
        self.resize(420, 680)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Center window
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        # Central Widget
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a2e, stop:1 #0f0f1a);
                border-radius: 20px;
                border: 1px solid #233554;
            }
        """)
        self.setCentralWidget(self.central_widget)

        # Main layout
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ─── 1. Header / Status Bar ─────────────────────────────────────
        self.header = QFrame()
        self.header.setFixedHeight(40)
        self.header.setStyleSheet(
            "background: rgba(10, 14, 23, 0.95); "
            "border-bottom: 1px solid #233554; "
            "border-top-left-radius: 20px; "
            "border-top-right-radius: 20px;"
        )
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(15, 0, 10, 0)
        
        self.status_label = QLabel("● INITIALIZING")
        self.status_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color: #8892b0; background: transparent; border: none;")
        
        self.mode_label = QLabel("AUTONOMOUS")
        self.mode_label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.mode_label.setStyleSheet(
            "color: #00ff9f; background: rgba(0, 255, 159, 0.1); "
            "border-radius: 4px; padding: 2px 6px; border: none;"
        )

        # Toggle button for command panel
        self.toggle_btn = QPushButton(">_")
        self.toggle_btn.setFixedSize(32, 26)
        self.toggle_btn.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                color: #8892b0;
                background: rgba(35, 53, 84, 0.6);
                border: 1px solid #233554;
                border-radius: 6px;
            }
            QPushButton:hover {
                color: #00ffff;
                background: rgba(0, 255, 255, 0.1);
                border-color: #00ffff;
            }
            QPushButton:pressed {
                background: rgba(0, 255, 255, 0.2);
            }
        """)
        self.toggle_btn.setToolTip("Toggle command input")
        self.toggle_btn.clicked.connect(self._toggle_command_panel)

        # Button for terminal window
        self.terminal_btn = QPushButton("Terminal")
        self.terminal_btn.setFixedSize(70, 26)
        self.terminal_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.terminal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.terminal_btn.setStyleSheet("""
            QPushButton {
                color: #8892b0;
                background: rgba(35, 53, 84, 0.6);
                border: 1px solid #233554;
                border-radius: 6px;
            }
            QPushButton:hover {
                color: #00ffff;
                background: rgba(0, 255, 255, 0.1);
                border-color: #00ffff;
            }
            QPushButton:pressed {
                background: rgba(0, 255, 255, 0.2);
            }
        """)
        self.terminal_btn.setToolTip("Show terminal output")
        self.terminal_btn.clicked.connect(self.show_terminal_window)

        header_layout.addWidget(self.status_label)
        header_layout.addStretch()
        header_layout.addWidget(self.mode_label)
        header_layout.addWidget(self.terminal_btn)
        header_layout.addWidget(self.toggle_btn)

        # ─── 2. Orb Container ───────────────────────────────────────────
        self.orb_container = QFrame()
        self.orb_container.setStyleSheet("background: transparent; border: none;")
        orb_layout = QVBoxLayout(self.orb_container)
        orb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # The Thinking Orb
        self.orb = ThinkingOrb()
        self.orb.setFixedSize(200, 200)

        # State Text
        self.state_text = QLabel("Initializing systems...")
        self.state_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_text.setFont(QFont("Segoe UI", 12))
        self.state_text.setStyleSheet(
            "color: #a8b2d1; background: transparent; "
            "margin-top: 20px; border: none;"
        )

        orb_layout.addWidget(self.orb)
        orb_layout.addWidget(self.state_text)

        # ─── 3. Command Panel (collapsible) ─────────────────────────────
        self.command_panel = QFrame()
        self.command_panel.setStyleSheet(
            "background: rgba(10, 14, 23, 0.95); "
            "border-top: 1px solid #233554; "
            "border-bottom-left-radius: 20px; "
            "border-bottom-right-radius: 20px;"
        )
        panel_layout = QVBoxLayout(self.command_panel)
        panel_layout.setContentsMargins(12, 8, 12, 12)
        panel_layout.setSpacing(6)

        # Response log (read-only)
        self.response_log = QTextEdit()
        self.response_log.setReadOnly(True)
        self.response_log.setFixedHeight(140)
        self.response_log.setFont(QFont("Consolas", 9))
        self.response_log.setStyleSheet("""
            QTextEdit {
                color: #c8d6e5;
                background: rgba(15, 15, 26, 0.9);
                border: 1px solid #1a2744;
                border-radius: 8px;
                padding: 8px;
                selection-background-color: #233554;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background: #233554;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #2e4a6e;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        self.response_log.setPlaceholderText("Responses will appear here...")

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self.command_input = QLineEdit()
        self.command_input.setFont(QFont("Consolas", 10))
        self.command_input.setPlaceholderText("Type a command or ask Jarvis...")
        self.command_input.setStyleSheet("""
            QLineEdit {
                color: #e6f1ff;
                background: rgba(15, 15, 26, 0.9);
                border: 1px solid #233554;
                border-radius: 8px;
                padding: 8px 12px;
                selection-background-color: #233554;
            }
            QLineEdit:focus {
                border-color: #00ffff;
                background: rgba(15, 15, 26, 1.0);
            }
        """)
        self.command_input.returnPressed.connect(self._on_submit)

        self.send_btn = QPushButton("▶")
        self.send_btn.setFixedSize(36, 36)
        self.send_btn.setFont(QFont("Segoe UI", 12))
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                color: #0f0f1a;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00ffff, stop:1 #00cc99);
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #33ffff, stop:1 #33ddaa);
            }
            QPushButton:pressed {
                background: #00cccc;
            }
        """)
        self.send_btn.clicked.connect(self._on_submit)

        input_row.addWidget(self.command_input)
        input_row.addWidget(self.send_btn)

        panel_layout.addWidget(self.response_log)
        panel_layout.addLayout(input_row)

        # ─── Assemble layout ────────────────────────────────────────────
        main_layout.addWidget(self.header)
        main_layout.addWidget(self.orb_container, 1)  # stretch factor
        main_layout.addWidget(self.command_panel)

        # Start with panel visible
        self._panel_visible = True

        # Audio Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        # Command history
        self._cmd_history = []
        self._history_index = -1

        # Streaming state
        self._streaming = False

        # Dragging variables
        self.old_pos = None

    # ── Command Panel ───────────────────────────────────────────────────

    def _toggle_command_panel(self):
        """Show/hide the command input panel."""
        self._panel_visible = not self._panel_visible
        self.command_panel.setVisible(self._panel_visible)

        if self._panel_visible:
            self.toggle_btn.setStyleSheet("""
                QPushButton {
                    color: #00ffff;
                    background: rgba(0, 255, 255, 0.15);
                    border: 1px solid #00ffff;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background: rgba(0, 255, 255, 0.25);
                }
            """)
            self.command_input.setFocus()
        else:
            self.toggle_btn.setStyleSheet("""
                QPushButton {
                    color: #8892b0;
                    background: rgba(35, 53, 84, 0.6);
                    border: 1px solid #233554;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    color: #00ffff;
                    background: rgba(0, 255, 255, 0.1);
                    border-color: #00ffff;
                }
                QPushButton:pressed {
                    background: rgba(0, 255, 255, 0.2);
                }
            """)

    def _on_submit(self):
        """Handle Enter key or Send button click."""
        text = self.command_input.text().strip()
        if not text:
            return

        # Add to history
        self._cmd_history.append(text)
        self._history_index = len(self._cmd_history)

        # Show user input in log
        self._append_log(f"<span style='color:#00ffff;font-weight:bold;'>▸ {_escape_html(text)}</span>")

        # Clear input
        self.command_input.clear()

        # Emit signal for main.py to handle
        self.command_submitted.emit(text)

    def keyPressEvent(self, event):
        """Handle Up/Down arrow for command history navigation."""
        if self.command_input.hasFocus():
            if event.key() == Qt.Key.Key_Up and self._cmd_history:
                self._history_index = max(0, self._history_index - 1)
                self.command_input.setText(self._cmd_history[self._history_index])
                return
            elif event.key() == Qt.Key.Key_Down and self._cmd_history:
                self._history_index = min(len(self._cmd_history), self._history_index + 1)
                if self._history_index < len(self._cmd_history):
                    self.command_input.setText(self._cmd_history[self._history_index])
                else:
                    self.command_input.clear()
                return
        super().keyPressEvent(event)

    # ── Response Display ────────────────────────────────────────────────

    def append_response(self, text: str, msg_type: str = "ai"):
        """
        Append a response to the GUI log panel.
        msg_type: 'ai', 'shell', 'info', 'error'
        """
        color_map = {
            "ai":    "#00ff9f",   # green
            "shell": "#e6c07b",   # yellow
            "info":  "#61afef",   # blue
            "error": "#e06c75",   # red
            "output": "#c678dd",  # magenta/purple
        }
        color = color_map.get(msg_type, "#c8d6e5")

        # Prefix based on type
        prefix_map = {
            "ai":     "JARVIS",
            "shell":  "EXEC",
            "info":   "INFO",
            "error":  "ERROR",
            "output": "OUTPUT",
        }
        prefix = prefix_map.get(msg_type, "")

        if prefix:
            html = (
                f"<span style='color:{color};font-weight:bold;'>[{prefix}]</span> "
                f"<span style='color:{color};'>{_escape_html(text)}</span>"
            )
        else:
            html = f"<span style='color:{color};'>{_escape_html(text)}</span>"

        self._append_log(html)

    def _append_log(self, html: str):
        """Append HTML line to the response log and auto-scroll."""
        self.response_log.append(html)
        # Auto-scroll to bottom
        cursor = self.response_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.response_log.setTextCursor(cursor)

    def append_terminal_output(self, text, type="info"):
        """Handle output from the worker signal — display in GUI log."""
        # Strip the "Response: " prefix if present
        if text.startswith("Response: "):
            text = text[len("Response: "):]

        self.append_to_terminal(text)

        # Detect type from content
        if text.startswith("Error"):
            self.append_response(text, "error")
        elif text.startswith("Output:"):
            self.append_response(text, "output")
        else:
            self.append_response(text, "ai")

    # ── Streaming Response Display ───────────────────────────────────────

    def on_stream_begin(self):
        """Start a new streaming response block in the log panel."""
        self._streaming = True
        color = "#00ff9f"
        self._append_log(
            f"<span style='color:{color};font-weight:bold;'>[JARVIS]</span> "
        )
        self.append_to_terminal("[JARVIS] ")

    def on_stream_chunk(self, text: str):
        """Append a streaming token inline (no new line)."""
        if not self._streaming:
            return
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#00ff9f"))

        cursor = self.response_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text, fmt)
        self.response_log.setTextCursor(cursor)
        self.response_log.ensureCursorVisible()

        if hasattr(self, "terminal_text"):
            tc = self.terminal_text.textCursor()
            tc.movePosition(QTextCursor.MoveOperation.End)
            tc.insertText(text)
            self.terminal_text.setTextCursor(tc)
            self.terminal_text.ensureCursorVisible()

    def on_stream_end(self):
        """Finalise a streaming response block."""
        self._streaming = False

    # ── Window State ────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def update_status(self, state_name):
        """Update the status label and state text based on listener state."""
        if state_name == "listening":
            self.status_label.setText("● LISTENING")
            self.status_label.setStyleSheet("color: #00ff9f; background: transparent; border: none;")
            self.state_text.setText("I'm listening...")
            self.orb.set_state("listening")
        elif state_name == "processing":
            self.status_label.setText("● THINKING")
            self.status_label.setStyleSheet("color: #ff79c6; background: transparent; border: none;")
            self.state_text.setText("Processing...")
            self.orb.set_state("processing")
        else:  # waiting
            self.status_label.setText("● READY")
            self.status_label.setStyleSheet("color: #00ffff; background: transparent; border: none;")
            self.state_text.setText("Standing by...")
            self.orb.set_state("idle")

    def play_audio(self, file_path):
        """Play TTS audio file."""
        try:
            url = QUrl.fromLocalFile(file_path)
            self.player.setSource(url)
            self.player.play()
        except Exception as e:
            print(f"Audio Play Error: {e}")

    def closeEvent(self, event):
        """Minimize to tray instead of quitting."""
        event.ignore()
        self.hide()
        
    def force_quit(self):
        """Actually quit the application."""
        QApplication.instance().quit()


    def create_terminal_window(self):
        """Creates a new window to display terminal output."""
        self.terminal_window = QMainWindow()
        self.terminal_window.setWindowTitle("Terminal Output")
        self.terminal_text = QTextEdit()
        self.terminal_text.setReadOnly(True)
        self.terminal_text.setFont(QFont("Consolas", 9))
        self.terminal_text.setStyleSheet("""
            QTextEdit {
                color: #c8d6e5;
                background: rgba(15, 15, 26, 0.9);
                border: 1px solid #1a2744;
                border-radius: 8px;
                padding: 8px;
                selection-background-color: #233554;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background: #233554;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #2e4a6e;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        self.terminal_window.setCentralWidget(self.terminal_text)
        self.terminal_window.resize(600, 400)

    def append_to_terminal(self, text: str):
        """Appends text to the terminal window."""
        if not hasattr(self, 'terminal_window'):
            self.create_terminal_window()
        self.terminal_text.append(text)
        cursor = self.terminal_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.terminal_text.setTextCursor(cursor)

    def show_terminal_window(self):
        """Shows the terminal window."""
        if not hasattr(self, 'terminal_window'):
            self.create_terminal_window()
        self.terminal_window.show()

    def show_confirmation_dialog(self, command_text: str):
        """Show a styled confirmation dialog for shell commands."""
        from PyQt6.QtWidgets import QMessageBox
        
        # Create a customized message box
        msg = QMessageBox(self)
        msg.setWindowTitle("Permission Required")
        msg.setText(f"Jarvis wants to execute a shell command:\n\n{command_text}")
        msg.setIcon(QMessageBox.Icon.Question)
        
        # Style it
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #3b82f6;
                border-radius: 10px;
            }
            QLabel {
                color: #e2e8f0;
                font-family: 'Segoe UI';
                font-size: 13px;
                min-width: 300px;
            }
            QPushButton {
                background-color: #1e293b;
                color: #3b82f6;
                border: 1px solid #3b82f6;
                border-radius: 5px;
                padding: 5px 15px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                color: #ffffff;
            }
        """)
        
        run_btn = msg.addButton("Run", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        
        approved = msg.clickedButton() == run_btn
        self.confirm_response.emit(approved)

def _escape_html(text: str) -> str:
    """Escape HTML special characters for safe display in QTextEdit."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
    )