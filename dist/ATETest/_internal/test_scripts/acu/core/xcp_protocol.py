# core/xcp_protocol.py
from typing import Optional, Dict
from PCANBasic import *


class XCPProtocol:
    """XCP协议实现类"""

    def __init__(self, pcan_manager, CAN_ID_SEND):
        self.pcan = pcan_manager
        self.bus = PCAN_USBBUS1
        self.CAN_ID_SEND = CAN_ID_SEND
        self.recv_can_id = CAN_ID_SEND + 1  # 默认recv id = send id +1

    def xcp_ff(self):
        """XCP FF命令 - 连接"""
        msg_data = [0xFF] + [0x00] * 7
        if not self.pcan.send_message(self.bus, self.CAN_ID_SEND, msg_data):
            return False

        # 等待响应
        for i in range(10000):
            can_id, data, _ = self.pcan.read_message(self.bus)
            if can_id == self.recv_can_id and data:
                if data[0:8] == [0xFF, 0x05, 0xC0, 0x40, 0x40, 0x00, 0x01, 0x01]:
                    return True
        return False

    def xcp_eb(self):
        """XCP EB命令 - 进入"""
        msg_data = [0xEB, 0x03, 0x00, 0x01] + [0x00] * 4
        if not self.pcan.send_message(self.bus, self.CAN_ID_SEND, msg_data):
            return False

        # 等待响应
        for i in range(10000):
            can_id, data, _ = self.pcan.read_message(self.bus)
            if can_id == self.recv_can_id and data:
                if data[0] == 0xFF:
                    return True
        return False

    def xcp_f6(self, variable_name, a2l_dic, offset=0):
        """XCP F6命令 - 设置内存传输地址"""
        if variable_name not in a2l_dic:
            print(f"变量 {variable_name} 不在A2L字典中")
            return False

        original_address = a2l_dic[variable_name]

        if offset != 0:
            observable_address = hex(int(original_address[2:], 16) + offset)
        else:
            observable_address = original_address

        # print(f'获取变量{variable_name}地址{observable_address}')

        try:
            process_address = bytes.fromhex(observable_address[2:])
            swapped_bytes = process_address[::-1]
        except ValueError:
            print('错误: 转换十六进制字符串到字节失败')
            return False

        msg_data = [0xF6, 0x00, 0x00, 0x00] + list(swapped_bytes)
        if not self.pcan.send_message(self.bus, self.CAN_ID_SEND, msg_data):
            return False

        # 等待响应
        for i in range(10000):
            can_id, data, _ = self.pcan.read_message(self.bus)
            if can_id == self.recv_can_id and data:
                if data[0] == 0xFF:
                    return True
        return False

    def xcp_f5(self, length):
        """XCP F5命令 - 上传数据"""
        msg_data = [0xF5, length] + [0x00] * 6
        if not self.pcan.send_message(self.bus, self.CAN_ID_SEND, msg_data):
            return False

        # 等待响应
        for i in range(10000):
            can_id, data, _ = self.pcan.read_message(self.bus)
            if can_id == self.recv_can_id and data:
                if data[0] == 0xFF:
                    bigdata = data[1:length + 1]
                    littledata = bigdata[::-1]
                    hex_str = ''.join(f'{x:02x}' for x in littledata)
                    return hex_str
        return False

    def send_message__(self, data):
        if not self.pcan.send_message(self.bus, self.CAN_ID_SEND, data):
            print("发送消息失败")
        for i in range(10000):
            can_id, data, _ = self.pcan.read_message(self.bus)
            if can_id == self.recv_can_id and data:
                if data[0] == 0xFF:
                    # 取出数据（位置1开始）
                    # print(f"接收到XCP F5命令响应: {[hex(x) for x in data]}")

                    bigdata = data[1::]
                    hex_str = ''.join(f'{x:02x}' for x in bigdata)

                    return hex_str
        return False

    def xcp_f0(self, stringdata):
        """XCP F0命令 - 下载数据"""
        # 将十六进制字符串转换为字节
        bytedata = bytes.fromhex(stringdata)
        # 反转字节序（根据原始脚本）
        swapdata = bytedata[::-1]
        datalen = len(swapdata)

        # 检查数据长度（最大6字节）
        if datalen > 6:
            print(f"错误: 数据长度{datalen}超过最大限制6字节")
            return False

        # 创建8字节的消息数据
        msg_data = [0xF0, datalen] + [0x00] * 6  # 总共8字节

        # 填充数据（位置2-7）
        for i in range(datalen):
            msg_data[i + 2] = swapdata[i]

        # print(f"发送XCP F0命令: {[hex(x) for x in msg_data]}")

        # 发送消息
        if not self.pcan.send_message(self.bus, self.CAN_ID_SEND, msg_data):
            print("发送XCP F0命令失败")
            return False

        # 等待响应
        for i in range(10000):
            can_id, data, _ = self.pcan.read_message(self.bus)
            if can_id == self.recv_can_id and data:
                if data[0] == 0xFF:
                    # print("XCP F0命令成功")
                    return True
                else:
                    print(f"XCP F0命令失败，响应码: {hex(data[0])}")
                    return False

        print("XCP F0命令超时")
        return False

    def read_variable(self, variable_name: str, a2l_dic: Dict[str, str],
                      offset: int = 0, length: int = 4) -> Optional[str]:
        """读取变量（标准三步法）"""
        if not self.xcp_ff():
            print(f"读取变量 {variable_name} 失败: FF命令失败")
            return None

        if not self.xcp_f6(variable_name, a2l_dic, offset):
            print(f"读取变量 {variable_name} 失败: F6命令失败")
            return None

        result = self.xcp_f5(length)
        if result is None:
            print(f"读取变量 {variable_name} 失败: F5命令失败")
            return None

        return result

    def write_variable(self, variable_name: str, a2l_dic: Dict[str, str],
                       hex_data: str, offset: int = 0) -> bool:
        """写入变量（标准三步法）"""
        if not self.xcp_ff():
            print(f"写入变量 {variable_name} 失败: FF命令失败")
            return False

        if not self.xcp_f6(variable_name, a2l_dic, offset):
            print(f"写入变量 {variable_name} 失败: F6命令失败")
            return False

        if not self.xcp_f0(hex_data):
            print(f"写入变量 {variable_name} 失败: F0命令失败")
            return False

        return True
