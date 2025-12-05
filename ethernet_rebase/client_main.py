# -*- coding: utf-8 -*-
# @Time: 2025/12/6 01:44
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: client_main.py
import time

from base_udp_client import BaseUDPFrameClient
from __init__ import UDFrame_Z_204

class ZCL_CSCADCU30_204_CLIENT(BaseUDPFrameClient):
    def __init__(self, **kwargs):
        super().__init__(frame_cls=UDFrame_Z_204, **kwargs)



if __name__ == '__main__':
    svc = ZCL_CSCADCU30_204_CLIENT(
        udp_local=('127.0.0.1', 12000),
        udp_remote=('127.0.0.1', 12001),
        framer_mode='custom_4_4',
        id_endian='big',
        len_endian='big'
    )

    def cb_1(parsed, raw):
        print("收到信号回调, payload:", raw.hex())
        for k, v in parsed.items():
            print(f"  {k} = {v}")

    svc.register_receive_callback(cb_1)
    svc.start()
    try:
        time.sleep(10)  # 更优雅地等待
    finally:
        svc.stop()
    print("服务已停止")