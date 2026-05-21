# core/speed_simulator.py
import threading
import time
from typing import List, Dict
from PCANBasic import PCAN_USBBUS1
class SpeedSimulator:
    """车速模拟器"""

    def __init__(self, pcan_manager, speed_can_id: int):
        self.pcan = pcan_manager
        self.bus = PCAN_USBBUS1
        self.speed_can_id = speed_can_id
        self.speeddata_counter = 0
        self.timer = None
        self.running = False
        self.stop_event = threading.Event()

        # 车速数据
        self.speeddata_list = [
            {'message_counter': 0, 'seed': 190, 'FData': [0x7c, 0x40, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 1, 'seed': 169, 'FData': [0x7b, 0x41, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 2, 'seed': 251, 'FData': [0xc1, 0x42, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 3, 'seed': 149, 'FData': [0x85, 0x43, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 4, 'seed': 117, 'FData': [0xe0, 0x44, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 5, 'seed': 79, 'FData': [0x50, 0x45, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 6, 'seed': 89, 'FData': [0xb0, 0x46, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 7, 'seed': 178, 'FData': [0x84, 0x47, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 8, 'seed': 209, 'FData': [0x22, 0x48, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 9, 'seed': 85, 'FData': [0x19, 0x49, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 10, 'seed': 220, 'FData': [0x2e, 0x4a, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 11, 'seed': 48, 'FData': [0xd7, 0x4b, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 12, 'seed': 113, 'FData': [0x0d, 0x4c, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 13, 'seed': 137, 'FData': [0xe6, 0x4d, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 14, 'seed': 76, 'FData': [0xdc, 0x4e, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]},
            {'message_counter': 15, 'seed': 27, 'FData': [0x3d, 0x4f, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0]}
        ]

    def start(self):
        """启动车速模拟"""
        print("启动车速模拟...")
        self.stop_event.clear()
        self.running = True
        self.speeddata_counter = 0
        self._speed_loop()

    def stop(self):
        """停止车速模拟"""
        print("停止车速模拟...")
        self.stop_event.set()
        self.running = False
        if self.timer:
            self.timer.cancel()

    def _speed_loop(self):
        """车速循环"""
        if self.stop_event.is_set() or not self.running:
            return

        # 发送车速消息
        self._send_speed_message()

        # 设置下一个定时器
        if not self.stop_event.is_set() and self.running:
            self.timer = threading.Timer(0.01, self._speed_loop)
            self.timer.daemon = True
            self.timer.start()

    def _send_speed_message(self):
        """发送车速CAN消息"""
        # 获取当前数据
        data = self.speeddata_list[self.speeddata_counter]['FData']

        # 发送CAN消息
        success = self.pcan.send_message(self.bus, self.speed_can_id, data)
        if not success:
            print(f"发送车速消息失败: {[hex(x) for x in data]}")

        # 更新计数器
        self.speeddata_counter += 1
        if self.speeddata_counter >= len(self.speeddata_list):
            self.speeddata_counter = 0