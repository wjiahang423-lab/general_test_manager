"""
check_sma_item.py — SMA 传感器有效性检测（通用参数化版本）

params（由 loop 展开后注入）：
  name         : str — 测试项名称
  var_name     : str — A2L 变量名
  length       : int — 字节长度（通常为 1）
  expected_int : int — 期望整数值（通常为 0）

返回 value = int，pass = (actual_int == expected_int)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session


def measure(params: dict) -> dict:
    var_name = params.get("var_name", "")
    length = int(params.get("length", 1))
    expected_int = int(params.get("expected_int", 0))
    item_name = params.get("name", var_name)

    try:
        config, xcp, a2l = get_session()
        result_hex = xcp.read_variable(
            variable_name=var_name,
            a2l_dic=a2l,
            offset=0,
            length=length,
        )
        if result_hex is None:
            return {
                "value": None, "unit": "", "pass": False,
                "message": f"{item_name}: 读取失败（返回 None）",
            }

        actual_int = int(result_hex, 16)
        passed = actual_int == expected_int
        return {
            "value": actual_int,
            "unit": "",
            "pass": passed,
            "message": f"{item_name}: 读取={result_hex}（int={actual_int}），期望={expected_int}",
        }
    except Exception as exc:
        return {"value": None, "unit": "", "pass": False, "message": str(exc)}
