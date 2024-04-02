# Standard includes
import grpc
import logging
import sys
import os
import time
from typing import List
from concurrent import futures

# Corekinect includes
from cipher import *

# App includes
from config import conf
from src.fw_files import *
from src.jlink.jlink import *

# Protocol includes
from protos.mtib_pi_stm.mtib_pi_stm_pb2_cipher import MtibPiStm
from protos.mtib_cs_pi.mtib_cs_pi_pb2_grpc import MtibCsPiServicer
from .types import * # All types are declared externally for readability of this file

class MtibCsPiServicerProvider(MtibCsPiServicer):
    def __init__(self):
        # Application daemon instance
        self.daemon:Cipher = None
        
        # STM32 (MTIB) fixture service
        self.stm32:MtibPiStm = None
        
        # General RPC info 
        self.rpc_info:CipherUnaryRpcUserInfo = CipherUnaryRpcUserInfo(
                destination_id=CIPHER_DESTINATION_ID_ANY,
                timeout_ms=20000
            )
        
        # App objects
        self.fw_file_manager = FwFileManager(config.conf.FW_FILE_STORAGE_DIR)
        self.jlink_manager = Jlink()

    # -------------------------------------------------------------------------------------------------
    #                                                                                 Instance Only API
    # -----------------------------------------------------------------------------------------------*/
    def SetInternalDaemon(self, daemon:Cipher):
        self.daemon:Cipher = daemon
        self.stm32 = MtibPiStm(self.daemon)

    # -------------------------------------------------------------------------------------------------
    #                                                                                       HealthCheck
    # -----------------------------------------------------------------------------------------------*/
    def HealthCheck(self, request, context):
        return HealthCheckResponse(ok=True)

    # -------------------------------------------------------------------------------------------------
    #                                                                                              Gpio
    # -----------------------------------------------------------------------------------------------*/
    def GpioConfig(self, request:GpioConfigRequest, context):
        rpc_response:GpioConfigResponse = GpioConfigResponse()
            
        # Create a request for the zephyr app
        stm_request:GpioConfigurePinRequest = GpioConfigurePinRequest()
        stm_request.pin_number = request.gpio
        stm_request.direction = request.type
        stm_request.resistor = request.resistor

        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.GpioConfigurePinRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            
            logging.info(f"RPC GpioConfig executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response

    def GpioWrite(self, request:GpioWriteRequest, context):
        rpc_response:GpioWriteResponse = GpioWriteResponse()
            
        # Create a request for the zephyr app
        stm_request:GpioSetPinRequest = GpioSetPinRequest()
        stm_request.pin_number = request.gpio
        stm_request.value = request.state

        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.GpioSetPinRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            
            logging.info(f"RPC GpioWrite executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response

    def GpioRead(self, request:GpioReadRequest, context):
        rpc_response:GpioReadResponse = GpioReadResponse()
            
        # Create a request for the zephyr app
        stm_request:GpioReadPinRequest = GpioReadPinRequest()
        stm_request.pin_number = request.gpio

        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.GpioReadPinRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            else:
                rpc_response.state = stm_response.value
            
            logging.info(f"RPC GpioRead executed successfully in {duration_ms:.3f} ms")

        return rpc_response
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                               Adc
    # -----------------------------------------------------------------------------------------------*/
    def AdcRead(self, request, context):
        rpc_response:AdcReadResponse = AdcReadResponse()
            
        # Create a request for the zephyr app
        stm_request:AdcReadChannelRequest = AdcReadChannelRequest()
        stm_request.channel_number = request.channel
        stm_request.delay_ms = request.delayMs

        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.AdcReadChannelRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.errorf
            else:
                rpc_response.voltage = stm_response.voltage
            
            logging.info(f"RPC AdcRead executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response
    
    def AdcReadAll(self, request, context):
        logging.debug("Starting AdcReadAll request with delayMs: %s", request.delayMs)

        # Prepare the request for the STM32 device
        stm_request = AdcReadAllChannelsRequest()
        stm_request.delay_ms = request.delayMs

        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.AdcReadAllChannelsRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        logging.debug("STM32 AdcReadAllChannelsRpc executed in %.3f ms", duration_ms)

        # Prepare the gRPC response
        rpc_response = AdcReadAllResponse()

        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            logging.debug("Processing STM32 response")
            if stm_response.success:
                rpc_response.success = True
                # Explicitly copy the voltage values
                for voltage in stm_response.voltage:
                    rpc_response.voltage.append(voltage)
                    logging.info(voltage)
                logging.info(f"RPC AdcReadAll executed successfully in {duration_ms:.3f} ms")
            else:
                logging.error("STM32 response indicated failure: %s", stm_response.error)
                rpc_response.success = False
                rpc_response.error = stm_response.error

        return rpc_response
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                    Firmware Files
    # -----------------------------------------------------------------------------------------------*/
    def ListFwFiles(self, request, context):
        # Fetch the list of FileInfo objects
        filesInfo: List[FileInfo] = self.fw_file_manager.list_files()

        # Prepare the ListFwFilesResponse message
        response = ListFwFilesResponse()
        for fileInfo in filesInfo:
            file = FwFileInfo(
                name=fileInfo.name,
                size_kb=fileInfo.size_kb,  
                sha256_digest=fileInfo.sha256_digest 
            )
            response.files.append(file)  # Append the FwFileInfo object to the response list

        return response
    
    def UploadFwFile(self, stream, context):
        filename = None
        content = bytearray()
        
        # Assemble the file from the stream
        for chunk in stream:
            if filename is None:
                filename = chunk.filename
            content.extend(chunk.content)
        
        if not filename:
            # Instead of raising an exception, set the gRPC context to reflect the error
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Filename is missing")
            return UploadFwFileResponse(success=False, error="Filename is missing")
        
        try:
            # Attempt to save the file
            success, error, sha256_digest = self.fw_file_manager.save_file(filename, content)
            
            if success:
                return UploadFwFileResponse(success=True, sha256_digest=sha256_digest)
            else:
                context.set_code(grpc.StatusCode.ALREADY_EXISTS)
                context.set_details(error)
                return UploadFwFileResponse(success=False, error=error)
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return UploadFwFileResponse(success=False, error=str(e))
    
    def DeleteFwFile(self, request, context):
        status, error = self.fw_file_manager.delete_file(request.filename)
        return DeleteFwFileResponse(success=status,error=error)
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                             JLink
    # -----------------------------------------------------------------------------------------------*/
    def FlashHexFile(self, request, context):
        jlink = self.jlink_manager
        try:
            success = False
            if request.isModemFw:
                success, error = jlink.program_modem(request.device, request.fileName)
            else:
                success, error = jlink.program_app(request.device, request.fileName)
                
            return FlashHexFileResponse(success=success, error=error, timeMs=0)
        except Exception as e:
            return FlashHexFileResponse(success=False, error=str(e), timeMs=0)
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                         DUT Power
    # -----------------------------------------------------------------------------------------------*/
    def DutPowerEnable(self, request:DutPowerEnableRequest, context):
        rpc_response: DutPowerEnableResponse = DutPowerEnableResponse()
            
        # Create a request
        stm_request:DutEnablePowerRequest = DutEnablePowerRequest()
        stm_request.enable = request.enable

        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.DutEnablePowerRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            
            logging.info(f"RPC DutPowerEnable executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response
    
    def DutChargePowerEnable(self, request:DutPowerEnableRequest, context):
        rpc_response: DutPowerEnableResponse = DutPowerEnableResponse()
            
        # Create a request
        stm_request:DutEnableChargerRequest = DutEnableChargerRequest()
        stm_request.enable = request.enable

        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.DutEnableChargerRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            
            logging.info(f"RPC DutChargePowerEnable executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response
    
    def DutVoltageSet(self, request:DutVoltageSetRequest, context):
        rpc_response: DutVoltageSetResponse = DutVoltageSetResponse()
            
        # Create a request
        stm_request:DutSetOutputVoltageRequest = DutSetOutputVoltageRequest()
        stm_request.voltage_mv = int(round(request.voltage * 1000)) # Convert from V to mV

        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.DutSetOutputVoltageRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            
            logging.info(f"RPC DutVoltageSet executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response
    
    def DutCurrentRead(self, request:DutCurrentReadRequest, context):
        rpc_response: DutCurrentReadResponse = DutCurrentReadResponse()
            
        # Create a request
        stm_request:Ina219ReadCurrentRequest = Ina219ReadCurrentRequest()

        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.Ina219ReadCurrentRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            else:
                rpc_response.current_ma = stm_response.current_value_ma
            
            logging.info(f"RPC DutCurrentRead executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response
    
    def DutVoltageRead(self, request:DutVoltageReadRequest, context):
        rpc_response: DutVoltageReadResponse = DutVoltageReadResponse()
            
        # Create a request
        stm_request:Ina219ReadVoltageRequest = Ina219ReadVoltageRequest()

        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.Ina219ReadVoltageRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            else:
                rpc_response.voltage_mv = stm_response.voltage_value_mv
            
            logging.info(f"RPC DutVoltageRead executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response
    
    def DutPowerRead(self, request:DutPowerReadRequest, context):
        rpc_response: DutPowerReadResponse = DutPowerReadResponse()
            
        # Create a request
        stm_request:Ina219ReadPowerRequest = Ina219ReadPowerRequest()

        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.Ina219ReadPowerRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            else:
                rpc_response.power_mw = stm_response.power_value_mw
            
            logging.info(f"RPC DutPowerRead executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response
    
    # -------------------------------------------------------------------------------------------------
    #                                                                                           Sensors
    # -----------------------------------------------------------------------------------------------*/
    def AltimeterRead(self, request: AltimeterReadRequest, context):
        rpc_response: AltimeterReadResponse = AltimeterReadResponse()
            
        # Create a request
        stm_request: Bmp390ReadValuesRequest = Bmp390ReadValuesRequest()
        
        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.Bmp390ReadValuesRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            else:
                rpc_response.temperature_f = stm_response.temperature_f
                rpc_response.pressure_hg = stm_response.pressure_hg
                rpc_response.altitude_ft = stm_response.altitude_ft
            
            logging.info(f"RPC AltimeterRead executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response
    
    def AccelRead(self, request:AccelReadRequest, context):
        rpc_response: AccelReadResponse = AccelReadResponse()
            
        # Create a request
        stm_request: Lis2de12ReadValuesRequest = Lis2de12ReadValuesRequest()
        
        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.Lis2de12ReadValuesRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            else:
                rpc_response.x = stm_response.x_value
                rpc_response.y = stm_response.y_value
                rpc_response.z = stm_response.z_value
            
            logging.info(f"RPC AccelRead executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response

    def AccelReadMaxForce(self, request:AccelReadMaxRequest, context):
        rpc_response: AccelReadMaxResponse = AccelReadMaxResponse()
            
        # Create a request
        stm_request: Lis2de12ReadMaxForceRequest = Lis2de12ReadMaxForceRequest()
        
        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.Lis2de12ReadMaxForceRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            else:
                rpc_response.max = stm_response.max_force
            
            logging.info(f"RPC AccelReadMaxForce executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response

    def EepromRead(self, request:EepromReadRequest, context):
        rpc_response: EepromReadResponse = EepromReadResponse()
            
        # Create a request
        stm_request: EepromReadFromMemRequest = EepromReadFromMemRequest()
        stm_request.address = request.address
        stm_request.len = request.len
        
        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.EepromReadFromMemRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            else:
                rpc_response.data = stm_response.data
            
            logging.info(f"RPC EepromRead executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response

    def EepromWrite(self, request:EepromWriteRequest, context):
        rpc_response: EepromWriteResponse = EepromWriteResponse()
            
        # Create a request
        stm_request:EepromWriteToMemRequest = EepromWriteToMemRequest()
        stm_request.address = request.address
        stm_request.data = request.buffer
        # stm_request.len = request.len
        
        # Execute the request
        start_time = time.time()
        stm_response, err = self.stm32.EepromWriteToMemRpc(self.rpc_info, stm_request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Parse the response
        if err is not CipherRpcErr.OK:
            rpc_response.success = False
            rpc_response.error = str(err)
        else:
            rpc_response.success = True
            
            if stm_response.success is not True:
                rpc_response.success = False
                rpc_response.error = stm_response.error
            
            logging.info(f"RPC EepromRead executed successfully in {duration_ms:.3f} ms")
            
        return rpc_response
    

    