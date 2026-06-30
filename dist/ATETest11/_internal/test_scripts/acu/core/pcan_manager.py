
from PCANBasic import *
import time
from typing import Optional, Tuple, List


class PCANManager:
    """PCAN设备管理类"""

    def __init__(self):
        self.pd = PCANBasic()
        self.initialized = False

    def initialize(self, bus, recv_id, dig_recv_id):
        """初始化CAN FD"""
        try:
            # CAN FD初始化
            result = self.pd.InitializeFD(bus,
                                          b'f_clock=40000000, nom_brp=5, nom_tseg1=11, nom_tseg2=4, nom_sjw=1, data_brp=4, data_tseg1=3, data_tseg2=1, data_sjw=1')
            if result != PCAN_ERROR_OK:
                print(f"CANFD初始化失败，错误码: {hex(result)}")
                return False

            # 设置滤波器
            result = self.pd.FilterMessages(bus, recv_id, dig_recv_id, "11-bit")
            if result != PCAN_ERROR_OK:
                print(f"设置滤波器失败，错误码: {hex(result)}")
                return False

            self.initialized = True
            return True

        except Exception as e:
            print(f"初始化失败: {e}")
            return False

    def send_message(self, bus, can_id, data, dlc=8):
        """发送CAN消息"""
        try:
            msg = TPCANMsgFD()
            msg.ID = can_id
            msg.MSGTYPE = PCAN_MESSAGE_FD
            msg.DLC = dlc
            for i in range(min(dlc, len(data))):
                msg.DATA[i] = data[i]

            result = self.pd.WriteFD(bus, msg)
            return result == PCAN_ERROR_OK

        except Exception as e:
            print(f"发送消息失败: {e}")
            return False

    def read_message(self, bus, timeout=0):
        """
        读取单条CAN消息（基础版）
        :param bus: PCAN总线编号
        :param timeout: 超时时间（毫秒），0表示不等待
        :return: (msg_id, data_list, timestamp) 或 (None, None, None)
        """
        try:
            result, msg, timestamp = self.pd.ReadFD(bus)
            if result == PCAN_ERROR_OK:
                # 修复：原代码用[:-1]会错误截断最后一个字节，应该按DLC长度取数据
                data = list(msg.DATA)
                # print(f"Pcan底层 成功收到{hex(msg.ID)}回复: {[hex(x) for x in data]}")
                return msg.ID, data, timestamp
            return None, None, None
        except Exception as e:
            print(f"读取消息失败: {e}")
            return None, None, None

    def read_specific_message(self, bus, target_id, max_attempts=100000, check_data=None):
        """
        循环读取指定ID的CAN消息（核心修复）
        :param bus: PCAN总线编号
        :param target_id: 目标CAN ID
        :param max_attempts: 最大尝试次数（对应原脚本的循环次数）
        :param check_data: 可选，需要校验的数据前缀 (如 [0x05, 0x62, 0xF1, 0x95])
        :return: 成功返回数据，失败返回False，超时返回None
        """
        if not self.initialized:
            print("CAN未初始化，无法读取消息")
            return False

        for _ in range(max_attempts):
            msg_id, data, _ = self.read_message(bus)

            # 找到目标ID的消息
            if msg_id == target_id:
                # 如果需要校验数据前缀
                if check_data and data[:len(check_data)] != check_data:
                    print(f"收到{hex(target_id)}回复，但数据校验失败: {[hex(x) for x in data]}")
                    return False

                print(f"成功收到{hex(target_id)}回复: {[hex(x) for x in data]}")
                return data

            # 短暂延时，避免CPU占用过高（可选优化）
            time.sleep(0.0001)

        # 超时
        print(f"读取{hex(target_id)}消息超时（最大尝试次数{max_attempts}）")
        return None

    def close(self, bus):
        """关闭CAN连接"""
        if self.initialized:
            self.pd.Uninitialize(bus)
            self.initialized = False


# 测试示例（模仿你的F195函数）
if __name__ == "__main__":
    # 定义常量
    DIG_CAN_ID_SEND = 0x7F1
    DIG_CAN_ID_RECV = 0x7F9
    PCAN_USBBUS1 = PCAN_USBBUS1  # 根据实际使用的总线编号调整

    # 创建管理器实例
    can_manager = PCANManager()

    # 初始化
    if can_manager.initialize(PCAN_USBBUS1, DIG_CAN_ID_RECV, DIG_CAN_ID_RECV):
        print("CAN FD初始化成功")

        # 发送F195指令
        send_data = [0x03, 0X22, 0XF1, 0X95, 0X00, 0X00, 0X00, 0X00]
        if can_manager.send_message(PCAN_USBBUS1, DIG_CAN_ID_SEND, send_data):
            print("F195指令发送成功，等待回复...")

            # 读取指定回复（带数据校验）
        for _ in range(10000):
            msg_id, data, _ = can_manager.read_message(PCAN_USBBUS1)

            # 找到目标ID的消息
            if msg_id == 0x7F9:
                # 如果需要校验数据前缀


                print(f"成功收到{hex(0x7F9)}回复: {[hex(x) for x in data]}")


            # 短暂延时，避免CPU占用过高（可选优化）
            time.sleep(0.00001)


        # 关闭连接
        can_manager.close(PCAN_USBBUS1)
    else:
        print("CAN FD初始化失败")