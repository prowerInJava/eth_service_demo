# -*- coding: utf-8 -*-
# @Time: 2025/11/29 20:43
# @Author: JackyYin
# @Email: jackhuan@icloud.com
# @File: __init__.py.py

__all__ = ['UDFrame_Z_ADCU30_204']

class UDFrame_Z_ADCU30_204:
    msg_name = "EthernetSignal_Z_ADCU30_10ms"
    msg_id = 0x94
    msg_type = "Unicast"
    msg_tx_method = 'cyclic'
    msg_cycle = 0.01
    msg_length = 23
    tx_node = "Z"
    rx_node = "ADCU30"
    sig_group_dict = {
        'CrsCtrlOvrdn':["CrsCtrlOvrdnChk8","CrsCtrlOvrdnCntr4", "CrsCtrlOvrdnDataID4", "CrsCtrlOvrdnReq"],
        'LVPwrSplyErrSts':["LVPwrSplyErrStsChk8","LVPwrSplyErrStsCntr4","LVPwrSplyErrStsDataID4", "LVPwrSplyErrStsSts"],
        'VehLVSysUZCL':["VehLVSysUZCLVehLVSysUBkp","VehLVSysUZCLVehLVSysUMai"]
    }
    sig_group_dataid_dict = {'CrsCtrlOvrdn':0x8C2,"LVPwrSplyErrSts":0x7A4, "VehLVSysUZCL":None}

    class CrsCtrlOvrdnChk8:
        sig_name = "CrsCtrlOvrdnChk8"
        sig_start_bit = 40
        update_id_bit = None
        sig_length = 8
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 255
        sig_value_min = 0
        sig_byteorder = "Intel"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = None
        compute_method = None
        length = 8
        startbit = 40
        byte = 5
        mask = 0xFF
        unmask = 0xFFFFFFFFFFFFFF00
        shift = 0
        description = "Counter for CrsCtrlOvrdn"

    class CrsCtrlOvrdnCntr4:
        sig_name = "CrsCtrlOvrdnCntr4"
        sig_start_bit = 48
        update_id_bit = None
        sig_length = 4
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 15
        sig_value_min = 0
        sig_byteorder = "Intel"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = None
        compute_method = None
        length = 4
        startbit = 48
        byte = 6
        mask = 0x0F
        unmask = 0xFFFFFFFFFFFFFFF0
        shift = 0
        description = "Checksum for CrsCtrlOvrdn"

    class CrsCtrlOvrdnDataID4:
        sig_name = "CrsCtrlOvrdnDataID4"
        sig_start_bit = 52
        update_id_bit = None
        sig_length = 4
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 15
        sig_value_min = 0
        sig_byteorder = "Intel"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = None
        compute_method = None
        length = 4
        startbit = 52
        byte = 6
        mask = 0xF0
        unmask = 0xFFFFFFFFFFFFFF0F
        shift = 4
        description = "Dataid4 for CrsCtrlOvrdn"

    class CrsCtrlOvrdnReq:
        sig_name = "CrsCtrlOvrdnReq"
        sig_start_bit = 56
        update_id_bit = None
        sig_length = 1
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 1
        sig_value_min = 0
        sig_byteorder = "Intel"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = "OnOff1"
        compute_method = None
        length = 1
        startbit = 56
        byte = 7
        mask = 0b00000001
        unmask = 0b11111110
        shift = 0
        description = "Override CC/ACC with accelerator pedal"

    class FltElecDcDc:
        sig_name = "FltElecDcDc"
        sig_start_bit = 36
        update_id_bit = 35
        sig_length = 1
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 1
        sig_value_min = 0
        sig_byteorder = "Motorola"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = "DevErrSts2"
        compute_method = None
        length = 1
        startbit = 36
        byte = 4
        mask = 0b00010000
        unmask = 0b11101111
        shift = 4
        description = "The fault of DC relevant tp temperature"

    class LVPwrSplyErrStsChk8:
        sig_name = "LVPwrSplyErrStsChk8"
        sig_start_bit = 0
        update_id_bit = None
        sig_length = 8
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 255
        sig_value_min = 0
        sig_byteorder = "Intel"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = ""
        compute_method = None
        length = 8
        startbit = 0
        byte = 0
        mask = 0xFF
        unmask = 0xFFFFFFFFFFFFFF00
        shift = 0
        description = "Check sum"

    class LVPwrSplyErrStsCntr4:
        sig_name = "LVPwrSplyErrStsCntr4"
        sig_start_bit = 8
        update_id_bit = None
        sig_length = 4
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 15
        sig_value_min = 0
        sig_byteorder = "Intel"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = ""
        compute_method = None
        length = 4
        startbit = 8
        byte = 1
        mask = 0x0F
        unmask = 0xFFFFFFFFFFFFFFF0
        shift = 0
        description = "Counter"

    class LVPwrSplyErrStsDataID4:
        sig_name = "LVPwrSplyErrStsDataID4"
        sig_start_bit = 12
        update_id_bit = None
        sig_length = 4
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 15
        sig_value_min = 0
        sig_byteorder = "Intel"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = ""
        compute_method = None
        length = 4
        startbit = 12
        byte = 1
        mask = 0xF0
        unmask = 0xFFFFFFFFFFFFFF0F
        shift = 4
        description = "Data id"

    class LVPwrSplyErrStsSts:
        sig_name = "LVPwrSplyErrStsSts"
        sig_start_bit = 16
        update_id_bit = None
        sig_length = 16
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 65535
        sig_value_min = 0
        sig_byteorder = "Intel"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = ""
        compute_method = None
        length = 16
        startbit = 16
        byte = 2
        mask = 0xFFFF
        unmask = 0xFFFFFFFFFFFF0000
        shift = 0
        description = "Low volt power supply error sts"

    class MsgReqForRtrctrRvsbDrvr:
        sig_name = "MsgReqForRtrctrRvsbDrvr"
        sig_start_bit = 33
        update_id_bit = 32
        sig_length = 1
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 1
        sig_value_min = 0
        sig_byteorder = "Motorola"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = "OnOff1"
        compute_method = None
        length = 1
        startbit = 33
        byte = 4
        mask = 0b00000010
        unmask = 0b11111101
        shift = 1
        description = "Request to show message in DIM indicating Drvr"

    class MsgReqForRtrctrRvsbPass:
        sig_name = "MsgReqForRtrctrRvsbPass"
        sig_start_bit = 123
        update_id_bit = 122
        sig_length = 1
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 1
        sig_value_min = 0
        sig_byteorder = "Motorola"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = "OnOff1"
        compute_method = None
        length = 1
        startbit = 123
        byte = 15
        mask = 0b10000000
        unmask = 0b01111111
        shift = 7
        description = "Request to show message in DIM indicating that is a fault with the RMP"

    class PrpsnADResvSigGrp:
        sig_name = "PrpsnADResvSigGrp"
        sig_start_bit = 87
        update_id_bit = 34
        sig_length = 16
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 65535
        sig_value_min = 0
        sig_byteorder = "Motorola"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = ""
        compute_method = None
        length = 16
        startbit = 87
        byte = 10
        mask = 0xFFFF
        unmask = 0xFFFFFFFFFFFF0000
        shift = 0
        description = "Reserved signal with ASM for AD function"

    class PrpsnVDResvSigGrp:
        sig_name = "PrpsnVDResvSigGrp"
        sig_start_bit = 71
        update_id_bit = 37
        sig_length = 16
        sig_value_factor = 1
        sig_value_offset = 0
        sig_value_max = 65535
        sig_value_min = 0
        sig_byteorder = "Motorola"
        sig_value_init = 0
        sig_value_type = "IDENTICAL"
        sig_value_table = ""
        compute_method = None
        length = 17
        startbit = 71
        byte = 8
        mask = 0xFFFF
        unmask = 0xFFFFFFFFFFFF0000
        shift = 0
        description = "Reserved signal with VDM for AD function"

    class VehLVSysUZCLVehLVSysUBkp:
        sig_name = "VehLVSysUZCLVehLVSysUBkp"
        sig_start_bit = 147
        update_id_bit = 163
        sig_length = 8
        sig_value_factor = 0.1
        sig_value_offset = 0.0
        sig_value_max = 25.0
        sig_value_min = 0
        sig_byteorder = "Motorola"
        sig_value_init = 0
        sig_value_type = "LINEAR"
        sig_value_table = ""
        compute_method = None
        length = 8
        startbit = 147
        byte = 18
        mask = 0xFF
        unmask = 0xFFFFFFFFFFFFFF00
        shift = 0
        description = "ZCL backup circuit voltage input"

    class VehLVSysUZCLVehLVSysUMai:
        sig_name = "VehLVSysUZCLVehLVSysUMai"
        sig_start_bit = 155
        update_id_bit = 163
        sig_length = 8
        sig_value_factor = 0.1
        sig_value_offset = 0.0
        sig_value_max = 25.0
        sig_value_min = 0
        sig_byteorder = "Motorola"
        sig_value_init = 0
        sig_value_type = "LINEAR"
        sig_value_table = ""
        compute_method = None
        length = 8
        startbit = 155
        byte = 19
        mask = 0xFF
        unmask = 0xFFFFFFFFFFFFFF00
        shift = 0
        description = "ZCL main circuit voltage input"
