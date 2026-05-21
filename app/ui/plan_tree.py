"""
PlanTree — QTreeWidget showing TestPlan → TestSequence → TestStep hierarchy.

Adapted from eol_tester: auth dependency removed (all edits always enabled).
"""

from __future__ import annotations

import copy

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QAction,
    QInputDialog, QMessageBox,
)

from app.engine.models import TestPlan, TestSequence, TestStep


_TYPE_SEQ          = "sequence"
_TYPE_STEP         = "step"
_TYPE_SETUP_SEQ    = "setup_seq"
_TYPE_TEARDOWN_SEQ = "teardown_seq"

_SPECIAL_SEQ_COLOR = "#1a6fb5"

_STEP_ICONS = {
    "measurement": "⚡",
    "script":      "📜",
    "prompt":      "💬",
    "delay":       "⏱",
}


class PlanTree(QTreeWidget):
    sig_step_selected         = pyqtSignal(object)
    sig_sequence_selected     = pyqtSignal(object)
    sig_rename_plan_requested = pyqtSignal()
    sig_delete_plan_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabel("测试计划结构")
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSelectionMode(QTreeWidget.SingleSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemClicked.connect(self._on_item_clicked)
        self._plan: TestPlan | None = None
        # run-state: step_name → (result, value_str, unit)
        self._run_states: dict[str, tuple] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_plan(self, plan: TestPlan) -> None:
        self._plan = plan
        self.clear()
        root = QTreeWidgetItem(self, [f"📋  {plan.name}"])
        root.setData(0, Qt.UserRole, ("plan", plan))
        root.setExpanded(True)

        setup_seq = plan.setup_sequence or TestSequence("前置序列")
        setup_item = self._make_special_seq_item(setup_seq, _TYPE_SETUP_SEQ, "⚙️  前置序列")
        root.addChild(setup_item)
        setup_item.setExpanded(True)

        for seq in plan.sequences:
            seq_item = self._make_seq_item(seq)
            root.addChild(seq_item)
            seq_item.setExpanded(True)

        teardown_seq = plan.teardown_sequence or TestSequence("后置序列")
        teardown_item = self._make_special_seq_item(teardown_seq, _TYPE_TEARDOWN_SEQ, "⚙️  后置序列")
        root.addChild(teardown_item)
        teardown_item.setExpanded(True)

    def get_plan(self) -> TestPlan | None:
        if self._plan is None:
            return None
        root = self.invisibleRootItem().child(0)
        if root is None:
            return None

        sequences = []
        setup_sequence = None
        teardown_sequence = None

        for i in range(root.childCount()):
            seq_item = root.child(i)
            data = seq_item.data(0, Qt.UserRole)
            if not data:
                continue
            kind, seq_obj = data
            steps = []
            for j in range(seq_item.childCount()):
                step_item = seq_item.child(j)
                step_obj: TestStep = step_item.data(0, Qt.UserRole)[1]
                steps.append(step_obj)
            seq_with_steps = TestSequence(name=seq_obj.name, steps=steps, skip=getattr(seq_obj, "skip", False))
            if kind == _TYPE_SETUP_SEQ:
                setup_sequence = seq_with_steps if steps else None
            elif kind == _TYPE_TEARDOWN_SEQ:
                teardown_sequence = seq_with_steps if steps else None
            else:
                sequences.append(seq_with_steps)

        plan = copy.copy(self._plan)
        plan.sequences = sequences
        plan.setup_sequence = setup_sequence
        plan.teardown_sequence = teardown_sequence
        return plan

    def rename_plan(self, new_name: str) -> None:
        if self._plan is None:
            return
        self._plan.name = new_name
        root = self.invisibleRootItem().child(0)
        if root:
            root.setText(0, f"📋  {new_name}")

    def update_variables(self, variables: dict, variable_types: dict) -> None:
        if self._plan is not None:
            self._plan.variables = variables
            self._plan.variable_types = variable_types

    def update_step_in_tree(self, step: TestStep) -> None:
        item = self.currentItem()
        if item and item.data(0, Qt.UserRole)[0] == _TYPE_STEP:
            item.setData(0, Qt.UserRole, (_TYPE_STEP, step))
            item.setText(0, self._step_label(step))
            item.setForeground(0, QColor("#aaaaaa") if step.skip else QColor("#000000"))

    # ------------------------------------------------------------------
    # Run-state markers (TestStand-style real-time feedback)
    # ------------------------------------------------------------------

    def reset_run_markers(self) -> None:
        """Clear all run-state indicators before a new run."""
        self._run_states.clear()
        for item in self._iter_step_items():
            step: TestStep = item.data(0, Qt.UserRole)[1]
            item.setText(0, self._step_label(step))
            item.setData(0, Qt.BackgroundRole, None)
            item.setForeground(0, QColor("#aaaaaa") if step.skip else QColor("#000000"))

    def mark_step_running(self, step_name: str) -> None:
        """Highlight the step that is currently executing."""
        self._run_states[step_name] = ("RUNNING", "", "")
        for item in self._iter_step_items():
            step: TestStep = item.data(0, Qt.UserRole)[1]
            if step.name == step_name:
                item.setText(0, f"▶  {step_name}")
                item.setBackground(0, QColor("#cce5ff"))
                item.setForeground(0, QColor("#003380"))
                self.scrollToItem(item)

    def mark_step_result(self, result) -> None:
        """Update a step's icon and background once it finishes."""
        name  = result.step_name
        res   = result.result
        val   = "" if result.value is None else str(result.value)
        unit  = result.unit or ""
        msg   = result.message or ""
        self._run_states[name] = (res, val, unit)

        icon, bg, fg = self._result_visuals(res)
        val_str = f" = {val} {unit}".rstrip() if val else ""
        label   = f"{icon}  {name}{val_str}"

        for item in self._iter_step_items():
            step: TestStep = item.data(0, Qt.UserRole)[1]
            if step.name == name:
                item.setText(0, label)
                item.setBackground(0, QColor(bg))
                item.setForeground(0, QColor(fg))
                if msg:
                    item.setToolTip(0, msg)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        kind = item.data(0, Qt.UserRole)[0] if item.data(0, Qt.UserRole) else None

        if kind == "plan":
            a = menu.addAction("➕  添加序列")
            a.triggered.connect(lambda: self._add_sequence(item))
            menu.addSeparator()
            a_ren = menu.addAction("✏️  重命名计划…")
            a_ren.triggered.connect(self.sig_rename_plan_requested)
            a_del = menu.addAction("🗑  删除计划文件…")
            a_del.triggered.connect(self.sig_delete_plan_requested)

        elif kind in (_TYPE_SETUP_SEQ, _TYPE_TEARDOWN_SEQ):
            a1 = menu.addAction("➕  添加步骤")
            a1.triggered.connect(lambda checked=False, it=item: self._add_step(it))

        elif kind == _TYPE_SEQ:
            a1 = menu.addAction("➕  添加步骤")
            a1.triggered.connect(lambda: self._add_step(item))
            menu.addSeparator()
            a2 = menu.addAction("✏️  重命名序列")
            a2.triggered.connect(lambda: self._rename_sequence(item))
            menu.addSeparator()
            seq_obj: TestSequence = item.data(0, Qt.UserRole)[1]
            skip_label = "✅  启用序列（取消跳过）" if seq_obj.skip else "⏭  跳过此序列"
            a_skip = menu.addAction(skip_label)
            a_skip.triggered.connect(lambda: self._toggle_seq_skip(item))
            menu.addSeparator()
            a3 = menu.addAction("🗑  删除序列")
            a3.triggered.connect(lambda: self._delete_item(item))

        elif kind == _TYPE_STEP:
            a1 = menu.addAction("📋  复制步骤")
            a1.triggered.connect(lambda: self._duplicate_step(item))
            menu.addSeparator()
            a2 = menu.addAction("🗑  删除步骤")
            a2.triggered.connect(lambda: self._delete_item(item))

        menu.exec_(self.viewport().mapToGlobal(pos))

    def _add_sequence(self, parent_item: QTreeWidgetItem) -> None:
        name, ok = QInputDialog.getText(self, "添加序列", "序列名称：")
        if ok and name.strip():
            seq = TestSequence(name=name.strip())
            seq_item = self._make_seq_item(seq)
            parent_item.addChild(seq_item)
            seq_item.setExpanded(True)

    def _add_step(self, seq_item: QTreeWidgetItem) -> None:
        name, ok = QInputDialog.getText(self, "添加步骤", "步骤名称：")
        if ok and name.strip():
            step = TestStep(
                name=name.strip(), step_type="script",
                script="", function="", params={},
                limits=None, on_fail="abort", timeout=30.0,
            )
            seq_item.addChild(self._make_step_item(step))

    def _rename_sequence(self, seq_item: QTreeWidgetItem) -> None:
        seq_obj: TestSequence = seq_item.data(0, Qt.UserRole)[1]
        name, ok = QInputDialog.getText(self, "重命名序列", "序列名称：", text=seq_obj.name)
        if ok and name.strip():
            seq_obj.name = name.strip()
            seq_item.setData(0, Qt.UserRole, (_TYPE_SEQ, seq_obj))
            seq_item.setText(0, self._seq_label(seq_obj))

    def _toggle_seq_skip(self, seq_item: QTreeWidgetItem) -> None:
        seq_obj: TestSequence = seq_item.data(0, Qt.UserRole)[1]
        seq_obj.skip = not seq_obj.skip
        seq_item.setData(0, Qt.UserRole, (_TYPE_SEQ, seq_obj))
        seq_item.setText(0, self._seq_label(seq_obj))
        color = QColor("#aaaaaa") if seq_obj.skip else QColor("#000000")
        seq_item.setForeground(0, color)
        for i in range(seq_item.childCount()):
            seq_item.child(i).setForeground(0, color)

    def _duplicate_step(self, step_item: QTreeWidgetItem) -> None:
        step_obj: TestStep = step_item.data(0, Qt.UserRole)[1]
        new_step = copy.deepcopy(step_obj)
        new_step.name = step_obj.name + "_复制"
        new_item = self._make_step_item(new_step)
        parent = step_item.parent()
        idx = parent.indexOfChild(step_item)
        parent.insertChild(idx + 1, new_item)

    def _delete_item(self, item: QTreeWidgetItem) -> None:
        kind = item.data(0, Qt.UserRole)[0]
        label = "序列" if kind == _TYPE_SEQ else "步骤"
        reply = QMessageBox.question(
            self, f"删除{label}",
            f"确认删除 '{item.text(0).strip()}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            (item.parent() or self.invisibleRootItem()).removeChild(item)

    # ------------------------------------------------------------------
    # Selection handler
    # ------------------------------------------------------------------

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        kind, obj = data
        if kind == _TYPE_STEP:
            self.sig_step_selected.emit(obj)
        elif kind == _TYPE_SEQ:
            self.sig_sequence_selected.emit(obj)

    # ------------------------------------------------------------------
    # Item factories
    # ------------------------------------------------------------------

    def _make_special_seq_item(self, seq: TestSequence, type_key: str, label: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.UserRole, (type_key, seq))
        item.setFlags((item.flags() | Qt.ItemIsDropEnabled) & ~Qt.ItemIsDragEnabled)
        item.setForeground(0, QColor(_SPECIAL_SEQ_COLOR))
        for step in seq.steps:
            item.addChild(self._make_step_item(step))
        return item

    def _make_seq_item(self, seq: TestSequence) -> QTreeWidgetItem:
        item = QTreeWidgetItem([self._seq_label(seq)])
        item.setData(0, Qt.UserRole, (_TYPE_SEQ, seq))
        item.setFlags(item.flags() | Qt.ItemIsDropEnabled | Qt.ItemIsDragEnabled)
        if seq.skip:
            item.setForeground(0, QColor("#aaaaaa"))
        for step in seq.steps:
            child = self._make_step_item(step)
            if seq.skip:
                child.setForeground(0, QColor("#aaaaaa"))
            item.addChild(child)
        return item

    def _make_step_item(self, step: TestStep) -> QTreeWidgetItem:
        item = QTreeWidgetItem([self._step_label(step)])
        item.setData(0, Qt.UserRole, (_TYPE_STEP, step))
        item.setFlags((item.flags() | Qt.ItemIsDragEnabled) & ~Qt.ItemIsDropEnabled)
        if step.skip:
            item.setForeground(0, QColor("#aaaaaa"))
        return item

    @staticmethod
    def _seq_label(seq: TestSequence) -> str:
        prefix = "⏭  " if seq.skip else "▶  "
        return f"{prefix}{seq.name}"

    @staticmethod
    def _step_label(step: TestStep) -> str:
        icon = _STEP_ICONS.get(step.step_type, "○")
        prefix = "[跳过] " if step.skip else ""
        return f"{icon}  {prefix}{step.name}"

    def _iter_step_items(self):
        """Yield every step QTreeWidgetItem across all sequences."""
        root = self.invisibleRootItem().child(0)
        if root is None:
            return
        for i in range(root.childCount()):
            seq_item = root.child(i)
            for j in range(seq_item.childCount()):
                child = seq_item.child(j)
                data = child.data(0, Qt.UserRole)
                if data and data[0] == _TYPE_STEP:
                    yield child

    @staticmethod
    def _result_visuals(result: str) -> tuple[str, str, str]:
        """Return (icon, background_hex, foreground_hex) for a result string."""
        return {
            "RUNNING": ("▶",  "#cce5ff", "#003380"),
            "PASS":    ("✓",  "#d4edda", "#155724"),
            "FAIL":    ("✗",  "#f8d7da", "#721c24"),
            "ERROR":   ("✗",  "#f8d7da", "#721c24"),
            "SKIP":    ("⏭", "#fff3cd", "#856404"),
            "ABORT":   ("■",  "#e2e3e5", "#383d41"),
        }.get(result, ("○", "#ffffff", "#000000"))
