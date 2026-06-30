"""
measure_fire_loop_item.py — 单路火回路阻值测量

params（由 loop 展开后注入）：
  var_name  : str    — A2L 变量名
  length    : int    — 字节长度（通常 4，float32）
  name      : str    — 测试项名称（用于 message）
  min / max : float  — 由框架 limits 判断，脚本只负责读值并返回 float

返回 value = float（Ω），pass = True（limits 由框架判断）
"""

import sys
import os
import struct
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session


def measure(params: dict) -> dict:
    var_name = params.get("var_name", "")
    length = int(params.get("length", 4))
    item_name = params.get("name", var_name)
    time.sleep(1)
    try:
        config, xcp, a2l = get_session()
        result_hex = xcp.read_variable(
            variable_name=var_name,
            a2l_dic=a2l,
            offset=0,
            length=length,
        )
        if result_hex is None:
            return {"value": None, "unit": "Ω", "pass": False,
                    "message": f"{item_name}: 读取失败（返回 None）"}

        bytes_data = bytes.fromhex(result_hex)
        resistance = struct.unpack(">f", bytes_data)[0]

        return {
            "value": round(resistance, 4),
            "unit": "Ω",
            "pass": True,   # 数值范围由 step limits 判断
            "message": f"{item_name}: {resistance:.4f} Ω",
        }
    except Exception as exc:
        return {"value": None, "unit": "Ω", "pass": False, "message": str(exc)}
