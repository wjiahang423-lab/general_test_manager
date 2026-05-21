"""
ParamEditor — three-column QTableWidget for editing a params dict.

Columns:  参数名 | 类型注解（只读）| 值/变量
  - load_params(dict)                : plain key→value load (type column empty)
  - load_params_typed(list of tuples): (name, type_str, default) — from signature scan
  - get_params() -> dict             : returns {name: value} ignoring type column
  - set_variables(dict)              : enables the "📋 选变量" picker button
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QMenu, QAction,
)


class ParamEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._variables: dict = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        hdr = QLabel("步骤参数")
        hdr.setStyleSheet("font-weight:bold;")
        layout.addWidget(hdr)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["参数名", "类型", "值 / {{变量名}}"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("➕ 添加")
        self._btn_del = QPushButton("🗑 删除")
        self._btn_var = QPushButton("📋 选变量")
        self._btn_var.setToolTip("将选中的变量以 {{名}} 插入当前行的值列")
        self._btn_var.setEnabled(False)
        for btn in (self._btn_add, self._btn_del, self._btn_var):
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._btn_add.clicked.connect(lambda: self._add_row())
        self._btn_del.clicked.connect(self._del_row)
        self._btn_var.clicked.connect(self._pick_variable)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_variables(self, variables: dict) -> None:
        self._variables = variables or {}
        self._btn_var.setEnabled(bool(self._variables))

    def load_params(self, params: dict) -> None:
        """Load from a plain {name: value} dict (type column stays empty)."""
        self._table.setRowCount(0)
        for k, v in params.items():
            self._add_row(str(k), "", str(v))

    def load_params_typed(self, params_info: list) -> None:
        """Load from signature scan: list of (name, type_str, default_value_str).
        Preserves any existing value the user has already entered, including
        extra rows (e.g. {{varname}} references) not present in the signature."""
        existing = self.get_params()
        known_names = {name for name, _, _ in params_info}
        self._table.setRowCount(0)
        for name, type_str, default in params_info:
            value = existing.get(name, default)
            self._add_row(str(name), str(type_str), str(value))
        # Keep any user-defined params that are not in the function signature
        # (e.g. {{varname}} references, or params for old-style single-dict functions)
        for name, value in existing.items():
            if name not in known_names:
                self._add_row(str(name), "", str(value) if value is not None else "")

    def get_params(self) -> dict:
        result = {}
        for row in range(self._table.rowCount()):
            k_item    = self._table.item(row, 0)
            type_item = self._table.item(row, 1)
            v_item    = self._table.item(row, 2)
            k      = k_item.text().strip()    if k_item    else ""
            type_s = type_item.text().strip() if type_item else ""
            v      = v_item.text().strip()    if v_item    else ""
            if not k:
                continue
            # Variable references are always kept as strings for later resolution
            if v.startswith("{{"):
                result[k] = v
                continue
            result[k] = self._coerce(v, type_s)
        return result

    @staticmethod
    def _coerce(v: str, type_hint: str):
        """Convert string *v* to a Python value guided by *type_hint*.

        type_hint is the annotation text from the function signature, e.g.
        'int', 'float', 'str', 'bool'.  When empty or unrecognised, fall back
        to auto-detection (int → float → str).
        """
        t = type_hint.lower().strip()
        if t in ("int",):
            try:
                return int(v)
            except (ValueError, TypeError):
                pass
        elif t in ("float",):
            try:
                return float(v)
            except (ValueError, TypeError):
                pass
        elif t in ("bool",):
            return v.lower() not in ("0", "false", "no", "")
        elif t in ("str", "string"):
            return v
        # No / unrecognised type hint — auto-detect
        try:
            return int(v)
        except (ValueError, TypeError):
            pass
        try:
            return float(v)
        except (ValueError, TypeError):
            pass
        return v

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    _TYPE_FG = QColor("#777777")

    def _add_row(self, key: str = "", type_str: str = "", value: str = "") -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(key))
        type_item = QTableWidgetItem(type_str)
        type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
        type_item.setForeground(QBrush(self._TYPE_FG))
        self._table.setItem(row, 1, type_item)
        self._table.setItem(row, 2, QTableWidgetItem(value))

    def _del_row(self) -> None:
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        for row in sorted(rows, reverse=True):
            self._table.removeRow(row)

    def _pick_variable(self) -> None:
        if not self._variables:
            return
        row = self._table.currentRow()
        if row < 0:
            row = self._table.rowCount() - 1
        if row < 0:
            return
        menu = QMenu(self)
        for vname, vval in self._variables.items():
            act = QAction(f"{vname}  （当前值: {vval}）", self)
            act.setData(vname)
            menu.addAction(act)
        chosen = menu.exec_(
            self._btn_var.mapToGlobal(self._btn_var.rect().bottomLeft())
        )
        if chosen:
            vname = chosen.data()
            item = self._table.item(row, 2)
            if item is None:
                item = QTableWidgetItem("")
                self._table.setItem(row, 2, item)
            item.setText(f"{{{{{vname}}}}}")
            self._table.setCurrentCell(row, 2)
