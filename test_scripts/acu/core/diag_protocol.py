# core/diag_protocol.py
import time
from typing import Optional, List

from PCANBasic import PCAN_USBBUS1


class DiagnosticProtocol:
    """诊断协议实现类 - 协议层"""

    def __init__(self, pcan_manager, send_can_id: int):
        self.pcan = pcan_manager
        self.bus = PCAN_USBBUS1
        self.send_can_id = send_can_id
        self.recv_can_id = 0x7F9

    def send_diagnostic_request(self, data: List[int]) -> bool:
        """发送诊断请求"""
        return self.pcan.send_message(self.bus, self.send_can_id, data)

    def read_diagnostic_response(self, timeout_ms: int = 100) -> Optional[List[int]]:
        """读取诊断响应"""
        for _ in range(100000):
            msg_id, data, _ = self.pcan.read_message(self.bus)

            # 找到目标ID的消息
            if msg_id == self.recv_can_id and data:
            #     print(f"收到{hex(msg_id)}回复: {[hex(x) for x in data]}")
            # can_id, data, _ = self.pcan.read_specific_message( self.recv_can_id)


                return data




    def read_did(self, did_high: int, did_low: int) -> Optional[List[int]]:

        """读取DID"""
        request_data = [0x03, 0x22, did_high, did_low] + [0x00] * 4
        self.pcan.send_message(self.bus, self.send_can_id, request_data)
        for _ in range(100000):
            msg_id, data, time1 = self.pcan.read_message(self.bus)
            if msg_id == self.recv_can_id and data:
                # print(f"收到{hex(msg_id)}回复: {[hex(x) for x in data]}")
                return data

    def read_dtc(self, timeout_ms: int = 10000) -> Optional[List[int]]:
        """读取DTC"""
        request_data = [0x03, 0x19, 0x02, 0x09] + [0x00] * 4
        if not self.send_diagnostic_request(request_data):
            return None

        return self.read_diagnostic_response(timeout_ms)

    def clear_dtc(self) -> bool:
        """清除DTC"""
        # 发送进入诊断会话
        if not self.send_diagnostic_request([0x02, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]):
            return False
        time.sleep(1)

        # 发送清除DTC命令
        clear_data = [0x04, 0X14, 0XFF, 0XFF, 0XFF, 0X00, 0X00, 0X00]
        if not self.send_diagnostic_request(clear_data):
            return False

        # 等待响应
        response = self.read_diagnostic_response(1000)
        if response and 0x7F not in response:
            return True
        return False