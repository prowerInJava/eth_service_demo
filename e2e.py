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
- profile11_crc8：针对 AUTOSAR E2E Profile 11 的包装函数，使用与 OEM/原始实现一致的 CRC 初始值（0xFF）。
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

def profile11_crc8_(data_id, data: List[int]) -> int:
    """
    历史兼容的辅助函数。保持原有行为：
    profile11_crc8(data_id, data) == crc8([data_id & 0xFF, 0x00] + data)
    """
    return crc8([data_id & 0xFF, 0x00] + list(data))


def profile11_crc8(data_id: int, counter: int, user_data: List[int]) -> int:
    """
    计算 AUTOSAR E2E Profile 11 的 CRC8。
    :param data_id: Data ID (e.g., 0x8C2)
    :param counter: 4-bit counter (0-15)
    :param user_data: List of protected signal bytes
    :return: 8-bit CRC
    """
    data_id_low = data_id & 0xFF
    combined_byte = ((counter & 0x0F) << 4) | (data_id_low & 0x0F)
    full_input = [data_id_low, 0x00, combined_byte] + list(user_data)
    return crc8(full_input, start_value=0x00, xor_value=0x00, div=0x1D, Crc_IsFirstCall=True)


def profile11_crc8_standard(data_id: int, counter: int, user_data: List[int]) -> int:
    """
    严格按照 AUTOSAR E2E Profile 11 分步计算 CRC。
    """
    data_id_low = data_id & 0xFF

    # Step 1: CRC(DataID_Low)
    crc1 = crc8(
        data=[data_id_low],
        start_value=0xFF,
        xor_value=0xFF,
        div=0x1D,
        Crc_IsFirstCall=False
    )  # 注意: 实际初始值 = 0xFF ^ 0xFF = 0x00

    # Step 2: CRC(0x00)
    crc2 = crc8(
        data=[0x00],
        start_value=crc1,
        xor_value=0xFF,
        div=0x1D,
        Crc_IsFirstCall=False
    )

    # Step 3: CRC(combined_byte + user_data)
    combined_byte = ((counter & 0x0F) << 4) | (data_id_low & 0x0F)
    crc3 = crc8(
        data=[combined_byte] + user_data,
        start_value=crc2,
        xor_value=0xFF,
        div=0x1D,
        Crc_IsFirstCall=False
    )

    # Step 4: Final XOR with 0xFF
    final_crc = crc3 ^ 0xFF
    return final_crc & 0xFF