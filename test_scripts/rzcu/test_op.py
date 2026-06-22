"""
test_op.py — RZCU_OP 单项输出 PWM 测试（OPH 型）（数据驱动，由框架 loop 调用）

params 字段（来自 test_items.yaml RZCU_OP 条目）：
  name             : 测试项名称
  channel          : 板卡 PI-DI 通道（采集 ECU 输出 PWM）
  cal_var          : XCP 标定量（输出开关）
  obs_var          : XCP 观测量（预留，可为空）
  expected_freq    : 期望 50% 时 PWM 频率（Hz），用于板卡采集验证（容差 ±10%）
  expected_duty    : 期望 50% 时 PWM 占空比（%），板卡采集
  expected_current : 期望 100% 占空比时的电流（mA）
  invalid_current  : 关断时电流增量上限（mA）

返回：
  value = "100%={full}mA, 50%=freq={freq}Hz duty={duty}%"
  pass  = 所有检查项通过
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session, get_config, get_power_current

_OPH_DUTY_VAR = "Li_Dv_Oph_pctEcuDuty_vu32"


def _read_pwm_avg(pwm_7841, channel: str, n: int = 10):
    total_freq = total_duty = 0
    for _ in range(n):
        rv = pwm_7841.read_pwm_by_channel(channel)
        ht = rv.get("High time", 0)
        lt = rv.get("Low Time", 0)
        if ht + lt > 0:
            total_freq += float(10 ** 9) / ((ht + lt) * 400)
            total_duty += float(ht) * 100 / (ht + lt)
    return int(total_freq / n), int(total_duty / n)


def run(params: dict) -> dict:
    a2l_dic, log = get_session()
    cfg = get_config()
    spec = cfg["test_tolerance"].get("op", 0.10)

    name        = str(params.get("name", ""))
    channel     = str(params.get("channel", ""))
    cal_var     = str(params.get("cal_var", ""))
    exp_freq    = int(params.get("expected_freq", 100))
    exp_duty    = int(params.get("expected_duty", 50))
    exp_current = int(params.get("expected_current", 0))
    unexp_val   = int(params.get("invalid_current", 0))

    log.info(f"[OP] {name} ({channel})")

    try:
        import rzcu_eol_basic_function as rbf
        import PCIe_7841

        pwm_7841 = PCIe_7841.pwm_model()

        if not channel.startswith("PI-DI"):
            msg = f"通道格式异常：{channel}（期望 PI-DI...）"
            log.error(f"  {msg}")
            return {"value": "FAIL", "unit": "mA", "pass": False, "message": msg}

        if not rbf.pre_test(a2l_dic):
            return {"value": "FAIL", "unit": "mA", "pass": False, "message": "pre_test 失败"}
        rbf.keepRunFlag(a2l_dic)

        initial_current = int((get_power_current(log) or 0) * 1000)

        # 有效测试 100%
        rbf.set_freq_duty(a2l_dic, _OPH_DUTY_VAR, "e803")
        rbf.set_calibrateable_variable(a2l_dic, cal_var, "01")
        time.sleep(1)
        full_current = int((get_power_current(log) or 0) * 1000) - initial_current
        full_ok = (exp_current * (1 - spec) < full_current < exp_current * (1 + spec))

        # 有效测试 50%
        rbf.set_freq_duty(a2l_dic, _OPH_DUTY_VAR, "f401")
        time.sleep(1)
        half_current = int((get_power_current(log) or 0) * 1000) - initial_current
        half_ok = (exp_current * (1 - spec) < half_current * 2 < exp_current * (1 + spec))

        dfzk_freq, dfzk_duty = _read_pwm_avg(pwm_7841, channel)
        freq_ok  = (exp_freq * (1 - spec) < dfzk_freq < exp_freq * (1 + spec))
        duty_ok  = (exp_duty * (1 - spec) < dfzk_duty < exp_duty * (1 + spec))
        valid_ok = full_ok and half_ok and freq_ok and duty_ok
        log.debug(f"  100%={full_current}mA 50%={half_current}mA freq={dfzk_freq}Hz duty={dfzk_duty}%"
                  f" → {'OK' if valid_ok else 'FAIL'}")

        # 无效测试
        rbf.set_calibrateable_variable(a2l_dic, cal_var, "00")
        time.sleep(1)
        disable_current = int((get_power_current(log) or 0) * 1000)
        disable_ok = (abs(disable_current - initial_current) < unexp_val)
        log.debug(f"  无效: 电流增量={abs(disable_current-initial_current)} 上限{unexp_val}"
                  f" → {'OK' if disable_ok else 'FAIL'}")

        value  = f"100%={full_current}mA,freq={dfzk_freq}Hz,duty={dfzk_duty}%"
        passed = valid_ok and disable_ok
        if passed:
            log.info(f"  {name} PASS")
            return {"value": value, "unit": "mA", "pass": True, "message": "PASS"}
        else:
            reasons = []
            if not full_ok:    reasons.append(f"100%电流={full_current}")
            if not half_ok:    reasons.append(f"50%电流={half_current}")
            if not freq_ok:    reasons.append(f"freq={dfzk_freq}")
            if not duty_ok:    reasons.append(f"duty={dfzk_duty}")
            if not disable_ok: reasons.append(f"无效电流增量={abs(disable_current-initial_current)}")
            msg = "，".join(reasons)
            log.warning(f"  {name} FAIL — {msg}")
            return {"value": value, "unit": "mA", "pass": False, "message": msg}

    except Exception as exc:
        log.error(f"[OP] {name} 异常: {exc}", exc_info=True)
        return {"value": "ERROR", "unit": "mA", "pass": False, "message": str(exc)}
