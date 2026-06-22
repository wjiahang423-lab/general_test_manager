"""
test_od.py — RZCU_OD 单项数字输出测试（数据驱动，由框架 loop 调用）

params 字段（来自 test_items.yaml RZCU_OD 条目）：
  name             : 测试项名称
  pin              : 管脚
  channel          : 板卡 DI 通道（DIx）
  cal_var          : XCP 标定量（输出开关）
  obs_var          : XCP 观测量（电流）
  expected_voltage : 有效 DI 电平（0 或 1）
  expected_current : 有效期望电流（mA）
  invalid_voltage  : 无效 DI 电平
  invalid_current  : 无效电流上限（mA）

返回：
  value = "有效DI=x,eth=y,cab=z"
  pass  = 有效测试 + 无效测试均通过
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session, get_config, get_power_current


def run(params: dict) -> dict:
    a2l_dic, log = get_session()
    cfg = get_config()
    spec = cfg["test_tolerance"].get("od", 0.15)

    name         = str(params.get("name", ""))
    channel      = str(params.get("channel", ""))
    cal_var      = str(params.get("cal_var", ""))
    obs_var      = str(params.get("obs_var", ""))
    exp_voltage  = int(params.get("expected_voltage", 1))
    exp_current  = int(params.get("expected_current", 0))
    unexp_voltage = int(params.get("invalid_voltage", 0))
    unexp_current = int(params.get("invalid_current", 0))

    log.info(f"[OD] {name} ({channel})")

    try:
        import rzcu_eol_basic_function as rbf
        import PCI_67433

        if not channel.startswith("DI") or not channel[2:].isdigit():
            msg = f"通道格式异常：{channel}（期望 DIx）"
            log.error(f"  {msg}")
            return {"value": "FAIL", "unit": "mA", "pass": False, "message": msg}

        ch_num = int(channel[2:])

        if not rbf.pre_test(a2l_dic):
            return {"value": "FAIL", "unit": "mA", "pass": False, "message": "pre_test 失败"}
        rbf.keepRunFlag(a2l_dic)

        initial_current = int((get_power_current(log) or 0) * 1000)

        # ── 有效测试 ──────────────────────────────────────────────
        rbf.set_calibrateable_variable(a2l_dic, cal_var, "01")
        time.sleep(1)

        di_voltage      = 1 if PCI_67433.GetOneChannelState(ch_num) else 0
        eth_current     = rbf.read_v_and_i(a2l_dic, obs_var)
        cabinet_current = int((get_power_current(log) or 0) * 1000) - initial_current

        voltage_ok = (di_voltage == exp_voltage)
        eth_ok     = (not obs_var or exp_current * (1 - spec) < eth_current < exp_current * (1 + spec))
        cab_ok     = (exp_current * (1 - spec) < cabinet_current < exp_current * (1 + spec))
        valid_ok   = voltage_ok and eth_ok and cab_ok
        log.debug(f"  有效: DI={di_voltage}(期{exp_voltage}) eth={eth_current} cab={cabinet_current}"
                  f" 期{exp_current}±{spec*100:.0f}% → {'OK' if valid_ok else 'FAIL'}")

        # ── 无效测试 ──────────────────────────────────────────────
        rbf.set_calibrateable_variable(a2l_dic, cal_var, "00")
        time.sleep(1.5)

        di_inv     = 1 if PCI_67433.GetOneChannelState(ch_num) else 0
        eth_inv    = rbf.read_v_and_i(a2l_dic, obs_var)
        inv_ok     = (di_inv == unexp_voltage) and (eth_inv < unexp_current)
        log.debug(f"  无效: DI={di_inv}(期{unexp_voltage}) eth={eth_inv}(上限{unexp_current})"
                  f" → {'OK' if inv_ok else 'FAIL'}")

        passed = valid_ok and inv_ok
        value  = f"DI={di_voltage},eth={eth_current},cab={cabinet_current}"
        if passed:
            log.info(f"  {name} PASS")
            return {"value": value, "unit": "mA", "pass": True, "message": "PASS"}
        else:
            reasons = []
            if not valid_ok:
                if not voltage_ok: reasons.append(f"有效DI{di_voltage}≠{exp_voltage}")
                if not eth_ok:     reasons.append(f"有效eth={eth_current}")
                if not cab_ok:     reasons.append(f"有效cab={cabinet_current}")
            if not inv_ok:         reasons.append(f"无效DI={di_inv},eth={eth_inv}")
            msg = "，".join(reasons)
            log.warning(f"  {name} FAIL — {msg}")
            return {"value": value, "unit": "mA", "pass": False, "message": msg}

    except Exception as exc:
        log.error(f"[OD] {name} 异常: {exc}", exc_info=True)
        return {"value": "ERROR", "unit": "mA", "pass": False, "message": str(exc)}
