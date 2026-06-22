"""
rzcu_eol_basic_function.py — RZCU EOL 基础 XCP 通信函数

本文件是原始 rzcu_eol_basic_function.py 的精简重写版：
  - 去掉所有 print()，不依赖原始项目路径
  - exit(0) 改为 return False/None，避免 sandbox 进程被杀死
  - 函数签名与原版完全兼容

公共函数：
  parse_a2l_file(file_path)                     → dict
  pre_test(a2l_dic)                             → bool
  keepRunFlag(a2l_dic)                          → None
  set_calibrateable_variable(a2l_dic, var, val) → bool
  read_v_and_i(a2l_dic, var)                    → int | None
  read_idl(a2l_dic, var)                        → int | None
  set_freq_duty(a2l_dic, var, val)              → bool
"""

import re
import socket
import time


# ── UDP 通信 ──────────────────────────────────────────────────────────────────

_LOCAL_IP   = "172.31.10.100"
_LOCAL_PORT = 50000
_TARGET_IP  = "172.31.10.33"
_TARGET_PORT = 50000
_TIMEOUT    = 2


def send_receive(msg_to_send: str) -> str:
    """发送十六进制 UDP 帧，返回响应 hex 字符串；异常时返回空串。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(_TIMEOUT)
    response = ""
    for _ in range(2):
        try:
            s.bind((_LOCAL_IP, _LOCAL_PORT))
            s.sendto(bytes.fromhex(msg_to_send), (_TARGET_IP, _TARGET_PORT))
            data, _ = s.recvfrom(1024)
            time.sleep(0.1)
            response = data.hex()
            break
        except Exception:
            time.sleep(1)
    s.close()
    return response


# ── XCP 协议基础 ──────────────────────────────────────────────────────────────

def xcp_ff(sr=None) -> bool:
    """XCP FF 握手。sr 参数保持兼容，内部固定使用 send_receive。"""
    for _ in range(5):
        time.sleep(0.5)
        rv = send_receive("02 00 00 00 FF 00")
        if rv and len(rv) >= 16 and rv[-16:] == "ff05c0ff09040101":
            return True
    return False


def xcp_eb(sr=None) -> bool:
    """XCP EB 切换工作簿。"""
    for _ in range(5):
        time.sleep(0.5)
        rv = send_receive("08 00 00 00 EB 03 00 01 00 00 00 00")
        if rv and len(rv) == 10 and rv[-2:] == "ff":
            return True
    return False


def xcp_f6(a2l_dic: dict, variable: str, sr=None) -> bool:
    """XCP F6 设定观测/标定地址。"""
    if variable not in a2l_dic:
        return False
    addr = a2l_dic[variable]
    if len(addr[2:]) % 2 != 0:
        return False
    swapped = bytes.fromhex(addr[2:])[::-1]
    frame = (bytes.fromhex("08000000F6000000") + swapped).hex()
    for _ in range(5):
        time.sleep(0.5)
        rv = send_receive(frame)
        if rv and len(rv) == 10 and rv[-2:] == "ff" and rv[:4] == "0100":
            return True
    return False


def xcp_f5(sr=None, observe_length: int = 2):
    """XCP F5 读取当前寄存器值（1 或 2 字节，小端）。"""
    if observe_length == 2:
        rv = send_receive("01000000F502")
        if not rv or len(rv) < 6:
            return None
        hex_val = rv[-4:]
        return int(hex_val[2:] + hex_val[:2], 16)
    elif observe_length == 1:
        rv = send_receive("01000000F501")
        if not rv or len(rv) < 5:
            return None
        return int(rv[-2:], 16)
    return None


def xcp_f0(sr=None, data: str = "") -> bool:
    """XCP F0 标定写入（1 字节）。"""
    frame = "03000000F001" + data
    for _ in range(5):
        time.sleep(0.5)
        rv = send_receive(frame)
        if rv and len(rv) == 10 and rv[-2:] == "ff":
            return True
    return False


# ── A2L 解析 ─────────────────────────────────────────────────────────────────

def parse_a2l_file(file_path: str) -> dict:
    """解析 A2L 文件，返回 {变量名: 十六进制地址} 字典。"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(
        r"/begin (CHARACTERISTIC|MEASUREMENT) (.*?)\s+\"\".*?LINK_MAP \"\2\" (0x[0-9a-fA-F]+)",
        re.DOTALL,
    )
    return {name: addr for _, name, addr in pattern.findall(content)}


# ── 高层测试函数 ──────────────────────────────────────────────────────────────

def pre_test(a2l_dic: dict) -> bool:
    """
    XCP FF + EB 握手，读取供电电压（PowerB1 J17），验证在 10~14V 范围内。
    成功时顺便写入 keepRunFlag=1。
    """
    if not xcp_ff():
        return False
    if not xcp_eb():
        return False
    if not xcp_f6(a2l_dic, "DvEol_ObsVol_PowerB1_J17_u16"):
        return False
    for _ in range(5):
        val = xcp_f5(observe_length=2)
        if val is None:
            continue
        if 10000 <= val <= 14000:
            xcp_f6(a2l_dic, "keepRunFlag")
            xcp_f0(data="01")
            return True
    return False


def keepRunFlag(a2l_dic: dict) -> None:
    """写入 keepRunFlag=1，保持 ECU 唤醒。"""
    xcp_f6(a2l_dic, "keepRunFlag")
    xcp_f0(data="01")


def set_calibrateable_variable(a2l_dic: dict, var_name: str, hex_val: str) -> bool:
    """XCP FF + EB + F6 + F0 标定一个变量。"""
    time.sleep(0.5)
    if not xcp_ff():
        return False
    if not xcp_eb():
        return False
    if not xcp_f6(a2l_dic, var_name):
        return False
    return xcp_f0(data=hex_val)


def read_v_and_i(a2l_dic: dict, var_name: str):
    """读取 2 字节观测量（电压/电流），返回整数或 None。"""
    if not xcp_f6(a2l_dic, var_name):
        return None
    return xcp_f5(observe_length=2)


def read_idl(a2l_dic: dict, var_name: str):
    """读取 1 字节数字量，返回整数或 None。"""
    if not xcp_f6(a2l_dic, var_name):
        return None
    return xcp_f5(observe_length=1)


def set_freq_duty(a2l_dic: dict, var_name: str, hex_val: str) -> bool:
    """XCP FF + EB + F6 + 2字节 F0 写入频率/占空比值（如 'f401' / 'e803'）。"""
    time.sleep(0.5)
    if not xcp_ff():
        return False
    if not xcp_eb():
        return False
    if not xcp_f6(a2l_dic, var_name):
        return False
    frame = "04000000F002" + hex_val
    for _ in range(5):
        time.sleep(0.5)
        rv = send_receive(frame)
        if rv and len(rv) == 10 and rv[-2:] == "ff":
            return True
    return False
