"""
LogPanel — real-time log viewer (read-only, auto-scroll).
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QLabel


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QLabel("运行日志")
        header.setStyleSheet("font-weight:bold; padding: 4px 0;")
        layout.addWidget(header)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        self._log.setFont(QFont("Consolas", 10))
        layout.addWidget(self._log)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_log(self, text: str) -> None:
        """Append *text* as a new line and scroll to bottom."""
        self._log.appendPlainText(text)
        self._log.moveCursor(QTextCursor.End)

    def clear(self) -> None:
        self._log.clear()
