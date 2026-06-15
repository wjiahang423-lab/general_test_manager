"""
MainWindow — single-window test management + inline execution.

Layout
------
MenuBar:  文件 | 工具
Toolbar:  [新建] [打开] [保存] [另存为] | [📋 变量]
Body:     Top splitter: PlanTree (left) | StepEditor (right, scrollable)
          Bottom: RunPanel (collapsible via splitter handle)

No login, no SN input, no mode selection.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QToolBar, QAction, QFileDialog, QMessageBox,
    QInputDialog, QDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QDialogButtonBox, QLabel, QComboBox,
    QScrollArea,
)

from app.config.settings import TEST_PLANS_DIR, TEST_SCRIPTS_DIR, REPORTS_DIR
from app.engine.models import TestPlan, TestSequence, TestStep
from app.engine.schema import load_plan, save_plan
from app.engine.runner import TestRunner
from app.engine.database import Database
from app.ui.plan_tree import PlanTree
from app.ui.step_editor import StepEditor
from app.ui.run_panel_window import RunPanelWindow


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("通用测试管理工具")
        self.resize(1280, 800)

        self._current_path: str = ""
        self._dirty = False
        self._runner: TestRunner | None = None

        self._run_panel_window = RunPanelWindow()
        self._db = Database(os.path.join(REPORTS_DIR, "test_records.db"))

        self._build_menu()
        self._build_toolbar()
        self._build_body()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("文件(&F)")
        self._act_new    = QAction("新建计划(&N)", self, shortcut="Ctrl+N")
        self._act_open   = QAction("打开计划(&O)…", self, shortcut="Ctrl+O")
        self._act_save   = QAction("保存(&S)", self, shortcut="Ctrl+S")
        self._act_saveas = QAction("另存为(&A)…", self, shortcut="Ctrl+Shift+S")
        self._act_exit   = QAction("退出(&Q)", self, shortcut="Ctrl+Q")
        for act in (self._act_new, self._act_open, self._act_save,
                    self._act_saveas, None, self._act_exit):
            if act is None:
                file_menu.addSeparator()
            else:
                file_menu.addAction(act)
        self._act_new.triggered.connect(self._new_plan)
        self._act_open.triggered.connect(self._open_plan)
        self._act_save.triggered.connect(self._save_plan)
        self._act_saveas.triggered.connect(self._saveas_plan)
        self._act_exit.triggered.connect(self.close)

        # Run menu
        run_menu = mb.addMenu("运行(&R)")
        self._act_run   = QAction("▶  运行(&R)", self, shortcut="F5")
        self._act_abort = QAction("■  中止(&X)", self, shortcut="F6")
        self._act_run.triggered.connect(self._run_plan)
        self._act_abort.triggered.connect(self._abort_run)
        self._act_abort.setEnabled(False)
        run_menu.addAction(self._act_run)
        run_menu.addAction(self._act_abort)

        # View menu
        view_menu = mb.addMenu("视图(&V)")
        self._act_panel = QAction("📊  执行面板(&P)", self, shortcut="Ctrl+P")
        self._act_panel.setCheckable(True)
        self._act_panel.setChecked(False)
        self._act_panel.triggered.connect(
            lambda checked: self._run_panel_window.show() if checked else self._run_panel_window.hide()
        )
        view_menu.addAction(self._act_panel)

        tool_menu = mb.addMenu("工具(&T)")
        self._act_vars = QAction("📋  变量管理(&V)…", self, shortcut="Ctrl+Shift+V")
        self._act_vars.triggered.connect(self._edit_variables)
        tool_menu.addAction(self._act_vars)

    def _build_toolbar(self) -> None:
        tb = QToolBar("main")
        tb.setMovable(False)
        self.addToolBar(tb)

        for label, slot in (
            ("📄 新建", self._new_plan),
            ("📂 打开", self._open_plan),
            ("💾 保存", self._save_plan),
        ):
            act = QAction(label, self)
            act.triggered.connect(slot)
            tb.addAction(act)

        tb.addSeparator()
        tb.addAction(self._act_run)
        tb.addAction(self._act_abort)

        tb.addSeparator()
        tb.addAction(self._act_vars)
        tb.addAction(self._act_panel)

    def _build_body(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        # Horizontal splitter: PlanTree (left) | StepEditor (right)
        h_split = QSplitter(Qt.Horizontal)

        self._tree   = PlanTree()
        self._editor = StepEditor()

        # Wrap editor in a QScrollArea so it doesn't get squashed
        scroll = QScrollArea()
        scroll.setWidget(self._editor)
        scroll.setWidgetResizable(True)

        h_split.addWidget(self._tree)
        h_split.addWidget(scroll)
        h_split.setSizes([800, 280])
        h_split.setStretchFactor(0, 1)
        h_split.setStretchFactor(1, 2)

        outer.addWidget(h_split)

        # Wire signals
        self._tree.sig_step_selected.connect(self._editor.load_step)
        self._editor.sig_step_changed.connect(self._on_step_changed)
        self._tree.sig_rename_plan_requested.connect(self._rename_plan)
        self._tree.sig_delete_plan_requested.connect(self._delete_plan)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _new_plan(self) -> None:
        if not self._confirm_discard():
            return
        name, ok = QInputDialog.getText(self, "新建计划", "计划名称：")
        if not ok or not name.strip():
            return
        plan = TestPlan(
            name=name.strip(),
            version="1.0",
            description="",
            global_params={},
            sequences=[
                TestSequence("默认序列", [
                    TestStep("示例步骤", "script", "", "run", {}, None, "abort", 30.0)
                ])
            ],
        )
        self._tree.load_plan(plan)
        self._current_path = ""
        self._set_dirty(False)
        self.setWindowTitle(f"通用测试管理工具 — {plan.name} [新建]")

    def _open_plan(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "打开测试计划", TEST_PLANS_DIR, "YAML 文件 (*.yaml *.yml)"
        )
        if not path:
            return
        try:
            plan = load_plan(path)
            self._tree.load_plan(plan)
            self._editor.set_variables(plan.variables)
            self._current_path = path
            self._set_dirty(False)
            self.setWindowTitle(
                f"通用测试管理工具 — {plan.name}  [{os.path.basename(path)}]"
            )
        except Exception as exc:
            QMessageBox.critical(self, "打开失败", str(exc))

    def _save_plan(self) -> None:
        if not self._current_path:
            self._saveas_plan()
            return
        self._do_save(self._current_path)

    def _saveas_plan(self) -> None:
        plan = self._tree.get_plan()
        if plan is None:
            QMessageBox.warning(self, "提示", "没有可保存的计划。")
            return
        default = os.path.join(TEST_PLANS_DIR, f"{plan.name}.yaml")
        path, _ = QFileDialog.getSaveFileName(
            self, "另存为", default, "YAML 文件 (*.yaml)"
        )
        if path:
            self._do_save(path)
            self._current_path = path

    def _do_save(self, path: str) -> None:
        plan = self._tree.get_plan()
        if plan is None:
            return
        try:
            save_plan(plan, path)
            self._set_dirty(False)
            self.setWindowTitle(
                f"通用测试管理工具 — {plan.name}  [{os.path.basename(path)}]"
            )
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def _rename_plan(self) -> None:
        plan = self._tree.get_plan()
        if plan is None:
            return
        new_name, ok = QInputDialog.getText(
            self, "重命名计划", "计划名称：", text=plan.name
        )
        if not ok or not new_name.strip():
            return
        self._tree.rename_plan(new_name.strip())
        self._set_dirty(True)
        fname = os.path.basename(self._current_path) if self._current_path else "新建"
        self.setWindowTitle(f"通用测试管理工具 — {new_name.strip()}  [{fname}]")

    def _delete_plan(self) -> None:
        if not self._current_path:
            QMessageBox.warning(self, "提示", "当前计划尚未保存到文件，无法删除。")
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要永久删除以下文件吗？\n\n{self._current_path}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            os.remove(self._current_path)
            self._tree.clear()
            self._current_path = ""
            self._set_dirty(False)
            self.setWindowTitle("通用测试管理工具")
        except Exception as exc:
            QMessageBox.critical(self, "删除失败", str(exc))

    # ------------------------------------------------------------------
    # Variables editor
    # ------------------------------------------------------------------

    def _edit_variables(self) -> None:
        plan = self._tree.get_plan()
        if plan is None:
            QMessageBox.warning(self, "提示", "请先加载或新建测试计划。")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("全局变量管理")
        dlg.resize(560, 400)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)
        layout.addWidget(QLabel(
            "变量在运行时作为共享状态传递，通过 {{变量名}} 在参数和限值中引用。\n"
            "类型决定运行时的数据类型：Number=浮点数  String=字符串  Boolean=布尔值"
        ))

        tbl = QTableWidget(0, 4)
        tbl.setHorizontalHeaderLabels(["变量名", "类型", "初始值", "说明（可选）"])
        hh = tbl.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setDefaultSectionSize(120)
        tbl.setColumnWidth(0, 110)
        tbl.setColumnWidth(1, 90)
        tbl.setColumnWidth(2, 100)
        layout.addWidget(tbl)

        _TYPES = ["Number", "String", "Boolean"]

        def _make_type_combo(current: str) -> QComboBox:
            cb = QComboBox()
            cb.addItems(_TYPES)
            idx = cb.findText(current if current in _TYPES else "Number")
            cb.setCurrentIndex(max(0, idx))
            return cb

        def _add_row_data(name: str, vtype: str, val: str, desc: str = "") -> None:
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setItem(r, 0, QTableWidgetItem(name))
            tbl.setCellWidget(r, 1, _make_type_combo(vtype))
            tbl.setItem(r, 2, QTableWidgetItem(val))
            tbl.setItem(r, 3, QTableWidgetItem(desc))

        for name, val in plan.variables.items():
            vtype = plan.variable_types.get(name, "Number")
            _add_row_data(name, vtype, str(val) if val is not None else "0")

        btn_row_layout = QHBoxLayout()
        btn_add = QPushButton("+ 添加变量")
        btn_del = QPushButton("- 删除选中")
        btn_add.clicked.connect(lambda: (
            _add_row_data("new_var", "Number", "0"),
            tbl.editItem(tbl.item(tbl.rowCount() - 1, 0)),
        ))
        btn_del.clicked.connect(lambda: tbl.removeRow(tbl.currentRow()) if tbl.currentRow() >= 0 else None)
        btn_row_layout.addWidget(btn_add)
        btn_row_layout.addWidget(btn_del)
        btn_row_layout.addStretch()
        layout.addLayout(btn_row_layout)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec_() != QDialog.Accepted:
            return

        new_vars: dict = {}
        new_types: dict = {}
        for r in range(tbl.rowCount()):
            n_item = tbl.item(r, 0)
            type_cb = tbl.cellWidget(r, 1)
            v_item = tbl.item(r, 2)
            name = n_item.text().strip() if n_item else ""
            vtype = type_cb.currentText() if isinstance(type_cb, QComboBox) else "Number"
            val_str = v_item.text().strip() if v_item else ""
            if not name:
                continue
            new_types[name] = vtype
            if vtype == "Number":
                try:
                    new_vars[name] = float(val_str)
                except ValueError:
                    new_vars[name] = 0.0
            elif vtype == "Boolean":
                new_vars[name] = val_str.lower() not in ("0", "false", "no", "")
            else:
                new_vars[name] = val_str

        self._tree.update_variables(new_vars, new_types)
        self._editor.set_variables(new_vars)
        self._set_dirty(True)

    # ------------------------------------------------------------------
    # Run / Abort
    # ------------------------------------------------------------------

    def _run_plan(self) -> None:
        plan = self._tree.get_plan()
        if plan is None:
            QMessageBox.warning(self, "提示", "请先加载或新建测试计划。")
            return
        if self._runner is not None and self._runner.isRunning():
            QMessageBox.warning(self, "提示", "已有任务正在运行。")
            return

        self._run_panel_window.reset()
        self._run_panel_window.show()
        self._act_panel.setChecked(True)
        self._tree.reset_run_markers()
        self._act_run.setEnabled(False)
        self._act_abort.setEnabled(True)

        sn = datetime.now().strftime("RUN-%Y%m%d%H%M%S")
        self._runner = TestRunner(plan=plan, scripts_root=TEST_SCRIPTS_DIR, sn=sn)
        self._runner.sig_step_started.connect(self._on_step_started)
        self._runner.sig_step_finished.connect(self._run_panel_window.on_step_finished)
        self._runner.sig_step_finished.connect(self._tree.mark_step_result)
        self._runner.sig_log.connect(self._run_panel_window.on_log)
        self._runner.sig_done.connect(self._on_run_done)
        self._runner.sig_aborted.connect(self._on_run_aborted)
        self._runner.sig_prompt.connect(self._on_prompt)
        self._runner.start()

    def _on_step_started(self, name: str, index: int, total: int) -> None:
        self._run_panel_window.on_step_started(name, index, total)
        self._tree.mark_step_running(name)

    def _on_run_done(self, record) -> None:
        self._run_panel_window.on_done(record)
        self._act_run.setEnabled(True)
        self._act_abort.setEnabled(False)
        # Save to DB and generate reports
        try:
            from app.utils.report_html import HtmlReportGenerator
            from app.utils.report_excel import ExcelReportGenerator
            record_id  = self._db.save_record(record)
            html_path  = HtmlReportGenerator.generate(record)
            xlsx_path  = ExcelReportGenerator.generate(record)
            self._db.update_report_path(record_id, html_path)
            self._run_panel_window.set_report_paths(html_path, xlsx_path)
        except Exception as exc:
            self._run_panel_window.on_log(f"[报告生成失败] {exc}")

    def _on_run_aborted(self, reason: str) -> None:
        self._run_panel_window.on_aborted(reason)
        self._act_run.setEnabled(True)
        self._act_abort.setEnabled(False)

    def _abort_run(self) -> None:
        if self._runner is not None:
            self._runner.request_abort()

    def _on_prompt(self, message: str, params_json: str) -> None:
        reply = QMessageBox.question(
            self, "操作提示", message,
            QMessageBox.Ok | QMessageBox.Cancel,
        )
        confirmed = (reply == QMessageBox.Ok)
        if self._runner:
            self._runner.prompt_reply(confirmed)

    # ------------------------------------------------------------------
    # Dirty state helpers
    # ------------------------------------------------------------------

    def _on_step_changed(self, step: TestStep) -> None:
        self._tree.update_step_in_tree(step)
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        title = self.windowTitle()
        if dirty and not title.endswith(" *"):
            self.setWindowTitle(title + " *")
        elif not dirty and title.endswith(" *"):
            self.setWindowTitle(title[:-2])

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self, "未保存的更改",
            "当前计划有未保存的更改，是否放弃？",
            QMessageBox.Discard | QMessageBox.Cancel,
        )
        return reply == QMessageBox.Discard

    def closeEvent(self, event) -> None:
        if self._runner and self._runner.isRunning():
            self._runner.request_abort()
            self._runner.wait(3000)
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
