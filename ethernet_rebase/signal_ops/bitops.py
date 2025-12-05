# -*- coding: utf-8 -*-
# @Time: 2025/11/29 22:58
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: bitops.py

"""
支持按信号定义的 byteorder 在 bytearray 中读写位域：
- "Intel" (Little-endian, LSB-first)：startbit 表示信号第一个（最低权）位的绝对位索引，
  在字节内按 bit 0 = LSB, bit 7 = MSB 计数（与原实现一致）。
- "Motorola" (Big-endian / MSB-first，常见于 DBC/AUTOSAR 的 Motorola/BigEndian 信号)：
  startbit 表示信号的最高有效位（MSB）在报文中的绝对位索引（DBC 风格）。
  从 startbit 向更小的位索引方向延展 length 位（跨字节时按 DBC 的连续存放规则）。

函数：
- set_bits(buf, startbit, length, value, byteorder="Intel")
- get_bits(buf, startbit, length, byteorder="Intel")

备注：
- 这里对 Motorola 的约定是 "startbit 为 MSB 的绝对位索引"（符合大多数 DBC/工具的表示）。
  如果你的信号定义使用不同的 Motorola 编号约定，请告诉我，我可以按你那套规则调整。
"""
from typing import ByteString


def set_bits(buf: bytearray, startbit: int, length: int, value: int, byteorder: str = "Intel") -> None:
    """
    在 buf 中写入 length 位的 value，从 startbit 开始，按指定 byteorder。
    - buf: bytearray（会原地修改）
    - startbit: 绝对位索引（0 表示字节 0 的 LSB 当使用 Intel；当使用 Motorola 时表示 MSB 的绝对位索引）
    - length: 位长度
    - value: 要写入的整数值（非负，不能超出 length 比特）
    - byteorder: "Intel" 或 "Motorola"
    """
    if length == 0:
        return
    if value < 0 or value >= (1 << length):
        raise ValueError(f"value {value} doesn't fit in {length} bits")

    if byteorder.lower() == "intel":
        # Intel: LSB-first，startbit 为最低位的绝对索引
        for bit_index in range(length):
            src_bit = (value >> bit_index) & 1
            abs_bit = startbit + bit_index
            byte_index = abs_bit // 8
            bit_in_byte = abs_bit % 8  # 0 = LSB, 7 = MSB
            if src_bit:
                buf[byte_index] |= (1 << bit_in_byte)
            else:
                buf[byte_index] &= ~(1 << bit_in_byte)
    elif byteorder.lower() in ("motorola", "bigendian"):
        # Motorola: MSB-first (DBC 风格)
        # startbit 表示信号的 MSB 的绝对位索引
        # 我们从 MSB 向下（绝对位索引减小）写入每一位
        for i in range(length):
            # 要写入的位，从高位到低位
            bit_to_write = (value >> (length - 1 - i)) & 1
            abs_bit = startbit - i
            if abs_bit < 0:
                raise IndexError("startbit/length 超出缓冲区范围（计算出的绝对位为负）")
            byte_index = abs_bit // 8
            bit_in_byte = abs_bit % 8  # 0..7, 0 表示字节内的 MSB
            # 在实际字节中，MSB 位对应掩码 1 << 7, LSB 对应 1 << 0
            mask = 1 << (7 - bit_in_byte)
            if bit_to_write:
                buf[byte_index] |= mask
            else:
                buf[byte_index] &= ~mask
    else:
        raise ValueError("未知的 byteorder，支持 'Intel' 或 'Motorola'。")


def get_bits(buf: ByteString, startbit: int, length: int, byteorder: str = "Intel") -> int:
    """
    从 buf 中读取从 startbit 开始的 length 位，按指定 byteorder 返回整数值。
    - 对于 Intel：startbit 为最低位的绝对索引，返回值的位 0 对应报文中的最低位（LSB）。
    - 对于 Motorola：startbit 表示信号 MSB 的绝对索引，返回值按自然整数（高位先读出）。
    """
    if length == 0:
        return 0
    if byteorder.lower() == "intel":
        val = 0
        for bit_index in range(length):
            abs_bit = startbit + bit_index
            byte_index = abs_bit // 8
            bit_in_byte = abs_bit % 8
            bit = (buf[byte_index] >> bit_in_byte) & 1
            val |= (bit << bit_index)
        return val
    elif byteorder.lower() in ("motorola", "bigendian"):
        val = 0
        for i in range(length):
            abs_bit = startbit - i
            if abs_bit < 0:
                raise IndexError("startbit/length 超出缓冲区范围（计算出的绝对位为负）")
            byte_index = abs_bit // 8
            bit_in_byte = abs_bit % 8  # 0..7, 0 对应字节 MSB
            mask = 1 << (7 - bit_in_byte)
            bit = 1 if (buf[byte_index] & mask) else 0
            val = (val << 1) | bit
        return val
    else:
        raise ValueError("未知的 byteorder，支持 'Intel' 或 'Motorola'。")


# 兼容旧接口（直接调用）
def set_bits_le(buf: bytearray, startbit: int, length: int, value: int) -> None:
    set_bits(buf, startbit, length, value, byteorder="Intel")


def get_bits_le(buf: ByteString, startbit: int, length: int) -> int:
    return get_bits(buf, startbit, length, byteorder="Intel")
