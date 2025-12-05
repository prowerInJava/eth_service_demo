# -*- coding: utf-8 -*-
# @Time: 2025/12/6 01:47
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: eth_udp_factory.py

from .base_udp_service import BaseUDPFrameService
from .base_udp_client import BaseUDPFrameClient

class UDPFactory:
    @staticmethod
    def _get_frame_class(name: str):
        # 假设所有 Frame 类定义在 __init__.py 中
        import __init__ as frame_mod
        cls = getattr(frame_mod, name, None)
        if cls is None:
            raise ValueError(f"Frame class '{name}' not found in __init__")
        return cls

    @staticmethod
    def asServer(frame_name: str, **kwargs):
        """创建发送服务（Server）"""
        frame_cls = UDPFactory._get_frame_class(frame_name)
        return BaseUDPFrameService(frame_cls=frame_cls, **kwargs)

    @staticmethod
    def asClient(frame_name: str, **kwargs):
        """创建接收客户端（Client）"""
        frame_cls = UDPFactory._get_frame_class(frame_name)
        return BaseUDPFrameClient(frame_cls=frame_cls, **kwargs)

# 全局单例（可选）
EthService = UDPFactory()