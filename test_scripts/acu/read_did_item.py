"""
read_did_item.py — 单个 DID 读取验证

params（由 loop 展开后注入）：
  did_name : str — DID 标识符（如 'F187'）
  var_name : str — A2L 变量名
  length   : int — 字节长度
  expected : str — 期望值

解码规则：
  F193：hex 字符串（反转后取前 N 位并补0）
  其他：ASCII 解码（反转后 decode ascii，去空字节，截取到期望值长度）
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session

_DID_ITEM_MAP = {"F187": "01", "F18A": "02", "F18C": "03", "F193": "05"}


def measure(params: dict) -> dict:
    did_name = str(params.get("did_name", ""))
    did_var_name = str(params.get("var_name", ""))
    did_length = int(params.get("length", 1))
    did_expected = str(params.get("expected", ""))
    expected_len = len(did_expected)

    try:
        config, xcp, a2l = get_session()

        # 前置：进入 DID 读取模式
        if not xcp.xcp_ff():
            return _fail(did_name, "XCP FF 命令失败")
        if not xcp.xcp_eb():
            return _fail(did_name, "XCP EB 命令失败")
        if not xcp.xcp_f6("did_rw_flag", a2l, 0):
            return _fail(did_name, "设置 did_rw_flag 地址失败")
        if not xcp.xcp_f0("02"):
            return _fail(did_name, "设置读取标志失败")

        # 设置读取项目编号
        item_code = _DID_ITEM_MAP.get(did_name, "01")
        if not xcp.xcp_f6("did_rw_items", a2l, 0):
            return _fail(did_name, "设置 did_rw_items 地址失败")
        if not xcp.xcp_f0(item_code):
            return _fail(did_name, f"设置读取项目 {item_code} 失败")
        time.sleep(0.1)

        # 读取
        result_hex = xcp.read_variable(
            variable_name=did_var_name,
            a2l_dic=a2l,
            offset=0,
            length=did_length,
        )
        if not result_hex:
            return _fail(did_name, "读取结果为空")

        # 解码
        bytes_data = bytes.fromhex(result_hex)
        bytes_rev = bytes_data[::-1]

        if did_name == "F193":
            read_value = bytes_rev.hex().upper()[:expected_len].zfill(expected_len)
        else:
            read_value = bytes_rev.decode("ascii", errors="ignore").replace("\x00", "").strip()
            read_value = read_value[:expected_len]

        clean = "".join(c for c in read_value if c.isprintable())
        expected_trunc = did_expected[:len(read_value)]
        passed = clean == expected_trunc

        return {
            "value": clean,
            "unit": "",
            "pass": passed,
            "message": f"DID {did_name}: 读取='{clean}'，期望='{did_expected}'",
        }
    except Exception as exc:
        return {"value": None, "unit": "", "pass": False, "message": str(exc)}


def _fail(did_name: str, reason: str) -> dict:
    return {"value": "FAIL", "unit": "", "pass": False,
            "message": f"DID {did_name} 读取失败：{reason}"}
