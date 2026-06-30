#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time

import pyvisa
from abc import ABCMeta, abstractmethod

import serial

"""
程控电源控制脚本

前提条件：
1. 程控电源必须支持读写操作
2. 程控电源必须支持USB模式，并且设置成USB模式
3. 串口模式的电源通过串口控制

Demo:
from submodules.atp_script.atp_program_power import AtpPowerManager

pm = AtpPowerManager(var.PM_TYPE)
if pm:
    res, err_str = pm.set_power_on_off('on')
    if 0 == res:
        pm.set_power_voltage(12)
        pm.set_power_current(5)
    else:
        print(err_str)

"""
__all__ = ["BasePowerManager", "AtpPowerManager"]

RES_OK = (0, "成功")
RES_EXCEPTION_OCCURS = 1
RES_ILLEGAL_TYPE = (2, "输入的类型与期望的类型不一致")
RES_ILLEGAL_VALUE = (3, "输入的是非法值")
RES_INIT_FAIL = (4, "没有侦测到U控制端口，请检查设备是否是属于该类定义的电源或者检查一下手册看是否设置为通过USB控制")
s_CRCHi = [0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
           0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
           0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
           0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
           0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
           0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
           0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
           0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
           0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
           0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40,
           0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
           0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
           0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
           0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40,
           0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
           0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
           0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
           0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
           0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
           0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
           0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
           0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40,
           0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
           0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
           0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
           0x80, 0x41, 0x00, 0xC1, 0x81, 0x40]
s_CRCLo = [0x00, 0xC0, 0xC1, 0x01, 0xC3, 0x03, 0x02, 0xC2, 0xC6, 0x06,
           0x07, 0xC7, 0x05, 0xC5, 0xC4, 0x04, 0xCC, 0x0C, 0x0D, 0xCD,
           0x0F, 0xCF, 0xCE, 0x0E, 0x0A, 0xCA, 0xCB, 0x0B, 0xC9, 0x09,
           0x08, 0xC8, 0xD8, 0x18, 0x19, 0xD9, 0x1B, 0xDB, 0xDA, 0x1A,
           0x1E, 0xDE, 0xDF, 0x1F, 0xDD, 0x1D, 0x1C, 0xDC, 0x14, 0xD4,
           0xD5, 0x15, 0xD7, 0x17, 0x16, 0xD6, 0xD2, 0x12, 0x13, 0xD3,
           0x11, 0xD1, 0xD0, 0x10, 0xF0, 0x30, 0x31, 0xF1, 0x33, 0xF3,
           0xF2, 0x32, 0x36, 0xF6, 0xF7, 0x37, 0xF5, 0x35, 0x34, 0xF4,
           0x3C, 0xFC, 0xFD, 0x3D, 0xFF, 0x3F, 0x3E, 0xFE, 0xFA, 0x3A,
           0x3B, 0xFB, 0x39, 0xF9, 0xF8, 0x38, 0x28, 0xE8, 0xE9, 0x29,
           0xEB, 0x2B, 0x2A, 0xEA, 0xEE, 0x2E, 0x2F, 0xEF, 0x2D, 0xED,
           0xEC, 0x2C, 0xE4, 0x24, 0x25, 0xE5, 0x27, 0xE7, 0xE6, 0x26,
           0x22, 0xE2, 0xE3, 0x23, 0xE1, 0x21, 0x20, 0xE0, 0xA0, 0x60,
           0x61, 0xA1, 0x63, 0xA3, 0xA2, 0x62, 0x66, 0xA6, 0xA7, 0x67,
           0xA5, 0x65, 0x64, 0xA4, 0x6C, 0xAC, 0xAD, 0x6D, 0xAF, 0x6F,
           0x6E, 0xAE, 0xAA, 0x6A, 0x6B, 0xAB, 0x69, 0xA9, 0xA8, 0x68,
           0x78, 0xB8, 0xB9, 0x79, 0xBB, 0x7B, 0x7A, 0xBA, 0xBE, 0x7E,
           0x7F, 0xBF, 0x7D, 0xBD, 0xBC, 0x7C, 0xB4, 0x74, 0x75, 0xB5,
           0x77, 0xB7, 0xB6, 0x76, 0x72, 0xB2, 0xB3, 0x73, 0xB1, 0x71,
           0x70, 0xB0, 0x50, 0x90, 0x91, 0x51, 0x93, 0x53, 0x52, 0x92,
           0x96, 0x56, 0x57, 0x97, 0x55, 0x95, 0x94, 0x54, 0x9C, 0x5C,
           0x5D, 0x9D, 0x5F, 0x9F, 0x9E, 0x5E, 0x5A, 0x9A, 0x9B, 0x5B,
           0x99, 0x59, 0x58, 0x98, 0x88, 0x48, 0x49, 0x89, 0x4B, 0x8B,
           0x8A, 0x4A, 0x4E, 0x8E, 0x8F, 0x4F, 0x8D, 0x4D, 0x4C, 0x8C,
           0x44, 0x84, 0x85, 0x45, 0x87, 0x47, 0x46, 0x86, 0x82, 0x42,
           0x43, 0x83, 0x41, 0x81, 0x80, 0x40]


class BasePowerManager(metaclass=ABCMeta):
    """
    所有程控电源的基类，新的程控电源子类都要实现下面的抽象方法。
    """

    def __init__(self):
        ...

    @abstractmethod
    def set_power_on_off(self, state):
        """
        总的开启关闭电源函数
        :param state: on/off
        :return: 操作返回结果
        """
        ...

    @abstractmethod
    def set_power_voltage(self, mum):
        """
        设置电压值
        :param mum: non-negative number
        :return:动作执行情况
        """
        ...

    @abstractmethod
    def set_power_current(self, mum):
        """
        设置电流值
        :param mum:
        :return:动作执行情况
        """
        ...

    @abstractmethod
    def get_power_voltage(self):
        """
        获取当前的电压值
        :return: 电源电压值
        """
        ...

    @abstractmethod
    def get_power_current(self):
        """
        获取当前电流值
        :return: 电源电流值
        """
        ...

    @abstractmethod
    def get_power_consumption(self):
        """
        获取当前电源的功率
        :return: 电源功率值
        """
        ...

    @abstractmethod
    def close(self):
        """
        关闭
        """
        ...


class PowerManagerRigol_DP811(BasePowerManager):
    """
    针对RIGOL的DP811程控电源
    """

    def __init__(self):
        """
        实际不同类型程控电源初始化时可能需要做不同的操作，这个视情况而定
        """
        super(PowerManagerRigol_DP811, self).__init__()
        self.rm = pyvisa.ResourceManager()
        # 电压、电流默认值
        self.vol = 12
        self.cur = 10
        try:
            self.res = self.rm.open_resource(self._find_usb_instrument("DP811"))
            self.res.write("*CLS")
            self.res.write("SYST:REM")
            self.inited = True
        except Exception as e:
            self.inited = False

    # get the USB instrument resourse by device info
    def _find_usb_instrument(self, device_id):
        error_info = ""
        instru_list = self.rm.list_resources("USB?*::INSTR")

        if len(instru_list) == 0:
            error_info = "No USB instrument found!"
            return error_info

        instru_res = ""
        for dev in instru_list:
            res = self.rm.open_resource(dev)
            device_info = res.query("*IDN?")
            if device_info.find(device_id) >= 0:
                instru_res = dev
                break
        if instru_res == "":
            error_info = "No desired USB instrument found!"
            return error_info

        return instru_res

    def set_power_on_off(self, state):
        """
        控制具体型号程控电源上下电
        :param set_state_cmd: ON/OFF
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(state, str):
            set_state = state.upper()
            if set_state in ["ON", "OFF"]:
                self.res.write(f":OUTP CH1, {set_state}")
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def set_power_voltage(self, num):
        """
        设置具体型号程控电源电压值
        :param num: 非负数，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(num, int) or isinstance(num, float):
            if num > 0:
                self.vol = num
                self.res.write(":APPL CH1," + str(self.vol) + ',' + str(self.cur))
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def set_power_current(self, num):
        """
        设置具体型号程控电源电流值
        :param num: 非负数，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(num, int) or isinstance(num, float):
            if num > 0:
                self.cur = num
                self.res.write(":APPL CH1," + str(self.vol) + ',' + str(self.cur))
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def get_power_voltage(self):
        """
        获取当前的电压值
        :return: 电源电压值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query("MEAS:VOLT? ALL"))

    def get_power_current(self):
        """
        获取当前电流值
        :return: 电源电流值
        """
        # for i in range(0, 3):
        #     result1 = SB ('COM6', '01 04 00 64 00 02 30 14')
        #     # print(result1)
        #     if len(result1) == 9:
        #         Current = (int(result1[5]) << 8 | int(result1[6])) * 0.01
        #         break
        #     else:
        #         print(result1)
        #         Current = 999
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query(':MEAS:CURR? CH1'))

    def get_power_consumption(self):
        """
        获取当前电源的功率
        :return: 电源功率值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        ...

    def close(self):
        """
        关闭
        """
        self.rm.close()


class PowerManagerRigol_DP832(BasePowerManager):
    """
    针对RIGOL的DP832程控电源
    """

    def __init__(self):
        """
        实际不同类型程控电源初始化时可能需要做不同的操作，这个视情况而定
        """
        super(PowerManagerRigol_DP832, self).__init__()
        self.rm = pyvisa.ResourceManager()
        # 电压、电流默认值
        self.vol = 12
        self.cur = 3
        try:
            self.res = self.rm.open_resource(self._find_usb_instrument("DP832"))
            self.res.write("*CLS")
            self.res.write("SYST:REM")
            self.inited = True
        except Exception as e:
            self.inited = False

    # get the USB instrument resourse by device info
    def _find_usb_instrument(self, device_id):
        error_info = ""
        instru_list = self.rm.list_resources("USB?*::INSTR")

        if len(instru_list) == 0:
            error_info = "No USB instrument found!"
            return error_info

        instru_res = ""
        for dev in instru_list:
            res = self.rm.open_resource(dev)
            device_info = res.query("*IDN?")
            if device_info.find(device_id) >= 0:
                instru_res = dev
                break
        if instru_res == "":
            error_info = "No desired USB instrument found!"
            return error_info

        return instru_res

    def set_power_on_off(self, state):
        """
        控制具体型号程控电源上下电
        :param set_state_cmd: ON/OFF
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(state, str):
            set_state = state.upper()
            if set_state in ["ON", "OFF"]:
                self.res.write(f":OUTP CH1, {set_state}")
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def set_power_voltage(self, num):
        """
        设置具体型号程控电源电压值
        :param num: 非负数，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(num, int) or isinstance(num, float):
            if num > 0:
                self.vol = num
                self.res.write(":APPL CH1," + str(self.vol) + ',' + str(self.cur))
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def set_power_current(self, num):
        """
        设置具体型号程控电源电流值
        :param num: 非负数，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(num, int) or isinstance(num, float):
            if num > 0:
                self.cur = num
                self.res.write(":APPL CH1," + str(self.vol) + ',' + str(self.cur))
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def get_power_voltage(self):
        """
        获取当前的电压值
        :return: 电源电压值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query("MEAS:VOLT? ALL"))

    def get_power_current(self):
        """
        获取当前电流值
        :return: 电源电流值
        """
        # for i in range(0, 3):
        #     result1 = SB ('COM6', '01 04 00 64 00 02 30 14')
        #     # print(result1)
        #     if len(result1) == 9:
        #         Current = (int(result1[5]) << 8 | int(result1[6])) * 0.01
        #         break
        #     else:
        #         print(result1)
        #         Current = 999
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query(':MEAS:CURR? CH1'))

    def get_power_consumption(self):
        """
        获取当前电源的功率
        :return: 电源功率值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        ...

    def close(self):
        """
        关闭
        """
        self.rm.close()


class PowerManagerITech(BasePowerManager):
    """
    具体的ITech型号程控电源，实现了父类中定义的所有的抽象方法
    """

    def __init__(self):
        """
        实际不同类型程控电源初始化时可能需要做不同的操作，这个视情况而定
        """
        super(PowerManagerITech, self).__init__()
        self.rm = pyvisa.ResourceManager()
        self.inited, detect_port = self._check_power_port("IT6722A")
        if self.inited:
            self.res = self.rm.open_resource(detect_port)

    def _check_power_port(self, device_id):
        # get the USB instrument resource by device info
        instru_list = self.rm.list_resources("USB?*::INSTR")
        if len(instru_list) == 0:
            error_info = "No USB instrument found!"
            print(error_info)
            return False, error_info

        instru_res = ""
        for dev in instru_list:
            res = self.rm.open_resource(dev)
            device_info = res.query("*IDN?")
            if device_info.find(device_id) >= 0:
                instru_res = dev
                break

        if instru_res == "":
            error_info = "No desired USB instrument found!"
            print(error_info)
            return False, error_info

        return True, instru_res

    def set_power_on_off(self, state):
        """
        控制具体型号程控电源上下电
        :param set_state_cmd: ON/OFF
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(state, str):
            set_state = state.upper()
            if set_state in ["ON", "OFF"]:
                self.res.write("SYST:RWL")
                self.res.write(f"OUTP {set_state}")
                self.res.write("SYST:LOC")
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def set_power_voltage(self, num):
        """
        设置具体型号程控电源电压值
        :param num: 非负数，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(num, int) or isinstance(num, float):
            if num > 0:
                self.res.write("SYST:RWL")
                self.res.write(f"VOLT {num}")
                self.res.write("SYST:LOC")
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def set_power_current(self, num):
        """
        设置具体型号程控电源电流值
        :param num: 非负数，，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(num, int) or isinstance(num, float):
            if num > 0:
                self.res.write("SYST:RWL")
                self.res.write(f":CURR {num}")
                self.res.write("SYST:LOC")
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def get_power_voltage(self):
        """
        获取当前状态程控电源的电压值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前电压值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query(f"MEAS:VOLT?"))

    def get_power_current(self):
        """
        获取当前状态程控电源的电流值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前电流值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query(f"MEAS:CURR?"))

    def get_power_consumption(self):
        """
        获取当前状态程控电源的功率值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前功率值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query(f"MEAS:POW?"))

    def close(self):
        self.rm.close()


class PowerManagerITech_IT6332A(BasePowerManager):
    """
    具体的ITech型号程控电源，实现了父类中定义的所有的抽象方法
    """

    def __init__(self):
        """
        实际不同类型程控电源初始化时可能需要做不同的操作，这个视情况而定
        """
        super(PowerManagerITech_IT6332A, self).__init__()
        self.rm = pyvisa.ResourceManager()
        self.inited, detect_port = self._check_power_port("IT6332A")
        if self.inited:
            self.res = self.rm.open_resource(detect_port)

    def _check_power_port(self, device_id):
        # get the USB instrument resource by device info
        instru_list = self.rm.list_resources("USB?*::INSTR")
        if len(instru_list) == 0:
            error_info = "No USB instrument found!"
            print(error_info)
            return False, error_info

        instru_res = ""
        for dev in instru_list:
            res = self.rm.open_resource(dev)
            device_info = res.query("*IDN?")
            if device_info.find(device_id) >= 0:
                instru_res = dev
                break

        if instru_res == "":
            error_info = "No desired USB instrument found!"
            print(error_info)
            return False, error_info

        return True, instru_res

    def set_power_on_off(self, state):
        """
        控制具体型号程控电源上下电
        :param set_state_cmd: ON/OFF
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(state, str):
            set_state = state.upper()
            if set_state in ["ON", "OFF"]:
                self.res.write("SYST:RWL")
                self.res.write(f"OUTP {set_state}")
                self.res.write("SYST:LOC")
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def set_power_voltage(self, num):
        """
        设置具体型号程控电源电压值
        :param num: 非负数，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(num, int) or isinstance(num, float):
            if num > 0:
                self.res.write("SYST:RWL")
                self.res.write(f"VOLT {num}")
                self.res.write("SYST:LOC")
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def set_power_current(self, num):
        """
        设置具体型号程控电源电流值
        :param num: 非负数，，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(num, int) or isinstance(num, float):
            if num > 0:
                self.res.write("SYST:RWL")
                self.res.write(f":CURR {num}")
                self.res.write("SYST:LOC")
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def get_power_voltage(self):
        """
        获取当前状态程控电源的电压值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前电压值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query(f"MEAS:VOLT?"))

    def get_power_current(self):
        """
        获取当前状态程控电源的电流值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前电流值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query(f"MEAS:CURR?"))

    def get_power_consumption(self):
        """
        获取当前状态程控电源的功率值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前功率值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query(f"MEAS:POW?"))

    def close(self):
        self.rm.close()



class PowerManagerITech_IT6722A(BasePowerManager):
    """
    具体的ITech型号程控电源，实现了父类中定义的所有的抽象方法
    """

    def __init__(self):
        """
        实际不同类型程控电源初始化时可能需要做不同的操作，这个视情况而定
        """
        super(PowerManagerITech_IT6722A, self).__init__()
        self.rm = pyvisa.ResourceManager()
        self.inited, detect_port = self._check_power_port("IT6722A")
        if self.inited:
            self.res = self.rm.open_resource(detect_port)

    def _check_power_port(self, device_id):
        # get the USB instrument resource by device info
        # instru_list = self.rm.list_resources('USB0::0x2EC7::0x6700::802259073777570247::INSTR')
        instru_list = self.rm.list_resources("USB?*::INSTR")
        if len(instru_list) == 0:
            error_info = "No USB instrument found!????"
            print(error_info)
            return False, error_info

        instru_res = ""
        for dev in instru_list:
            res = self.rm.open_resource(dev)
            device_info = res.query("*IDN?")
            if device_info.find(device_id) >= 0:
                instru_res = dev
                break

        if instru_res == "":
            error_info = "No desired USB instrument found!"
            print(error_info)
            return False, error_info

        return True, instru_res

    def set_power_on_off(self, state):
        """
        控制具体型号程控电源上下电
        :param set_state_cmd: ON/OFF
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(state, str):
            set_state = state.upper()
            if set_state in ["ON", "OFF"]:
                self.res.write("SYST:RWL")
                self.res.write(f"OUTP {set_state}")
                self.res.write("SYST:LOC")
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def set_power_voltage(self, num):
        """
        设置具体型号程控电源电压值
        :param num: 非负数，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(num, int) or isinstance(num, float):
            if num > 0:
                self.res.write("SYST:RWL")
                self.res.write(f"VOLT {num}")
                self.res.write("SYST:LOC")
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def set_power_current(self, num):
        """
        设置具体型号程控电源电流值
        :param num: 非负数，，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL

        if isinstance(num, int) or isinstance(num, float):
            if num > 0:
                self.res.write("SYST:RWL")
                self.res.write(f":CURR {num}")
                self.res.write("SYST:LOC")
                return RES_OK
            else:
                return RES_ILLEGAL_VALUE
        else:
            return RES_ILLEGAL_TYPE

    def get_power_voltage(self):
        """
        获取当前状态程控电源的电压值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前电压值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query(f"MEAS:VOLT?"))

    def get_power_current(self):
        """
        获取当前状态程控电源的电流值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前电流值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query(f"MEAS:CURR?"))

    def get_power_consumption(self):
        """
        获取当前状态程控电源的功率值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前功率值
        """
        if not self.inited:
            print(RES_INIT_FAIL(1))
            return RES_INIT_FAIL(0)

        return float(self.res.query(f"MEAS:POW?"))

    def close(self):
        self.rm.close()



class PowerManagerVaried(BasePowerManager):
    """
    具体的万瑞达Varied型号程控电源，实现了父类中定义的所有的抽象方法
    """

    # 计算CRC
    def crc16_modbus(self, buf, _len_buf):
        global s_CRCHi
        global s_CRCLo
        _uc_CRCHi = 0
        _uc_CRCLo = 0
        _dir = 0
        _us_Index = 0
        _uc_CRCHi = 0xFF
        _uc_CRCLo = 0xFF

        while _len_buf > 0:
            _len_buf = _len_buf - 1
            _us_Index = _uc_CRCHi ^ buf[_dir]
            _uc_CRCHi = _uc_CRCLo ^ s_CRCHi[_us_Index]
            _uc_CRCLo = s_CRCLo[_us_Index]
            _dir = _dir + 1
        return (_uc_CRCHi << 8 | _uc_CRCLo)

    def __init__(self):
        """
        实际不同类型程控电源初始化时可能需要做不同的操作，这个视情况而定
        """
        super(PowerManagerVaried, self).__init__()
        print("程控电源的串口号，使用时，确认好串口号然后更改")
        load_port = 'COM14'
        self.res = serial.Serial(load_port, 115200, bytesize=8, timeout=1, parity="N", stopbits=1)
        self.inited = True

    def serial_115200_send_command(self, load_port, cmd_to_send, baudrate=115200):
        try:
            result = "OK"
            self.res.write(bytes.fromhex(cmd_to_send))

        except Exception as e:
            result = e
            print(e)

        finally:
            return result

    def serial_115200_send_recv(self, load_port, cmd_to_send):
        try:
            result = ""
            self.res.write(bytes.fromhex(cmd_to_send))
            time.sleep(0.1)
            response = self.res.readline()
            # ser.close()
            result = response
            print(result)

        except Exception as e:
            print(str(e))

        finally:
            return result

    def power_init(self):
        """
        初始化电源
        """
        print('电源初始化')
        buf1 = [0x01, 0x05, 0x00, 0x85, 0x00, 0x00]
        crc_num = self.crc16_modbus(buf1, 6)
        buf1.append(crc_num >> 8)
        buf1.append(crc_num & 0x00FF)
        self.serial_115200_send_command('COM14', ' '.join([hex(int(i)).replace("0x", "").rjust(2, "0") for i in buf1]))
        print("电源初始化成功")
        return RES_OK

    def set_power_on_off(self, set_state_cmd):
        """
        控制具体型号程控电源上下电
        :param set_state_cmd: 1/0
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL
        # 电源上电
        if set_state_cmd == 1:
            buf1 = [0x01, 0x05, 0x00, 0x85, 0xFF, 0x00]
            crc_num = self.crc16_modbus(buf1, 6)
            buf1.append(crc_num >> 8)
            buf1.append(crc_num & 0x00FF)
            self.serial_115200_send_command('COM14',
                                            ' '.join([hex(int(i)).replace("0x", "").rjust(2, "0") for i in buf1]))
            print("电源上电成功")
            return RES_OK
        # 电源下电
        else:
            buf1 = [0x01, 0x05, 0x00, 0x85, 0x00, 0x00]
            crc_num = self.crc16_modbus(buf1, 6)
            buf1.append(crc_num >> 8)
            buf1.append(crc_num & 0x00FF)
            self.serial_115200_send_command('COM14', ' '.join([hex(int(i)).replace("0x", "").rjust(2, "0") for i in buf1]))
            print("电源下电成功")
            return RES_OK

    def set_power_voltage(self, num):
        """
        设置具体型号程控电源电压值
        :param num: 非负数，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        if not self.inited:
            return RES_INIT_FAIL
        # 设置电源电压
        print("设置电源电压")
        set_voltage = int(num * 100)
        buf1 = [0x01, 0x06, 0x00, 0x95]
        buf1.append(set_voltage >> 8)
        buf1.append(set_voltage & 0x00FF)
        crc_num = self.crc16_modbus(buf1, 6)
        buf1.append(crc_num >> 8)
        buf1.append(crc_num & 0x00FF)
        self.serial_115200_send_command('COM14', ' '.join([hex(int(i)).replace("0x", "").rjust(2, "0") for i in buf1]))
        print('设置电压：%.f V 成功' % num)
        return RES_OK

    def get_power_current(self):
        """
        获取当前状态程控电源的电流值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前电流值
        """
        print("获取电流")
        for i in range(0, 3):
            current_value = self.serial_115200_send_recv('COM14', '01 04 00 64 00 02 30 14')
            print(current_value)
            print(len(current_value))
            if len(current_value) == 9:
                current = (int(current_value[5]) << 8 | int(current_value[6])) * 0.01
                print("获取电流成功")
                break
            else:
                print(current_value)
                current = 999
                print("获取电流失败")
        return current

    def get_power_voltage(self):
        """
        获取当前状态程控电源的电压值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前电压值
        """
        print("该电源无该指令，不获取电压")

    def set_power_current(self, mum):
        """
        设置具体型号程控电源电流值
        :param num: 非负数，，具体精确到小数点后多少位取决于程控电源的本身的支持能力
        :return: code, description
        """
        print("该电源无该指令，不置电流")

    def get_power_consumption(self):
        """
        获取当前状态程控电源的功率值，可取值 VOLT, CURR, POW分别为电压、电流、功率
        :return: 当前功率值
        """
        print("该电源无该指令，不获取功率")

    def close(self):
        self.rm.close()


# 工厂模式获取程控电源
def AtpPowerManager(type: str) -> BasePowerManager:
    """
    根据参数type返回对应的程控电源
    """
    handler = {
        'ITech': PowerManagerITech,
        'ITech_IT6722A': PowerManagerITech_IT6722A,
        'Rigol_DP811': PowerManagerRigol_DP811,
        'Varied': PowerManagerVaried,
        'Rigol_DP832': PowerManagerRigol_DP832,
        'ITech_IT6332A': PowerManagerITech_IT6332A
    }

    if type not in handler:
        return None

    return handler[type]()


if __name__ == '__main__':
    # pm = PowerManagerITech()
    # print(pm.get_power_current())
    pm = AtpPowerManager('Rigol_DP811')
    pm.set_power_on_off("On")


