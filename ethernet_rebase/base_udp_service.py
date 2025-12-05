# -*- coding: utf-8 -*-
# @Time: 2025/12/6 01:39
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: base_udp_service.py


from typing import Callable, Optional, Tuple, Dict, Any
import threading

from .signal_ops.framer import Framer
from .eth_udp.eth_comm import EthECUCommunicator
from .eth_udp.transport_udp import UDPTransport


class BaseUDPFrameService:
    def __init__(
        self,
        frame_cls,
        transport_type: str = 'udp',
        udp_local: Optional[Tuple[str, int]] = None,
        udp_remote: Optional[Tuple[str, int]] = None,
        ethertype: int = 0x88B5,
        framer_mode: str = 'custom_4_4',
        id_endian: str = 'big',
        len_endian: str = 'big'
    ):
        if transport_type.lower() != 'udp':
            raise ValueError("当前仅支持 'udp' transport_type")
        if not udp_local or not udp_remote:
            raise ValueError("UDP 模式需要提供 udp_local 与 udp_remote")

        self.frame_cls = frame_cls
        self.transport_type = transport_type.lower()
        self.ethertype = ethertype

        # Framer 初始化
        if framer_mode in (None, 'none'):
            self.framer = None
        else:
            self.framer = Framer(mode=framer_mode, id_endian=id_endian, len_endian=len_endian)

        # 发送 transport 和 communicator
        self.transport_send = UDPTransport(local_addr=udp_local, remote_addr=udp_remote)
        self.comm_send = EthECUCommunicator(self.frame_cls, self.transport_send, framer=self.framer)

        # 接收支持（可选，子类可初始化 comm_recv 如果需要）
        self.transport_recv = None
        self.comm_recv = None
        self._receive_cbs = []

        # 线程安全
        self._send_lock = threading.Lock()
        self._running = False

    # --- 生命周期（接收相关，可选）---
    def start(self):
        if self._running:
            return
        self._running = True
        if self.comm_recv:
            try:
                self.comm_recv.start_receiving()
            except Exception as e:
                print(f"[WARN] 启动接收失败: {e}")

    def stop(self):
        if not self._running:
            return
        try:
            if self.transport_send and hasattr(self.transport_send, 'stop'):
                self.transport_send.stop()
        except Exception:
            pass
        if self.transport_recv and self.transport_recv is not self.transport_send:
            try:
                self.transport_recv.stop()
            except Exception:
                pass
        self._running = False

    # --- 接收回调（可选）---
    def register_receive_callback(self, cb: Callable[[Dict[str, Any], bytes], None]):
        if not callable(cb):
            raise ValueError("cb must be callable")
        self._receive_cbs.append(cb)

    def unregister_receive_callback(self, cb):
        try:
            self._receive_cbs.remove(cb)
        except ValueError:
            pass

    def _internal_on_receive(self, parsed: Dict[str, Any], raw_payload: bytes):
        for cb in list(self._receive_cbs):
            try:
                cb(parsed, raw_payload)
            except Exception:
                pass  # 或记录日志

    # --- 发送接口（核心）---
    def set_signal(self, sig_name: str, value: int):
        self.comm_send.set_signal(sig_name, value)

    def send(self):
        with self._send_lock:
            self.comm_send.send()

    def send_raw_frame(self, frame_bytes: bytes):
        if not isinstance(frame_bytes, (bytes, bytearray)):
            raise TypeError("frame_bytes must be bytes or bytearray")
        with self._send_lock:
            if self.transport_send:
                self.transport_send.send(bytes(frame_bytes))
            else:
                raise RuntimeError("没有可用的发送 transport")

    def build_framed_payload(self) -> bytes:
        with self._send_lock:
            self.comm_send._pack_signals()
            self.comm_send._apply_e2e_for_groups()
            payload = bytes(self.comm_send.payload)
            if self.framer is not None:
                msg_id = getattr(self.frame_cls, 'msg_id', 0)
                return self.framer.add_header(payload, msg_id=msg_id)
            return payload

    def send_and_return_bytes(self) -> bytes:
        with self._send_lock:
            self.comm_send._pack_signals()
            self.comm_send._apply_e2e_for_groups()
            payload = bytes(self.comm_send.payload)
            if self.framer is not None:
                msg_id = getattr(self.frame_cls, 'msg_id', 0)
                framed = self.framer.add_header(payload, msg_id=msg_id)
                if self.transport_send:
                    self.transport_send.send(framed)
                return framed
            else:
                if self.transport_send:
                    self.transport_send.send(payload)
                return payload