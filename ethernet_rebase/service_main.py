# -*- coding: utf-8 -*-
# @Time: 2025/12/6 01:41
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: service_main.py
import time

from base_udp_service import BaseUDPFrameService
from __init__ import UDFrame_Z_204
from .eth_udp.eth_comm import EthECUCommunicator
from .eth_udp.transport_udp import UDPTransport


class ZCL_CSCADCU30_204_SERVICE(BaseUDPFrameService):
    def __init__(self, **kwargs):
        super().__init__(frame_cls=UDFrame_Z_204, **kwargs)


# 如果想在某个服务中启用接收功能（比如回环测试），可以在子类 __init__ 中初始化 comm_recv 并注册 _internal_on_receive
class LoopbackZCLService(ZCL_CSCADCU30_204_SERVICE):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 额外初始化接收端（绑定到 remote 端口）
        self.transport_recv = UDPTransport(local_addr=self.udp_remote, remote_addr=self.udp_local)
        self.comm_recv = EthECUCommunicator(self.frame_cls, self.transport_recv, framer=self.framer)
        self.comm_recv.register_on_receive(self._internal_on_receive)

if __name__ == "__main__":
    svc = ZCL_CSCADCU30_204_SERVICE(
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

    for i in range(1000):
        framed = svc.send_and_return_bytes()
        print(f"→ 发往 {svc.transport_send.remote_addr} （{len(framed)} B）: {framed.hex()}")
        time.sleep(0.01)

    svc.stop()