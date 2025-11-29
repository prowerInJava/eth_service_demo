# -*- coding: utf-8 -*-
# @Time: 2025/11/29 23:43
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: transport_afpacket.py

"""
transport_afpacket.py
基于 Linux AF_PACKET 原始以太网套接字的传输层实现。

要求：在 Linux（如 Ubuntu）上以 root 权限运行或授予 CAP_NET_RAW。
接口：
- AFPacketTransport(iface, dst_mac, ethertype=0x88B5, src_mac=None)
- send(payload: bytes)
- start_receiving(callback: Callable[[bytes], None], filter_ethertype: bool=True)
- stop()
"""
import socket
import threading
import struct
import fcntl
from typing import Callable, Optional

SIOCGIFHWADDR = 0x8927  # get hardware address
ETH_P_ALL = 0x0003

def mac_str_to_bytes(mac: str) -> bytes:
    """"aa:bb:cc:dd:ee:ff" -> b'\xaa\xbb\xcc\xdd\xee\xff'"""
    parts = mac.split(':')
    if len(parts) != 6:
        raise ValueError("MAC 格式错误，应为 aa:bb:cc:dd:ee:ff")
    return bytes(int(p, 16) for p in parts)

def get_iface_mac(iface: str) -> str:
    """通过 ioctl 获取接口 MAC 字符串 "aa:bb:..."。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ifreq = struct.pack('256s', iface.encode('utf-8')[:15])
        res = fcntl.ioctl(s.fileno(), SIOCGIFHWADDR, ifreq)
        mac_raw = res[18:24]
        return ':'.join('%02x' % b for b in mac_raw)
    finally:
        s.close()

class AFPacketTransport:
    def __init__(self, iface: str, dst_mac: str, ethertype: int = 0x88B5, src_mac: Optional[str] = None):
        """
        iface: 要绑定的网络接口名称，例如 'eth0' 或 'enp3s0'
        dst_mac: 目的 MAC，字符串形式 "aa:bb:cc:dd:ee:ff"
        ethertype: 以太类型（默认为 0x88B5，可按需修改）
        src_mac: 发送方 MAC（可选），不提供则从 iface 读取
        """
        self.iface = iface
        self.dst_mac_bytes = mac_str_to_bytes(dst_mac)
        self.ethertype = ethertype & 0xFFFF
        if src_mac:
            self.src_mac_bytes = mac_str_to_bytes(src_mac)
        else:
            self.src_mac_bytes = mac_str_to_bytes(get_iface_mac(iface))
        # 原始套接字
        self.sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
        # bind 到接口
        self.sock.bind((iface, 0))
        self._recv_thread = None
        self._running = False

        # 以太网最小 payload 长度 (不含以太头)：46 bytes
        self._min_payload = 46

    def _build_frame(self, payload: bytes) -> bytes:
        """构建完整以太网帧：dst(6) + src(6) + ethertype(2 big-endian) + payload(+padding)"""
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("payload 必须是 bytes 或 bytearray")
        # padding 到最小负载
        payload_bytes = bytes(payload)
        if len(payload_bytes) < self._min_payload:
            payload_bytes = payload_bytes + (b'\x00' * (self._min_payload - len(payload_bytes)))
        eth_type_bytes = struct.pack('!H', self.ethertype)  # network(big-endian)
        frame = self.dst_mac_bytes + self.src_mac_bytes + eth_type_bytes + payload_bytes
        return frame

    def send(self, payload: bytes):
        """发送原始 payload（不含以太头），函数会组装以太头并通过 AF_PACKET 发送完整帧。"""
        frame = self._build_frame(payload)
        # 在 AF_PACKET + SOCK_RAW 下，send() 发送整个帧
        self.sock.send(frame)

    def start_receiving(self, callback: Callable[[bytes], None], filter_ethertype: bool = True):
        """
        启动后台线程接收以太帧并调用 callback(payload_bytes).
        payload_bytes 为以太头之后的数据（已经去掉以太头和 type 字段）。
        filter_ethertype: 如果 True，则只回调 ethertype 匹配 self.ethertype 的帧。
        """
        if self._recv_thread:
            return
        self._running = True

        def _loop():
            while self._running:
                try:
                    # recv 返回完整以太帧
                    data = self.sock.recv(65535)
                except Exception:
                    break
                # 至少应包含 14 字节以太头
                if len(data) < 14:
                    continue
                ethertype_be = struct.unpack('!H', data[12:14])[0]
                payload = data[14:]
                if filter_ethertype and ethertype_be != self.ethertype:
                    continue
                try:
                    callback(payload)
                except Exception:
                    # 不抛出到线程外，保护接收循环
                    pass

        self._recv_thread = threading.Thread(target=_loop, daemon=True)
        self._recv_thread.start()

    def stop(self):
        self._running = False
        try:
            self.sock.close()
        except Exception:
            pass
        self._recv_thread = None