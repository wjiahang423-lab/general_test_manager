import serial
import time

# 串口配置
SERIAL_PORT = 'COM6'  # 替换为你的串口号，如 /dev/ttyUSB0 (Linux)
BAUD_RATE = 9600

# 指令定义
CMD_OPEN_RELAY1 = bytes([0x00, 0xF1, 0xFF])
CMD_CLOSE_RELAY1 = bytes([0x00, 0x01, 0xFF])
CMD_OPEN_RELAY2 = bytes([0x00, 0xF2, 0xFF])
CMD_CLOSE_RELAY2 = bytes([0x00, 0x02, 0xFF])


def relay_control(cmd):
    try:
        # 创建串口对象
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        if ser.is_open:
            # print(f"串口 {SERIAL_PORT} 已打开")
            # 发送指令
            ser.write(cmd)

        else:
            print("串口打开失败")
    except serial.SerialException as e:
        print(f"串口错误: {e}")


def Kl30_open():
    relay_control(CMD_OPEN_RELAY2)


def Kl30_close():
    relay_control(CMD_CLOSE_RELAY2)


def Kl15_open():
    relay_control(CMD_OPEN_RELAY1)


def Kl15_close():
    relay_control(CMD_CLOSE_RELAY1)


# Kl30_open()
# Kl15_open()

Kl15_close()
Kl30_close()