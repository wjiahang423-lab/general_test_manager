"""
_session.py — ACU 硬件会话单例

通过模块级变量持久化 PCAN/XCP/A2L 资源，利用 Python sys.modules 缓存在
同一进程的多次 sandbox 调用之间共享同一连接，避免重复初始化。

用法（在所有 acu 包装脚本中）：
    from _session import get_session, close_session
    config, xcp, a2l = get_session()
"""

from __future__ import annotations

import atexit
import os
import sys

# 确保 acu 目录和 core/ 都在 sys.path 中，使得 import PCANBasic 和 import core.xxx 正常工作
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_CORE = os.path.join(_HERE, "core")
if _CORE not in sys.path:
    sys.path.insert(0, _CORE)

import yaml
from core.pcan_manager import PCANManager
from core.xcp_protocol import XCPProtocol
from core.utils import parse_a2l
from PCANBasic import PCAN_USBBUS1
import time

# ---------------------------------------------------------------------------
# 模块级单例状态
# ---------------------------------------------------------------------------

_config: dict | None = None
_pcan: PCANManager | None = None
_xcp: XCPProtocol | None = None
_a2l: dict | None = None


def _load_config() -> dict:
    config_path = os.path.join(_HERE, "test_data", "test_config.yaml")
    with open(config_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _init_pcan(config: dict) -> PCANManager:
    recv_id = config["can_ids"].get("recv", 0x6C7)
    dig_recv_id = config["can_ids"].get("dig_recv", 0x7F9)
    pcan = PCANManager()
    if not pcan.initialize(PCAN_USBBUS1, recv_id, dig_recv_id):
        raise RuntimeError(
            f"PCAN 初始化失败。通道: PCAN_USBBUS1  recv_id={hex(recv_id)}  dig_recv_id={hex(dig_recv_id)}"
        )
    return pcan


def get_session() -> tuple[dict, XCPProtocol, dict]:
    """返回 (config, xcp_protocol, a2l_dic)，首次调用时完整初始化，后续复用缓存。"""
    global _config, _pcan, _xcp, _a2l

    if _xcp is None:
        _config = _load_config()
        _pcan = _init_pcan(_config)
        _xcp = XCPProtocol(
            pcan_manager=_pcan,
            CAN_ID_SEND=_config["can_ids"]["send"],
        )
        a2l_path = _config["file_paths"]["a2l_file"]
        if not os.path.isabs(a2l_path):
            a2l_path = os.path.join(_HERE, a2l_path)
        _a2l = parse_a2l(a2l_path)

    return _config, _xcp, _a2l


def close_session() -> None:
    """关闭 PCAN 连接并清空缓存，进程退出时由 atexit 自动调用。"""
    global _config, _pcan, _xcp, _a2l
    if _pcan is not None:
        try:
            _pcan.close(PCAN_USBBUS1)
        except Exception:
            pass
    _config = _pcan = _xcp = _a2l = None


atexit.register(close_session)


# 延时函数
def delay(sec: int) -> None:
    time.sleep(sec)


def get_sn(params: dict) -> str:
    try:
        return params.get("sn", "None")
    except Exception as e:
        return str(e)


def get_all_test_result(params: dict) -> dict:
    try:
        result = params.get("overall_result", "")
        return {
            "value": result,
            "unit": "",
            "pass": True,
            "message": f"读取overall_result ={result}",
        }
    except Exception as e:
        return str(e)


def measure(params: dict) -> dict:
    sn = params.get("sn", "")
    print(f"读取SN ={sn}")
    return {
        "value": sn,
        "unit": "",
        "pass": True,
        "message": f"读取SN ={sn}",
    }


def get_(string: str) -> str:
    return string


def get_bool(result: bool) -> bool:
    return result


def num_str_to_ascii(num_string: str, separator: str = " ") -> str:
    """将数字类型字符串转换为 ASCII 字符串。

    例如:
        num_str_to_ascii("123") -> "123"
        num_str_to_ascii("505a4355") -> "PZCU"
    """
    if not isinstance(num_string, str):
        raise TypeError("输入必须是字符串")

    if num_string.isdecimal():
        return num_string

    hex_digits = "0123456789abcdefABCDEF"
    if len(num_string) % 2 != 0 or any(ch not in hex_digits for ch in num_string):
        raise ValueError("输入必须是只包含数字的字符串，或长度为偶数的十六进制字符串")
    decoded = bytes.fromhex(num_string)
    return decoded.decode("latin1")



if __name__ == "__main__":
    print(num_str_to_ascii("505a43"))