# -*- coding: utf-8 -*-
# @Time: 2025/11/30 00:05
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: eth_service.py

# -*- coding: utf-8 -*-
"""
修正版：在 UDP 模式下同时创建发送与接收的 UDPTransport（分别绑定发送端口与接收端口），
以实现本地回环测试时能够收到自己发送的数据；AF_PACKET 模式保留单 socket（send/recv 同一 socket）。

对外接口：
- register_receive_callback(cb)
- set_signal(name, value)
- send()
- send_raw_frame(frame_bytes)
- start() / stop()
- build_framed_payload()
- send_and_return_bytes()
"""
from typing import Callable, Optional, Tuple, Dict, Any
import threading
import time

try:
    from __init__ import UDFrame_Z_204
except ImportError:
    UDFrame_Z_204 = None

from framer import Framer
from eth_comm import EthECUCommunicator

# transport 实现
from transport_udp import UDPTransport
from transport_afpacket import AFPacketTransport


class EthService:
    """
    将 EthECUCommunicator + transport + framer 封装为长期运行的服务对象。

    关键改动：
    - 当 transport_type == 'udp' 时，会同时创建两个 UDPTransport：
        * self.transport_send: 绑定到 udp_local，remote 指向 udp_remote（用于发送）
        * self.transport_recv: 绑定到 udp_remote，remote 指向 udp_local（用于接收）
      并分别创建发送/接收的 EthECUCommunicator（接收的 communicator 注册回调并 start_receiving）。
    - 当 transport_type == 'afpacket' 时，保持原先行为（单 AFPacketTransport，既发送也接收）。
    """
    def __init__(self,
                 transport_type: str = 'afpacket',
                 frame_cls = None,
                 # AF_PACKET params
                 iface: Optional[str] = None,
                 dst_mac: Optional[str] = None,
                 # UDP params (供发送/接收两端使用)
                 udp_local: Optional[Tuple[str, int]] = None,
                 udp_remote: Optional[Tuple[str, int]] = None,
                 # common
                 ethertype: int = 0x88B5,
                 framer_mode: str = 'custom_4_4',
                 id_endian: str = 'big',
                 len_endian: str = 'big'):
        if frame_cls is None:
            if UDFrame_Z_204 is None:
                raise ValueError("frame_cls 未提供，且默认 UDFrame_Z_204 无法导入，请传入 frame_cls 参数")
            frame_cls = UDFrame_Z_204
        self.frame_cls = frame_cls

        self.transport_type = transport_type.lower()
        self.ethertype = ethertype

        # framer（可选）
        if framer_mode is None or framer_mode == 'none':
            self.framer = None
        else:
            self.framer = Framer(mode=framer_mode, id_endian=id_endian, len_endian=len_endian)

        # 发送/接收 communicator 与 transport 占位
        self.transport_send = None
        self.transport_recv = None
        self.comm_send: Optional[EthECUCommunicator] = None
        self.comm_recv: Optional[EthECUCommunicator] = None

        # 初始化 transport(s)
        if self.transport_type == 'afpacket':
            if not iface or not dst_mac:
                raise ValueError("AF_PACKET 模式需要提供 iface 与 dst_mac")
            # 单一 transport 即可 send/recv
            transport = AFPacketTransport(iface=iface, dst_mac=dst_mac, ethertype=ethertype)
            self.transport_send = transport
            self.transport_recv = transport
            # 发送与接收共用同一个 communicator（可以同时 send 和 start_receiving）
            self.comm_send = EthECUCommunicator(self.frame_cls, self.transport_send, framer=self.framer)
            self.comm_recv = self.comm_send
        elif self.transport_type == 'udp':
            # 需要 udp_local 与 udp_remote，创建两个 UDPTransport（发送与接收）
            if not udp_local or not udp_remote:
                raise ValueError("UDP 模式需要提供 udp_local 与 udp_remote")
            # 发送端：绑定到 udp_local，发送到 udp_remote
            self.transport_send = UDPTransport(local_addr=udp_local, remote_addr=udp_remote)
            # 接收端：绑定到 udp_remote，发送目标为 udp_local（用于与发送端对等回环）
            self.transport_recv = UDPTransport(local_addr=udp_remote, remote_addr=udp_local)
            # 创建发送/接收的 communicator（发送使用 transport_send，接收使用 transport_recv）
            self.comm_send = EthECUCommunicator(self.frame_cls, self.transport_send, framer=self.framer)
            # 接收端也需要同样的 framer 来 strip header（若 framer 为 None，则解析整个 payload）
            self.comm_recv = EthECUCommunicator(self.frame_cls, self.transport_recv, framer=self.framer)
        else:
            raise ValueError("未知的 transport_type: 支持 'afpacket' 或 'udp'")

        # 注册列表
        self._receive_cbs = []
        # 内部转发接收回调（由接收端 communicator 调用）
        self.comm_recv.register_on_receive(self._internal_on_receive)

        # 线程/锁管理
        self._send_lock = threading.Lock()
        self._running = False

    # --- 生命周期 ---
    def start(self):
        if self._running:
            return
        self._running = True
        # 启动接收端的接收循环（AF_PACKET 时 comm_recv == comm_send）
        try:
            self.comm_recv.start_receiving()
        except Exception:
            # 启动接收失败也不要抛出，让上层决定如何处理
            pass

    def stop(self):
        if not self._running:
            return
        # 停止 transport(s)
        try:
            if self.transport_send and hasattr(self.transport_send, 'stop'):
                self.transport_send.stop()
        except Exception:
            pass
        try:
            # 如果发送与接收是不同实例，停止接收 transport
            if self.transport_recv and self.transport_recv is not self.transport_send and hasattr(self.transport_recv, 'stop'):
                self.transport_recv.stop()
        except Exception:
            pass
        self._running = False

    # --- 接收回调注册 ---
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
        # 分发给用户注册的回调
        for cb in list(self._receive_cbs):
            try:
                cb(parsed, raw_payload)
            except Exception:
                pass

    # --- 发送接口 ---
    def set_signal(self, sig_name: str, value: int):
        self.comm_send.set_signal(sig_name, value)

    def send(self):
        with self._send_lock:
            self.comm_send.send()

    def send_raw_frame(self, frame_bytes: bytes):
        if not isinstance(frame_bytes, (bytes, bytearray)):
            raise TypeError("frame_bytes must be bytes or bytearray")
        with self._send_lock:
            # 发送通过发送 transport（不经 comm_send）
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
                return self.framer.add_header(payload, msg_id=getattr(self.frame_cls, 'msg_id', 0))
            return payload

    def send_and_return_bytes(self) -> bytes:
        with self._send_lock:
            self.comm_send._pack_signals()
            self.comm_send._apply_e2e_for_groups()
            payload = bytes(self.comm_send.payload)
            if self.framer is not None:
                framed = self.framer.add_header(payload, msg_id=getattr(self.frame_cls, 'msg_id', 0))
                # 通过发送 transport 发出 framed bytes
                if self.transport_send:
                    self.transport_send.send(framed)
                return framed
            else:
                if self.transport_send:
                    self.transport_send.send(payload)
                return payload


# ==== 简短示例（仅用于直接运行时演示） ====
if __name__ == '__main__':
    # 下面示例不使用命令行，直接创建一个 UDP loopback 的服务实例用于本地测试
    try:
        svc = EthService(
            transport_type='udp',
            udp_local=('127.0.0.1', 12000),
            udp_remote=('127.0.0.1', 12001),
            framer_mode='custom_4_4',
            id_endian='big',
            len_endian='big'
        )
        print("使用 UDP 双 socket 模式：发送绑定 127.0.0.1:12000，接收绑定 127.0.0.1:12001")
    except Exception as e:
        print("初始化失败：", e)
        raise

    def cb(parsed, raw):
        print("收到信号回调, payload:", raw.hex())
        for k in ('CrsCtrlOvrdnReq', 'CrsCtrlOvrdnCntr4', 'CrsCtrlOvrdnChk8'):
            if k in parsed:
                print(f"  {k} = {parsed[k]}")

    svc.register_receive_callback(cb)
    svc.start()

    svc.set_signal('CrsCtrlOvrdnReq', 1)
    svc.set_signal('LVPwrSplyErrStsSts', 0x1234)

    for i in range(4):
        b = svc.send_and_return_bytes()
        print(f"已发送（{len(b)} bytes）: {b.hex()}")
        time.sleep(0.2)

    # 直接发送 pcap 中的完整帧示例
    sample_hex = "00000094000000170100c4e78601000004d20000000000000000000000"
    svc.send_raw_frame(bytes.fromhex(sample_hex))

    time.sleep(1.0)
    svc.stop()
    print("服务已停止")