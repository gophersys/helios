from protos.mtib_cs_pi.mtib_cs_pi_pb2 import ( # Types for C# client to Orange Pi gRPC server
    # Gpio
    GpioConfigRequest, GpioConfigResponse,
    GpioWriteRequest, GpioWriteResponse,
    GpioReadRequest, GpioReadResponse,

    # Adc
    AdcReadRequest, AdcReadResponse,
    AdcReadAllRequest, AdcReadAllResponse,

    # Power
    DutPowerEnableRequest, DutPowerEnableResponse,
    DutVoltageSetRequest, DutVoltageSetResponse,

    # Power Monitor
    DutCurrentReadRequest, DutCurrentReadResponse,
    DutVoltageReadRequest, DutVoltageReadResponse,
    DutPowerReadRequest, DutPowerReadResponse,

    # Sensors
    AltimeterReadRequest, AltimeterReadResponse,
    AccelReadRequest, AccelReadResponse, 
    AccelReadMaxRequest, AccelReadMaxResponse, 
    EepromReadRequest, EepromReadResponse,
    EepromWriteRequest, EepromWriteResponse,

    # Firmware Files
    FwFileInfo, ListFwFilesRequest, ListFwFilesResponse,
    UploadFwFileRequest, UploadFwFileResponse,
    DeleteFwFileRequest, DeleteFwFileResponse, 

    # J-Link
    JLinkInfo, ListJLinksRequest, ListJLinksResponse,
    FlashHexFileRequest, FlashHexFileResponse, 
)

from protos.mtib_pi_stm.mtib_pi_stm_pb2_cipher import ( # Types for Orange Pi to STM32
    # Gpio
    GpioDirection, GpioValue,
    GpioConfigurePinRequest, GpioConfigurePinResponse,
    GpioSetPinRequest, GpioSetPinResponse,
    GpioReadPinRequest, GpioReadPinResponse,

    # Adc
    AdcReadChannelRequest, AdcReadChannelResponse,
    AdcReadAllChannelsRequest, AdcReadAllChannelsResponse,

    # Power
    DutEnablePowerRequest, DutEnablePowerResponse,
    DutEnableChargerRequest, DutEnableChargerResponse,
    DutSetOutputVoltageRequest, DutSetOutputVoltageResponse,

    # Power Monitor
    Ina219ReadCurrentRequest, Ina219ReadCurrentResponse,
    Ina219ReadVoltageRequest, Ina219ReadVoltageResponse,
    Ina219ReadPowerRequest, Ina219ReadPowerResponse,

    # Altimeter
    Bmp390ReadValuesRequest, Bmp390ReadValuesResponse,

    # Accelerometer
    Lis2de12ReadValuesRequest, Lis2de12ReadValuesResponse,
    Lis2de12ReadMaxForceRequest, Lis2de12ReadMaxForceResponse,

    # Memory
    EepromReadFromMemRequest, EepromReadFromMemResponse,
    EepromWriteToMemRequest, EepromWriteToMemResponse,

    # Uart
    UartMessageRequest, UartMessageResponse
)
