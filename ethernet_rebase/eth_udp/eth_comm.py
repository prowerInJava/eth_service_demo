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

    def set_signal(self, sig_name: str, value: int):
        self._signal_values[sig_name] = int(value)

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
            if not hasattr(sig_cls, 'sig_name'):
                continue
            sig_name = getattr(sig_cls, 'sig_name')
            sig_defs[sig_name] = sig_cls

        for gname, members in groups.items():
            dataid = dataids.get(gname)
            profile = profiles.get(gname)
            if dataid is None:
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

            # Get signal values for CRC (non-E2E fields)
            sig_bytes = bytearray()
            for name in other_members:
                if name not in sig_defs:
                    continue
                sig_c = sig_defs[name]
                length = getattr(sig_c, 'sig_length', getattr(sig_c, 'length', None))
                if length is None:
                    continue
                val = self._signal_values.get(name, getattr(sig_c, 'sig_value_init', 0))
                # Pack as little-endian bytes, padded to full bytes
                nbytes = (length + 7) // 8
                sig_bytes.extend(int(val).to_bytes(nbytes, 'little'))

            # Update counter
            counter_length = None
            if counter_name and counter_name in sig_defs:
                cdef = sig_defs[counter_name]
                counter_length = getattr(cdef, 'sig_length', getattr(cdef, 'length', None))

            if counter_length is not None and counter_length > 0:
                counter_mask = (1 << counter_length) - 1
            else:
                # Fallback: assume 4-bit counter if not specified (for backward compatibility)
                counter_mask = 0x0F

            cnt = (self._group_counters.get(gname, 0) + 1) & counter_mask
            if cnt >= 0x0F:  # maximum counter value 0x0E
                cnt = 0
            self._group_counters[gname] = cnt

            # crc校验使用profile11
            if profile == 'PROFILE_11':
                # Profile 11 CRC input format:
                # [data_id_low, 0x00, (counter << 4) | (data_id_low & 0x0F)] + signal_bytes
                data_id_low = dataid & 0xFF
                combined_byte = ((cnt & 0x0F) << 4) | (data_id_low & 0x0F)
                crc_input = [data_id_low, 0x00, combined_byte] + list(sig_bytes)
                crc = e2e.crc8(crc_input, start_value=0xFF, xor_value=0x00, div=0x1D)
            else:
                # 不使用profile11的crc校验
                sig_value_length = []
                for name in other_members:
                    if name not in sig_defs:
                        continue
                    sig_c = sig_defs[name]
                    length = getattr(sig_c, 'sig_length', getattr(sig_c, 'length', None))
                    if length is None:
                        continue
                    val = self._signal_values.get(name, getattr(sig_c, 'sig_value_init', 0))
                    sig_value_length.append((int(val), int(length)))
                crc_input = e2e.get_crc_countdata(dataid, cnt, sig_value_length)
                crc = e2e.crc8(crc_input)

            # E2E 回写入playload
            if counter_name and counter_name in sig_defs:
                cdef = sig_defs[counter_name]
                cstart = getattr(cdef, 'sig_start_bit', getattr(cdef, 'startbit', None))
                clength = getattr(cdef, 'sig_length', getattr(cdef, 'length', None))
                cbyteorder = getattr(cdef, 'sig_byteorder', "Intel")
                if cstart is not None and clength is not None:
                    set_bits(self.payload, cstart, clength, cnt, byteorder=cbyteorder)

            if dataid_field_name and dataid_field_name in sig_defs:
                ddef = sig_defs[dataid_field_name]
                dstart = getattr(ddef, 'sig_start_bit', getattr(ddef, 'startbit', None))
                dlength = getattr(ddef, 'sig_length', getattr(ddef, 'length', None))
                dbyteorder = getattr(ddef, 'sig_byteorder', "Intel")
                if dstart is not None and dlength is not None:
                    # Truncate DataID to field length
                    val_to_write = dataid & ((1 << dlength) - 1)
                    set_bits(self.payload, dstart, dlength, val_to_write, byteorder=dbyteorder)

            if checksum_name and checksum_name in sig_defs:
                chkdef = sig_defs[checksum_name]
                chkstart = getattr(chkdef, 'sig_start_bit', getattr(chkdef, 'startbit', None))
                chklength = getattr(chkdef, 'sig_length', getattr(chkdef, 'length', None))
                chkbyteorder = getattr(chkdef, 'sig_byteorder', "Intel")
                if chkstart is not None and chklength is not None:
                    val_to_write = crc & ((1 << chklength) - 1)
                    set_bits(self.payload, chkstart, chklength, val_to_write, byteorder=chkbyteorder)

    def _apply_e2e_for_groups_bak(self):
        groups = getattr(self.frame, 'sig_group_dict', {})
        dataids = getattr(self.frame, 'sig_group_dataid_dict', {})
        # build sig_defs map
        sig_defs = {}
        for attr in dir(self.frame):
            if attr.startswith('__'):
                continue
            sig_cls = getattr(self.frame, attr)
            if not hasattr(sig_cls, 'sig_name'):
                continue
            sig_defs[getattr(sig_cls, 'sig_name')] = sig_cls

        for gname, members in groups.items():
            dataid = dataids.get(gname, None)
            if dataid is None:
                continue

            counter_name = None
            checksum_name = None
            dataid_field_name = None
            other_members = []
            for m in members:
                mn = m
                if 'Cntr' in mn:
                    counter_name = mn
                elif 'Chk' in mn:
                    checksum_name = mn
                elif 'DataID' in mn:
                    dataid_field_name = mn
                else:
                    other_members.append(mn)

            sig_value_length = []
            for name in other_members:
                if name not in sig_defs:
                    continue
                sig_c = sig_defs[name]
                length = getattr(sig_c, 'sig_length', getattr(sig_c, 'length', None))
                startbit = getattr(sig_c, 'sig_start_bit', getattr(sig_c, 'startbit', None))
                if length is None or startbit is None:
                    continue
                val = self._signal_values.get(name, getattr(sig_c, 'sig_value_init', 0))
                sig_value_length.append((int(val), int(length)))

            cnt = self._group_counters.get(gname, 0)
            cnt = (cnt + 1) & 0x0F
            self._group_counters[gname] = cnt

            crc_input = e2e.get_crc_countdata(dataid, cnt, sig_value_length)
            crc = e2e.crc8(crc_input)

            # 写计数器/数据ID/校验（保留 byteorder）
            if counter_name and counter_name in sig_defs:
                cdef = sig_defs[counter_name]
                cstart = getattr(cdef, 'sig_start_bit', getattr(cdef, 'startbit', None))
                clength = getattr(cdef, 'sig_length', getattr(cdef, 'length', None))
                cbyteorder = getattr(cdef, 'sig_byteorder', "Intel")
                if cstart is not None and clength is not None:
                    set_bits(self.payload, cstart, clength, cnt, byteorder=cbyteorder)
            if dataid_field_name and dataid_field_name in sig_defs:
                ddef = sig_defs[dataid_field_name]
                dstart = getattr(ddef, 'sig_start_bit', getattr(ddef, 'startbit', None))
                dlength = getattr(ddef, 'sig_length', getattr(ddef, 'length', None))
                dbyteorder = getattr(ddef, 'sig_byteorder', "Intel")
                if dstart is not None and dlength is not None:
                    set_bits(self.payload, dstart, dlength, dataid & ((1 << dlength) - 1), byteorder=dbyteorder)
            if checksum_name and checksum_name in sig_defs:
                chk = sig_defs[checksum_name]
                chkstart = getattr(chk, 'sig_start_bit', getattr(chk, 'startbit', None))
                chklength = getattr(chk, 'sig_length', getattr(chk, 'length', None))
                chkbyteorder = getattr(chk, 'sig_byteorder', "Intel")
                if chkstart is not None and chklength is not None:
                    set_bits(self.payload, chkstart, chklength, crc & ((1 << chklength) - 1), byteorder=chkbyteorder)

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
                val = get_bits(payload, startbit, length, byteorder=byteorder)
                parsed[name] = val

            for cb in self._on_receive_callbacks:
                try:
                    cb(parsed, bytes(payload))
                except Exception:
                    pass

        self.transport.start_receiving(_cb)
