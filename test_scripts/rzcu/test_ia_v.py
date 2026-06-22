"""
test_ia_v.py — RZCU_IA_V 单项模拟输入（电压型）测试（数据驱动，由框架 loop 调用）

params 字段（来自 test_items.yaml RZCU_IA_V 条目）：
  name              : 测试项名称
  channel           : 板卡 AO 通道名
  obs_var           : XCP 观测量
  set_value         : 有效设置电压（V，直接传给 control.write_analog_input）
  expected          : 有效期望 XCP 读取值（在 expected×1000 附近）
  invalid_set_value : 无效设置电压（V）
  invalid_expected  : 无效 XCP 读取值上限

返回：
  value = "有效={actual}, 无效={actual_inv}"
  pass  = 有效测试 + 无效测试均通过
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session, get_config


def run(params: dict) -> dict:
    a2l_dic, log = get_session()
    cfg = get_config()
    spec = cfg["test_tolerance"].get("ia_v", 0.10)

    name        = str(params.get("name", ""))
    channel     = str(params.get("channel", ""))
    obs_var     = str(params.get("obs_var", ""))
    set_val     = int(params.get("set_value", 0))
    exp_val     = int(params.get("expected", 0))
    invalid_set = int(params.get("invalid_set_value", 0))
    unexp_val   = int(params.get("invalid_expected", 0))

    log.info(f"[IA_V] {name} ({channel})")

    try:
        import rzcu_eol_basic_function as rbf
        import control

        if not channel.startswith("AO") or len(channel) <= 2:
            msg = f"通道格式异常：{channel}（期望 AO...）"
            log.error(f"  {msg}")
            return {"value": "FAIL", "unit": "mV", "pass": False, "message": msg}

        if not rbf.pre_test(a2l_dic):
            return {"value": "FAIL", "unit": "mV", "pass": False, "message": "pre_test 失败"}
        rbf.keepRunFlag(a2l_dic)

        # 有效测试（set_val 单位 V；XCP 读值与 exp_val×1000 比较）
        control.write_analog_input(channel, set_val)
        time.sleep(1)
        actual = rbf.read_v_and_i(a2l_dic, obs_var)
        exp_mv = exp_val * 1000
        valid_ok = (exp_mv * (1 - spec) < actual < exp_mv * (1 + spec))
        log.debug(f"  有效: actual={actual} 期≈{exp_mv}±{spec*100:.0f}% → {'OK' if valid_ok else 'FAIL'}")

        # 无效测试
        control.write_analog_input(channel, invalid_set)
        time.sleep(1)
        actual_inv = rbf.read_v_and_i(a2l_dic, obs_var)
        invalid_ok = (actual_inv < unexp_val)
        log.debug(f"  无效: actual={actual_inv} 上限{unexp_val} → {'OK' if invalid_ok else 'FAIL'}")

        value  = f"有效={actual},无效={actual_inv}"
        passed = valid_ok and invalid_ok
        if passed:
            log.info(f"  {name} PASS")
            return {"value": value, "unit": "mV", "pass": True, "message": "PASS"}
        else:
            reasons = []
            if not valid_ok:   reasons.append(f"有效{actual}超范围[{exp_mv*(1-spec):.0f},{exp_mv*(1+spec):.0f}]")
            if not invalid_ok: reasons.append(f"无效{actual_inv}≥{unexp_val}")
            msg = "，".join(reasons)
            log.warning(f"  {name} FAIL — {msg}")
            return {"value": value, "unit": "mV", "pass": False, "message": msg}

    except Exception as exc:
        log.error(f"[IA_V] {name} 异常: {exc}", exc_info=True)
        return {"value": "ERROR", "unit": "mV", "pass": False, "message": str(exc)}
