"""
test_ip.py — RZCU_IP 单项数字输入 PWM 测试（数据驱动，由框架 loop 调用）

params 字段（来自 test_items.yaml RZCU_IP 条目）：
  name          : 测试项名称
  pin           : 管脚（用于判断是否需要 HALL 供电）
  channel       : 板卡 PO-DO 通道
  obs_var       : "频率XCP变量,占空比XCP变量"（逗号分隔）
  set_freq      : 板卡输出频率（Hz）
  set_duty      : 板卡输出占空比（%）
  expected_freq : 期望 XCP 读回频率
  expected_duty : 期望 XCP 读回占空比
  hall_supply   : bool — 是否需要使能 HALL 5V 供电

返回：
  value = "freq={actual_freq}, duty={actual_duty}"
  pass  = 频率 + 占空比均在范围内
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session, get_config

_HALL_SUPPLY_VAR = "DvEol_CalTrackerOut_FeedbackVoltageOfAirConditioningMotor5VPowerSupply_J12_13_u8_Switch"


def run(params: dict) -> dict:
    a2l_dic, log = get_session()
    cfg = get_config()
    spec = cfg["test_tolerance"].get("ip", 0.05)

    name         = str(params.get("name", ""))
    channel      = str(params.get("channel", ""))
    obs_raw      = str(params.get("obs_var", ","))
    set_freq     = int(params.get("set_freq", 100))
    set_duty     = int(params.get("set_duty", 50))
    exp_freq     = int(params.get("expected_freq", 100))
    exp_duty     = int(params.get("expected_duty", 50))
    hall_supply  = bool(params.get("hall_supply", False))

    log.info(f"[IP] {name} ({channel})")

    try:
        obs_parts = obs_raw.split(",")
        if len(obs_parts) != 2:
            msg = f"obs_var 格式异常：{obs_raw}（期望 freq_var,duty_var）"
            log.error(f"  {msg}")
            return {"value": "FAIL", "unit": "Hz/%", "pass": False, "message": msg}
        obs_freq_var, obs_duty_var = obs_parts[0].strip(), obs_parts[1].strip()

        import rzcu_eol_basic_function as rbf
        import PCIe_7841

        pwm_7841 = PCIe_7841.pwm_model()

        if not channel.startswith("PO-DO"):
            msg = f"通道格式异常：{channel}（期望 PO-DO...）"
            log.error(f"  {msg}")
            return {"value": "FAIL", "unit": "Hz/%", "pass": False, "message": msg}

        if not rbf.pre_test(a2l_dic):
            return {"value": "FAIL", "unit": "Hz/%", "pass": False, "message": "pre_test 失败"}
        rbf.keepRunFlag(a2l_dic)

        # 霍尔供电使能
        if hall_supply:
            rbf.set_calibrateable_variable(a2l_dic, _HALL_SUPPLY_VAR, "01")

        # 有效测试：输出 PWM → 读 XCP 频率/占空比
        ok = pwm_7841.write_pwm_by_channel(channel, False, set_freq, set_duty)
        if not ok:
            msg = f"板卡 PWM 设置失败（{channel} {set_freq}Hz {set_duty}%）"
            log.error(f"  {msg}")
            return {"value": "FAIL", "unit": "Hz/%", "pass": False, "message": msg}
        time.sleep(1)

        actual_freq = rbf.read_v_and_i(a2l_dic, obs_freq_var)
        actual_duty = rbf.read_v_and_i(a2l_dic, obs_duty_var)
        freq_ok     = (exp_freq * (1 - spec) < actual_freq < exp_freq * (1 + spec))
        duty_ok     = (exp_duty * (1 - spec) < actual_duty < exp_duty * (1 + spec))
        valid_ok    = freq_ok and duty_ok
        log.debug(f"  freq={actual_freq}(期{exp_freq}) duty={actual_duty}(期{exp_duty})"
                  f" → {'OK' if valid_ok else 'FAIL'}")

        # 关闭 PWM
        pwm_7841.write_pwm_by_channel(channel, False, 100, 0)

        value = f"freq={actual_freq},duty={actual_duty}"
        if valid_ok:
            log.info(f"  {name} PASS")
            return {"value": value, "unit": "Hz/%", "pass": True, "message": "PASS"}
        else:
            reasons = []
            if not freq_ok: reasons.append(f"freq={actual_freq}(期{exp_freq})")
            if not duty_ok: reasons.append(f"duty={actual_duty}(期{exp_duty})")
            msg = "，".join(reasons)
            log.warning(f"  {name} FAIL — {msg}")
            return {"value": value, "unit": "Hz/%", "pass": False, "message": msg}

    except Exception as exc:
        log.error(f"[IP] {name} 异常: {exc}", exc_info=True)
        return {"value": "ERROR", "unit": "Hz/%", "pass": False, "message": str(exc)}
