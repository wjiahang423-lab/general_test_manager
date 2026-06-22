"""
TestRunner — QThread that executes a full TestPlan and emits Qt signals.

Adapted from eol_tester: sn is optional (defaults to ""), no SN requirement.
"""

from __future__ import annotations

import json
import os
import threading
import yaml
from datetime import datetime

from PyQt5.QtCore import QThread, pyqtSignal

from app.engine.models import TestPlan, TestRecord, StepResult, TestStep, TestSequence, StepLimit
from app.engine.sandbox import ScriptSandbox
from app.engine.executor import StepExecutor
from app.config.settings import SCRIPT_PYTHON


class TestRunner(QThread):
    sig_step_started  = pyqtSignal(str, int, int)   # name, index, total
    sig_step_finished = pyqtSignal(object)           # StepResult
    sig_log           = pyqtSignal(str)
    sig_prompt        = pyqtSignal(str, str)         # message, json-params
    sig_breakpoint    = pyqtSignal(str, int, int)    # step_name, index, total
    sig_done          = pyqtSignal(object)           # TestRecord
    sig_aborted       = pyqtSignal(str)              # reason

    def __init__(
        self,
        plan: TestPlan,
        scripts_root: str,
        sn: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._plan = plan
        self._sn = sn
        self._scripts_root = scripts_root

        self._abort_event      = threading.Event()
        self._prompt_event     = threading.Event()
        self._prompt_result: bool = False
        self._breakpoint_event  = threading.Event()
        self._breakpoint_action: str = "continue"
        self._executor: StepExecutor | None = None

    # ------------------------------------------------------------------
    # Public control interface (called from UI thread)
    # ------------------------------------------------------------------

    def request_abort(self) -> None:
        self._abort_event.set()
        self._prompt_event.set()
        self._breakpoint_event.set()

    def prompt_reply(self, confirmed: bool) -> None:
        self._prompt_result = confirmed
        self._prompt_event.set()

    def breakpoint_reply(self, action: str) -> None:
        self._breakpoint_action = action
        self._breakpoint_event.set()

    # ------------------------------------------------------------------
    # QThread.run
    # ------------------------------------------------------------------

    def run(self) -> None:
        plan = self._plan
        start_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        step_results: list[StepResult] = []

        variable_store: dict = {}
        for name, val in plan.variables.items():
            vtype = plan.variable_types.get(name, "")
            if vtype == "Number":
                try:
                    variable_store[name] = float(val)
                except (TypeError, ValueError):
                    variable_store[name] = 0.0
            elif vtype == "Boolean":
                variable_store[name] = val if isinstance(val, bool) else (
                    str(val).lower() not in ("0", "false", "no", ""))
            else:
                variable_store[name] = val

        sandbox = ScriptSandbox(self._scripts_root, python_exe=SCRIPT_PYTHON)
        self._executor = StepExecutor(
            sandbox=sandbox,
            on_prompt=self._handle_prompt,
            abort_event=self._abort_event,
            variable_store=variable_store,
        )

        self.sig_log.emit(f"[Runner] 开始计划 '{plan.name}' v{plan.version}")
        if variable_store:
            self.sig_log.emit(f"[Runner] 变量: {variable_store}")

        all_steps: list[tuple[TestSequence, TestStep]] = []
        if plan.setup_sequence:
            for step in plan.setup_sequence.steps:
                all_steps.extend(self._expand_loop_steps(plan.setup_sequence, step))
        for seq in plan.sequences:
            for step in seq.steps:
                all_steps.extend(self._expand_loop_steps(seq, step))

        teardown_steps: list[tuple[TestSequence, TestStep]] = []
        if plan.teardown_sequence:
            for step in plan.teardown_sequence.steps:
                teardown_steps.extend(self._expand_loop_steps(plan.teardown_sequence, step))

        total = len(all_steps) + len(teardown_steps)
        aborted = False
        abort_reason = ""

        for idx, (seq, step) in enumerate(all_steps):
            if self._abort_event.is_set():
                aborted = True
                abort_reason = "用户中止，位于步骤: " + step.name
                break

            if seq.skip or step.skip:
                reason = f"序列 '{seq.name}' 已跳过。" if seq.skip else "步骤已跳过。"
                skip_r = StepResult(step.name, seq.name, "SKIP", None, "", reason, 0)
                step_results.append(skip_r)
                self.sig_step_finished.emit(skip_r)
                self.sig_log.emit(f"  [SKIP] {step.name}")
                continue

            if step.breakpoint and not self._abort_event.is_set():
                self._breakpoint_event.clear()
                self._breakpoint_action = "continue"
                self.sig_breakpoint.emit(step.name, idx, total)
                self._breakpoint_event.wait()
                action = self._breakpoint_action
                if self._abort_event.is_set() or action == "abort":
                    aborted = True
                    abort_reason = f"断点中止: {step.name}"
                    break
                if action == "skip":
                    skip_r = StepResult(step.name, seq.name, "SKIP", None, "",
                                        "断点处跳过。", 0)
                    step_results.append(skip_r)
                    self.sig_step_finished.emit(skip_r)
                    continue

            self.sig_step_started.emit(step.name, idx, total)
            self.sig_log.emit(f"[{seq.name}] → {step.name}  (type={step.step_type})")

            result = self._executor.run(step, {**plan.global_params, "sn": self._sn},
                                        seq_name=seq.name)
            step_results.append(result)
            self.sig_step_finished.emit(result)
            self.sig_log.emit(
                f"  [{result.result}] {result.step_name}"
                + (f"  value={result.value} {result.unit}" if result.value is not None else "")
                + (f"  — {result.message}" if result.message else "")
            )

            if result.result in ("FAIL", "ERROR") and step.on_fail == "abort":
                aborted = True
                abort_reason = f"步骤 '{step.name}' {result.result}: {result.message}"
                break

            if self._abort_event.is_set():
                aborted = True
                abort_reason = "用户中止，在步骤之后: " + step.name
                break

        if aborted:
            overall = "ABORT"
        elif any(r.result in ("FAIL", "ERROR") for r in step_results):
            overall = "FAIL"
        else:
            overall = "PASS"

        if teardown_steps:
            teardown_global = {**plan.global_params, "sn": self._sn, "overall_result": overall}
            teardown_offset = len(all_steps)
            for i, (seq, step) in enumerate(teardown_steps):
                if step.skip:
                    skip_r = StepResult(step.name, seq.name, "SKIP", None, "", "步骤已跳过。", 0)
                    step_results.append(skip_r)
                    self.sig_step_finished.emit(skip_r)
                    continue
                self.sig_step_started.emit(step.name, teardown_offset + i, total)
                result = self._executor.run(step, teardown_global, seq_name=seq.name)
                step_results.append(result)
                self.sig_step_finished.emit(result)
                self.sig_log.emit(
                    f"  [{result.result}] {result.step_name}"
                    + (f"  — {result.message}" if result.message else "")
                )

        end_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = TestRecord(
            id=None, sn=self._sn,
            plan_name=plan.name, plan_version=plan.version,
            start_time=start_dt, end_time=end_dt,
            overall_result=overall, step_results=step_results,
        )
        self.sig_log.emit(f"[Runner] 完成 — overall={overall}  steps={len(step_results)}/{total}")

        if aborted:
            self.sig_aborted.emit(abort_reason)
        else:
            self.sig_done.emit(record)

    # ------------------------------------------------------------------
    # Loop step expansion
    # ------------------------------------------------------------------

    def _load_excel_loop(self, xlsx_path: str, sheet_name: str) -> list:
        """从 xlsx 文件读取指定 sheet，返回 是否测试==是 的行列表。
        每行以 {列名: 值} 字典表示；自动将 '测试项名称' 映射为 'name'。
        仅依赖标准库（zipfile + xml.etree），无需 openpyxl/pandas。
        """
        import zipfile
        import xml.etree.ElementTree as ET
        import re as _re

        NS   = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

        def _col_idx(ref):
            letters = _re.sub(r"\d", "", ref)
            n = 0
            for ch in letters:
                n = n * 26 + (ord(ch) - ord("A") + 1)
            return n - 1

        with zipfile.ZipFile(xlsx_path) as zf:
            # shared strings
            try:
                ss_xml = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                shared = [
                    "".join(t.text or "" for t in si.iter(f"{{{NS}}}t"))
                    for si in ss_xml.iter(f"{{{NS}}}si")
                ]
            except Exception:
                shared = []

            # workbook → 找目标 sheet 路径
            wb_xml  = ET.fromstring(zf.read("xl/workbook.xml"))
            wb_rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            rid_map = {
                r.get(f"{{{NS_R}}}id", r.get("Id")): r.get("Target")
                for r in wb_rels
            }
            ws_path = None
            for s in wb_xml.iter(f"{{{NS}}}sheet"):
                if s.get("name") == sheet_name:
                    rid     = s.get(f"{{{NS_R}}}id", s.get("r:id"))
                    target  = rid_map.get(rid, "")
                    ws_path = f"xl/{target}" if not target.startswith("xl/") else target
                    break
            if ws_path is None or ws_path not in zf.namelist():
                raise ValueError(f"Sheet '{sheet_name}' 未在 {xlsx_path} 中找到")

            ws_xml   = ET.fromstring(zf.read(ws_path))
            all_rows = []
            for row_el in ws_xml.iter(f"{{{NS}}}row"):
                cells = {}
                for c in row_el:
                    ref  = c.get("r", "")
                    cidx = _col_idx(ref)
                    t    = c.get("t", "")
                    v_el = c.find(f"{{{NS}}}v")
                    if v_el is None:
                        val = None
                    elif t == "s":
                        val = shared[int(v_el.text)] if v_el.text is not None else ""
                    elif t == "b":
                        val = bool(int(v_el.text))
                    else:
                        try:
                            val = float(v_el.text)
                            if val == int(val):
                                val = int(val)
                        except Exception:
                            val = v_el.text
                    cells[cidx] = val
                if cells:
                    mc = max(cells.keys()) + 1
                    all_rows.append([cells.get(i) for i in range(mc)])

        if not all_rows:
            return []

        headers = [str(c) if c is not None else "" for c in all_rows[0]]
        items   = []
        for row in all_rows[1:]:
            d = {h: (row[i] if i < len(row) else None) for i, h in enumerate(headers)}
            if str(d.get("是否测试", "")).strip() != "是":
                continue
            # runner 用 'name' 字段作步骤显示名
            if "name" not in d:
                d["name"] = d.get("测试项名称") or d.get("pin") or ""
            items.append(d)
        return items

    def _expand_loop_steps(self, seq, step):
        if step.step_type != "loop":
            return [(seq, step)]
        source_path = os.path.join(self._scripts_root, step.loop_source)
        try:
            if source_path.lower().endswith(".xlsx"):
                items = self._load_excel_loop(source_path, step.loop_key)
            else:
                with open(source_path, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                items = data[step.loop_key]
            if not isinstance(items, list) or len(items) == 0:
                raise ValueError(f"loop_key '{step.loop_key}' 为空或非列表。")
        except Exception as exc:
            placeholder = TestStep(
                name=f"{step.name} [loop-expand-error]",
                step_type="script", script=step.script, function=step.function,
                params={**step.params, "_loop_error": str(exc)},
                limits=None, on_fail=step.on_fail, timeout=step.timeout,
            )
            self.sig_log.emit(f"[Runner] 警告: 展开loop步骤失败 '{step.name}': {exc}")
            return [(seq, placeholder)]

        expanded = []
        for i, item in enumerate(items):
            item_name = item.get("name", str(i))
            virtual_name = f"{step.name} / {item_name}"
            if "min" in item or "max" in item:
                limits = StepLimit(
                    low=item.get("min"), high=item.get("max"),
                    unit=item.get("unit", step.limits.unit if step.limits else ""),
                )
            else:
                limits = step.limits
            virtual = TestStep(
                name=virtual_name, step_type=step.loop_item_type,
                script=step.script, function=step.function,
                params={**step.params, **item}, limits=limits,
                on_fail=step.on_fail, timeout=step.timeout,
                retry_count=step.retry_count, breakpoint=step.breakpoint,
                return_map=step.return_map,
            )
            expanded.append((seq, virtual))
        return expanded

    # ------------------------------------------------------------------
    # Prompt handling
    # ------------------------------------------------------------------

    def _handle_prompt(self, message: str, params: dict) -> bool:
        self._prompt_event.clear()
        self._prompt_result = False
        self.sig_prompt.emit(message, json.dumps(params, ensure_ascii=False))
        timeout = float(params.get("timeout", 0)) or None
        signalled = self._prompt_event.wait(timeout=timeout)
        if not signalled:
            return False
        return self._prompt_result
