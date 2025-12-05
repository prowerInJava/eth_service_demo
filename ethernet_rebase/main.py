# -*- coding: utf-8 -*-
# @Time: 2025/12/6 01:49
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: main.py

import time

# from .eth_udp_factory import EthService
# svc = EthService.asServer("UDFrame_Z_204", udp_local=('127.0.0.1', 12000), udp_remote=('127.0.0.1', 12001))
# svc.set_signal("CrsCtrlOvrdn_UB", 1)
# svc.set_signal('CrsCtrlOvrdnReq', 1)
# svc.set_signal("MsgReqForRtrctrRvsbDrvr", 1)
# svc.set_signal("PrpsnVDResvSigGrp", 128)
#
# for i in range(1000):
#     framed = svc.send_and_return_bytes()
#     print(f"→ 发往 {svc.transport_send.remote_addr} （{len(framed)} B）: {framed.hex()}")
#     time.sleep(0.01)
#
# svc.send_and_return_bytes()
# svc.stop()
#
# client = EthService.asClient("UDFrame_Z_204", udp_local=('127.0.0.1', 12001), udp_remote=('127.0.0.1', 12000))
#
# def cb_1(parsed, raw):
#     print("收到信号回调, payload:", raw.hex())
#     for k, v in parsed.items():
#         print(f"  {k} = {v}")
#
# client.register_receive_callback(cb_1)
# client.start()
# try:
#     time.sleep(10)
# except KeyboardInterrupt:
#     client.stop()

# main_test
import threading
from eth_udp_factory import EthService


def run_sender():
    print("[Sender] 启动发送服务...")
    svc = EthService.asServer(
        "UDFrame_Z_204",
        udp_local=('127.0.0.1', 12000),
        udp_remote=('127.0.0.1', 12001),
        framer_mode='custom_4_4',
        id_endian='big',
        len_endian='big'
    )
    svc.set_signal("CrsCtrlOvrdn_UB", 1)
    svc.set_signal('CrsCtrlOvrdnReq', 1)
    svc.set_signal("MsgReqForRtrctrRvsbDrvr", 1)
    svc.set_signal("PrpsnVDResvSigGrp", 128)

    try:
        for i in range(1000):
            framed = svc.send_and_return_bytes()
            print(f"[Sender] → {svc.transport_send.remote_addr} ({len(framed)} B): {framed.hex()}")
            time.sleep(0.01)
        # 最后发一次
        svc.send_and_return_bytes()
    except Exception as e:
        print(f"[Sender] 异常: {e}")
    finally:
        svc.stop()
        print("[Sender] 已停止")


def run_receiver():
    print("[Receiver] 启动接收客户端...")
    client = EthService.asClient(
        "UDFrame_Z_204",
        udp_local=('127.0.0.1', 12001),
        udp_remote=('127.0.0.1', 12000),
        framer_mode='custom_4_4',
        id_endian='big',
        len_endian='big'
    )

    def cb_1(parsed, raw):
        print(f"[Receiver] 收到信号回调, payload: {raw.hex()}")
        for k, v in parsed.items():
            print(f"  {k} = {v}")

    client.register_receive_callback(cb_1)
    client.start()
    try:
        # 接收 15 秒（比发送时间稍长）
        time.sleep(15)
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()
        print("[Receiver] 已停止")


if __name__ == '__main__':
    # 启动两个线程
    sender_thread = threading.Thread(target=run_sender, daemon=True)
    receiver_thread = threading.Thread(target=run_receiver, daemon=True)

    receiver_thread.start()  # 先启动接收，避免丢包
    time.sleep(0.1)          # 稍等确保接收端就绪
    sender_thread.start()

    # 等待 sender 完成（receiver 会自动超时退出）
    sender_thread.join()
    receiver_thread.join(timeout=1)  # 确保 receiver 也退出

    print("✅ 测试完成")