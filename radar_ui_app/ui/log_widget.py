from PySide6.QtWidgets import QTextEdit
from PySide6.QtGui import QTextCursor

class LogWidget(QTextEdit):
    """
    Scrollable text area for displaying application logs.
    """
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setPlaceholderText("Application logs will appear here...")
        self.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: 'Consolas', monospace;")

    def log(self, message):
        """Adds a message to the log widget."""
        self.append(message)
        self.moveCursor(QTextCursor.End)
