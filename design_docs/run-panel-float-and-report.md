# 执行面板独立窗口 + 测试报告功能（HTML + Excel）

## 目录

- [1. 需求摘要与目标](#1-需求摘要与目标)
- [2. 技术设计](#2-技术设计)
  - [2.1 模块划分](#21-模块划分)
  - [2.2 RunPanelWindow 浮动窗口设计](#22-runpanelwindow-浮动窗口设计)
  - [2.3 报告生成器设计（HTML + Excel）](#23-报告生成器设计html--excel)
  - [2.4 数据流：运行结束 → 保存 → 生成报告 → 通知窗口](#24-数据流运行结束--保存--生成报告--通知窗口)
  - [2.5 MainWindow 改动要点](#25-mainwindow-改动要点)
  - [2.6 openpyxl 路径修复](#26-openpyxl-路径修复)
- [3. 实现步骤](#3-实现步骤)
  - [Step 1: 创建 RunPanelWindow 浮动窗口](#step-1-创建-runpanelwindow-浮动窗口)
  - [Step 2: 创建报告生成器（HTML + Excel）](#step-2-创建报告生成器html--excel)
  - [Step 3: 更新 MainWindow——替换嵌入式面板为浮动窗口](#step-3-更新-mainwindow替换嵌入式面板为浮动窗口)
  - [Step 4: 更新 MainWindow——运行结束时保存数据库并生成报告](#step-4-更新-mainwindow运行结束时保存数据库并生成报告)

---

## 1. 需求摘要与目标

**背景**：当前执行面板（RunPanel）嵌入在主窗口底部 QSplitter 中，无法独立显示；测试结束后结果仅显示在 UI，不持久化也不生成文件。

**功能**：
1. 执行面板改为独立浮动窗口（点 X 隐藏，点"执行面板"按钮重新显示）；窗口底部内嵌"查看 HTML"和"查看 Excel"两个报告按钮，测试完成后分别激活。
2. 每次测试运行结束后：① 将结果保存到 SQLite 数据库；② 同时生成 HTML 和 Excel 两份报告到 `reports/` 目录；③ 对应按钮激活后可用系统默认程序打开。
3. 报告样式参考 `D:\Siada\eol_tester\app\utils\` 中的 `report_html.py` 和 `report_excel.py`。

**目标**：执行面板独立、可复现；测试记录持久化；HTML 和 Excel 双格式报告可随时查阅。

---

## 2. 技术设计

### 2.1 模块划分

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `app/ui/run_panel_window.py` | 新建 | `RunPanelWindow` 浮动窗口，包含 `RunPanel` + "查看 HTML"/"查看 Excel"按钮 |
| `app/utils/__init__.py` | 新建 | 空文件，声明 utils 包 |
| `app/utils/report_html.py` | 新建 | `HtmlReportGenerator.generate(record)` HTML 报告，样式同 eol_tester |
| `app/utils/report_excel.py` | 新建 | `ExcelReportGenerator.generate(record)` Excel 报告，样式同 eol_tester |
| `app/ui/main_window.py` | 修改 | 移除嵌入式 RunPanel，改用浮动窗口；运行结束调用 DB + 双格式报告生成 |
| `app/engine/database.py` | 不变 | 已有完整 `save_record` / `update_report_path`，无需修改 |
| `app/ui/run_panel.py` | 不变 | 被 `RunPanelWindow` 组合使用 |

### 2.2 RunPanelWindow 浮动窗口设计

```
RunPanelWindow(QWidget, Qt.Window)
├── RunPanel                   ← 现有组件，步骤表 + 日志
└── 底部工具栏（右对齐）
    ├── [📄 查看 HTML 报告]    ← 初始禁用，有 HTML 路径后激活
    └── [📊 查看 Excel 报告]   ← 初始禁用，有 Excel 路径后激活
```

- `Qt.Window` flag 使其成为独立系统窗口（有标题栏和 X 按钮）
- `closeEvent`：`event.ignore(); self.hide()`，X 只隐藏不销毁
- `set_report_paths(html_path, xlsx_path)`：分别存储并激活对应按钮
- `reset()` 时同时禁用两个按钮并清空路径
- 代理方法转发到内部 `RunPanel`：`reset`, `on_step_started`, `on_step_finished`, `on_log`, `on_done`, `on_aborted`

### 2.3 报告生成器设计（HTML + Excel）

**HTML（`app/utils/report_html.py`）**：
- 类接口：`HtmlReportGenerator.generate(record: TestRecord) -> str`（返回生成路径）
- 文件名：`<safe_plan_name>_<sn>_<YYYYMMDD_HHMMSS>.html`
- 样式与 eol_tester 保持一致：摘要卡片（带结果色块）+ 步骤明细表（行背景色区分 PASS/FAIL/SKIP/ERROR）
- 标题改为"测试报告"（通用，非"EOL"）

**Excel（`app/utils/report_excel.py`）**：
- 类接口：`ExcelReportGenerator.generate(record: TestRecord) -> str`（返回生成路径）
- 文件名：`<safe_plan_name>_<sn>_<YYYYMMDD_HHMMSS>.xlsx`
- 两个 Sheet："摘要"（1行汇总）+ "步骤明细"（每步一行）
- 样式与 eol_tester 完全相同（填充色、字体、边框）
- 包含 openpyxl 路径修复（见 2.6）

### 2.4 数据流：运行结束 → 保存 → 生成报告 → 通知窗口

```
TestRunner.sig_done(record)
    │
    ▼ MainWindow._on_run_done(record)
    ├─ Database.save_record(record)               → record_id
    ├─ HtmlReportGenerator.generate(record)       → html_path
    ├─ ExcelReportGenerator.generate(record)      → xlsx_path
    ├─ Database.update_report_path(id, html_path) → DB 存 html 路径
    └─ RunPanelWindow.set_report_paths(html_path, xlsx_path)
                                                  → 两个按钮激活
```

`sig_aborted` 只保存 DB（`overall_result="ABORT"`），不生成报告文件，按钮保持禁用。

### 2.5 MainWindow 改动要点

1. `__init__`：创建 `RunPanelWindow`（不 show）；初始化 `Database(os.path.join(REPORTS_DIR, "test_records.db"))`
2. `_build_body`：移除 `v_split`（垂直 QSplitter）和嵌入式 `RunPanel`；body 改为纯 `h_split`（PlanTree + StepEditor）
3. `_build_menu` / `_build_toolbar`："执行面板" toggle 改为 show/hide `RunPanelWindow`
4. `_run_plan`：运行前 `reset()` + `show()`；信号全部连接到 `RunPanelWindow` 的代理方法
5. `_on_run_done`：调用 DB + 两个报告生成器 + `set_report_paths`
6. 删除 `_toggle_run_panel`、`_panel_sizes` 废弃代码

### 2.6 openpyxl 路径修复

`siada_cli_venv` 中的 openpyxl 依赖一个损坏的 numpy（`AttributeError: class must define a '_type_' attribute`）。与 eol_tester 相同，`report_excel.py` 在 `import openpyxl` 前临时从 `sys.path` 移除 siada_cli_venv 路径，改用 uv 管理的 openpyxl，import 完成后恢复。具体路径常量直接复用 eol_tester 中已验证的值。

---

## 3. 实现步骤

### Step 1: 创建 RunPanelWindow 浮动窗口

- **状态**: [x] Done
- **Result**: 新建 `app/ui/run_panel_window.py`；`RunPanelWindow(QWidget, Qt.Window)` 含 `RunPanel` + 两个报告按钮；`closeEvent` hide-only；`set_report_paths` / `reset` / 代理方法全部实现。
- **内容**:
  新建 `app/ui/run_panel_window.py`，实现 `RunPanelWindow(QWidget)` 类：
  - 构造：`super().__init__(None, Qt.Window)`，`setWindowTitle("执行面板")`，`resize(960, 580)`
  - 布局：`QVBoxLayout` → `self.run_panel = RunPanel()` → 底部 `QHBoxLayout`（`addStretch()` + "📄 查看 HTML 报告"按钮 + "📊 查看 Excel 报告"按钮，两者初始 `setEnabled(False)`）
  - `closeEvent`：`event.ignore(); self.hide()`
  - `reset()`：禁用两个按钮，清空路径，调用 `self.run_panel.reset()`
  - `set_report_paths(html_path, xlsx_path)`：分别存储，按路径非空激活对应按钮
  - `_open_html()` / `_open_xlsx()`：`os.startfile(path)`（仅文件存在时调用）
  - 代理方法直接转发：`on_step_started`, `on_step_finished`, `on_log`, `on_done`, `on_aborted`
- **验收标准**:
  - `import` 无报错；`show()` 后独立窗口出现，点 X 后隐藏（进程不退出）
  - 两个报告按钮默认灰色；调用 `set_report_paths("a.html", "a.xlsx")` 后均变为可点击
  - `reset()` 后两个按钮重新变灰

### Step 2: 创建报告生成器（HTML + Excel）

- **状态**: [x] Done
- **Result**: 新建 `app/utils/__init__.py`（空）、`app/utils/report_html.py`（`HtmlReportGenerator`）、`app/utils/report_excel.py`（`ExcelReportGenerator` + openpyxl路径修复）；文件名含 `safe_plan_name`+`sn`+`ts`；HTML 标题改为"测试报告"；Excel 含"摘要"和"步骤明细"两个 Sheet。
- **内容**:
  1. 新建 `app/utils/__init__.py`（空文件）
  2. 新建 `app/utils/report_html.py`：
     - 复制 eol_tester 的 `HtmlReportGenerator` 和 `_build_html` 逻辑
     - 文件名改为 `<safe_plan_name>_<sn>_<ts>.html`（`safe_plan_name = re.sub(r'[\\/:*?"<>|]', '_', record.plan_name)`）
     - HTML 标题 `<h1>` 改为"测试报告"，`<title>` 改为"测试报告 — {plan_name}"
     - import 路径改为 `from app.config.settings import REPORTS_DIR` 和 `from app.engine.models import TestRecord`
  3. 新建 `app/utils/report_excel.py`：
     - 完整复制 eol_tester 的 `ExcelReportGenerator`、`_build_summary_sheet`、`_build_detail_sheet` 及 openpyxl 路径修复代码
     - 文件名同样改为 `<safe_plan_name>_<sn>_<ts>.xlsx`
     - import 路径同 HTML 版本
- **验收标准**:
  - `HtmlReportGenerator.generate(mock_record)` 生成 HTML 文件，浏览器打开后摘要和表格可见，中文无乱码
  - `ExcelReportGenerator.generate(mock_record)` 生成 xlsx 文件，Excel 打开后有"摘要"和"步骤明细"两个 Sheet，行背景色正确
  - 两者均不报 openpyxl/numpy 错误

### Step 3: 更新 MainWindow——替换嵌入式面板为浮动窗口

- **状态**: [x] Done
- **Result**: `main_window.py` 中移除 `v_split`/`RunPanel`/`_panel_sizes`/`_toggle_run_panel`；import 改为 `RunPanelWindow`、`Database`、`REPORTS_DIR`；`_build_body` 改为纯 `h_split`；`_run_plan` 信号全部连接到 `_run_panel_window`。
- **内容**，修改 `app/ui/main_window.py`：
  1. 新增 import：`from app.ui.run_panel_window import RunPanelWindow`；删除 `from app.ui.run_panel import RunPanel`（run_panel_window 内部导入，main_window 不再直接使用）
  2. `__init__` 末尾追加：`self._run_panel_window = RunPanelWindow()`
  3. `_build_body`：整个 `v_split`（`QSplitter(Qt.Vertical)`）及其内的 `RunPanel` 创建、`setSizes`、`_run_panel` 引用全部删除；body 改为只含 `h_split`，并在 `outer.addWidget(h_split)` 替换原 `outer.addWidget(v_split)`
  4. `_build_menu`："执行面板"的 `triggered` slot 改为 `lambda checked: self._run_panel_window.show() if checked else self._run_panel_window.hide()`
  5. `_run_plan`：`self._run_panel_window.reset()` + `self._run_panel_window.show()`；所有 `self._run_panel.*` 连接改为 `self._run_panel_window.*`
  6. `_on_step_started` 中 `self._run_panel.on_step_started(...)` 改为 `self._run_panel_window.on_step_started(...)`
  7. 删除 `_toggle_run_panel` 方法和 `self._panel_sizes` 属性
- **验收标准**:
  - 主窗口启动，body 全部为 PlanTree/StepEditor，无嵌入执行面板
  - 点"执行面板"按钮，浮动窗口弹出；点 X 隐藏；再点按钮重新显示
  - 运行计划时浮动窗口自动弹出，步骤实时更新

### Step 4: 更新 MainWindow——运行结束时保存数据库并生成报告

- **状态**: [x] Done
- **Result**: `_on_run_done` 中 try/except 块调用 `Database.save_record` + `HtmlReportGenerator.generate` + `ExcelReportGenerator.generate` + `update_report_path` + `set_report_paths`；失败时 on_log 输出错误；`_on_run_aborted` 不生成报告。
- **内容**，继续修改 `app/ui/main_window.py`：
  1. 新增 import：`import re`；`from app.engine.database import Database`；`from app.utils.report_html import HtmlReportGenerator`；`from app.utils.report_excel import ExcelReportGenerator`；`from app.config.settings import REPORTS_DIR`
  2. `__init__` 中追加：`self._db = Database(os.path.join(REPORTS_DIR, "test_records.db"))`
  3. `_on_run_done(record)` 末尾追加：
     ```python
     try:
         record_id = self._db.save_record(record)
         html_path = HtmlReportGenerator.generate(record)
         xlsx_path = ExcelReportGenerator.generate(record)
         self._db.update_report_path(record_id, html_path)
         self._run_panel_window.set_report_paths(html_path, xlsx_path)
     except Exception as exc:
         self._run_panel_window.on_log(f"[报告生成失败] {exc}")
     ```
  4. `_on_run_aborted(reason)` 末尾追加（仅 DB 保存，不生成报告）：
     ```python
     try:
         self._db.save_record(record)
     except Exception:
         pass
     ```
     注意：`sig_aborted` 只传 `reason: str`，不传 record。需在 `runner.py` 的 `sig_aborted` 之前先通过 `sig_done` 路径处理，或在 `_on_run_aborted` 中记录日志即可，不做 DB 保存（保持简单，ABORT 无完整 record）。
  5. 最终结论：`_on_run_aborted` 中**不做** DB 保存（`sig_aborted` 不携带 record，无法保存步骤结果），只更新 UI；DB 保存和报告生成仅在 `_on_run_done` 中执行。
- **验收标准**:
  - 跑完一次测试（正常结束），`reports/` 中同时出现 `.html` 和 `.xlsx` 文件
  - `reports/test_records.db` 中有对应记录，`report_path` 字段指向 HTML 文件
  - 执行面板两个报告按钮均激活，点击后系统默认程序打开对应文件
  - 中止（ABORT）时两个按钮保持禁用，`reports/` 目录无新文件生成
