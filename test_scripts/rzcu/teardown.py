"""
teardown.py — RZCU EOL 测试收尾

执行：关闭主电源和副电源。
无论上方步骤是否 PASS，teardown 始终运行。
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_config, get_logger, power_off


def teardown(params: dict) -> dict:
    try:
        cfg = get_config()
        log = get_logger()
        log.info("Teardown：开始下电")

        dev_main  = cfg["power"]["device_main"]
        dev_other = cfg["power"]["device_other"]
        power_off(dev_main,  log)
        power_off(dev_other, log)

        overall = params.get("overall_result", "")
        log.info(f"Teardown 完成。本次测试总结果：{overall}")
        log.info("=" * 60)
        return {"value": "OK", "unit": "", "pass": True, "message": f"下电完成，总结果={overall}"}

    except Exception as exc:
        try:
            get_logger().error(f"Teardown 异常: {exc}", exc_info=True)
        except Exception:
            pass
        return {"value": "ERROR", "unit": "", "pass": False, "message": str(exc)}
