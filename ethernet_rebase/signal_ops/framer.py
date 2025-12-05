# -*- coding: utf-8 -*-
# @Time: 2025/11/29 23:26
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: framer.py

"""
可插拔的帧封装/解封装（framing）工具。
支持模式：
- "none"：无封装，add_header 返回原 payload，strip_header 返回 (None, frame)
- "custom_4_4"：自定义格式：4 字节 ID + 4 字节 length + payload
    - ID 和 length 的字节序可配置（'little' 或 'big'）
"""
from typing import Optional, Tuple

class Framer:
    def __init__(self, mode: str = "none", id_endian: str = "big", len_endian: str = "big"):
        """
        mode: "none" 或 "custom_4_4"
        id_endian / len_endian: "little" 或 "big"
        默认改为 big-endian，方便匹配您给出的 PCAP 示例： 00000094 00000017 ...
        """
        self.mode = mode
        if id_endian not in ("little", "big"):
            raise ValueError("id_endian must be 'little' or 'big'")
        if len_endian not in ("little", "big"):
            raise ValueError("len_endian must be 'little' or 'big'")
        self.id_endian = id_endian
        self.len_endian = len_endian

    def add_header(self, payload: bytes, msg_id: Optional[int] = None) -> bytes:
        """
        将 header 附加到 payload 并返回完整帧。
        对于 custom_4_4 模式，msg_id 必须提供（整数），会作为 4 字节写入（按照 id_endian）。
        length 写入为 payload 的字节长度（4 字节，根据 len_endian）。
        """
        if self.mode == "none":
            return payload
        if self.mode == "custom_4_4":
            if msg_id is None:
                raise ValueError("msg_id must be provided for custom_4_4 framer")
            id_bytes = int(msg_id).to_bytes(4, self.id_endian, signed=False)
            length_bytes = len(payload).to_bytes(4, self.len_endian, signed=False)
            return id_bytes + length_bytes + payload
        raise NotImplementedError(f"Unsupported framer mode: {self.mode}")

    def strip_header(self, frame: bytes) -> Tuple[Optional[int], bytes]:
        """
        从 frame 中剥离 header 并返回 (msg_id_or_None, payload_bytes)。
        如果 header 校验失败（长度与实际不符）将抛出 ValueError。
        如果 mode == "none"，返回 (None, frame)。
        """
        if self.mode == "none":
            return None, frame
        if self.mode == "custom_4_4":
            if len(frame) < 8:
                raise ValueError("frame too short to contain 4+4 header")
            id_bytes = frame[0:4]
            len_bytes = frame[4:8]
            msg_id = int.from_bytes(id_bytes, self.id_endian, signed=False)
            payload_length = int.from_bytes(len_bytes, self.len_endian, signed=False)
            payload = frame[8:]
            if payload_length > len(payload):
                raise ValueError(f"Declared payload length {payload_length} > actual {len(payload)}")
            payload = payload[:payload_length]
            return msg_id, payload
        raise NotImplementedError(f"Unsupported framer mode: {self.mode}")