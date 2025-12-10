# -*- coding: utf-8 -*-
# @Time: 2025/11/29 23:05
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: eth_comm.py

"""
eth_comm.py（带可选 framer 支持）

对原先实现的修改点：
- 构造函数增加 framer 参数（默认为 None），接受 Framer 实例。
- send() 在 transport.send 之前，若配置了 framer 会先调用 framer.add_header(payload, msg_id=self.frame.msg_id)。
- start_receiving 的回调会在解析之前调用 framer.strip_header(raw)（若配置了 framer），并把剥离后的 payload 用于信号解析。
"""
from typing import Callable, Dict, Any, List, Optional
from ..signal_ops.bitops import set_bits, get_bits
from ..signal_ops import e2e
from ..signal_ops.framer import Framer  # 引入 Framer（如果没有使用 framer，可传入 None）

class EthECUCommunicator:
    def __init__(self, frame_cls, transport, framer: Optional[Framer] = None):
        """
        frame_cls: 描述信号的类（例如 UDFrame_Z_ADCU30_204）
        transport: 必须实现 send(bytes) 和 start_receiving(callback)
        framer: 可选的 Framer 实例（用于封装/解封装应用层 header），若为 None 则不做 header 操作
        """
        self.frame = frame_cls
        self.transport = transport
        self.framer = framer
        self.payload = bytearray(self.frame.msg_length)
        self._signal_values: Dict[str, int] = {}
        self._group_counters: Dict[str, int] = {}
        self._on_receive_callbacks: List[Callable[[Dict[str, Any], bytes], None]] = []

        for g in getattr(self.frame, 'sig_group_dict', {}):
            self._group_counters[g] = 0

    # def set_signal(self, sig_name: str, value: int):
    #     self._signal_values[sig_name] = int(value)

    def set_signal(self, sig_name: str, physical_value: float):
        """
        设置信号的物理值（如 23.5 或 100），内部根据 sig_value_factor / sig_value_offset 转为 raw_value 并存储。
        接受 int 或 float，均视为物理值。
        """
        # 查找信号定义
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

        # 统一处理：int 或 float 都是物理值
        physical_value = float(physical_value)  # 允许传 int，转为 float 计算

        raw_value = (physical_value - offset) / factor

        # 检查是否接近整数
        if abs(raw_value - round(raw_value)) >= 1e-6:
            raise ValueError(
                f"Computed raw_value ({raw_value}) for signal '{sig_name}' is not an integer "
                f"(factor={factor}, offset={offset}, physical={physical_value})"
            )

        raw_value = int(round(raw_value))
        max_val = (1 << length) - 1

        if raw_value < 0 or raw_value > max_val:
            raise ValueError(
                f"Raw value {raw_value} for signal '{sig_name}' out of range [0, {max_val}] "
                f"(physical={physical_value}, factor={factor}, offset={offset})"
            )

        self._signal_values[sig_name] = raw_value

    def set_raw_signal(self, sig_name: str, raw_value: int):
        """绕过物理值转换，直接设置原始位域值（用于测试或特殊信号）"""
        # 可选：校验 raw_value 范围
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

            if profile == 'PROFILE_11':
                cnt = self._group_counters[gname]
                self._group_counters[gname] = (cnt + 1) & 0x0F

                counter_name = None
                checksum_name = None
                dataid_name = None
                other_signals = []

                # Classify members, skip _UB signals
                for m in members:
                    if m.endswith('_UB'):
                        continue  # Update Bit is NOT part of protected data
                    if 'Cntr' in m or 'Counter' in m:
                        counter_name = m
                    elif 'Chk' in m or 'Check' in m:
                        checksum_name = m
                    elif 'DataID' in m:
                        dataid_name = m
                    else:
                        other_signals.append(m)

                if not counter_name or not checksum_name:
                    continue

                # Build protected data
                protected_data = []
                dataid_high_nibble = (dataid >> 8) & 0x0F
                first_byte = ((dataid_high_nibble & 0x0F) << 4) | (cnt & 0x0F)
                protected_data.append(first_byte)

                for sig_name in other_signals:
                    if sig_name not in sig_defs:
                        continue
                    sig_def = sig_defs[sig_name]
                    length = getattr(sig_def, 'length', getattr(sig_def, 'sig_length', 0))
                    if length <= 0:
                        continue
                    raw_val = self._signal_values.get(sig_name, 0)
                    num_bytes = (length + 7) // 8
                    protected_data.extend(raw_val.to_bytes(num_bytes, 'little'))

                crc_value = e2e.profile11_crc8(dataid, protected_data)

                # Write back fields
                if counter_name in sig_defs:
                    cdef = sig_defs[counter_name]
                    startbit = getattr(cdef, 'startbit', getattr(cdef, 'sig_start_bit', 0))
                    length = getattr(cdef, 'length', getattr(cdef, 'sig_length', 4))
                    byteorder = getattr(cdef, 'sig_byteorder', "Intel")
                    set_bits(self.payload, startbit, length, cnt, byteorder=byteorder)

                if dataid_name in sig_defs:
                    ddef = sig_defs[dataid_name]
                    startbit = getattr(ddef, 'startbit', 0)
                    length = getattr(ddef, 'length', 4)
                    byteorder = getattr(ddef, 'sig_byteorder', "Intel")
                    set_bits(self.payload, startbit, length, dataid_high_nibble, byteorder=byteorder)

                if checksum_name in sig_defs:
                    chkdef = sig_defs[checksum_name]
                    startbit = getattr(chkdef, 'startbit', 0)
                    length = getattr(chkdef, 'length', 8)
                    byteorder = getattr(chkdef, 'sig_byteorder', "Intel")
                    set_bits(self.payload, startbit, length, crc_value, byteorder=byteorder)

    def send(self):
        self._pack_signals()
        self._apply_e2e_for_groups()
        payload_bytes = bytes(self.payload)
        if self.framer is not None:
            # 用 frame class 的 msg_id（或可替换为其它编号）
            framed = self.framer.add_header(payload_bytes, msg_id=getattr(self.frame, 'msg_id', 0))
            self.transport.send(framed)
        else:
            self.transport.send(payload_bytes)

    def register_on_receive(self, callback: Callable[[Dict[str, Any], bytes], None]):
        self._on_receive_callbacks.append(callback)

    def start_receiving(self):
        def _cb(raw: bytes):
            # 如果配置了 framer，则先剥离 header
            try:
                if self.framer is not None:
                    msg_id, payload = self.framer.strip_header(raw)
                    # 可选：若 msg_id 与 frame.msg_id 不匹配可以忽略或继续处理，当前我们继续处理 payload
                else:
                    payload = raw
            except Exception as ex:
                # header 解析错误 -> 忽略该帧
                return

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
                # val = get_bits(payload, startbit, length, byteorder=byteorder)
                # parsed[name] = val
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
