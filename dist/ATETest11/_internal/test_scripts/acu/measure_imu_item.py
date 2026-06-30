"""
measure_imu_item.py — SMI970 IMU 单项测量（加速度/角速度）

params（由 loop 展开后注入）：
  var_name : str   — A2L 变量名
  length   : int   — 字节长度（通常 4，float32）
  name     : str   — 测试项名称
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
            return {"value": None, "unit": "", "pass": False,
                    "message": f"{item_name}: 读取失败（返回 None）"}

        bytes_data = bytes.fromhex(result_hex)
        value = struct.unpack(">f", bytes_data)[0]

        return {
            "value": round(value, 6),
            "unit": "",
            "pass": True,   # 数值范围由 step limits 判断
            "message": f"{item_name}: {value:.6f}",
        }
    except Exception as exc:
        return {"value": None, "unit": "", "pass": False, "message": str(exc)}
