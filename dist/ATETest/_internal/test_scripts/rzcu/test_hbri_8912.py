"""
test_hbri_8912.py — RZCU_HBRI_8912 单项 H 桥驱动输出测试（8912 变体，数据驱动）

与 test_hbri.py 逻辑相同，params 字段相同，仅：
  - loop_key = RZCU_HBRI_8912

返回：
  value = "100%={full}mA, eth={eth}mA"
  pass  = 所有检查项通过
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session, get_config, get_power_current

_HBD_DUTY = "Li_Dv_Hbd_pctEcuDuty_vu32"
_HBD_DIR  = "Li_EOL_Core2_Body_ASILB_Hbd_DirLvl"


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
    spec = cfg["test_tolerance"].get("hbri_8912", 0.10)

    name        = str(params.get("name", ""))
    channel     = str(params.get("channel", ""))
    set_val     = int(params.get("set_value", 1))
    cal_var     = str(params.get("cal_var", ""))
    obs_var     = str(params.get("obs_var", ""))
    exp_freq    = params.get("expected_freq")
    exp_duty    = params.get("expected_duty")
    exp_current = int(params.get("expected_current", 0))
    unexp_val   = int(params.get("invalid_current", 0))

    log.info(f"[HBRI_8912] {name} ({channel})")

    try:
        import rzcu_eol_basic_function as rbf
        import PCIe_7841

        pwm_7841 = PCIe_7841.pwm_model()

        if not channel.startswith("PI-DI"):
            msg = f"通道格式异常：{channel}（期望 PI-DI...）"
            log.error(f"  {msg}")
            return {"value": "FAIL", "unit": "mA", "pass": False, "message": msg}

        dir_val = "0" + str(set_val)

        if not rbf.pre_test(a2l_dic):
            return {"value": "FAIL", "unit": "mA", "pass": False, "message": "pre_test 失败"}
        rbf.keepRunFlag(a2l_dic)

        initial_current = int((get_power_current(log) or 0) * 1000)

        rbf.set_freq_duty(a2l_dic, _HBD_DUTY, "e803")
        rbf.set_calibrateable_variable(a2l_dic, _HBD_DIR, dir_val)
        rbf.set_calibrateable_variable(a2l_dic, cal_var, "01")
        time.sleep(2)

        full_current = int((get_power_current(log) or 0) * 1000) - initial_current
        eth_current  = rbf.read_v_and_i(a2l_dic, obs_var)
        full_cab_ok  = (exp_current * (1 - spec) < full_current < exp_current * (1 + spec))
        eth_full_ok  = (exp_current * (1 - spec) < eth_current  < exp_current * (1 + spec))
        current_ok   = full_cab_ok and eth_full_ok
        log.debug(f"  100%: cab={full_current}mA eth={eth_current}mA 期{exp_current}"
                  f" → {'OK' if current_ok else 'FAIL'}")

        dfzk_freq = dfzk_duty = None
        if exp_freq is None:
            freq_ok = duty_ok = True
        else:
            rbf.set_freq_duty(a2l_dic, _HBD_DUTY, "f401")
            time.sleep(1)
            dfzk_freq, dfzk_duty = _read_pwm_avg(pwm_7841, channel)
            exp_freq_i = int(exp_freq)
            exp_duty_i = int(exp_duty)
            freq_ok = (exp_freq_i * (1 - spec) < dfzk_freq < exp_freq_i * (1 + spec))
            duty_ok = (exp_duty_i * (1 - spec) < dfzk_duty < exp_duty_i * (1 + spec))

        valid_ok = current_ok and freq_ok and duty_ok

        rbf.set_calibrateable_variable(a2l_dic, cal_var, "00")
        time.sleep(1)
        disable_current = int((get_power_current(log) or 0) * 1000)
        eth_disable     = rbf.read_v_and_i(a2l_dic, obs_var)
        disable_ok      = (abs(disable_current - initial_current) < unexp_val and eth_disable < unexp_val)
        log.debug(f"  无效: cab_delta={abs(disable_current-initial_current)} eth={eth_disable} 上限{unexp_val}"
                  f" → {'OK' if disable_ok else 'FAIL'}")

        value  = f"100%={full_current}mA,eth={eth_current}mA"
        passed = valid_ok and disable_ok
        if passed:
            log.info(f"  {name} PASS")
            return {"value": value, "unit": "mA", "pass": True, "message": "PASS"}
        else:
            reasons = []
            if not current_ok: reasons.append(f"有效电流cab={full_current},eth={eth_current}")
            if not freq_ok:    reasons.append(f"freq={dfzk_freq}")
            if not duty_ok:    reasons.append(f"duty={dfzk_duty}")
            if not disable_ok: reasons.append("无效电流超限")
            msg = "，".join(reasons)
            log.warning(f"  {name} FAIL — {msg}")
            return {"value": value, "unit": "mA", "pass": False, "message": msg}

    except Exception as exc:
        log.error(f"[HBRI_8912] {name} 异常: {exc}", exc_info=True)
        return {"value": "ERROR", "unit": "mA", "pass": False, "message": str(exc)}
