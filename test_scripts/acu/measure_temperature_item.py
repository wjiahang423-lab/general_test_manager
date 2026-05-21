"""
measure_temperature_item.py — 温度单项测量

params（由 loop 展开后注入）：
  var_name : str — A2L 变量名
  length   : int — 字节长度（4=float32, 2=signed int16）
  name     : str — 测试项名称
  min/max  : float — 由框架 limits 判断

返回 value = float，pass = True（limits 由框架判断）
"""

import sys
import os
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session


def measure(params: dict) -> dict:
    var_name = params.get("var_name", "")
    length = int(params.get("length", 4))
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
            return {"value": None, "unit": "°C", "pass": False,
                    "message": f"{item_name}: 读取失败（返回 None）"}

        bytes_data = bytes.fromhex(result_hex)
        if length == 4:
            value = struct.unpack(">f", bytes_data)[0]
        else:
            value = float(int.from_bytes(bytes_data, "big", signed=True))

        return {
            "value": round(value, 4),
            "unit": "°C",
            "pass": True,   # 数值范围由 step limits 判断
            "message": f"{item_name}: {value:.4f} °C",
        }
    except Exception as exc:
        return {"value": None, "unit": "°C", "pass": False, "message": str(exc)}
