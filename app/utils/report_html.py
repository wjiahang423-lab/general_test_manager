"""
HtmlReportGenerator — produces a self-contained HTML test report.

Usage
-----
    path = HtmlReportGenerator.generate(record)   # returns file path
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from app.config.settings import REPORTS_DIR
from app.engine.models import TestRecord


_STATUS_COLOR = {
    "PASS":  "#1a8a1a",
    "FAIL":  "#cc1a1a",
    "ERROR": "#c87020",
    "SKIP":  "#888888",
    "ABORT": "#c87020",
}

_STATUS_BG = {
    "PASS":  "#e8f5e9",
    "FAIL":  "#ffebee",
    "ERROR": "#fff3e0",
    "SKIP":  "#f5f5f5",
    "ABORT": "#fff3e0",
}


class HtmlReportGenerator:
    @staticmethod
    def generate(record: TestRecord) -> str:
        """Generate HTML report for *record* and return the file path."""
        os.makedirs(REPORTS_DIR, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_plan = re.sub(r'[\\/:*?"<>|]', '_', record.plan_name)
        safe_sn   = record.sn.replace("/", "_").replace("\\", "_")
        filename  = f"{safe_plan}_{safe_sn}_{ts}.html"
        path      = os.path.join(REPORTS_DIR, filename)

        html = _build_html(record)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return path


# ---------------------------------------------------------------------------
# Internal builder
# ---------------------------------------------------------------------------

def _build_html(record: TestRecord) -> str:
    overall_color = _STATUS_COLOR.get(record.overall_result, "#333333")
    overall_bg    = _STATUS_BG.get(record.overall_result,    "#f5f5f5")

    rows_html = ""
    for i, sr in enumerate(record.step_results, 1):
        fg     = _STATUS_COLOR.get(sr.result, "#333333")
        row_bg = _STATUS_BG.get(sr.result, "#ffffff")
        val_str = f"{sr.value} {sr.unit}".strip() if sr.value is not None else "—"
        rows_html += (
            f"<tr style='background:{row_bg}'>"
            f"<td style='text-align:center'>{i}</td>"
            f"<td>{_esc(sr.seq_name)}</td>"
            f"<td>{_esc(sr.step_name)}</td>"
            f"<td style='color:{fg};font-weight:bold;text-align:center'>{sr.result}</td>"
            f"<td style='text-align:right'>{_esc(val_str)}</td>"
            f"<td style='text-align:right'>{sr.duration_ms} ms</td>"
            f"<td>{_esc(sr.message)}</td>"
            f"</tr>\n"
        )

    passed = sum(1 for r in record.step_results if r.result == "PASS")
    total  = len(record.step_results)

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>测试报告 — {_esc(record.plan_name)}</title>
<style>
  body   {{ font-family:'Microsoft YaHei',Arial,sans-serif; background:#f0f2f5;
            color:#222; margin:0; padding:24px; }}
  h1     {{ color:#222; border-bottom:2px solid #d0d0d0; padding-bottom:10px;
            margin-bottom:16px; font-size:1.6em; }}
  .badge {{ display:inline-block; padding:8px 32px; border-radius:8px;
            font-size:2.2em; font-weight:bold;
            color:{overall_color}; background:{overall_bg};
            border:2px solid {overall_color}; margin-bottom:16px; }}
  .info  {{ background:#ffffff; border:1px solid #dde3ec; border-radius:8px;
            padding:16px 24px; margin:16px 0;
            display:grid; grid-template-columns:1fr 1fr; gap:8px 32px; }}
  .info span.k {{ color:#1a5fb4; font-weight:bold; }}
  table  {{ width:100%; border-collapse:collapse; background:#ffffff;
            border:1px solid #dde3ec; border-radius:8px;
            overflow:hidden; margin-top:16px; box-shadow:0 1px 4px #0001; }}
  th     {{ background:#e8edf4; color:#333; padding:10px 14px;
            text-align:left; font-size:13px; border-bottom:2px solid #c8d0dc; }}
  td     {{ padding:8px 14px; border-bottom:1px solid #eaeef4;
            font-size:13px; color:#333; }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ filter:brightness(0.96); }}
</style>
</head>
<body>
<h1>测试报告</h1>
<div class="badge">{record.overall_result}</div>
<div class="info">
  <div><span class="k">测试计划：</span>{_esc(record.plan_name)} v{_esc(record.plan_version)}</div>
  <div><span class="k">运行编号：</span>{_esc(record.sn)}</div>
  <div><span class="k">开始时间：</span>{_esc(record.start_time)}</div>
  <div><span class="k">结束时间：</span>{_esc(record.end_time)}</div>
  <div><span class="k">步骤总数：</span>{total}</div>
  <div><span class="k">通过步骤：</span>{passed} / {total}</div>
</div>
<table>
<thead>
  <tr>
    <th>#</th><th>序列</th><th>步骤名称</th><th>结果</th>
    <th>测量值</th><th>耗时</th><th>消息</th>
  </tr>
</thead>
<tbody>
{rows_html}</tbody>
</table>
</body>
</html>
"""


def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
