"""
test_id.py — RZCU_ID 单项数字输入测试（数据驱动，由框架 loop 调用）

params 字段（来自 test_items.yaml RZCU_ID 条目）：
  name              : 测试项名称
  channel           : 板卡 DO 通道（DOx）
  obs_var           : XCP 观测量（数字量）
  set_value         : 有效设置状态（0 → 拉低；1 → 拉高）
  expected          : 有效期望 XCP 读取值
  invalid_set_value : 无效设置状态（有效取反）
  invalid_expected  : 无效期望 XCP 读取值

返回：
  value = "有效={actual}, 无效={actual_inv}"
  pass  = 有效测试 + 无效测试均通过
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _session import get_session


def run(params: dict) -> dict:
    a2l_dic, log = get_session()

    name       = str(params.get("name", ""))
    channel    = str(params.get("channel", ""))
    obs_var    = str(params.get("obs_var", ""))
    set_val    = int(params.get("set_value", 0))
    exp_val    = int(params.get("expected", 0))
    unexp_val  = int(params.get("invalid_expected", 0))

    log.info(f"[ID] {name} ({channel})")

    try:
        import rzcu_eol_basic_function as rbf
        import PCI_67434

        if not channel.startswith("DO") or not channel[2:].isdigit():
            msg = f"通道格式异常：{channel}（期望 DOx）"
            log.error(f"  {msg}")
            return {"value": "FAIL", "unit": "", "pass": False, "message": msg}
        ch_num = int(channel[2:])

        if not rbf.pre_test(a2l_dic):
            return {"value": "FAIL", "unit": "", "pass": False, "message": "pre_test 失败"}
        rbf.keepRunFlag(a2l_dic)

        # 有效测试（set_val 0 → True/0V；1 → False/12V）
        id_state = (set_val == 0)
        PCI_67434.WriteOneChannelState(ch_num, id_state)
        time.sleep(1)
        actual   = rbf.read_idl(a2l_dic, obs_var)
        valid_ok = (actual == exp_val)
        log.debug(f"  有效: actual={actual} 期{exp_val} → {'OK' if valid_ok else 'FAIL'}")

        # 无效测试（取反）
        PCI_67434.WriteOneChannelState(ch_num, not id_state)
        time.sleep(1)
        actual_inv  = rbf.read_idl(a2l_dic, obs_var)
        invalid_ok  = (actual_inv == unexp_val)
        log.debug(f"  无效: actual={actual_inv} 期{unexp_val} → {'OK' if invalid_ok else 'FAIL'}")

        value  = f"有效={actual},无效={actual_inv}"
        passed = valid_ok and invalid_ok
        if passed:
            log.info(f"  {name} PASS")
            return {"value": value, "unit": "", "pass": True, "message": "PASS"}
        else:
            reasons = []
            if not valid_ok:   reasons.append(f"有效{actual}≠{exp_val}")
            if not invalid_ok: reasons.append(f"无效{actual_inv}≠{unexp_val}")
            msg = "，".join(reasons)
            log.warning(f"  {name} FAIL — {msg}")
            return {"value": value, "unit": "", "pass": False, "message": msg}

    except Exception as exc:
        log.error(f"[ID] {name} 异常: {exc}", exc_info=True)
        return {"value": "ERROR", "unit": "", "pass": False, "message": str(exc)}
