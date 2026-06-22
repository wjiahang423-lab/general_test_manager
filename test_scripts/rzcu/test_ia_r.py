"""
test_ia_r.py — RZCU_IA_R 单项模拟输入（电阻型）测试（数据驱动，由框架 loop 调用）

params 字段（来自 test_items.yaml RZCU_IA_R 条目）：
  name             : 测试项名称
  channel          : 板卡 RES 通道名
  obs_var          : XCP 观测量
  set_value        : 有效设置电阻值（Ω）
  expected         : 有效期望 XCP 读取值
  invalid_expected : 无效期望 XCP 读取值（开路时）

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
    spec = cfg["test_tolerance"].get("ia_r", 0.10)

    name      = str(params.get("name", ""))
    channel   = str(params.get("channel", ""))
    obs_var   = str(params.get("obs_var", ""))
    set_val   = int(params.get("set_value", 0))
    exp_val   = int(params.get("expected", 0))
    unexp_val = int(params.get("invalid_expected", 0))

    log.info(f"[IA_R] {name} ({channel})")

    try:
        import rzcu_eol_basic_function as rbf
        import canmessage

        if not channel.startswith("RES"):
            msg = f"通道格式异常：{channel}（期望 RES...）"
            log.error(f"  {msg}")
            return {"value": "FAIL", "unit": "Ω", "pass": False, "message": msg}

        if not rbf.pre_test(a2l_dic):
            return {"value": "FAIL", "unit": "Ω", "pass": False, "message": "pre_test 失败"}
        rbf.keepRunFlag(a2l_dic)

        # 有效测试
        canmessage.Set_Resistor_By_Name(channel, set_val)
        time.sleep(1)
        actual   = rbf.read_v_and_i(a2l_dic, obs_var)
        valid_ok = (exp_val * (1 - spec) < actual < exp_val * (1 + spec))
        log.debug(f"  有效: actual={actual} 期{exp_val}±{spec*100:.0f}% → {'OK' if valid_ok else 'FAIL'}")

        # 无效测试（设置开路 50000Ω）
        canmessage.Set_Resistor_By_Name(channel, 50000)
        time.sleep(1)
        actual_inv  = rbf.read_v_and_i(a2l_dic, obs_var)
        invalid_ok  = (unexp_val * (1 - spec * 2) < actual_inv < unexp_val * (1 + spec * 2))
        log.debug(f"  无效: actual={actual_inv} 期≈{unexp_val} → {'OK' if invalid_ok else 'FAIL'}")

        value  = f"有效={actual},无效={actual_inv}"
        passed = valid_ok and invalid_ok
        if passed:
            log.info(f"  {name} PASS")
            return {"value": value, "unit": "Ω", "pass": True, "message": "PASS"}
        else:
            reasons = []
            if not valid_ok:   reasons.append(f"有效{actual}超范围[{exp_val*(1-spec):.0f},{exp_val*(1+spec):.0f}]")
            if not invalid_ok: reasons.append(f"无效{actual_inv}超范围")
            msg = "，".join(reasons)
            log.warning(f"  {name} FAIL — {msg}")
            return {"value": value, "unit": "Ω", "pass": False, "message": msg}

    except Exception as exc:
        log.error(f"[IA_R] {name} 异常: {exc}", exc_info=True)
        return {"value": "ERROR", "unit": "Ω", "pass": False, "message": str(exc)}
