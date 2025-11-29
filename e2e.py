# -*- coding: utf-8 -*-
# @Time: 2025/11/29 22:06
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: e2e.py


"""
端到端辅助函数：CRC8 和工具函数。

包含：
- crc8：CRC-8 算法（多项式 0x1D），与您提供的实现兼容。
- get_crc_countdata：用于构建 CRC 计算输入的辅助函数。
- profile11_crc8：历史兼容的包装函数。
"""
from typing import List, Tuple

def crc8(data: List[int], start_value: int = 0x0, xor_value: int = 0x0, div: int = 0x1D, Crc_IsFirstCall: bool = True) -> int:
    """
    计算 CRC-8，输入为字节列表（0-255）。
    使用多项式 div（默认 0x1D），8 位寄存器。
    实现与您提供的代码一致。
    """
    if Crc_IsFirstCall:
        t_crc = start_value
    else:
        t_crc = start_value ^ xor_value
    for i in range(len(data)):
        t_crc ^= data[i]
        for _ in range(8):
            if t_crc & 0x80:
                t_crc = ((t_crc << 1) & 0xFF)
                t_crc ^= div
            else:
                t_crc = ((t_crc << 1) & 0xFF)
    t_crc ^= xor_value
    return t_crc & 0xFF

def get_crc_countdata(data_id: int, counter: int, sig_value_length: List[Tuple[int, int]]) -> List[int]:
    """
    按照您给出的方式构建用于 CRC 的数据。
    data_id: 整数（通常为 12 位或 16 位 DataID）
    counter: 整数（计数器）
    sig_value_length: 列表，每项为 (value, length_in_bits)
    返回：字节列表（每项为 0-255 的整数）
    """
    crc_data = bytearray()
    crc_data += data_id.to_bytes(2, 'little')
    crc_data += counter.to_bytes(1, 'little')
    for value, length in sig_value_length:
        nbytes = ((length - 1) // 8) + 1
        crc_data += int(value).to_bytes(nbytes, 'little', signed=False)
    return list(crc_data)

def profile11_crc8(data_id, data: List[int]) -> int:
    """
    历史兼容的辅助函数。保持原有行为：
    profile11_crc8(data_id, data) == crc8([data_id & 0xFF, 0x00] + data)
    """
    return crc8([data_id & 0xFF, 0x00] + list(data))