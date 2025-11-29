# -*- coding: utf-8 -*-
# @Time: 2025/11/29 23:42
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: example_send.py

"""
example_send_afpacket.py

发送端示例（AF_PACKET + 4+4 header 格式）

功能：
- 使用 AFPacketTransport（基于 AF_PACKET 原始以太网套接字）发送报文
- 使用 Framer 将 payload 封装为 4 字节 ID + 4 字节 length + payload（默认 big-endian）
- 演示两种发送方式：
    1) 高层接口：使用 EthECUCommunicator，调用 set_signal(...) 后 comm.send() 自动打包信号、计算 E2E 并发送（会走 Framer）
    2) 低层原始发送：直接构造 23 字节 payload（或使用您提供的 sample payload），调用 framer.add_header(...) 然后 transport.send(...)

运行环境：
- Ubuntu / Linux，需要 root 权限或 CAP_NET_RAW（sudo python3 ...）
- 请修改 iface 和 dst_mac 为您环境的实际值
"""
import time
import binascii
import argparse

from transport_afpacket import AFPacketTransport
from framer import Framer
from eth_comm import EthECUCommunicator
from eth_fr import UDFrame_Z_ADCU30_204

def send_using_comm(iface, dst_mac, ethertype):
    # 创建 AF_PACKET transport
    transport = AFPacketTransport(iface=iface, dst_mac=dst_mac, ethertype=ethertype)
    # 使用 big-endian 的 4+4 header，匹配您 PCAP 的格式: 00000094 00000017 ...
    framer = Framer(mode="custom_4_4", id_endian="big", len_endian="big")

    # 将 framer 注入 communicator（send() 会自动 add_header）
    comm = EthECUCommunicator(UDFrame_Z_ADCU30_204, transport, framer=framer)

    # 示例：设置信号（使用信号名），然后发送多帧
    comm.set_signal('CrsCtrlOvrdnReq', 1)
    # 示例：设置 LVPwrSplyErrStsSts 为 0x1234（16 位信号）
    comm.set_signal('LVPwrSplyErrStsSts', 0x1234)

    print("开始通过 EthECUCommunicator 发送 5 帧（每帧会自动 e2e 处理并带 4+4 header）...")
    for i in range(5):
        comm.send()
        print(f"  已发送第 {i+1} 帧")
        time.sleep(0.2)

    transport.stop()
    print("发送完成，transport 已停止。")

def send_raw_sample(iface, dst_mac, ethertype, sample_hex=None):
    """
    直接发送用户提供（或示例）的 raw payload：
    - 若 sample_hex 提供，则把它当作完整 31 字节 frame hex（包含 4+4 header + 23 payload）发送（不再额外 add_header）
    - 若 sample_hex 未提供，则把 example payload（23 bytes）用 framer.add_header 封装再发送
    """
    transport = AFPacketTransport(iface=iface, dst_mac=dst_mac, ethertype=ethertype)
    framer = Framer(mode="custom_4_4", id_endian="big", len_endian="big")

    if sample_hex:
        frame_bytes = binascii.unhexlify(sample_hex)
        # 注意：这是完整 frame（含 4+4 header），直接通过 AF_PACKET 发送整个 frame（包含以太头在 AF_PACKET 层由 sock.send 构造）
        # 但 AFPacketTransport._build_frame 会在内部再加以太头；因此我们应直接 send payload-without-ethernet,
        # 如果 sample_hex 已经是 4+4+payload（没有以太头），则直接 transport.send(frame_bytes) 会把 frame_bytes 当作 payload，
        # transport 会把它封装成以太帧（在 payload 前再加以太类型等），这正是我们希望的行为（上行逻辑保持一致）。
        print("直接发送 PCAP 中观测到的完整 4+4+23 字节数据（不再额外 add_header）...")
        transport.send(frame_bytes)
        print("已发送 raw frame（4+4+23）")
    else:
        # 构造 23 字节的示例 payload（可替换为由 comm._pack_signals() 生成的 payload）
        # 这里用上面您提供的 PCAP 中的 payload 部分（去掉前 8 字节 header）作为示例：
        example_payload_hex = "0100c4e78601000004d20000000000000000000000"  # 23 bytes from your sample after header
        payload = binascii.unhexlify(example_payload_hex)
        framed = framer.add_header(payload, msg_id=getattr(UDFrame_Z_ADCU30_204, 'msg_id', 0x94))
        print("发送封装后的帧（framer.add_header -> 4+4+23）...")
        transport.send(framed)
        print("已发送 framed payload")

    transport.stop()

def main():
    parser = argparse.ArgumentParser(description="AF_PACKET 发送端示例（带 4+4 header 或 使用 EthECUCommunicator）")
    parser.add_argument('--iface', required=True, help='发送使用的网络接口，例如 eth0')
    parser.add_argument('--dst', required=True, help='目的 MAC 地址，例如 aa:bb:cc:dd:ee:ff')
    parser.add_argument('--ethertype', default="0x88B5", help='以太类型，十六进制，例如 0x88B5')
    parser.add_argument('--mode', choices=['comm', 'raw', 'raw_pcap_hex'], default='comm',
                        help='发送模式：comm（高层 signal 接口），raw（send sample payload via framer），raw_pcap_hex（直接发送完整 4+4+23 hex）')
    parser.add_argument('--sample_hex', help='当 mode=raw_pcap_hex 时，传入完整 frame 的 hex（例如您给的示例 hex）')
    args = parser.parse_args()

    ethertype = int(args.ethertype, 16)

    if args.mode == 'comm':
        send_using_comm(args.iface, args.dst, ethertype)
    elif args.mode == 'raw':
        send_raw_sample(args.iface, args.dst, ethertype, sample_hex=None)
    else:
        if not args.sample_hex:
            print("mode=raw_pcap_hex 需提供 --sample_hex 参数（完整 4+4+23 hex，例如您提供的示例）。")
            return
        # 将您给出的示例 hex 作为 sample_hex 直接发送
        send_raw_sample(args.iface, args.dst, ethertype, sample_hex=args.sample_hex)

if __name__ == '__main__':
    main()
"""
示例运行命令（以 root 运行）：
- 高层发送（使用 communicator、自动 e2e、带 4+4 header）：
    sudo python3 example_send_afpacket.py --iface eth0 --dst aa:bb:cc:dd:ee:ff --mode comm

- 低层发送（用 framer 封装示例 payload 并发送）：
    sudo python3 example_send_afpacket.py --iface eth0 --dst aa:bb:cc:dd:ee:ff --mode raw

- 直接把您抓到的完整 31 字节 frame hex 发出去（不再额外 add_header）：
    sudo python3 example_send_afpacket.py --iface eth0 --dst aa:bb:cc:dd:ee:ff --mode raw_pcap_hex --sample_hex 00000094000000170100c4e78601000004d20000000000000000000000

注意：
- 运行前请确保项目目录中存在 transport_afpacket.py、framer.py、eth_comm.py、frames.py、e2e.py、bitops.py 等模块（我此前给出的实现）。
- 请根据实际网卡名和目标 MAC 调整命令参数，并以 root 权限运行。
"""