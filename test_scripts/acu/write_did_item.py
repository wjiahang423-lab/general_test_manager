"""
write_did_item.py — 单个 DID 写入

params（由 loop 展开后注入）：
  did_name : str — DID 标识符（如 'F187'）
  var_name : str — A2L 变量名（did_rw_flag 等）
  length   : int — 字节长度
  expected : str — 要写入的值

编码规则：
  F193：hex 编码（直接按16进制，反转后写入）
  其他：ASCII 编码（空格右补全到 length 字节，反转后分批写入）
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session

_DID_ITEM_MAP = {"F187": "01", "F18A": "02", "F18C": "03", "F193": "05"}


def measure(params: dict) -> dict:
    did_name = str(params.get("did_name", ""))
    did_length = int(params.get("length", 1))
    write_value = str(params.get("expected", ""))

    try:
        config, xcp, a2l = get_session()

        # 前置：进入 DID 写入模式
        if not xcp.xcp_ff():
            return _fail(did_name, "XCP FF 命令失败")
        if not xcp.xcp_eb():
            return _fail(did_name, "XCP EB 命令失败")
        if not xcp.xcp_f6("did_rw_flag", a2l, 0):
            return _fail(did_name, "设置 did_rw_flag 地址失败")
        if not xcp.xcp_f0("01"):
            return _fail(did_name, "设置写入标志失败")

        # 编码
        if did_name == "F193":
            hex_padded = write_value.zfill(did_length)
            bytes_data = bytes.fromhex(hex_padded)
            hex_data = bytes_data[::-1].hex()
        else:
            hex_data = "".join(format(ord(c), "02x") for c in write_value.ljust(did_length))

        # 分批写入（每批最多 6 字节）
        max_batch = 6
        total_bytes = len(hex_data) // 2
        for offset in range(0, total_bytes, max_batch):
            end_idx = (offset + max_batch) * 2
            chunk_hex = hex_data[offset * 2: end_idx]
            if not chunk_hex:
                continue
            chunk_bytes = bytes.fromhex(chunk_hex)
            if did_name == "F193":
                chunk_rev = chunk_bytes          # 已提前整体反转
            else:
                chunk_rev = chunk_bytes[::-1]

            if not xcp.xcp_f6("DID_Write_Data", a2l, offset):
                return _fail(did_name, f"设置 DID_Write_Data 地址失败（偏移={offset}）")
            if not xcp.xcp_f0(chunk_rev.hex()):
                return _fail(did_name, f"写入数据失败（偏移={offset}）")
            time.sleep(0.1)

        # 设置写入项目编号
        item_code = _DID_ITEM_MAP.get(did_name, "01")
        if not xcp.xcp_f6("did_rw_items", a2l, 0):
            return _fail(did_name, "设置 did_rw_items 地址失败")
        if not xcp.xcp_f0(item_code):
            return _fail(did_name, f"设置写入项目 {item_code} 失败")

        clean = "".join(c for c in write_value if c.isprintable())
        return {
            "value": clean,
            "unit": "",
            "pass": True,
            "message": f"DID {did_name} 写入成功：{clean}",
        }
    except Exception as exc:
        return {"value": None, "unit": "", "pass": False, "message": str(exc)}


def _fail(did_name: str, reason: str) -> dict:
    return {"value": "FAIL", "unit": "", "pass": False,
            "message": f"DID {did_name} 写入失败：{reason}"}
