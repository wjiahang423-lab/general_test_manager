"""
读取 _excel_dump.json，生成 rzcu/test_data/test_items.yaml
每个 sheet 的行按字段拆分成独立 YAML 字段，方便数据驱动循环使用。
只保留 is_test=="是" 的条目（disabled 行不写入）。
"""
import json
import os
import sys

SRC  = r"D:\Siada\general_test_manager\_excel_dump.json"
DST  = r"D:\Siada\general_test_manager\test_scripts\rzcu\test_data\test_items.yaml"

with open(SRC, encoding="utf-8") as f:
    data = json.load(f)


def _sv(v):
    """safe value → str or int/float"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    return s if s else None


def _int(v):
    try:
        return int(float(str(v).strip()))
    except Exception:
        return None


def _str(v):
    if v is None:
        return ""
    return str(v).strip()


def parse_od(row):
    """RZCU_OD: 期望值="DI电平,电流mA", 无效期望值同格式"""
    exp = _str(row.get("期望值", ""))
    unexp = _str(row.get("无效期望值", ""))
    ev, ec, uv, uc = None, None, None, None
    try:
        parts = exp.split(",")
        ev, ec = int(parts[0]), int(parts[1])
    except Exception:
        pass
    try:
        parts = unexp.split(",")
        uv, uc = int(parts[0]), int(parts[1])
    except Exception:
        pass
    return {
        "name":             _str(row.get("测试项名称")),
        "pin":              _str(row.get("pin")),
        "channel":          _str(row.get("对应通道")),
        "cal_var":          _str(row.get("标定量")),
        "obs_var":          _str(row.get("观测量")),
        "expected_voltage": ev,
        "expected_current": ec,
        "invalid_voltage":  uv,
        "invalid_current":  uc,
    }


def parse_od_v(row):
    """RZCU_OD_V: 期望值=电压mV单值, 无效期望值=电压上限"""
    return {
        "name":             _str(row.get("测试项名称")),
        "pin":              _str(row.get("pin")),
        "channel":          _str(row.get("对应通道")),
        "cal_var":          _str(row.get("标定量")),
        "obs_var":          _str(row.get("观测量")),
        "expected_voltage": _int(row.get("期望值")),
        "invalid_voltage":  _int(row.get("无效期望值")),
    }


def parse_ia_r(row):
    """RZCU_IA_R: 电阻型输入, set_value=有效设置欧姆值"""
    return {
        "name":             _str(row.get("测试项名称")),
        "pin":              _str(row.get("pin")),
        "channel":          _str(row.get("对应通道")),
        "obs_var":          _str(row.get("观测量")),
        "set_value":        _int(row.get("设置值")),
        "expected":         _int(row.get("期望值")),
        "invalid_expected": _int(row.get("无效期望值")),
    }


def parse_ia_v(row):
    """RZCU_IA_V: 电压型输入"""
    return {
        "name":               _str(row.get("测试项名称")),
        "pin":                _str(row.get("pin")),
        "channel":            _str(row.get("对应通道")),
        "obs_var":            _str(row.get("观测量")),
        "set_value":          _int(row.get("设置值")),
        "expected":           _int(row.get("期望值")),
        "invalid_set_value":  _int(row.get("无效设置值")),
        "invalid_expected":   _int(row.get("无效期望值")),
    }


def parse_id(row):
    """RZCU_ID: 数字输入 (开关)"""
    return {
        "name":               _str(row.get("测试项名称")),
        "pin":                _str(row.get("pin")),
        "channel":            _str(row.get("对应通道")),
        "obs_var":            _str(row.get("观测量")),
        "set_value":          _int(row.get("设置值")),
        "expected":           _int(row.get("期望值")),
        "invalid_set_value":  _int(row.get("无效设置值")),
        "invalid_expected":   _int(row.get("无效期望值")),
    }


def parse_ip(row):
    """RZCU_IP: 电源输入"""
    return {
        "name":             _str(row.get("测试项名称")),
        "pin":              _str(row.get("pin")),
        "channel":          _str(row.get("对应通道")),
        "obs_var":          _str(row.get("观测量")),
        "expected":         _int(row.get("期望值")),
        "invalid_expected": _int(row.get("无效期望值")),
    }


def parse_op(row):
    """RZCU_OP: PWM 输出, 期望值="freq,duty,current", 无效=电流上限"""
    exp = _str(row.get("期望值", ""))
    ef, ed, ec = None, None, None
    try:
        parts = exp.split(",")
        ef, ed, ec = int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        pass
    return {
        "name":             _str(row.get("测试项名称")),
        "pin":              _str(row.get("pin")),
        "channel":          _str(row.get("对应通道")),
        "cal_var":          _str(row.get("标定量")),
        "obs_var":          _str(row.get("观测量")),
        "expected_freq":    ef,
        "expected_duty":    ed,
        "expected_current": ec,
        "invalid_current":  _int(row.get("无效期望值")),
    }


def parse_hbri(row):
    """RZCU_HBRI / RZCU_HBRI_8912: 期望值="freq,duty,current" 或 "NA,NA,current"
       set_value = 方向值 (整数, 转为 01/02 hex)"""
    exp = _str(row.get("期望值", ""))
    ef, ed, ec = None, None, None
    try:
        parts = exp.split(",")
        ef_s = parts[0].strip()
        ed_s = parts[1].strip()
        ec   = int(parts[2])
        ef   = None if ef_s.upper() == "NA" else int(ef_s)
        ed   = None if ed_s.upper() == "NA" else int(ed_s)
    except Exception:
        pass
    return {
        "name":             _str(row.get("测试项名称")),
        "pin":              _str(row.get("pin")),
        "channel":          _str(row.get("对应通道")),
        "set_value":        _int(row.get("设置值")),   # 方向: 1 or 2
        "cal_var":          _str(row.get("标定量")),
        "obs_var":          _str(row.get("观测量")),
        "expected_freq":    ef,
        "expected_duty":    ed,
        "expected_current": ec,
        "invalid_current":  _int(row.get("无效期望值")),
    }


PARSERS = {
    "RZCU_OD":       parse_od,
    "RZCU_OD_V":     parse_od_v,
    "RZCU_IA_R":     parse_ia_r,
    "RZCU_IA_V":     parse_ia_v,
    "RZCU_ID":       parse_id,
    "RZCU_IP":       parse_ip,
    "RZCU_OP":       parse_op,
    "RZCU_HBRI":     parse_hbri,
    "RZCU_HBRI_8912": parse_hbri,
}


# ── 简单 YAML 序列化（不依赖 pyyaml，避免 encoding 问题）──────────

def _yaml_str(s: str) -> str:
    """将字符串序列化为 YAML 双引号值，转义特殊字符"""
    if s is None:
        return "null"
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def _yaml_val(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return _yaml_str(str(v))


def item_to_yaml(item: dict, indent: int = 4) -> str:
    """将一个 dict 序列化为 YAML 项（以 "- " 开头）"""
    sp = " " * indent
    lines = []
    first = True
    for k, v in item.items():
        prefix = "- " if first else "  "
        lines.append(f"{sp}{prefix}{k}: {_yaml_val(v)}")
        first = False
    return "\n".join(lines)


# ── 生成 YAML ──────────────────────────────────────────────────

out_lines = [
    "# RZCU EOL 测试数据 — 自动从 RzcuTestCase_SKU4.xlsx 生成",
    "# 格式: 每个 sheet 为一个顶层 key，值为列表，每项为一个测试用例",
    "# 只保留 是否测试==是 的条目",
    "",
]

for sheet_name, parser in PARSERS.items():
    if sheet_name not in data:
        sys.stderr.write(f"[warn] sheet {sheet_name} not found in dump, skip\n")
        continue

    rows = data[sheet_name]["rows"]
    items = []
    for row in rows:
        if _str(row.get("是否测试")) != "是":
            continue
        try:
            item = parser(row)
            items.append(item)
        except Exception as e:
            sys.stderr.write(f"[warn] {sheet_name} parse row error: {e} row={row}\n")

    out_lines.append(f"{sheet_name}:")
    if not items:
        out_lines.append("  []")
    else:
        for item in items:
            out_lines.append(item_to_yaml(item, indent=2))
    out_lines.append("")
    sys.stderr.write(f"  {sheet_name}: {len(items)} enabled items\n")


yaml_content = "\n".join(out_lines)
with open(DST, "w", encoding="utf-8") as f:
    f.write(yaml_content)
sys.stderr.write(f"\nSaved → {DST}\n")
