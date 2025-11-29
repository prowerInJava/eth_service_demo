# -*- coding: utf-8 -*-
# @Time: 2025/11/29 23:39
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: parser_sample.py

"""
演示如何使用 Framer（big-endian 4+4 header）解析您提供的 PCAP payload 示例：
00000094000000170100c4e78601000004d20000000000000000000000

步骤：
- 用 Framer.strip_header 切掉 4+4 header，得到 msg_id 和 23 字节的 payload
- 使用 frames 中定义的信号（注意 sig_byteorder）来读取几个示例信号并打印
"""
from framer import Framer
from bitops import get_bits
from eth_fr import UDFrame_Z_ADCU30_204
import binascii

# 您在 pcap 中观察到的原始 payload（31 bytes，hex）
hex_frame = "000000940000001709770100c4e78601000004d20000000000000000000000"
frame_bytes = binascii.unhexlify(hex_frame)

# 配置 Framer：根据您示例中的字节顺序使用 big-endian (00 00 00 94 -> msg_id = 0x94)
framer = Framer(mode="custom_4_4", id_endian="big", len_endian="big")

msg_id, payload = framer.strip_header(frame_bytes)
print(f"msg_id: 0x{msg_id:02X}, payload_len: {len(payload)} bytes")
print("payload (hex):", payload.hex())

# 解析 payload 中的一些信号（使用 frames 中的定义）
frame_def = UDFrame_Z_ADCU30_204

# 收集信号类 map，便于通过名字查找定义
sig_defs = {}
for attr in dir(frame_def):
    if attr.startswith('__'):
        continue
    sig_cls = getattr(frame_def, attr)
    if not hasattr(sig_cls, 'sig_name'):
        continue
    sig_defs[getattr(sig_cls, 'sig_name')] = sig_cls

# 要解析并打印的信号名称（示例）
to_print = [
    "CrsCtrlOvrdnChk8",
    "CrsCtrlOvrdnCntr4",
    "CrsCtrlOvrdnDataID4",
    "CrsCtrlOvrdnReq",
    "LVPwrSplyErrStsChk8",
    "LVPwrSplyErrStsCntr4",
    "LVPwrSplyErrStsDataID4",
    "LVPwrSplyErrStsSts"
]

for name in to_print:
    sig = sig_defs.get(name)
    if not sig:
        continue
    startbit = getattr(sig, 'sig_start_bit', getattr(sig, 'startbit', None))
    length = getattr(sig, 'sig_length', getattr(sig, 'lenght', None))
    byteorder = getattr(sig, 'sig_byteorder', "Intel")
    if startbit is None or length is None:
        continue
    # 确保 payload 长度足够；get_bits 内会根据索引读取
    try:
        val = get_bits(payload, startbit, length, byteorder=byteorder)
    except Exception as e:
        val = f"ERR: {e}"
    print(f"{name}: startbit={startbit}, len={length}, byteorder={byteorder} -> {val}")