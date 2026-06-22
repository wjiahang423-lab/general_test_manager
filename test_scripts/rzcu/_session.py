"""
_session.py — RZCU 硬件会话单例

通过模块级变量在同一进程的多次 sandbox 调用之间共享：
  - 配置（test_config.yaml）
  - A2L 变量地址字典
  - 日志记录器（写入 logs/ 目录）

用法（所有测试脚本）：
    from _session import get_session, get_config
    a2l_dic, log = get_session()
    cfg = get_config()
"""

from __future__ import annotations

import atexit
import logging
import os
import sys
import yaml
from datetime import datetime

# ── 路径 ─────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_DEPS = os.path.join(_HERE, "deps")


def _ensure_paths(cfg: dict) -> None:
    """把 deps/、本地 venv site-packages 和原始工程目录加入 sys.path。"""
    original = cfg.get("file_paths", {}).get("original_project", "")
    # 自动检测同级 venv（用于打包环境中存放硬件驱动包）
    venv_site = os.path.join(_HERE, "venv", "Lib", "site-packages")
    for p in [_HERE, _DEPS, venv_site, original]:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)


# ── 配置 ─────────────────────────────────────────────────────────────────────
_config: dict | None = None


def get_config() -> dict:
    global _config
    if _config is None:
        path = os.path.join(_HERE, "test_data", "test_config.yaml")
        with open(path, encoding="utf-8") as f:
            _config = yaml.safe_load(f)
        _ensure_paths(_config)
    return _config


# ── 日志 ─────────────────────────────────────────────────────────────────────
_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        log_dir = os.path.join(_HERE, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, datetime.now().strftime("rzcu_%Y%m%d_%H%M%S.log"))
        _logger = logging.getLogger(f"rzcu_{os.getpid()}")
        _logger.setLevel(logging.DEBUG)
        if not _logger.handlers:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            _logger.addHandler(fh)
    return _logger


# ── A2L ──────────────────────────────────────────────────────────────────────
_a2l_dic: dict | None = None


def _load_a2l(cfg: dict, log: logging.Logger) -> dict:
    a2l_path = cfg["file_paths"]["a2l_file"]
    import rzcu_eol_basic_function as rbf
    dic = rbf.parse_a2l_file(a2l_path)
    log.info(f"A2L 加载完成：{len(dic)} 个变量，来自 {a2l_path}")
    return dic


def get_session() -> tuple[dict, logging.Logger]:
    """返回 (a2l_dic, logger)，首次调用时初始化，后续复用缓存。"""
    global _a2l_dic
    cfg = get_config()
    log = get_logger()
    if _a2l_dic is None:
        _a2l_dic = _load_a2l(cfg, log)
    return _a2l_dic, log


# ── Excel 路径 ────────────────────────────────────────────────────────────────
def get_excel_path() -> str:
    cfg = get_config()
    p = cfg["file_paths"]["test_case_excel"]
    if not os.path.isabs(p):
        p = os.path.join(_HERE, p)
    return p


# ── 电源辅助 ─────────────────────────────────────────────────────────────────
def power_off(device_id: str, log: logging.Logger) -> bool:
    import powermanager, time
    pm = powermanager.PowerManagerITech_IT6500()
    if not pm.open_device(device_id):
        pm.close()
        log.warning(f"电源 {device_id} 打开失败（下电）")
        return False
    pm.set_power_on_off("OFF")
    time.sleep(0.3)
    pm.close()
    return True


def power_on(device_id: str, vol: float, current: float, log: logging.Logger) -> bool:
    import powermanager, time
    pm = powermanager.PowerManagerITech_IT6500()
    if not pm.open_device(device_id):
        pm.close()
        log.warning(f"电源 {device_id} 打开失败（上电）")
        return False
    pm.set_power_on_off("OFF")
    time.sleep(0.3)
    pm.set_power_voltage(vol)
    pm.set_power_current(current)
    pm.set_power_on_off("ON")
    time.sleep(0.3)
    pm.close()
    return True


def restart_power(test_type: str, log: logging.Logger) -> bool:
    """
    按 test_type 配置重新上电并开启机柜继电器。
    test_type 对应 test_config.yaml 中 power_settings 的 key。
    """
    import canmessage, time
    cfg = get_config()
    ps = cfg.get("power_settings", {})
    setting = ps.get(test_type, ps.get("default", {}))

    dev_main  = cfg["power"]["device_main"]
    dev_other = cfg["power"]["device_other"]

    power_off(dev_main,  log)
    power_off(dev_other, log)

    if not power_on(dev_main, setting["vol_main"], setting["cur_main"], log):
        log.error(f"主电源上电失败（{test_type}）")
        return False
    if not power_on(dev_other, setting["vol_other"], setting["cur_other"], log):
        log.error(f"副电源上电失败（{test_type}）")
        return False

    canmessage.power_by_switch(False)
    time.sleep(0.3)
    canmessage.power_by_switch(True)
    time.sleep(0.3)
    log.info(f"电源初始化完成（{test_type}）：主 {setting['vol_main']}V/{setting['cur_main']}A，"
             f"副 {setting['vol_other']}V/{setting['cur_other']}A")
    return True


def get_power_current(log: logging.Logger) -> float | None:
    import powermanager
    cfg = get_config()
    dev = cfg["power"]["device_main"]
    pm = powermanager.PowerManagerITech_IT6500()
    if not pm.open_device(dev):
        pm.close()
        log.warning("读取电源电流失败")
        return None
    current = pm.get_power_current()
    pm.close()
    return current


# ── 会话清理 ─────────────────────────────────────────────────────────────────
def close_session() -> None:
    global _config, _a2l_dic, _logger
    _config = None
    _a2l_dic = None
    if _logger:
        for h in list(_logger.handlers):
            h.close()
            _logger.removeHandler(h)
        _logger = None


atexit.register(close_session)
