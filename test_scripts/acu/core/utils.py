import os
import re
import sys
try:
    from .excel_manager import *
except Exception:
    pass
import yaml
from typing import Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_a2l(file_path: str) -> Dict[str, str]:
    """解析A2L文件，提取变量地址"""
    variable_addresses = {}

    measurement_pattern = re.compile(r'/begin MEASUREMENT (\w+) "(.*?)"\s+.*?ECU_ADDRESS (0x\w+)', re.DOTALL)
    characteristic_pattern = re.compile(r'/begin CHARACTERISTIC (\w+) "(.*?)"\s+.*?VALUE (0x\w+)', re.DOTALL)

    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
        measurement_matches = measurement_pattern.findall(content)
        characteristic_matches = characteristic_pattern.findall(content)

        for name, _, address in measurement_matches:
            variable_addresses[name] = address

        for name, _, address in characteristic_matches:
            variable_addresses[name] = address

    return variable_addresses


#

def load_yaml(file_path: str) -> Dict:
    """加载YAML配置文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)




def get_config_file():
    """加载全局配置"""
    # 修正配置文件路径（使用绝对路径）
    # 获取项目路径
    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_path, "test_data", "test_config.yaml")
    # config_path = os.path.join(
    #     os.path.dirname(os.path.abspath(__file__)),
    #     "test_data",
    #     "test_config.yaml"
    # )
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    return load_yaml(config_path)


def CLEARDTC(PCAN_USBBUS):

    SpeedStart(PCAN_USBBUS)
    time.sleep(1)
    msg = TPCANMsgFD()
    msg.ID = DIG_CAN_ID_SEND
    msg.MSGTYPE = PCAN_MESSAGE_FD
    msg.DLC = 8
    msg.DATA[0] = 0x04
    msg.DATA[1] = 0X14
    msg.DATA[2] = 0XFF
    msg.DATA[3] = 0XFF
    msg.DATA[4] = 0XFF
    msg.DATA[5] = 0X00
    msg.DATA[6] = 0X00
    msg.DATA[7] = 0X00
    pd.WriteFD(PCAN_USBBUS, msg)
    for i in range(100000):
        (res, msg, time1) = pd.ReadFD(PCAN_USBBUS)
        if msg.ID == 0x7f9:
            print(f"Clear DTC receive:{hex(msg.ID),list_to_hex(list(msg.DATA))}")
            if list(msg.DATA)[0:8] == [0x01, 0x54, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55]:
                print("Clear DTC success")
                stop_event.set()
                time.sleep(1)
                return True
            else:
                print(f"Clear DTC failed,return:{list(msg.DATA)[0:8]}")

                stop_event.set()
                time.sleep(1)
                return False
    print("Clear DTC failed,reply timeout")

    stop_event.set()
    time.sleep(1)
    return False
