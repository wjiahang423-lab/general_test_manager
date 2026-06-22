"""
test_od_v.py — RZCU_OD_V 单项模拟电压输出测试（数据驱动，由框架 loop 调用）

params 字段（来自 test_items.yaml RZCU_OD_V 条目）：
  name              : 测试项名称
  channel           : 板卡 AI 通道（AIx）
  cal_var           : XCP 标定量（输出开关）
  obs_var           : XCP 观测量（电压 mV）
  expected_voltage  : 有效期望电压（mV）
  invalid_voltage   : 无效期望电压上限（mV）

返回：
  value = "cabinet=x mV, eth=y mV"
  pass  = 有效测试 + 无效测试均通过
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session, get_config


def run(params: dict) -> dict:
    a2l_dic, log = get_session()
    cfg = get_config()
    spec = cfg["test_tolerance"].get("od_v", 0.10)

    name      = str(params.get("name", ""))
    channel   = str(params.get("channel", ""))
    cal_var   = str(params.get("cal_var", ""))
    obs_var   = str(params.get("obs_var", ""))
    exp_val   = int(params.get("expected_voltage", 0))
    unexp_val = int(params.get("invalid_voltage", 0))

    log.info(f"[OD_V] {name} ({channel})")

    try:
        import rzcu_eol_basic_function as rbf
        import control

        if not channel.startswith("AI") or len(channel) <= 2:
            msg = f"通道格式异常：{channel}（期望 AIx）"
            log.error(f"  {msg}")
            return {"value": "FAIL", "unit": "mV", "pass": False, "message": msg}

        if not rbf.pre_test(a2l_dic):
            return {"value": "FAIL", "unit": "mV", "pass": False, "message": "pre_test 失败"}
        rbf.keepRunFlag(a2l_dic)

        # 有效测试
        rbf.set_calibrateable_variable(a2l_dic, cal_var, "01")
        time.sleep(2)
        cabinet_mv = int(control.read_analog_input(channel) * 1000)
        eth_val    = rbf.read_v_and_i(a2l_dic, obs_var)
        valid_ok   = (exp_val * (1 - spec) < cabinet_mv < exp_val * (1 + spec) and
                      exp_val * (1 - spec) < eth_val     < exp_val * (1 + spec))
        log.debug(f"  有效: cabinet={cabinet_mv}mV eth={eth_val} 期{exp_val}±{spec*100:.0f}%"
                  f" → {'OK' if valid_ok else 'FAIL'}")

        # 无效测试
        rbf.set_calibrateable_variable(a2l_dic, cal_var, "00")
        time.sleep(2)
        cabinet_inv = int(control.read_analog_input(channel) * 1000)
        eth_inv     = rbf.read_v_and_i(a2l_dic, obs_var)
        invalid_ok  = (cabinet_inv < unexp_val and eth_inv < unexp_val)
        log.debug(f"  无效: cabinet={cabinet_inv}mV eth={eth_inv} 上限{unexp_val}"
                  f" → {'OK' if invalid_ok else 'FAIL'}")

        value = f"cabinet={cabinet_mv}mV,eth={eth_val}mV"
        passed = valid_ok and invalid_ok
        if passed:
            log.info(f"  {name} PASS")
            return {"value": value, "unit": "mV", "pass": True, "message": "PASS"}
        else:
            reasons = []
            if not valid_ok:   reasons.append(f"有效cabinet={cabinet_mv},eth={eth_val}(期{exp_val})")
            if not invalid_ok: reasons.append(f"无效cabinet={cabinet_inv},eth={eth_inv}(上限{unexp_val})")
            msg = "，".join(reasons)
            log.warning(f"  {name} FAIL — {msg}")
            return {"value": value, "unit": "mV", "pass": False, "message": msg}

    except Exception as exc:
        log.error(f"[OD_V] {name} 异常: {exc}", exc_info=True)
        return {"value": "ERROR", "unit": "mV", "pass": False, "message": str(exc)}
