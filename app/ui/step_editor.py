"""
StepEditor — right-side panel for editing a TestStep's properties.

Adapted from eol_tester: auth dependency removed, imports updated.
"""

from __future__ import annotations

import ast
import copy
import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QFormLayout, QVBoxLayout, QHBoxLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox,
    QPushButton, QLabel, QGroupBox, QFileDialog, QMessageBox,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QMenu, QAction,
)

from app.engine.models import TestStep, StepLimit
from app.ui.param_editor import ParamEditor
from app.config.settings import TEST_SCRIPTS_DIR


class StepEditor(QWidget):
    sig_step_changed = pyqtSignal(object)   # TestStep

    def __init__(self, parent=None):
        super().__init__(parent)
        self._step: TestStep | None = None
        self._variables: dict = {}
        self._build_ui()
        self.setEnabled(False)

    def set_variables(self, variables: dict) -> None:
        self._variables = variables or {}
        self._param_editor.set_variables(self._variables)
        has_vars = bool(self._variables)
        self._btn_expr_var.setEnabled(has_vars)
        self._btn_lo_var.setEnabled(has_vars)
        self._btn_hi_var.setEnabled(has_vars)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_step(self, step: TestStep) -> None:
        self._step = copy.deepcopy(step)
        self.setEnabled(True)

        self._name_edit.setText(step.name)
        idx = self._type_combo.findText(step.step_type)
        self._type_combo.setCurrentIndex(max(0, idx))
        self._script_edit.setText(step.script)

        self._param_editor.load_params(step.params)
        self._load_return_map(step.return_map)
        self._scan_script(select=step.function)

        self._timeout_spin.setValue(step.timeout)
        idx2 = self._fail_combo.findText(step.on_fail)
        self._fail_combo.setCurrentIndex(max(0, idx2))
        self._retry_spin.setValue(step.retry_count)
        self._bp_check.blockSignals(True)
        self._bp_check.setChecked(step.breakpoint)
        self._bp_check.blockSignals(False)
        self._skip_check.blockSignals(True)
        self._skip_check.setChecked(step.skip)
        self._skip_check.blockSignals(False)

        self._delay_seconds_spin.setValue(float(step.params.get("seconds", 1.0)))
        self._prompt_message_edit.setText(str(step.params.get("message", "")))

        self._loop_src_edit.setText(step.loop_source)
        self._loop_key_edit.setText(step.loop_key)
        idx_it = self._loop_item_type_combo.findText(step.loop_item_type)
        self._loop_item_type_combo.setCurrentIndex(max(0, idx_it))

        limits = step.limits
        self._limits_group.setVisible(step.step_type == "measurement")
        if limits:
            self._expr_edit.setText(limits.expression or "")
            self._lo_edit.setText("" if limits.low is None else str(limits.low))
            self._hi_edit.setText("" if limits.high is None else str(limits.high))
            self._unit_edit.setText(limits.unit)
        else:
            self._expr_edit.setText("")
            self._lo_edit.setText("")
            self._hi_edit.setText("")
            self._unit_edit.setText("")

        self._on_type_changed(step.step_type)

    def clear(self) -> None:
        self._step = None
        self.setEnabled(False)
        self._name_edit.clear()
        self._script_edit.clear()
        self._func_combo.clear()
        self._ret_label.setText("")
        self._loop_src_edit.clear()
        self._loop_key_edit.clear()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        title = QLabel("步骤属性")
        title.setStyleSheet("font-weight:bold; font-size:14px;")
        outer.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        outer.addWidget(sep)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(8)

        self._name_edit = QLineEdit()
        form.addRow(QLabel("步骤名称："), self._name_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["script", "measurement", "prompt", "delay", "loop"])
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        form.addRow(QLabel("步骤类型："), self._type_combo)

        script_row = QHBoxLayout()
        self._script_edit = QLineEdit()
        self._btn_browse = QPushButton("浏览…")
        self._btn_browse.clicked.connect(self._browse_script)
        script_row.addWidget(self._script_edit)
        script_row.addWidget(self._btn_browse)
        self._script_edit.editingFinished.connect(self._scan_script)
        self._script_widget = QWidget()
        self._script_widget.setLayout(script_row)
        form.addRow(QLabel("脚本路径："), self._script_widget)

        self._func_combo = QComboBox()
        self._func_combo.setEditable(True)
        self._func_combo.setInsertPolicy(QComboBox.NoInsert)
        self._func_combo.setPlaceholderText("选择脚本后自动列出函数…")
        self._func_combo.currentTextChanged.connect(self._on_func_changed)
        form.addRow(QLabel("函数名称："), self._func_combo)

        self._ret_label = QLabel("")
        self._ret_label.setWordWrap(True)
        self._ret_label.setStyleSheet("color: #555; font-size: 9px;")
        form.addRow(QLabel("返回类型："), self._ret_label)

        self._timeout_spin = QDoubleSpinBox()
        self._timeout_spin.setRange(0, 3600)
        self._timeout_spin.setSuffix("  秒")
        self._timeout_spin.setDecimals(1)
        form.addRow(QLabel("超时时间："), self._timeout_spin)

        self._fail_combo = QComboBox()
        self._fail_combo.addItems(["abort", "continue"])
        form.addRow(QLabel("失败策略："), self._fail_combo)

        self._retry_spin = QSpinBox()
        self._retry_spin.setRange(0, 10)
        self._retry_spin.setSuffix("  次")
        form.addRow(QLabel("失败重试："), self._retry_spin)

        self._bp_check = QCheckBox("在此步骤前暂停（断点）")
        self._bp_check.stateChanged.connect(self._on_toggle_bp)
        form.addRow(QLabel("断点："), self._bp_check)

        self._skip_check = QCheckBox("跳过此步骤（运行时跳过，计入 SKIP）")
        self._skip_check.setStyleSheet("color: #888;")
        self._skip_check.stateChanged.connect(self._on_toggle_skip)
        form.addRow(QLabel("跳过："), self._skip_check)

        outer.addLayout(form)

        # Loop config
        self._loop_group = QGroupBox("循环配置（loop 步骤）")
        loop_form = QFormLayout(self._loop_group)
        loop_form.setSpacing(6)
        loop_src_row = QHBoxLayout()
        self._loop_src_edit = QLineEdit()
        self._loop_src_edit.setPlaceholderText("相对 scripts_root 的 .yaml / .xlsx 文件路径")
        self._btn_loop_src = QPushButton("浏览…")
        self._btn_loop_src.clicked.connect(self._browse_loop_source)
        loop_src_row.addWidget(self._loop_src_edit)
        loop_src_row.addWidget(self._btn_loop_src)
        loop_src_widget = QWidget()
        loop_src_widget.setLayout(loop_src_row)
        loop_form.addRow(QLabel("数据文件："), loop_src_widget)
        self._loop_key_edit = QLineEdit()
        self._loop_key_edit.setPlaceholderText("YAML 顶层 key")
        loop_form.addRow(QLabel("数据key/sheetName："), self._loop_key_edit)
        self._loop_item_type_combo = QComboBox()
        self._loop_item_type_combo.addItems(["measurement", "script"])
        loop_form.addRow(QLabel("展开步骤类型："), self._loop_item_type_combo)
        outer.addWidget(self._loop_group)

        # Delay config
        self._delay_group = QGroupBox("延时配置（delay 步骤）")
        delay_form = QFormLayout(self._delay_group)
        self._delay_seconds_spin = QDoubleSpinBox()
        self._delay_seconds_spin.setRange(0.0, 3600.0)
        self._delay_seconds_spin.setDecimals(1)
        self._delay_seconds_spin.setSuffix("  秒")
        self._delay_seconds_spin.setValue(1.0)
        delay_form.addRow(QLabel("延时时长："), self._delay_seconds_spin)
        outer.addWidget(self._delay_group)

        # Prompt config
        self._prompt_group = QGroupBox("提示配置（prompt 步骤）")
        prompt_form = QFormLayout(self._prompt_group)
        self._prompt_message_edit = QLineEdit()
        self._prompt_message_edit.setPlaceholderText("显示给操作员的提示内容")
        prompt_form.addRow(QLabel("提示文字："), self._prompt_message_edit)
        outer.addWidget(self._prompt_group)

        # Limits group
        self._limits_group = QGroupBox("判定限值")
        lim_form = QFormLayout(self._limits_group)
        lim_form.setSpacing(6)

        self._expr_edit = QLineEdit()
        self._expr_edit.setPlaceholderText("留空=使用函数返回值 value；或填返回字段名；或 {{变量名}}")
        self._btn_expr_var = QPushButton("📋")
        self._btn_expr_var.setFixedWidth(32)
        self._btn_expr_var.setEnabled(False)
        self._btn_expr_var.clicked.connect(lambda: self._pick_limit_var(self._expr_edit))
        expr_row = QWidget(); expr_layout = QHBoxLayout(expr_row)
        expr_layout.setContentsMargins(0, 0, 0, 0)
        expr_layout.addWidget(self._expr_edit); expr_layout.addWidget(self._btn_expr_var)
        lim_form.addRow(QLabel("判断对象："), expr_row)

        self._lo_edit = QLineEdit()
        self._lo_edit.setPlaceholderText("数字或 {{变量名}}")
        self._hi_edit = QLineEdit()
        self._hi_edit.setPlaceholderText("数字或 {{变量名}}")
        self._unit_edit = QLineEdit()
        self._unit_edit.setPlaceholderText("如 V, A, rpm …")

        self._btn_lo_var = QPushButton("📋"); self._btn_lo_var.setFixedWidth(32)
        self._btn_lo_var.setEnabled(False)
        self._btn_lo_var.clicked.connect(lambda: self._pick_limit_var(self._lo_edit))
        self._btn_hi_var = QPushButton("📋"); self._btn_hi_var.setFixedWidth(32)
        self._btn_hi_var.setEnabled(False)
        self._btn_hi_var.clicked.connect(lambda: self._pick_limit_var(self._hi_edit))

        lo_row = QWidget(); lo_layout = QHBoxLayout(lo_row)
        lo_layout.setContentsMargins(0, 0, 0, 0)
        lo_layout.addWidget(self._lo_edit); lo_layout.addWidget(self._btn_lo_var)
        hi_row = QWidget(); hi_layout = QHBoxLayout(hi_row)
        hi_layout.setContentsMargins(0, 0, 0, 0)
        hi_layout.addWidget(self._hi_edit); hi_layout.addWidget(self._btn_hi_var)

        lim_form.addRow(QLabel("下限："), lo_row)
        lim_form.addRow(QLabel("上限："), hi_row)
        lim_form.addRow(QLabel("单位："), self._unit_edit)
        outer.addWidget(self._limits_group)

        # Return-map editor
        self._retmap_group = QGroupBox("返回值映射（返回字段 → 变量名）")
        rm_layout = QVBoxLayout(self._retmap_group)
        rm_layout.setSpacing(4)
        rm_layout.setContentsMargins(6, 6, 6, 6)
        self._retmap_table = QTableWidget(0, 2)
        self._retmap_table.setHorizontalHeaderLabels(["返回字段 key", "写入变量名"])
        self._retmap_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._retmap_table.setMaximumHeight(120)
        rm_layout.addWidget(self._retmap_table)
        rm_btn_row = QHBoxLayout()
        self._btn_rm_add = QPushButton("+ 行")
        self._btn_rm_del = QPushButton("- 行")
        self._btn_rm_add.clicked.connect(self._retmap_add_row)
        self._btn_rm_del.clicked.connect(self._retmap_del_row)
        rm_btn_row.addWidget(self._btn_rm_add)
        rm_btn_row.addWidget(self._btn_rm_del)
        rm_btn_row.addStretch()
        rm_layout.addLayout(rm_btn_row)
        outer.addWidget(self._retmap_group)

        self._param_editor = ParamEditor()
        outer.addWidget(self._param_editor)

        self._btn_apply = QPushButton("✓  应用修改")
        self._btn_apply.setFixedHeight(45)
        self._btn_apply.setFixedWidth(150)
        self._btn_apply.setStyleSheet(
            "QPushButton { background-color: #2a9a2a; color: white; "
            "font-weight: bold; border-radius: 5px; }"
            "QPushButton:hover { background-color: #1e7a1e; }"
            "QPushButton:pressed { background-color: #166016; }"
        )
        self._btn_apply.clicked.connect(self._on_apply)
        outer.addWidget(self._btn_apply, alignment=Qt.AlignLeft)
        outer.addStretch()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_type_changed(self, step_type: str) -> None:
        is_script_like = step_type in ("script", "measurement", "loop")
        self._script_widget.setVisible(is_script_like)
        self._func_combo.setVisible(is_script_like)
        self._ret_label.setVisible(is_script_like)
        self._limits_group.setVisible(step_type == "measurement")
        self._loop_group.setVisible(step_type == "loop")
        self._delay_group.setVisible(step_type == "delay")
        self._prompt_group.setVisible(step_type == "prompt")
        self._retmap_group.setVisible(is_script_like)

    def _load_return_map(self, rm: dict) -> None:
        self._retmap_table.setRowCount(0)
        for k, v in (rm or {}).items():
            row = self._retmap_table.rowCount()
            self._retmap_table.insertRow(row)
            self._retmap_table.setItem(row, 0, QTableWidgetItem(str(k)))
            self._retmap_table.setItem(row, 1, QTableWidgetItem(str(v)))

    def _get_return_map(self) -> dict:
        result = {}
        for r in range(self._retmap_table.rowCount()):
            k_item = self._retmap_table.item(r, 0)
            v_item = self._retmap_table.item(r, 1)
            k = k_item.text().strip() if k_item else ""
            v = v_item.text().strip() if v_item else ""
            if k:
                result[k] = v
        return result

    def _retmap_add_row(self) -> None:
        row = self._retmap_table.rowCount()
        self._retmap_table.insertRow(row)
        self._retmap_table.setItem(row, 0, QTableWidgetItem(""))
        self._retmap_table.setItem(row, 1, QTableWidgetItem(""))

    def _retmap_del_row(self) -> None:
        row = self._retmap_table.currentRow()
        if row >= 0:
            self._retmap_table.removeRow(row)

    # ------------------------------------------------------------------
    # AST-based function scanning
    # ------------------------------------------------------------------

    @staticmethod
    def _abs_script(script_rel: str) -> str:
        p = os.path.join(TEST_SCRIPTS_DIR, script_rel)
        return p if os.path.isfile(p) else (script_rel if os.path.isfile(script_rel) else "")

    @staticmethod
    def _ast_list_functions(abs_path: str) -> list[str]:
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            return [
                n.name for n in ast.iter_child_nodes(tree)
                if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
            ]
        except Exception:
            return []

    @staticmethod
    def _ast_func_signature(abs_path: str, func_name: str) -> tuple[list, str]:
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except Exception:
            return [], ""
        for node in ast.iter_child_nodes(tree):
            if not (isinstance(node, ast.FunctionDef) and node.name == func_name):
                continue
            args = node.args
            raw_args = [a for a in args.args if a.arg != "self"]
            n = len(raw_args)
            n_def = len(args.defaults)
            params_info = []
            for i, arg in enumerate(raw_args):
                type_str = ast.unparse(arg.annotation) if arg.annotation else ""
                def_idx = i - (n - n_def)
                default_str = ast.unparse(args.defaults[def_idx]) if def_idx >= 0 else ""
                params_info.append((arg.arg, type_str, default_str))
            ret_str = ast.unparse(node.returns) if node.returns else ""
            return params_info, ret_str
        return [], ""

    @staticmethod
    def _ast_typeddict_fields(abs_path: str, class_name: str) -> list[str]:
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except Exception:
            return []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return [
                    item.target.id
                    for item in node.body
                    if isinstance(item, ast.AnnAssign)
                    and isinstance(item.target, ast.Name)
                ]
        return []

    def _scan_script(self, select: str = "") -> None:
        try:
            abs_path = self._abs_script(self._script_edit.text().strip())
            self._func_combo.blockSignals(True)
            self._func_combo.clear()
            if abs_path:
                funcs = self._ast_list_functions(abs_path)
                self._func_combo.addItems(funcs)
            self._func_combo.blockSignals(False)
            target = select or self._func_combo.currentText()
            idx = self._func_combo.findText(target)
            if idx >= 0:
                self._func_combo.setCurrentIndex(idx)
            elif target:
                self._func_combo.setEditText(target)
            self._auto_inspect()
        except Exception as exc:
            self._func_combo.blockSignals(False)
            self._ret_label.setText(f"[扫描错误] {exc}")

    def _on_func_changed(self, _: str) -> None:
        try:
            self._auto_inspect()
        except Exception as exc:
            self._ret_label.setText(f"[检测错误] {exc}")

    def _auto_inspect(self) -> None:
        try:
            abs_path = self._abs_script(self._script_edit.text().strip())
            func_name = self._func_combo.currentText().strip()
            if not abs_path or not func_name:
                self._ret_label.setText("")
                return
            params_info, ret_str = self._ast_func_signature(abs_path, func_name)
            if params_info:
                self._param_editor.load_params_typed(params_info)
            current_rm = self._get_return_map()
            detected_fields: list[str] = []
            label_suffix = ""
            if ret_str:
                td_fields = self._ast_typeddict_fields(abs_path, ret_str)
                if td_fields:
                    detected_fields = td_fields
                    label_suffix = f"  →  字段: {', '.join(td_fields)}（已填入映射表）"
            if not detected_fields:
                detected_fields = ["value", "unit", "message"]
                label_suffix = "  （已填入标准字段）"
            self._ret_label.setText((ret_str or "（未标注）") + label_suffix)
            merged: dict = {k: current_rm.get(k, "") for k in detected_fields}
            for k, v in current_rm.items():
                if k not in merged:
                    merged[k] = v
            self._load_return_map(merged)
        except Exception as exc:
            self._ret_label.setText(f"[检测错误] {exc}")

    def _pick_limit_var(self, line_edit: QLineEdit) -> None:
        if not self._variables:
            return
        btn = self.sender()
        menu = QMenu(self)
        for vname, vval in self._variables.items():
            act = QAction(f"{vname}  （当前值: {vval}）", self)
            act.setData(vname)
            menu.addAction(act)
        pos = btn.mapToGlobal(btn.rect().bottomLeft()) if btn else None
        chosen = menu.exec_(pos) if pos else None
        if chosen:
            line_edit.setText(f"{{{{{chosen.data()}}}}}")

    def _browse_script(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择脚本文件", TEST_SCRIPTS_DIR, "Python 脚本 (*.py)"
        )
        if path:
            try:
                rel = os.path.relpath(path, TEST_SCRIPTS_DIR)
                self._script_edit.setText(rel.replace("\\", "/"))
            except ValueError:
                self._script_edit.setText(path)
            self._scan_script()

    def _on_toggle_skip(self, state: int) -> None:
        if self._step is None:
            return
        self._step.skip = bool(state)
        self.sig_step_changed.emit(self._step)

    def _on_toggle_bp(self, state: int) -> None:
        if self._step is None:
            return
        self._step.breakpoint = bool(state)
        self.sig_step_changed.emit(self._step)

    def _browse_loop_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择循环数据文件", TEST_SCRIPTS_DIR, "YAML 文件或 xlsx (*.yaml *.yml *.xlsx)"
        )
        if path:
            try:
                rel = os.path.relpath(path, TEST_SCRIPTS_DIR)
                self._loop_src_edit.setText(rel.replace("\\", "/"))
            except ValueError:
                self._loop_src_edit.setText(path)

    def _on_apply(self) -> None:
        if self._step is None:
            return
        step_type = self._type_combo.currentText()
        limits = None
        if step_type == "measurement":
            def _parse_limit(text: str):
                t = text.strip()
                if not t:
                    return None
                if t.startswith("{{"):
                    return t
                try:
                    return float(t)
                except ValueError:
                    return t
            limits = StepLimit(
                low=_parse_limit(self._lo_edit.text()),
                high=_parse_limit(self._hi_edit.text()),
                unit=self._unit_edit.text().strip(),
                expression=self._expr_edit.text().strip(),
            )
        params = self._param_editor.get_params()
        if step_type == "delay":
            params["seconds"] = self._delay_seconds_spin.value()
        elif step_type == "prompt":
            msg = self._prompt_message_edit.text().strip()
            if msg:
                params["message"] = msg
        updated = TestStep(
            name=self._name_edit.text().strip() or self._step.name,
            step_type=step_type,
            script=self._script_edit.text().strip(),
            function=self._func_combo.currentText().strip(),
            params=params,
            limits=limits,
            on_fail=self._fail_combo.currentText(),
            timeout=self._timeout_spin.value(),
            retry_count=self._retry_spin.value(),
            breakpoint=self._bp_check.isChecked(),
            return_map=self._get_return_map(),
            loop_source=self._loop_src_edit.text().strip(),
            loop_key=self._loop_key_edit.text().strip(),
            loop_item_type=self._loop_item_type_combo.currentText(),
            skip=self._skip_check.isChecked(),
        )
        self._step = updated
        self.sig_step_changed.emit(updated)
