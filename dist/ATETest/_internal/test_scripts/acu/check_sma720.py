"""
check_sma720.py — SMA720 有效性检测

读取 DvEol_ObsIMUIn_Sma720DataValid_b（1 字节），期望整数值 0。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session


def measure(params: dict) -> dict:
    try:
        config, xcp, a2l = get_session()
        result_hex = xcp.read_variable(
            variable_name="DvEol_ObsIMUIn_Sma720DataValid_b",
            a2l_dic=a2l,
            offset=0,
            length=1,
        )
        actual_int = int(result_hex, 16) if result_hex else -1
        passed = actual_int == 0
        return {
            "value": actual_int,
            "unit": "",
            "pass": passed,
            "message": f"Sma720DataValid={result_hex}（int={actual_int}），期望=0",
        }
    except Exception as exc:
        return {"value": None, "unit": "", "pass": False, "message": str(exc)}
