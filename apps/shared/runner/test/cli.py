# Standard libraryes
import binascii
import hashlib
import logging
import os
import re
import struct
import threading
import time
import zlib
from queue import Queue
from typing import Literal, Optional, Tuple

import click

# 3rd party libraries
import grpc
import protos.mtib_runner.mtib_runner_pb2 as mtib
import protos.mtib_runner.mtib_runner_pb2_grpc as mtib_grpc
import typer

# Protocol includes
from protos.mtib_runner.mtib_runner_pb2 import (
    AccelReadMaxRequest,
    AccelReadMaxResponse,
    AccelReadRequest,
    AccelReadResponse,
    AdcChannel,
    AdcReadAllRequest,
    AdcReadAllResponse,
    AdcReadRequest,
    AdcReadResponse,
    AltimeterReadRequest,
    AltimeterReadResponse,
    DeleteFwFileRequest,
    DeleteFwFileResponse,
    DeviceType,
    DutCurrentReadRequest,
    DutCurrentReadResponse,
    DutPowerEnableRequest,
    DutPowerEnableResponse,
    DutPowerReadRequest,
    DutPowerReadResponse,
    DutVoltageReadRequest,
    DutVoltageReadResponse,
    DutVoltageSetRequest,
    DutVoltageSetResponse,
    EepromReadRequest,
    EepromReadResponse,
    EepromWriteRequest,
    EepromWriteResponse,
    FlashHexFileRequest,
    FlashHexFileResponse,
    FwFileInfo,
    Gpio,
    GpioConfigRequest,
    GpioConfigResponse,
    GpioReadRequest,
    GpioReadResponse,
    GpioResistorConfig,
    GpioType,
    GpioWriteRequest,
    GpioWriteResponse,
    ListFwFilesRequest,
    ListFwFilesResponse,
    UartStreamRequest,
    UploadFwFileRequest,
    UploadFwFileResponse,
)
from rich import print as rprint
from rich.console import Console
from rich.progress import Progress

app = typer.Typer()

# -------------------------------------------------------------------------------------------------
#                                                                                     Configuration
# -----------------------------------------------------------------------------------------------*/
SERVER_ADDRESS = "slot-6:50051"


def get_server_instance():
    """Create a gRPC client stub"""
    channel = grpc.insecure_channel(SERVER_ADDRESS)
    stub = mtib_grpc.MtibRunnerStub(channel)
    return stub


def rpc_error(err: str):
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
def gpio_config(
    gpio: str = typer.Option(..., help="GPIO pin to configure, e.g., GPIO_0"),
    type: str = typer.Option(..., help="GPIO type, e.g., GPIO_INPUT or GPIO_OUTPUT"),
    resistor: str = typer.Option(
        ..., help="GPIO resistor config, e.g., GPIO_RESISTOR_PULL_UP or GPIO_RESISTOR_PULL_DOWN"
    ),
):
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
def gpio_write(
    gpio: str = typer.Option(..., help="GPIO pin to write to, e.g., GPIO_0"),
    state: str = typer.Option(..., help="State to set the GPIO pin, 'true' for high, 'false' for low"),
):
    """Writes a state to a specified GPIO pin."""
    try:
        # Convert the state string to a boolean
        if state.lower() not in ["true", "false"]:
            raise ValueError("State must be 'true' or 'false'")
        state_bool = state.lower() == "true"

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
def adc_read(
    channel: str = typer.Option(..., help="ADC channel to read from, e.g., ADC_CHANNEL_1"),
    delay_ms: int = typer.Option(0, help="Delay in milliseconds before reading the ADC"),
):
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
        response: ListFwFilesResponse = server.ListFwFiles(mtib.ListFwFilesRequest())
        duration_ms = (time.time() - start_time) * 1000

        rprint(f"[green]Succesful Query! ({duration_ms})ms\n")

        # Print all the file info to the terminal
        if len(response.files) > 0:
            for file in response.files:
                rprint(
                    f"Filename: [green]{file.name}[/green], size: [blue]{file.sizeKb} Kb[/blue], SHA256: {file.sha256Digest}"
                )
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
        with open(file_path, "rb") as f:
            content = f.read()

        total_size = len(content)
        chunk_size = 1024  # Define chunk size
        num_chunks = total_size // chunk_size + (1 if total_size % chunk_size else 0)

        # Generate requests with progress bar
        def generate_requests():
            with Progress() as progress:
                task = progress.add_task("[cyan]Uploading...", total=num_chunks)
                for i in range(0, total_size, chunk_size):
                    yield mtib.UploadFwFileRequest(
                        filename=os.path.basename(file_path), content=content[i : i + chunk_size]
                    )
                    progress.update(task, advance=1)

        # Execute RPC with timing
        start_time = time.time()
        response = server.UploadFwFile(generate_requests())
        duration_ms = (time.time() - start_time) * 1000

        if response.success:
            rprint(f"[green]Upload successful! ({duration_ms} ms)[/green]")
            rprint(f"Server-side SHA-256 Digest: {response.sha256Digest}")
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


def enable_power(server: mtib_grpc.MtibRunnerStub) -> bool:
    response: DutPowerEnableResponse = server.DutPowerEnable(DutPowerEnableRequest(enable=True))
    if not response.success:
        rprint(f"[red]DutChargePowerEnable Error: {response.error}:[/red]")
        return False

    return True


def disable_power(server: mtib_grpc.MtibRunnerStub) -> bool:
    response: DutPowerEnableResponse = server.DutPowerEnable(DutPowerEnableRequest(enable=False))
    if not response.success:
        rprint(f"[red]DutPowerEnable Error: {response.error}:[/red]")
        return False

    return True


def set_vbat(server: mtib_grpc.MtibRunnerStub, voltage: float) -> bool:
    disable_power(server)

    # Set the power
    response: DutVoltageSetResponse = server.DutVoltageSet(DutVoltageSetRequest(voltage=voltage))
    if not response.success:
        rprint(f"[red]DutVoltageSet Error: {response.error}:[/red]")
        return False

    enable_power(server)

    return True


class DeviceTypeParamType(click.ParamType):
    name = "device_type"

    def convert(self, value, param, ctx):
        try:
            return DeviceType.Value(value)
        except ValueError:
            self.fail(f"{value} is not a valid DeviceType", param, ctx)

    def get_metavar(self, param):
        return "[DEVICE_NRF9160|DEVICE_NRF82840]"


DEVICE_TYPE = DeviceTypeParamType()


@app.command()
def flash_hex_file(
    filename: str,
    device: str = typer.Option(
        "DEVICE_NRF9160",
        help="Specify the device type",
        case_sensitive=False,
        show_choices=True,
        metavar="[DEVICE_NRF9160|DEVICE_NRF82840]",
        callback=lambda value: DeviceType.Value(value),
    ),
    is_modem_fw: Optional[bool] = typer.Option(False, help="Specify if the firmware is for the modem"),
):
    """Flashes a HEX file to a device."""

    try:
        server = get_server_instance()

        # Enable power
        set_vbat(server, 4.5)

        # Prepare the FlashHexFileRequest
        request = FlashHexFileRequest(fileName=filename, device=device, isModemFw=is_modem_fw)

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
def enable_power(server) -> bool:
    response: DutPowerEnableResponse = server.DutPowerEnable(DutPowerEnableRequest(enable=True))
    if not response.success:
        logging.error(f"DutChargePowerEnable Error: {response.error}")
        return False

    return True


def disable_power(server) -> bool:
    response: DutPowerEnableResponse = server.DutPowerEnable(DutPowerEnableRequest(enable=False))
    if not response.success:
        logging.error(f"DutChargePowerEnable Error: {response.error}")
        return False

    return True


def set_vbat(server, voltage: float) -> bool:
    disable_power(server)

    # Set the power
    response: DutVoltageSetResponse = server.DutVoltageSet(DutVoltageSetRequest(voltage=voltage))
    if not response.success:
        logging.error(f"DutVoltageSet Error: {response.error}")
        return False

    enable_power(server)

    return True


def set_hard_reset(server, state: bool) -> bool:
    TP50_HARD_RESET = Gpio.GPIO_0
    response: GpioWriteResponse = server.GpioWrite(GpioWriteRequest(gpio=TP50_HARD_RESET, state=state))
    if not response.success:
        logging.error(f"GpioWrite for {TP50_HARD_RESET} Error: {response.error}")
        return False

    return True


# -------------------------------------------------------------------------------------------------
#                                                                                               Dut
# -----------------------------------------------------------------------------------------------*/


# python3 test/client.py dut-power-enable --enable=true
@app.command()
def dut_power_enable(enable: str = typer.Option(..., help="Enable or disable the DUT power")):
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
            rprint(
                f"Temperature: {response.temperature_f} °F, Pressure: {response.pressure_hg} Hg, Altitude: {response.altitude_ft} ft"
            )
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
            data_bytes = data.encode("utf-8")

        response = server.EepromWrite(EepromWriteRequest(buffer=data_bytes, address=address, len=len(data_bytes)))

        if response.success:
            rprint("[green]EEPROM write successful![/green]")
        else:
            rprint(f"[red]Error:[/red] {response.error}")
    except Exception as e:
        rpc_error(e)


# -------------------------------------------------------------------------------------------------
#                                                                                              Uart
# -----------------------------------------------------------------------------------------------*/


# Function to format log entries
def format_log_entry(log_entry: str) -> str:
    # Remove the unnecessary escape sequences
    log_entry = re.sub(r"\[\d+m", "", log_entry)

    # Define log levels and corresponding colors
    log_levels = {"inf": "[green]", "wrn": "[yellow]", "err": "[red]", "dbg": "[white]"}

    # Format log entry based on its level
    for level, color in log_levels.items():
        if f"<{level}>" in log_entry or f" {level}>" in log_entry:
            log_entry = f"{color}{log_entry}[/]"
            break

    return log_entry


# Constants
NUM_SYNC_BYTES = 4
NUM_CRC_BYTES = 4
SYNC_BYTE1 = 0x12
SYNC_BYTE2 = 0xE4
CMD_ACK = 0x01
CMD_GET_IMEI_ICCID = 0x2B


def calculate_crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def parse_response(response):
    logging.error("Unpacking response")

    # Print the raw response for debugging
    rprint(f"Raw response: {response.hex()}")

    # Check if the response starts with the sync bytes
    if response[:2] != struct.pack("BB", SYNC_BYTE1, SYNC_BYTE2):
        rprint("[red]Sync bytes mismatch[/red]")
        return None

    # Extract the command identifier and print it
    command = response[2]
    rprint(f"Command identifier: {command}")

    if command != CMD_GET_IMEI_ICCID:
        rprint("[red]Unexpected command identifier[/red]")
        return None

    # Extract the message length
    mlength = struct.unpack(">H", response[3:5])[0]
    rprint(f"Message length: {mlength}")

    # Extract the payload and CRC
    payload = response[5 : 5 + mlength - NUM_CRC_BYTES]  # Subtract 4 bytes for the CRC
    crc_received = struct.unpack(">I", response[5 + mlength - NUM_CRC_BYTES : 5 + mlength])[0]

    # Calculate CRC for the received data (excluding the CRC itself and the sync bytes)
    crc_calculated = calculate_crc32(
        response[2 : 5 + mlength - NUM_CRC_BYTES]
    )  # Start from the third byte (excluding sync bytes)
    rprint(f"CRC received: {crc_received}, CRC calculated: {crc_calculated}")

    # Verify the CRC
    if crc_received != crc_calculated:
        rprint("[red]CRC mismatch[/red]")
        return None

    # Decode payload
    imei_iccid = payload.decode("ascii").strip("\x00")
    rprint(f"IMEI,ICCID string: {imei_iccid}")

    # Split the IMEI and ICCID from the payload
    imei_iccid_list = imei_iccid.split(",")
    if len(imei_iccid_list) < 2:
        rprint("[red]Failed to parse IMEI and ICCID[/red]")
        return None

    imei = imei_iccid_list[0]
    iccids = imei_iccid_list[1:]  # May contain one or more ICCIDs

    rprint(f"IMEI: {imei}")
    for idx, iccid in enumerate(iccids, start=1):
        rprint(f"ICCID {idx}: {iccid}")

    return imei, iccids


# def send_get_imei_iccid(request_queue):
#     """Function to send CMD_GET_IMEI_ICCID command."""
#     while True:
#         # Construct the message header
#         sync_bytes = struct.pack("BB", SYNC_BYTE1, SYNC_BYTE2)
#         command = struct.pack("B", CMD_GET_IMEI_ICCID)
#         message_length = struct.pack(">H", 0)  # MLength is 0 for this request

#         # Calculate CRC32
#         crc_value = calculate_crc32(command + message_length)
#         crc_bytes = struct.pack(">I", crc_value)

#         # Combine the header and CRC
#         payload = sync_bytes + command + message_length + crc_bytes

#         # Print the payload for verification
#         print(f"Payload: {payload.hex()}")  # Print as hex for readability
#         print(f"Payload length: {len(payload)}")  # Print length for verification

#         # Send the payload
#         request = UartStreamRequest(data=payload)
#         request_queue.put(request)
#         time.sleep(1)  # Send data every 1 second


@app.command()
def nrf9160_uart():
    """Receives data from the NRF9160 UART stream."""
    try:
        server = get_server_instance()
        request_queue = Queue()
        request_iterator = iter(request_queue.get, None)  # Create an iterator from the queue

        # Start a thread to send dummy data periodically
        # threading.Thread(target=send_get_imei_iccid, args=(request_queue,), daemon=True).start()

        buffer = b""

        for response in server.nrf9160UartStream(request_iterator):
            try:
                data = response.data
                buffer += data

                while len(buffer) > 0:
                    if buffer.startswith(struct.pack("BB", SYNC_BYTE1, SYNC_BYTE2)):
                        # Expected response
                        length = struct.unpack(">H", buffer[3:5])[0]
                        total_length = 2 + 1 + 2 + length + 4

                        if len(buffer) >= total_length:
                            full_response = buffer[:total_length]
                            buffer = buffer[total_length:]
                            imei_iccid = parse_response(full_response)
                            if imei_iccid:
                                rprint(f"[purple]{imei_iccid}[/purple]")
                            else:
                                rprint("[red]Error parsing response[/red]")
                        else:
                            break
                    else:
                        # Process log entry
                        if b"\r\n" in buffer:
                            line, buffer = buffer.split(b"\r\n", 1)
                            cleaned_log = format_log_entry(line.decode("utf-8", "replace"))
                            rprint(cleaned_log)  # Uncomment this to print the actual logs
                        else:
                            break
            except Exception as e:
                rprint(f"[red]Error decoding data: {e}[/red]")

    except Exception as e:
        rprint(f"[red]RPC error: {e}[/red]")


@app.command()
def nrf52840_uart():
    """Receives data from the NRF52840 UART stream."""
    try:
        server = get_server_instance()
        request_queue = Queue()
        request_iterator = iter(request_queue.get, None)  # Create an iterator from the queue

        # Start a thread to send dummy data periodically
        # threading.Thread(target=send_dummy_data, args=(request_queue,), daemon=True).start()

        buffer = ""

        for response in server.nrf52840UartStream(request_iterator):
            try:
                data_str = response.data.decode("utf-8", "replace")
                buffer += data_str

                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    cleaned_log = format_log_entry(line)
                    rprint(cleaned_log)
            except Exception as e:
                rprint(f"[red]Error decoding data: {e}[/red]")

    except Exception as e:
        rpc_error(e)


@app.command()
def enable_battery_power():
    """Enable battery power by setting VBAT to 3.6V."""
    try:
        server = get_server_instance()

        if not set_vbat(server, 3.2):
            print("error setting vbat")

    except Exception as e:
        rpc_error(e)


@app.command()
def disable_battery_power():
    """Disable battery power by setting VBAT to 0V."""
    try:
        server = get_server_instance()

        if not set_vbat(server, 0.0):
            print("error setting vbat")

        disable_power(server)

    except Exception as e:
        rpc_error(e)


@app.command()
def reset():
    """Reset the device."""
    try:
        server = get_server_instance()

        if not set_hard_reset(server, False):
            print("could not set reset low")

        time.sleep(0.1)

        if not set_hard_reset(server, True):
            print("could not set reset high")

    except Exception as e:
        rpc_error(e)


if __name__ == "__main__":
    app()
