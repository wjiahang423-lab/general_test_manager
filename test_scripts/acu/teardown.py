"""
teardown.py — ACU EOL 清理步骤

执行顺序：
  1. 关闭硬件会话（PCAN 连接）
  2. KL15 / KL30 断电
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import close_session
from core.serial_com_relay import Kl15_close, Kl30_close


def teardown(params: dict) -> dict:
    try:
        close_session()
        Kl15_close()
        Kl30_close()
        return {"value": "OK", "unit": "", "pass": True, "message": "断连并断电完成"}
    except Exception as exc:
        return {"value": "ERROR", "unit": "", "pass": False, "message": str(exc)}
