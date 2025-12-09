# -*- coding: utf-8 -*-
# @Time: 2025/12/09
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: eth_comm2.py

"""
EthECUCommunicator 支持 AUTOSAR E2E Profile 11（符合 OEM 实测帧）。

特性：
- Counter 从 0 开始，0→1→...→15→0
- DataID 字段写入高字节低4位（OEM 定制）
- CRC 计算使用 e2e.profile11_crc8(data_id, counter, user_data)
- 可选 Framer 支持（add_header / strip_header）
"""

from typing import Callable, Dict, Any, List, Optional
from bitops import set_bits, get_bits
import e2e
from framer import Framer  # 可选，若未使用可传 None


class EthECUCommunicator:
    def __init__(self, frame_cls, transport, framer: Optional[Framer] = None):
        """
        :param frame_cls: 帧定义类（如 UDPFrame_ZCL_CSCADCU30_204）
        :param transport: 必须实现 send(bytes) 和 start_receiving(callback)
        :param framer: 可选 Framer 实例，用于加/解应用层头
        """
        self.frame = frame_cls
        self.transport = transport
        self.framer = framer
        self.payload = bytearray(self.frame.msg_length)
        self._signal_values: Dict[str, int] = {}
        self._group_counters: Dict[str, int] = {}
        self._on_receive_callbacks: List[Callable[[Dict[str, Any], bytes], None]] = []

        # 初始化所有信号组 Counter 为 0（第一帧将发送 0）
        for g in getattr(self.frame, 'sig_group_dict', {}):
            self._group_counters[g] = 0

    def set_signal(self, sig_name: str, physical_value: float):
        """设置信号物理值（自动转 raw value）"""
        sig_def = None
        for attr in dir(self.frame):
            if attr.startswith('__'):
                continue
            sig_cls = getattr(self.frame, attr)
            if hasattr(sig_cls, 'sig_name') and sig_cls.sig_name == sig_name:
                sig_def = sig_cls
                break
        if sig_def is None:
            raise KeyError(f"Signal '{sig_name}' not found in frame definition")

        factor = getattr(sig_def, 'sig_value_factor', 1.0)
        offset = getattr(sig_def, 'sig_value_offset', 0.0)
        length = getattr(sig_def, 'sig_length', getattr(sig_def, 'length', None))
        if length is None:
            raise AttributeError(f"Signal '{sig_name}' missing 'sig_length' or 'length'")
        if factor == 0:
            raise ValueError("sig_value_factor cannot be zero")

        physical_value = float(physical_value)
        raw_value = (physical_value - offset) / factor
        if abs(raw_value - round(raw_value)) >= 1e-6:
            raise ValueError(f"Computed raw_value ({raw_value}) is not an integer")
        raw_value = int(round(raw_value))
        max_val = (1 << length) - 1
        if not (0 <= raw_value <= max_val):
            raise ValueError(f"Raw value {raw_value} out of range [0, {max_val}]")

        self._signal_values[sig_name] = raw_value

    def set_raw_signal(self, sig_name: str, raw_value: int):
        """直接设置原始值（绕过物理转换）"""
        self._signal_values[sig_name] = int(raw_value)

    def _pack_signals(self):
        self.payload = bytearray(self.frame.msg_length)
        for attr in dir(self.frame):
            if attr.startswith('__'):
                continue
            sig_cls = getattr(self.frame, attr)
            if not hasattr(sig_cls, 'sig_name'):
                continue
            name = getattr(sig_cls, 'sig_name')
            startbit = getattr(sig_cls, 'sig_start_bit', None) or getattr(sig_cls, 'startbit', None)
            length = getattr(sig_cls, 'sig_length', None) or getattr(sig_cls, 'length', None)
            byteorder = getattr(sig_cls, 'sig_byteorder', "Intel")
            if startbit is None or length is None:
                continue
            val = self._signal_values.get(name, getattr(sig_cls, 'sig_value_init', 0))
            maxv = (1 << length) - 1
            if val < 0:
                val = 0
            if val > maxv:
                val = maxv
            set_bits(self.payload, startbit, length, val, byteorder=byteorder)

    def _apply_e2e_for_groups(self):
        groups = getattr(self.frame, 'sig_group_dict', {})
        dataids = getattr(self.frame, 'sig_group_dataid_dict', {})
        profiles = getattr(self.frame, 'e2e_profile_dict', {})

        # Build sig_defs map
        sig_defs = {}
        for attr in dir(self.frame):
            if attr.startswith('__'):
                continue
            sig_cls = getattr(self.frame, attr)
            if hasattr(sig_cls, 'sig_name'):
                sig_defs[sig_cls.sig_name] = sig_cls

        for gname, members in groups.items():
            dataid = dataids.get(gname)
            profile = profiles.get(gname)
            if dataid is None or profile is None:
                continue

            # Parse group members
            counter_name = None
            checksum_name = None
            dataid_field_name = None
            other_members = []
            for m in members:
                if 'Cntr' in m:
                    counter_name = m
                elif 'Chk' in m:
                    checksum_name = m
                elif 'DataID' in m:
                    dataid_field_name = m
                else:
                    other_members.append(m)

            if profile == 'PROFILE_11':
                # --- Counter: 当前值（第一帧为 0），下次递增 ---
                cnt = self._group_counters[gname]
                self._group_counters[gname] = (cnt + 1) & 0x0F  # 4-bit 循环

                # --- 收集用户信号字节（little-endian）---
                user_data_bytes = bytearray()
                for name in other_members:
                    if name not in sig_defs:
                        continue
                    sig_c = sig_defs[name]
                    length = getattr(sig_c, 'sig_length', getattr(sig_c, 'length', None))
                    if length is None:
                        continue
                    val = self._signal_values.get(name, getattr(sig_c, 'sig_value_init', 0))
                    nbytes = (length + 7) // 8
                    user_data_bytes.extend(int(val).to_bytes(nbytes, 'little'))

                # --- 计算 CRC（使用修正后的 e2e.profile11_crc8）---
                crc = e2e.profile11_crc8(dataid, cnt, list(user_data_bytes))

                # --- 写入 Counter ---
                if counter_name and counter_name in sig_defs:
                    cdef = sig_defs[counter_name]
                    cstart = getattr(cdef, 'sig_start_bit', getattr(cdef, 'startbit', None))
                    clength = getattr(cdef, 'sig_length', getattr(cdef, 'length', None))
                    cbyteorder = getattr(cdef, 'sig_byteorder', "Intel")
                    if cstart is not None and clength is not None:
                        set_bits(self.payload, cstart, clength, cnt, byteorder=cbyteorder)

                # --- 写入 DataID 字段（OEM 定制：高字节低4位）---
                if dataid_field_name and dataid_field_name in sig_defs:
                    ddef = sig_defs[dataid_field_name]
                    dstart = getattr(ddef, 'sig_start_bit', getattr(ddef, 'startbit', None))
                    dlength = getattr(ddef, 'sig_length', getattr(ddef, 'length', None))
                    dbyteorder = getattr(ddef, 'sig_byteorder', "Intel")
                    if dstart is not None and dlength is not None:
                        val_to_write = (dataid & 0x0F00) >> 8
                        set_bits(self.payload, dstart, dlength, val_to_write, byteorder=dbyteorder)

                # --- 写入 Checksum ---
                if checksum_name and checksum_name in sig_defs:
                    chkdef = sig_defs[checksum_name]
                    chkstart = getattr(chkdef, 'sig_start_bit', getattr(chkdef, 'startbit', None))
                    chklength = getattr(chkdef, 'sig_length', getattr(chkdef, 'length', None))
                    chkbyteorder = getattr(chkdef, 'sig_byteorder', "Intel")
                    if chkstart is not None and chklength is not None:
                        val_to_write = crc & ((1 << chklength) - 1)
                        set_bits(self.payload, chkstart, chklength, val_to_write, byteorder=chkbyteorder)

    def send(self):
        self._pack_signals()
        self._apply_e2e_for_groups()
        payload_bytes = bytes(self.payload)
        if self.framer is not None:
            framed = self.framer.add_header(payload_bytes, msg_id=getattr(self.frame, 'msg_id', 0))
            self.transport.send(framed)
        else:
            self.transport.send(payload_bytes)

    def register_on_receive(self, callback: Callable[[Dict[str, Any], bytes], None]):
        self._on_receive_callbacks.append(callback)

    def start_receiving(self):
        def _cb(raw: bytes):
            try:
                if self.framer is not None:
                    _, payload = self.framer.strip_header(raw)
                else:
                    payload = raw
            except Exception:
                return  # Header error → drop

            payload = bytearray(payload[:self.frame.msg_length])
            parsed = {}
            for attr in dir(self.frame):
                if attr.startswith('__'):
                    continue
                sig_cls = getattr(self.frame, attr)
                if not hasattr(sig_cls, 'sig_name'):
                    continue
                name = getattr(sig_cls, 'sig_name')
                startbit = getattr(sig_cls, 'sig_start_bit', getattr(sig_cls, 'startbit', None))
                length = getattr(sig_cls, 'sig_length', getattr(sig_cls, 'length', None))
                byteorder = getattr(sig_cls, 'sig_byteorder', "Intel")
                if startbit is None or length is None:
                    continue
                raw_val = get_bits(payload, startbit, length, byteorder=byteorder)
                factor = getattr(sig_cls, 'sig_value_factor', 1.0)
                offset = getattr(sig_cls, 'sig_value_offset', 0.0)
                physical_val = raw_val * factor + offset
                parsed[name] = physical_val

            for cb in self._on_receive_callbacks:
                try:
                    cb(parsed, bytes(payload))
                except Exception:
                    pass

        self.transport.start_receiving(_cb)