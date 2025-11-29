# -*- coding: utf-8 -*-
# @Time: 2025/11/29 23:04
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: transport_udp.py

"""
transport_udp.py
一个简单的 UDP 传输实现，提供 send() 和 start_receiving(callback) 接口。

注意：这是用于演示/测试的实现 — 在生产或真实车载以太环境中需替换为真实的以太网/原始套接字传输。
"""
import socket
import threading
from typing import Callable

class UDPTransport:
    def __init__(self, local_addr=('0.0.0.0', 12000), remote_addr=('127.0.0.1', 12001)):
        self.local_addr = local_addr
        self.remote_addr = remote_addr
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(self.local_addr)
        self._recv_thread = None
        self._running = False

    def send(self, payload: bytes):
        """把原始 payload 作为 UDP 报文发送到 remote_addr。"""
        self.sock.sendto(payload, self.remote_addr)

    def start_receiving(self, callback: Callable[[bytes], None]):
        """启动后台线程接收数据报并调用 callback(payload)。"""
        if self._recv_thread:
            return
        self._running = True
        def _loop():
            while self._running:
                try:
                    data, _ = self.sock.recvfrom(4096)
                    callback(data)
                except Exception:
                    break
        self._recv_thread = threading.Thread(target=_loop, daemon=True)
        self._recv_thread.start()

    def stop(self):
        self._running = False
        try:
            self.sock.close()
        except Exception:
            pass