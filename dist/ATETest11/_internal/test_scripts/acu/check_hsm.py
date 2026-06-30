"""
check_hsm.py — HSM 开启检测

读取 ACU_HSM_Status（1 字节），期望值 '01'。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session


def measure(params: dict) -> dict:
    try:
        config, xcp, a2l = get_session()
        result_hex = xcp.read_variable(
            variable_name="ACU_HSM_Status",
            a2l_dic=a2l,
            offset=0,
            length=1,
        )
        expected = "01"
        passed = result_hex == expected
        return {
            "value": result_hex,
            "unit": "",
            "pass": passed,
            "message": f"ACU_HSM_Status={result_hex}，期望={expected}",
        }
    except Exception as exc:
        return {"value": None, "unit": "", "pass": False, "message": str(exc)}
