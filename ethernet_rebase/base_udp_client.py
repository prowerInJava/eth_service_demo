# -*- coding: utf-8 -*-
# @Time: 2025/12/6 01:38
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: base_udp_client.py


from typing import Callable, Optional, Tuple, Dict, Any

from .signal_ops.framer import Framer
from .eth_udp.eth_comm import EthECUCommunicator
from .eth_udp.transport_udp import UDPTransport


class BaseUDPFrameClient:
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

        # UDP Transport：接收端绑定 remote（因为对端发到 remote 端口）
        self.transport_recv = UDPTransport(local_addr=udp_remote, remote_addr=udp_local)
        self.comm_recv = EthECUCommunicator(self.frame_cls, self.transport_recv, framer=self.framer)

        # 回调管理
        self._receive_cbs = []
        self.comm_recv.register_on_receive(self._internal_on_receive)

        # 线程/状态
        self._running = False

    # --- 生命周期 ---
    def start(self):
        if self._running:
            return
        self._running = True
        try:
            self.comm_recv.start_receiving()
        except Exception as e:
            print(f"[WARN] 启动接收失败: {e}")

    def stop(self):
        if not self._running:
            return
        try:
            if hasattr(self.transport_recv, 'stop'):
                self.transport_recv.stop()
        except Exception:
            pass
        self._running = False

    # --- 回调注册 ---
    def register_receive_callback(self, cb: Callable[[Dict[str, Any], bytes], None]):
        if not callable(cb):
            raise ValueError("cb must be callable")
        self._receive_cbs.append(cb)

    def unregister_receive_callback(self, cb: Callable[[Dict[str, Any], bytes], None]):
        try:
            self._receive_cbs.remove(cb)
        except ValueError:
            pass

    def _internal_on_receive(self, parsed: Dict[str, Any], raw_payload: bytes):
        for cb in list(self._receive_cbs):
            try:
                cb(parsed, raw_payload)
            except Exception:
                # 可选：记录日志
                pass