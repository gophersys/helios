# Standard libraryes
import hashlib
import os
import time

# 3rd party libraries
import grpc
import typer
from typing import Optional, Tuple, Literal
from rich import print as rprint
from rich.progress import Progress

# Protocol includes
from protos.mtib_cs_pi.mtib_cs_pi_pb2 import (
    Gpio, GpioType, GpioResistorConfig,
    GpioWriteRequest, GpioWriteResponse,
    GpioConfigRequest, GpioConfigResponse,
    GpioReadRequest, GpioReadResponse,
    AdcChannel, AdcReadRequest, AdcReadResponse,
    AdcReadAllRequest, AdcReadAllResponse, 
    AltimeterReadRequest, AltimeterReadResponse,
    JLinkInfo, ListJLinksRequest, ListJLinksResponse,
    FlashHexFileRequest, FlashHexFileResponse,
    ListFwFilesRequest, ListFwFilesResponse, FwFileInfo,
    UploadFwFileRequest, UploadFwFileResponse,
    DeleteFwFileRequest, DeleteFwFileResponse,
    DutPowerEnableRequest, DutPowerEnableResponse,
    DutVoltageSetRequest, DutVoltageSetResponse,
    DutCurrentReadRequest, DutCurrentReadResponse,
    DutVoltageReadRequest, DutVoltageReadResponse, 
    DutPowerReadRequest, DutPowerReadResponse,
    AccelReadRequest, AccelReadResponse,
    AccelReadMaxRequest, AccelReadMaxResponse,
    EepromReadRequest, EepromReadResponse,
    EepromWriteRequest, EepromWriteResponse
)

import protos.mtib_cs_pi.mtib_cs_pi_pb2 as mtib
import protos.mtib_cs_pi.mtib_cs_pi_pb2_grpc as mtib_grpc

app = typer.Typer()

# -------------------------------------------------------------------------------------------------
#                                                                                     Configuration
# -----------------------------------------------------------------------------------------------*/
SERVER_ADDRESS = 'control-plane:12345' 

def get_server_instance():
    """Create a gRPC client stub"""
    channel = grpc.insecure_channel(SERVER_ADDRESS)
    stub = mtib_grpc.MtibCsPiStub(channel)
    return stub

def rpc_error(err:str):
    rprint(f"[red]Unsuccesful Query!\n")
    rprint(f"[red]Error:[/red] {err}")

# This function parses the string to the corresponding Gpio enum value
def parse_gpio(value: str) -> int:
    try:
        return getattr(Gpio, value)
    except AttributeError:
        raise typer.BadParameter(f"Invalid GPIO: {value}")
    
# -------------------------------------------------------------------------------------------------
#                                                                                              Gpio
# -----------------------------------------------------------------------------------------------*/
    
# python3 test/client.py gpio-config --gpio=GPIO_0 --type=GPIO_OUTPUT --resistor=GPIO_RESISTOR_PULL_UP
@app.command()
def gpio_config(gpio: str = typer.Option(..., help="GPIO pin to configure, e.g., GPIO_0"),
                type: str = typer.Option(..., help="GPIO type, e.g., GPIO_INPUT or GPIO_OUTPUT"),
                resistor: str = typer.Option(..., help="GPIO resistor config, e.g., GPIO_RESISTOR_PULL_UP or GPIO_RESISTOR_PULL_DOWN")):
    """Configures a specified GPIO pin."""
    try:
        # Parse enums directly from strings using the protobuf enum mappings
        gpio_enum = getattr(Gpio, gpio)
        type_enum = getattr(GpioType, type)
        resistor_enum = getattr(GpioResistorConfig, resistor)

        server = get_server_instance()

        # Execute RPC with provided channel and delay
        start_time = time.time()
        response = server.GpioConfig(GpioConfigRequest(gpio=gpio_enum, type=type_enum, resistor=resistor_enum))
        rprint(f"[green]Successful Query! ({(time.time() - start_time) * 1000}ms)[/green]")

        if response.success:
            rprint("[green]GPIO configuration successful![/green]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")

    except Exception as e:
        rpc_error(e)
        
# python3 test/client.py gpio-write --gpio=GPIO_0 --state=true
@app.command()
def gpio_write(gpio: str = typer.Option(..., help="GPIO pin to write to, e.g., GPIO_0"),
               state: str = typer.Option(..., help="State to set the GPIO pin, 'true' for high, 'false' for low")):
    """Writes a state to a specified GPIO pin."""
    try:
        # Convert the state string to a boolean
        if state.lower() not in ['true', 'false']:
            raise ValueError("State must be 'true' or 'false'")
        state_bool = state.lower() == 'true'

        gpio_enum = getattr(Gpio, gpio)

        server = get_server_instance()

        start_time = time.time()
        response = server.GpioWrite(GpioWriteRequest(gpio=gpio_enum, state=state_bool))
        rprint(f"[green]Successful Query! ({(time.time() - start_time) * 1000}ms)[/green]")

        if response.success:
            rprint("[green]GPIO write successful![/green]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")

    except Exception as e:
        rpc_error(e)

# python3 test/client.py gpio-read --gpio GPIO_0
@app.command()
def gpio_read(gpio: str = typer.Option(..., help="GPIO pin to read from, e.g., GPIO_0")):
    """Reads the state of a specified GPIO pin."""
    try:
        gpio_enum = getattr(Gpio, gpio)

        server = get_server_instance()
        response = server.GpioRead(GpioReadRequest(gpio=gpio_enum))

        if response.success:
            state = "high" if response.state else "low"
            rprint(f"[green]GPIO read successful: {state}[/green]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")

    except Exception as e:
        rpc_error(e)

# -------------------------------------------------------------------------------------------------
#                                                                                               Adc
# -----------------------------------------------------------------------------------------------*/

# python3 test/client.py adc-read --channel=ADC_CHANNEL_1 --delay-ms 50
@app.command()
def adc_read(channel: str = typer.Option(..., help="ADC channel to read from, e.g., ADC_CHANNEL_1"),
             delay_ms: int = typer.Option(0, help="Delay in milliseconds before reading the ADC")):
    """Reads voltage from a specified ADC channel with an optional delay."""
    try:
        # Parse enum directly from string using the protobuf enum mappings
        channel_enum = getattr(AdcChannel, channel)

        server = get_server_instance()
        
        # Execute RPC with provided channel and delay
        start_time = time.time()
        response = server.AdcRead(AdcReadRequest(channel=channel_enum, delayMs=delay_ms))
        duration_ms = (time.time() - start_time) * 1000

        if response.success:
            rprint(f"[green]Successful Query! ({duration_ms}ms)[/green]")
            rprint(f"Voltage: [blue]{response.voltage} V[/blue]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")

    except Exception as e:
        rpc_error(e)

# python3 test/client.py adc-read-all --delay-ms 100
@app.command()
def adc_read_all(delay_ms: int = typer.Option(0, help="Delay in milliseconds before reading all ADC channels")):
    """Fetches and prints voltages from all ADC channels with an optional delay."""
    try:
        server = get_server_instance()
        # Execute RPC
        start_time = time.time()
        response = server.AdcReadAll(AdcReadAllRequest(delayMs=delay_ms))
        duration_ms = (time.time() - start_time) * 1000

        if response.success:
            rprint(f"[green]Successful Query! ({duration_ms:.2f}ms)[/green]")
            # Check if there are voltages to print
            if response.voltage:
                for idx, voltage in enumerate(response.voltage, start=1):
                    rprint(f"Voltage on channel {idx}: [blue]{voltage} V[/blue]")
            else:
                rprint("[yellow]No voltages returned by the server.[/yellow]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")

    except Exception as e:
        rpc_error(e)

# -------------------------------------------------------------------------------------------------
#                                                                                    Firmware Files
# -----------------------------------------------------------------------------------------------*/
        
# python3 test/client.py list-fw-files
@app.command()
def list_fw_files():
    """Lists firmware files."""
    try:
        server = get_server_instance()
        
        # Execute RPC
        start_time = time.time()
        response:ListFwFilesResponse = server.ListFwFiles(mtib.ListFwFilesRequest())
        duration_ms = (time.time() - start_time) * 1000

        rprint(f"[green]Succesful Query! ({duration_ms})ms\n")
        
        # Print all the file info to the terminal
        if len(response.files) > 0:
            for file in response.files:
                rprint(f"Filename: [green]{file.name}[/green], size: [blue]{file.size_kb} Kb[/blue], SHA256: {file.sha256_digest}")
        else:
            rprint(f"No files found in server")

    except Exception as e:
        rpc_error(e)

# python3 test/client.py upload-fw-file test/zephyr.hex
@app.command()
def upload_fw_file(file_path: str):
    """Uploads a firmware file with progress tracking and exception handling."""
    try:
        server = get_server_instance()
        
        # Read the file
        with open(file_path, 'rb') as f:
            content = f.read()
        
        total_size = len(content)
        chunk_size = 1024  # Define chunk size
        num_chunks = total_size // chunk_size + (1 if total_size % chunk_size else 0)
        
        # Generate requests with progress bar
        def generate_requests():
            with Progress() as progress:
                task = progress.add_task("[cyan]Uploading...", total=num_chunks)
                for i in range(0, total_size, chunk_size):
                    yield mtib.UploadFwFileRequest(filename=os.path.basename(file_path), content=content[i:i+chunk_size])
                    progress.update(task, advance=1)
        
        # Execute RPC with timing
        start_time = time.time()
        response = server.UploadFwFile(generate_requests())
        duration_ms = (time.time() - start_time) * 1000
        
        if response.success:
            rprint(f"[green]Upload successful! ({duration_ms} ms)[/green]")
            rprint(f"Server-side SHA-256 Digest: {response.sha256_digest}")
        else:
            rprint(f"[red]Upload failed:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

# python3 test/client.py delete-fw-file zephyr.hex
@app.command()
def delete_fw_file(filename: str):
    """Deletes a firmware file."""
    try:
        server = get_server_instance()

         # Execute RPC
        start_time = time.time()
        response = server.DeleteFwFile(mtib.DeleteFwFileRequest(filename=filename))
        duration_ms = (time.time() - start_time) * 1000

        rprint(f"[green]Succesful Query! ({duration_ms})ms\n")

        if response.success:
            rprint("[green]File deleted successfully![/green]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

# -------------------------------------------------------------------------------------------------
#                                                                                            J-Link
# -----------------------------------------------------------------------------------------------*/

def enable_power(server: mtib_grpc.MtibCsPiStub) -> bool:
    response:DutPowerEnableResponse = server.DutPowerEnable(DutPowerEnableRequest(enable=True))
    if not response.success:
        rprint(f"[red]DutChargePowerEnable Error: {response.error}:[/red]")
        return False    
    
    return True

def disable_power(server: mtib_grpc.MtibCsPiStub) -> bool:
    response:DutPowerEnableResponse = server.DutPowerEnable(DutPowerEnableRequest(enable=False))
    if not response.success:
        rprint(f"[red]DutPowerEnable Error: {response.error}:[/red]")
        return False    
    
    return True

def set_vbat(server:  mtib_grpc.MtibCsPiStub, voltage: float) -> bool:
    disable_power(server)

    # Set the power
    response:DutVoltageSetResponse = server.DutVoltageSet(DutVoltageSetRequest(voltage=voltage))
    if not response.success:
        rprint(f"[red]DutVoltageSet Error: {response.error}:[/red]")
        return False
    
    enable_power(server)  

    return True

# python3 test/client.py list-jlinks
@app.command()
def list_jlinks():
    """Lists all connected J-Link devices."""
    try:
        server = get_server_instance()

        # Execute RPC with timing
        start_time = time.time()
        response = server.ListJlinks(ListJLinksRequest())
        duration_ms = (time.time() - start_time) * 1000

        if response.success:
            rprint(f"[green]Successful Query! ({duration_ms:.2f}ms)[/green]")
            for jlink in response.jlink:
                rprint(f"Serial Number: {jlink.serialNumber}, USB Port: {jlink.usbPort}")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

# python3 test/client.py flash-hex-file 821009545
@app.command()
def flash_hex_file(filename: str, serial_number: str, is_modem_fw: Optional[bool] = typer.Option(False, help="Specify if the firmware is for the modem")):
    """Flashes a HEX file to a J-Link device."""

    try:
        server = get_server_instance()

        # Enable power
        set_vbat(server, 4.5)

        # Prepare the JLinkInfo and request
        jlink_info = JLinkInfo(serialNumber=serial_number, usbPort=0)  # Assuming usbPort is not used
        request = FlashHexFileRequest(fileName=filename, jlink=jlink_info, isModemFw=is_modem_fw)

        # Execute RPC with timing
        start_time = time.time()
        response = server.FlashHexFile(request)
        duration_ms = (time.time() - start_time) * 1000

        disable_power(server)

        if response.success:
            rprint(f"[green]Flash successful! ({duration_ms:.2f}ms)[/green]")
            rprint(f"Time Taken: {response.timeMs}ms")
        else:
            rprint(f"[red]Flash failed:[/red] {response.error}")
    except Exception as e:
        disable_power(server)
        rpc_error(e)

# -------------------------------------------------------------------------------------------------
#                                                                                               Dut
# -----------------------------------------------------------------------------------------------*/

# python3 test/client.py dut-power-enable --enable=true
@app.command()
def dut_power_enable(enable: str= typer.Option(..., help="Enable or disable the DUT power")):
    """Enables or disables DUT power."""
    try:
        enable_bool = enable.lower() == "true"  # Convert the string to a boolean
        server = get_server_instance()
        response = server.DutPowerEnable(DutPowerEnableRequest(enable=enable_bool))

        if response.success:
            rprint("[green]DUT power enable state updated successfully![/green]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

@app.command()
def dut_charge_power_enable(enable: str = typer.Option(..., help="Enable or disable the DUT charge power")):
    """Enables or disables DUT charge power."""
    try:
        enable_bool = enable.lower() == "true"  # Convert the string to a boolean
        server = get_server_instance()
        response = server.DutChargePowerEnable(DutPowerEnableRequest(enable=enable_bool))

        if response.success:
            rprint("[green]DUT charge power enable state updated successfully![/green]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

# python3 test/client.py dut-current-read
@app.command()
def dut_current_read():
    """Reads the current from the DUT."""
    try:
        server = get_server_instance()
        response = server.DutCurrentRead(DutCurrentReadRequest())

        if response.success:
            rprint(f"[green]DUT current read successfully: {response.current_ma} mA[/green]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

# python3 test/client.py dut-voltage-read
@app.command()
def dut_voltage_read():
    """Reads the voltage from the DUT."""
    try:
        server = get_server_instance()
        response = server.DutVoltageRead(DutVoltageReadRequest())

        if response.success:
            rprint(f"[green]DUT voltage read successfully: {response.voltage_mv} mV[/green]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

# python3 test/client.py dut-power-read
@app.command()
def dut_power_read():
    """Reads the power from the DUT."""
    try:
        server = get_server_instance()
        response = server.DutPowerRead(DutPowerReadRequest())

        if response.success:
            rprint(f"[green]DUT power read successfully: {response.power_mw} mW[/green]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

# -------------------------------------------------------------------------------------------------
#                                                                                           Sensors
# -----------------------------------------------------------------------------------------------*/
@app.command()
def altimeter_read():
    """Reads altitude, pressure, and temperature from the altimeter."""
    try:
        server = get_server_instance()
        response = server.AltimeterRead(AltimeterReadRequest())

        if response.success:
            rprint(f"[green]Altimeter read successful![/green]")
            rprint(f"Temperature: {response.temperature_f} °F, Pressure: {response.pressure_hg} Hg, Altitude: {response.altitude_ft} ft")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

@app.command()
def accel_read():
    """Reads acceleration in the X, Y, and Z directions."""
    try:
        server = get_server_instance()
        response = server.AccelRead(AccelReadRequest())

        if response.success:
            rprint(f"[green]Acceleration read successful![/green]")
            rprint(f"X: {response.x} g, Y: {response.y} g, Z: {response.z} g")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

@app.command()
def accel_read_max_force():
    """Reads the maximum force from the accelerometer."""
    try:
        server = get_server_instance()
        response = server.AccelReadMaxForce(AccelReadMaxRequest())

        if response.success:
            rprint(f"[green]Maximum acceleration force read successful![/green]")
            rprint(f"Max Force: {response.max} g")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

@app.command()
def eeprom_read(address: int, len: int):
    """Reads data from the EEPROM."""
    try:
        server = get_server_instance()
        # Assuming buffer is not used in request for reading
        response = server.EepromRead(EepromReadRequest(address=address, len=len))

        if response.success:
            rprint(f"[green]EEPROM read successful![/green], data = {response.data}")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

@app.command()
def eeprom_write(address: int, data: str):
    """Writes data to the EEPROM."""
    try:
        server = get_server_instance()
        # Convert string data to bytes. Assuming data is hex encoded
        # Check if the data starts with '0x', indicating a hex string
        if data.startswith("0x"):
            # Remove the '0x' prefix and convert the remaining hex string to bytes
            data_bytes = bytes.fromhex(data[2:])
        else:
            # Treat the data as a plain string and convert to bytes
            data_bytes = data.encode('utf-8')
            
        response = server.EepromWrite(EepromWriteRequest(buffer=data_bytes, address=address, len=len(data_bytes)))

        if response.success:
            rprint("[green]EEPROM write successful![/green]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)

if __name__ == "__main__":
    app()
