"""
RunPanel — inline execution panel embedded in the main window.

Shows a step-progress table (left) and a live log (right).
Run / Abort controls live in the main toolbar; this panel is display-only.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QTextCursor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPlainTextEdit, QLabel,
)


_COLOR_PASS  = QColor("#d4edda")
_COLOR_FAIL  = QColor("#f8d7da")
_COLOR_SKIP  = QColor("#fff3cd")
_COLOR_RUN   = QColor("#cce5ff")
_COLOR_ABORT = QColor("#e2e3e5")


class RunPanel(QWidget):
    """
    Embedded panel:
    - Top bar: overall result label
    - Body splitter: step-progress table (left) | log (right)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear table and log for a new run."""
        self._table.setRowCount(0)
        self._log.clear()
        self._overall_label.setText("")
        self._overall_label.setStyleSheet("")

    def on_step_started(self, name: str, index: int, total: int) -> None:
        """Called when a step begins executing."""
        row = self._find_or_add_row(name)
        self._set_row_result(row, "运行中…", _COLOR_RUN)

    def on_step_finished(self, result) -> None:
        """Called with a StepResult."""
        row = self._find_or_add_row(result.step_name)
        color = {
            "PASS":  _COLOR_PASS,
            "FAIL":  _COLOR_FAIL,
            "ERROR": _COLOR_FAIL,
            "SKIP":  _COLOR_SKIP,
        }.get(result.result, QColor("white"))
        val_str = "" if result.value is None else f"{result.value} {result.unit}".strip()
        self._set_row_result(row, result.result, color, val_str, result.message or "")

    def on_log(self, text: str) -> None:
        self._log.appendPlainText(text)
        self._log.moveCursor(QTextCursor.End)

    def on_done(self, record) -> None:
        result = record.overall_result
        color_map = {"PASS": "#2a9a2a", "FAIL": "#cc3333", "ABORT": "#888800"}
        color = color_map.get(result, "#333333")
        self._overall_label.setText(f"整体结果: {result}")
        self._overall_label.setStyleSheet(
            f"font-weight:bold; font-size:14px; color:{color}; padding:4px;"
        )

    def on_aborted(self, reason: str) -> None:
        self._overall_label.setText(f"已中止: {reason}")
        self._overall_label.setStyleSheet(
            "font-weight:bold; font-size:12px; color:#888800; padding:4px;"
        )

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 4)
        outer.setSpacing(2)

        # Thin status bar: overall result label
        self._overall_label = QLabel("")
        self._overall_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        outer.addWidget(self._overall_label)

        # Splitter: table | log
        splitter = QSplitter(Qt.Horizontal)

        # Step progress table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["步骤名称", "结果", "测量值", "信息"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        splitter.addWidget(self._table)

        # Log
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        self._log.setFont(QFont("Consolas", 10))
        splitter.addWidget(self._log)

        splitter.setSizes([500, 400])
        outer.addWidget(splitter)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_or_add_row(self, name: str) -> int:
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            if item and item.text() == name:
                return r
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(name))
        self._table.setItem(row, 1, QTableWidgetItem(""))
        self._table.setItem(row, 2, QTableWidgetItem(""))
        self._table.setItem(row, 3, QTableWidgetItem(""))
        return row

    def _set_row_result(
        self, row: int, result: str, color: QColor,
        value: str = "", message: str = ""
    ) -> None:
        self._table.item(row, 1).setText(result)
        self._table.item(row, 2).setText(value)
        self._table.item(row, 3).setText(message)
        for col in range(4):
            item = self._table.item(row, col)
            if item:
                item.setBackground(color)
        self._table.scrollToItem(self._table.item(row, 0))
