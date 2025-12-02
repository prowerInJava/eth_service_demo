# -*- coding: utf-8 -*-
# @Time: 2025/11/29 23:07
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: main.py
"""
示例：展示如何使用 EthECUCommunicator 设置信号、发送并接收报文。

示例使用 transport_udp.py 中的 UDPTransport 本地模拟发送/接收。
"""
import time

from transport_udp import UDPTransport
from eth_comm import EthECUCommunicator
from __init__ import UDFrame_Z_204
from framer import Framer

def on_receive(parsed_signals, raw):
    print("Received payload (parsed, payload only):", raw.hex())
    print("Parsed signals snapshot (sample):")
    for k in ('CrsCtrlOvrdnReq', 'CrsCtrlOvrdnCntr4', 'CrsCtrlOvrdnChk8'):
        if k in parsed_signals:
            print(f"  {k} = {parsed_signals[k]}")

def send_one_via_comm_and_print(comm: EthECUCommunicator, framer: Framer):
    """
    使用 comm 的打包 / e2e 逻辑构造 payload、由 framer 封装 4+4 header，
    打印并通过 transport 发送（不调用 comm.send()，以便我们能控制何时增加计数器并避免重复）。
    """
    # 手动打包并应用 e2e（与 comm.send() 内部相同，但我们不再让 comm.send() 再次操作）
    comm._pack_signals()
    comm._apply_e2e_for_groups()
    payload = bytes(comm.payload)
    framed = framer.add_header(payload, msg_id=getattr(comm.frame, 'msg_id', 0))
    print("Framed (4+4+payload) hex:", framed.hex())
    # 直接通过 transport 发送 framed bytes
    comm.transport.send(framed)

def main():
    # 本地 UDP 地址示例（用于本地回环测试）
    local = ('127.0.0.1', 12001)   # 接收方监听
    remote = ('127.0.0.1', 12000)  # 发送方发送到此地址

    # 创建两个传输互相回环以示范
    t_sender = UDPTransport(local_addr=remote, remote_addr=local)
    t_receiver = UDPTransport(local_addr=local, remote_addr=remote)

    # Framer 配置：根据您之前的示例，选择 little-endian（如果 pcap 是 big-endian，
    # 请改为 id_endian="big", len_endian="big"）
    framer = Framer(mode="custom_4_4", id_endian="big", len_endian="big")

    # 发送端使用 framer，这样发送的时候会在 payload 前附加 4+4 header
    comm = EthECUCommunicator(UDFrame_Z_204, t_sender, framer=framer)
    # 接收端也需要使用相同的 framer（用于 strip_header），否则接收到的数据会包含 header，解析会错位
    comm_receiver = EthECUCommunicator(UDFrame_Z_204, t_receiver, framer=framer)
    comm_receiver.register_on_receive(on_receive)
    comm_receiver.start_receiving()

    # 设置一些信号（用户接口）
    comm.set_signal('CrsCtrlOvrdnReq', 1)
    comm.set_signal('LVPwrSplyErrStsSts', 0x1234)

    # 发送多帧示例：使用自定义的 send_one_via_comm_and_print（避免重复内部计数器增量）
    for i in range(5):
        send_one_via_comm_and_print(comm, framer)
        print("Sent frame", i)
        time.sleep(0.2)
    # 保持接收端存活演示
    time.sleep(1.0)
    t_sender.stop()
    t_receiver.stop()

if __name__ == '__main__':
    main()  # 3145341200f62501000000000000000000000000000000
