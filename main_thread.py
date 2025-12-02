# -*- coding: utf-8 -*-
# @Time: 2025/11/30 10:30
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: main_thread.py
"""
双线程示例：一个线程发送信号到ADCU，另一个线程接收并验证响应信号。
"""
import threading
import time
from collections import deque
from transport_udp import UDPTransport
from eth_comm import EthECUCommunicator
from __init__ import UDFrame_Z_204
from framer import Framer

# 全局变量用于存储发送的信号值，供接收线程验证
sent_signals_history = deque(maxlen=10)  # 保存最近10次发送的信号
sent_signals_lock = threading.Lock()

# 配置模式：True表示使用本地模拟，False表示连接实际设备
USE_LOCAL_SIMULATION = True  # 改为False即可连接实际设备10.204.0.3


def sender_worker():
    """发送工作线程：定期发送信号到ADCU"""
    if USE_LOCAL_SIMULATION:
        # 本地模拟模式：发送到本地回环地址
        sender_transport = UDPTransport(
            local_addr=('127.0.0.1', 12000),
            remote_addr=('127.0.0.1', 12002)  # 模拟 10.204.0.3:42825
        )
    else:
        # 实际设备模式：发送到真实ADC设备
        sender_transport = UDPTransport(
            local_addr=('127.0.0.1', 12000),
            remote_addr=('10.204.0.3', 42825)  # 实际ADC设备地址
        )

    # 创建framer和communicator
    framer = Framer(mode="custom_4_4", id_endian="big", len_endian="big")
    sender_comm = EthECUCommunicator(UDFrame_Z_204, sender_transport, framer=framer)

    counter = 0
    try:
        while True:
            # 设置信号值
            crs_ctrl_value = counter % 2
            lv_pwr_value = 0x1234 + counter

            sender_comm.set_signal('CrsCtrlOvrdnReq', crs_ctrl_value)
            sender_comm.set_signal('LVPwrSplyErrStsSts', lv_pwr_value)

            # 保存发送的信号值用于后续验证
            with sent_signals_lock:
                sent_signals_history.append({
                    'CrsCtrlOvrdnReq': crs_ctrl_value,
                    'LVPwrSplyErrStsSts': lv_pwr_value,
                    'timestamp': time.time()
                })

            # 发送信号（内部自动处理E2E CRC计算）
            sender_comm.send()
            print(
                f"[Sender] Sent frame {counter}: CrsCtrlOvrdnReq={crs_ctrl_value}, LVPwrSplyErrStsSts=0x{lv_pwr_value:X}")

            counter += 1
            time.sleep(1)  # 每秒发送一次

    except KeyboardInterrupt:
        print("[Sender] Stopping sender thread...")
    finally:
        sender_transport.stop()


def receiver_worker():
    """接收工作线程：接收并验证来自ADCU的响应信号"""
    if USE_LOCAL_SIMULATION:
        # 本地模拟模式：从本地回环地址接收
        receiver_transport = UDPTransport(
            local_addr=('127.0.0.1', 12001),
            remote_addr=('127.0.0.1', 12003)  # 模拟 10.204.0.3:42824
        )
    else:
        # 实际设备模式：从真实ADC设备接收
        receiver_transport = UDPTransport(
            local_addr=('127.0.0.1', 12001),
            remote_addr=('10.204.0.3', 42824)  # 实际ADC设备地址
        )

    # 创建framer和communicator
    framer = Framer(mode="custom_4_4", id_endian="big", len_endian="big")
    receiver_comm = EthECUCommunicator(UDFrame_Z_204, receiver_transport, framer=framer)

    def on_receive(parsed_signals, raw):
        """接收回调函数"""
        print(f"[Receiver] Received payload: {raw.hex()}")
        print("[Receiver] Parsed signals:")
        for k in ('CrsCtrlOvrdnReq', 'LVPwrSplyErrStsSts', 'CrsCtrlOvrdnCntr4', 'CrsCtrlOvrdnChk8'):
            if k in parsed_signals:
                print(f"  {k} = {parsed_signals[k]}")

        # 验证接收到的信号是否与最近发送的信号一致
        verify_received_signals(parsed_signals)

    def verify_received_signals(parsed_signals):
        """验证接收到的信号"""
        with sent_signals_lock:
            if not sent_signals_history:
                print("[Receiver] No sent signals to compare with")
                return

            # 获取最近一次发送的信号
            last_sent = sent_signals_history[-1]

            # 比较关键信号值
            matches = True
            for signal_name in ['CrsCtrlOvrdnReq', 'LVPwrSplyErrStsSts']:
                if signal_name in parsed_signals and signal_name in last_sent:
                    if parsed_signals[signal_name] != last_sent[signal_name]:
                        print(
                            f"[Receiver] MISMATCH: {signal_name} sent={last_sent[signal_name]}, received={parsed_signals[signal_name]}")
                        matches = False
                else:
                    print(f"[Receiver] MISSING: {signal_name} in either sent or received data")
                    matches = False

            if matches:
                print("[Receiver] ✓ Signal verification PASSED")
            else:
                print("[Receiver] ✗ Signal verification FAILED")

    # 注册接收回调并启动接收
    receiver_comm.register_on_receive(on_receive)
    receiver_comm.start_receiving()

    try:
        # 保持线程运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[Receiver] Stopping receiver thread...")
    finally:
        receiver_transport.stop()


def mock_adcu_responder():
    """模拟ADCU设备响应（仅在本地模拟模式下使用）"""
    if not USE_LOCAL_SIMULATION:
        return

    # 监听模拟的ADCU接收端口
    adcu_rx_transport = UDPTransport(
        local_addr=('127.0.0.1', 12002),  # 模拟 10.204.0.3:42825
        remote_addr=('127.0.0.1', 12000)  # 回复到发送端
    )

    # 监听模拟的ADCU发送端口
    adcu_tx_transport = UDPTransport(
        local_addr=('127.0.0.1', 12003),  # 模拟 10.204.0.3:42824
        remote_addr=('127.0.0.1', 12001)  # 发送到接收端
    )

    def on_adcu_receive(data):
        """模拟ADCU处理接收到的数据并回应"""
        print(f"[Mock ADCU] Received: {data.hex()}")
        # 简单回传相同数据作为响应
        adcu_tx_transport.send(data)

    adcu_rx_transport.start_receiving(on_adcu_receive)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        adcu_rx_transport.stop()
        adcu_tx_transport.stop()


def main():
    """主函数：启动发送和接收线程"""
    if USE_LOCAL_SIMULATION:
        print("Starting dual-thread communication simulation (LOCAL MODE)...")
        print("Simulating: Sending to 127.0.0.1:12002, Receiving from 127.0.0.1:12003")
        # 启动模拟ADCU响应线程
        mock_thread = threading.Thread(target=mock_adcu_responder, name="MockADCUThread")
        mock_thread.daemon = True
        mock_thread.start()
    else:
        print("Starting dual-thread communication (REAL DEVICE MODE)...")
        print("Connecting to 10.204.0.3:42825 (send) and 10.204.0.3:42824 (receive)")

    # 创建并启动发送线程
    sender_thread = threading.Thread(target=sender_worker, name="SenderThread")
    sender_thread.daemon = True
    sender_thread.start()

    # 创建并启动接收线程
    receiver_thread = threading.Thread(target=receiver_worker, name="ReceiverThread")
    receiver_thread.daemon = True
    receiver_thread.start()

    try:
        # 保持主线程运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        # 等待线程结束
        sender_thread.join(timeout=2)
        receiver_thread.join(timeout=2)
        print("Shutdown complete.")


if __name__ == '__main__':
    main()
