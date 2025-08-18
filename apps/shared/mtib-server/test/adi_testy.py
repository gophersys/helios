# Copyright (C) 2021 Analog Devices, Inc.
#
# SPDX short identifier: ADIBSD

import adi

# Set up AD7689
ad7689 = adi.ad7689(uri="local:")
ad_channel = 0

ad7689.rx_enabled_channels = [ad_channel]
ad7689.rx_buffer_size = 100

raw = ad7689.channel[1].raw
# data = ad7689.rx()

print(raw)
