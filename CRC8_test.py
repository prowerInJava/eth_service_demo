# -*- coding: utf-8 -*-
# @Time: 2025/12/10 22:41
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: CRC8_test.py


def CRC8(data, startvlue, size):
    initValue = startvlue ^ 0xFF
    poly = 0x1D  # CRC8 多项式
    for i in range(size):
        initValue ^= data[i]
        for _ in range(8):
            if initValue & 0x80:
                initValue = ((initValue << 1) & 0xFF) ^ poly
            else:
                initValue = (initValue << 1) & 0xFF
    return initValue ^ 0xFF

dataid = 0x8C2
data = [0x80, 0x01]

a = [dataid & 0xFF]  # [0xC2]
b = [0x00]
crc1 = CRC8(a, 0xFF, 1)   # → 0x45
crc2 = CRC8(b, crc1, 1)   # → 0xE8
crc3 = CRC8(data, crc2, 2) # → 0xAD
final = crc3 ^ 0xFF        # → 0x52 ✅
print(hex(final))