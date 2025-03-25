class GpioConfig:
    def __init__(
        self,
        pin_hard_reset: int = 0,
        pin_chrg_detect: int = 1,
        pin_uvp_n: int = 2,
        pin_3v3_psm: int = 3,
    ):
        self.pin_hard_reset: int = pin_hard_reset
        self.pin_chrg_detect: int = pin_chrg_detect
        self.pin_uvp_n: int = pin_uvp_n
        self.pin_3v3_psm: int = pin_3v3_psm


class AdcConfig:
    def __init__(
        self,
        read_delay_ms: int = 100,
        ch_3v3: int = 0,
        ch_vin: int = 1,
        ch_vbckp: int = 2,
        ch_vbat: int = 3,
        ch_3v3_gps: int = 4,
    ):
        self.read_delay_ms: int = read_delay_ms
        self.ch_3v3: int = ch_3v3
        self.ch_vin: int = ch_vin
        self.ch_vbckp: int = ch_vbckp
        self.ch_vbat: int = ch_vbat
        self.ch_3v3_gps: int = ch_3v3_gps


class NetConfig:
    def __init__(
        self,
        addr: str = "127.0.0.1",
        port: int = 50051,
    ):
        self.addr: str = addr
        self.port: int = port
