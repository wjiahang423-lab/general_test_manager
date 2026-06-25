"""
measure_adc_item.py — ADC 单项测量

params（由 loop 展开后注入）：
  var_name : str — A2L 变量名
  length   : int — 字节长度（1 或 2）
  name     : str — 测试项名称
  min/max  : int — 由框架 limits 判断

返回 value = int（有符号整数），pass = True（limits 由框架判断）
"""

import sys
import os
from PCANBasic import *

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session
from core import DiagnosticProtocol

diag = DiagnosticProtocol(
    pcan_manager=PCAN_USBBUS1,
    send_can_id=0x7F1
)


def measure(params: dict) -> dict:
    var_name = params.get("var_name", "")
    length = int(params.get("length", 2))
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
        value = int.from_bytes(bytes_data, "big", signed=True)

        return {
            "value": value,
            "unit": "",
            "pass": True,  # 数值范围由 step limits 判断
            "message": f"{item_name}: {value}",
        }
    except Exception as exc:
        return {"value": None, "unit": "", "pass": False, "message": str(exc)}


def check_app_version(params: dict) -> dict:
    var_name = params.get("did_name", "")
    length = int(params.get("length", 2))
    item_name = params.get("did_name", var_name)
    expected = params.get("expected", "")

    try:
        # 1. 读取EOL版本
        response = diag.read_did(0xF1, 0x95)
        assert response is not None, "读取F195 DID失败"
        _version = ''
        if response and len(response) >= 6 and response[0:4] == [0x05, 0x62, 0xF1, 0x95]:
            _version = bytes(response[4:6]).hex()

        if response is None:
            return {"value": None, "unit": "", "pass": False,
                    "message": f"{item_name}: 读取失败（返回 None）"}

        if _version == expected:

            return {
                "value": _version,
                "unit": "",
                "pass": True,  # 数值范围由 step limits 判断
                "message": f"{item_name}: {_version}",
            }
    except Exception as exc:
        return {"value": None, "unit": "", "pass": False, "message": str(exc)}


def switch_to_app():
    try:
        config, xcp, a2l = get_session()
        xcp.xcp_ff()
        xcp.xcp_eb()
        assert xcp.xcp_f6('Eol_To_App_Flag', a2l, 0), "设置Eol_To_App_Flag地址失败"
        assert xcp.xcp_f0("01"), "写入Eol_To_App_Flag(01)失败"
        # 等待并确认
        import time
        time.sleep(1)

        assert xcp.xcp_f6('Eol_To_App_Flag', a2l, 0), "设置Eol_To_App_Flag地址失败"
        if not xcp.xcp_f0("02"):
            return {
                "value": 1,
                "unit": "",
                "pass": True,  # 数值范围由 step limits 判断
                "message": "switch_to_app",
            }
    except Exception as exc:
        return {"value": None, "unit": "", "pass": False, "message": str(exc)}
