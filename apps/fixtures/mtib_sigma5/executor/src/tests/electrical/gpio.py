# Protocol includes
from protos.cluster_runner.cluster_runner_pb2 import (
    AdcChannel, Gpio
)

# Power
TP8_BATT=0
TP47_5V_IN=0

# Adc
TP11_3V3=AdcChannel.ADC_CHANNEL_0
TP52_VIN=AdcChannel.ADC_CHANNEL_1
TP30_VBCKP=AdcChannel.ADC_CHANNEL_2
TP7_VBAT_MEAS=AdcChannel.ADC_CHANNEL_3
TP24_3V3_GPS=AdcChannel.ADC_CHANNEL_4

ADC_READ_DELAY_MS=100

# Gpio
TP50_HARD_RESET=Gpio.GPIO_0
TP49_CHRG_DET=Gpio.GPIO_1
TP12_UVP_N=Gpio.GPIO_2
TP1_3V3_PSM=Gpio.GPIO_3