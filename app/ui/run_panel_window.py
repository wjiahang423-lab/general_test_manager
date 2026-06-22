"""
RunPanelWindow — standalone floating window that wraps RunPanel.

Behaviour
---------
- Created once by MainWindow; shown/hidden on demand.
- Closing the window (X button) hides it instead of destroying it.
- Bottom toolbar holds "查看 HTML 报告" and "查看 Excel 报告" buttons,
  both disabled until set_report_paths() is called after a completed run.
- All RunPanel public methods are proxied so MainWindow can connect
  runner signals directly to this window.
"""

from __future__ import annotations

import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
)

from app.ui.run_panel import RunPanel


class RunPanelWindow(QWidget):
    """Floating execution-panel window."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("执行面板")
        self.resize(960, 580)

        self._html_path: str = ""
        self._xlsx_path: str = ""

        # ── inner panel ──────────────────────────────────────────────
        self.run_panel = RunPanel()

        # ── bottom toolbar ───────────────────────────────────────────
        self._btn_html  = QPushButton("📄 查看 HTML 报告")
        self._btn_excel = QPushButton("📊 查看 Excel 报告")
        self._btn_html.setEnabled(False)
        self._btn_excel.setEnabled(False)
        self._btn_html.setMinimumWidth(150)
        self._btn_excel.setMinimumWidth(150)

        self._btn_html.clicked.connect(self._open_html)
        self._btn_excel.clicked.connect(self._open_xlsx)

        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(self._btn_html)
        bottom.addWidget(self._btn_excel)

        # ── layout ───────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 8)
        layout.setSpacing(4)
        layout.addWidget(self.run_panel, 1)  # stretch=1: takes all extra space
        layout.addLayout(bottom, 0)          # stretch=0: fixed to button height

    # ------------------------------------------------------------------
    # Window behaviour
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        """Hide instead of close so the window can be re-shown."""
        event.ignore()
        self.hide()

    # ------------------------------------------------------------------
    # Report paths
    # ------------------------------------------------------------------

    def set_report_paths(self, html_path: str, xlsx_path: str) -> None:
        """Activate report buttons after a completed run."""
        self._html_path  = html_path  or ""
        self._xlsx_path  = xlsx_path or ""
        self._btn_html.setEnabled(bool(self._html_path))
        self._btn_excel.setEnabled(bool(self._xlsx_path))

    def _open_html(self) -> None:
        if self._html_path and os.path.isfile(self._html_path):
            os.startfile(self._html_path)

    def _open_xlsx(self) -> None:
        if self._xlsx_path and os.path.isfile(self._xlsx_path):
            os.startfile(self._xlsx_path)

    # ------------------------------------------------------------------
    # RunPanel proxy methods (so MainWindow can connect signals here)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self._html_path  = ""
        self._xlsx_path  = ""
        self._btn_html.setEnabled(False)
        self._btn_excel.setEnabled(False)
        self.run_panel.reset()

    def on_step_started(self, name: str, index: int, total: int) -> None:
        self.run_panel.on_step_started(name, index, total)

    def on_step_finished(self, result) -> None:
        self.run_panel.on_step_finished(result)

    def on_log(self, text: str) -> None:
        self.run_panel.on_log(text)

    def on_done(self, record) -> None:
        self.run_panel.on_done(record)

    def on_aborted(self, reason: str) -> None:
        self.run_panel.on_aborted(reason)
