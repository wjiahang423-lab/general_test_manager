"""
setup.py — RZCU EOL 测试初始化

执行顺序：
  1. 按默认配置上电（12V/5A）并开启机柜继电器
  2. XCP 握手（FF + EB）
  3. 验证供电电压正常（pre_test：读取 DvEol_ObsVol_PowerB1_J17_u16）
  4. 标定 keepRunFlag = 1，保持 ECU 唤醒状态

返回：
  value = "OK" | "FAIL"
  pass  = True | False
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session, get_config, restart_power


def setup(params: dict) -> dict:
    try:
        a2l_dic, log = get_session()
        log.info("=" * 60)
        log.info("RZCU EOL 测试 Setup 开始")

        # 1. 上电
        if not restart_power("default", log):
            return {"value": "FAIL", "unit": "", "pass": False, "message": "电源初始化失败"}
        time.sleep(1)

        # 2. XCP 连接 + 供电验证
        import rzcu_eol_basic_function as rbf
        if not rbf.pre_test(a2l_dic):
            msg = "XCP 连接失败或供电电压异常，请检查 EOL 分区和 A2L 文件"
            log.error(msg)
            return {"value": "FAIL", "unit": "", "pass": False, "message": msg}

        log.info("Setup 完成：上电 + XCP 连接 + 供电验证通过")
        return {"value": "OK", "unit": "", "pass": True, "message": "Setup 完成"}

    except Exception as exc:
        try:
            from _session import get_logger
            get_logger().error(f"Setup 异常: {exc}", exc_info=True)
        except Exception:
            pass
        return {"value": "ERROR", "unit": "", "pass": False, "message": str(exc)}


def restart_power_for(params: dict) -> dict:
    """
    可被测试计划调用的电源重启步骤。
    params:
      test_type: str — 对应 test_config.yaml power_settings 中的 key（如 od / ia_r / id 等）
    """
    test_type = params.get("test_type", "default")
    try:
        _, log = get_session()
        ok = restart_power(test_type, log)
        if not ok:
            return {"value": "FAIL", "unit": "", "pass": False, "message": f"电源初始化失败({test_type})"}
        import time
        time.sleep(1)
        return {"value": "OK", "unit": "", "pass": True, "message": f"电源就绪({test_type})"}
    except Exception as exc:
        return {"value": "ERROR", "unit": "", "pass": False, "message": str(exc)}
