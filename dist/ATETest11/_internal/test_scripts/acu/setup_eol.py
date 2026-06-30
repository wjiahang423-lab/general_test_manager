"""
setup_eol.py — ACU EOL 初始化步骤

执行顺序：
  1. KL30 / KL15 上电
  2. 等待 ECU 启动（2 秒）
  3. XCP 连接 (FF + EB)
  4. 关闭 SAM (Close_Sam_Flag = 0)
  5. 关闭 ASW (Asw_Code_Flag = 0)
  6. 验证进入 EOL 模式 (cg904_Sam == '00000000')

返回值：
  value   = "OK" | "FAIL"
  pass    = True | False
  message = 描述信息
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session
from core.serial_com_relay import Kl30_open, Kl15_open, Kl30_close, Kl15_close


def setup(params: dict) -> dict:
    try:
        # 1. 上电
        Kl30_open()
        Kl15_open()
        time.sleep(2)

        config, xcp, a2l = get_session()

        # 2. XCP 连接
        if not xcp.xcp_ff():
            return {"value": "FAIL", "unit": "", "pass": False, "message": "XCP FF 命令失败"}
        if not xcp.xcp_eb():
            return {"value": "FAIL", "unit": "", "pass": False, "message": "XCP EB 命令失败"}

        # 3. 关闭 SAM
        if not xcp.xcp_f6("Close_Sam_Flag", a2l, 0):
            return {"value": "FAIL", "unit": "", "pass": False, "message": "设置 Close_Sam_Flag 地址失败"}
        xcp.xcp_f0("00")

        # 4. 关闭 ASW
        if not xcp.xcp_ff():
            return {"value": "FAIL", "unit": "", "pass": False, "message": "XCP FF 命令失败（ASW）"}
        if not xcp.xcp_eb():
            return {"value": "FAIL", "unit": "", "pass": False, "message": "XCP EB 命令失败（ASW）"}
        if not xcp.xcp_f6("Asw_Code_Flag", a2l, 0):
            return {"value": "FAIL", "unit": "", "pass": False, "message": "设置 Asw_Code_Flag 地址失败"}
        xcp.xcp_f0("00")

        # 5. 验证 EOL 模式：读取 cg904_Sam
        if not xcp.xcp_ff():
            return {"value": "FAIL", "unit": "", "pass": False, "message": "XCP FF 命令失败（SAM check）"}
        if not xcp.xcp_f6("cg904_Sam", a2l, 0):
            return {"value": "FAIL", "unit": "", "pass": False, "message": "设置 cg904_Sam 地址失败"}
        sam_result = xcp.xcp_f5(4)

        if sam_result != "00000000":
            return {
                "value": "FAIL",
                "unit": "",
                "pass": False,
                "message": f"EOL 模式验证失败：cg904_Sam={sam_result}，期望 00000000",
            }

        return {"value": "OK", "unit": "", "pass": True, "message": "上电并进入 EOL 模式成功"}

    except Exception as exc:
        return {"value": "ERROR", "unit": "", "pass": False, "message": str(exc)}



def power_on():
        # 1. 上电
        Kl30_open()
        Kl15_open()



def power_off():
    #断电
    Kl30_close()
    Kl15_close()
