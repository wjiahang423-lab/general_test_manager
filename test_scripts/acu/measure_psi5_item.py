"""
measure_psi5_item.py — 单路 PSI5 传感器测量

params（由 loop 展开后注入）：
  var_name : str — A2L 变量名
  length   : int — 字节长度（1 或 2）
  expected : str — 期望十六进制字符串（精确匹配）
  name     : str — 测试项名称

返回 value = str（hex），pass = (result == expected)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session


def measure(params: dict) -> dict:
    var_name = params.get("var_name", "")
    length = int(params.get("length", 1))
    expected = str(params.get("expected", ""))
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
            return {"value": None, "unit": "", "pass": False,
                    "message": f"{item_name}: 读取失败（返回 None）"}

        passed = result_hex == expected
        return {
            "value": result_hex,
            "unit": "",
            "pass": passed,
            "message": f"{item_name}: 读取={result_hex}，期望={expected}",
        }
    except Exception as exc:
        return {"value": None, "unit": "", "pass": False, "message": str(exc)}
