
from PyQt6.QtWebEngineWidgets import QWebEngineView

class WebView(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.load("https://www.google.com")  # Default to google for now
