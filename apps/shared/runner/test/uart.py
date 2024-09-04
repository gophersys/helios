import os
import threading
import struct
from queue import Queue
from datetime import datetime
import re
import grpc
import protos.mtib_runner.mtib_runner_pb2_grpc as mtib_grpc
from rich import print as rprint
import typer

app = typer.Typer()

SERVER_ADDRESSES = {
    1: "192.168.8.242:50051",  # slot-1
    2: "192.168.8.143:50051",  # slot-2
    3: "192.168.8.216:50051",  # slot-3
    4: "192.168.8.142:50051",  # slot-4
    5: "192.168.8.184:50051",  # slot-5
    6: "192.168.8.186:50051",  # slot-6
}

SYNC_BYTE1 = 0xA5  # Replace with actual sync byte values
SYNC_BYTE2 = 0x5A  # Replace with actual sync byte values


def format_log_entry(log_entry: str) -> str:
    """Format log entry for terminal display."""
    log_entry = re.sub(r"\[\d+m", "", log_entry)  # Remove unnecessary escape sequences

    log_levels = {"inf": "[green]", "wrn": "[yellow]", "err": "[red]", "dbg": "[white]"}

    for level, color in log_levels.items():
        if f"<{level}>" in log_entry or f" {level}>" in log_entry:
            log_entry = f"{color}{log_entry}[/]"
            break

    return log_entry


def clean_log_entry(log_entry: str) -> str:
    """Clean log entry to remove color codes, escape sequences, and special characters before saving to file."""
    log_entry = re.sub(r"\x1B[@-_][0-?]*[ -/]*[@-~]", "", log_entry)
    return log_entry


def get_server_instance(server_address):
    """Create a gRPC client stub."""
    channel = grpc.insecure_channel(server_address)
    stub = mtib_grpc.MtibRunnerStub(channel)
    return stub


def save_log(log_folder, filename, log_entry):
    """Save log entry to a file."""
    with open(os.path.join(log_folder, filename), "a") as f:
        f.write(log_entry + "\n")


def nrf9160_uart(log_folder, server_address, display_in_terminal=False):
    """Receives data from the NRF9160 UART stream and saves to a file."""
    try:
        server = get_server_instance(server_address)
        request_queue = Queue()
        request_iterator = iter(request_queue.get, None)
        buffer = b""
        log_file = "nrf9160.log"

        for response in server.nrf9160UartStream(request_iterator):
            try:
                data = response.data
                buffer += data

                while len(buffer) > 0:
                    if buffer.startswith(struct.pack("BB", SYNC_BYTE1, SYNC_BYTE2)):
                        pass
                    else:
                        if b"\r\n" in buffer:
                            line, buffer = buffer.split(b"\r\n", 1)
                            cleaned_log = format_log_entry(line.decode("utf-8", "replace"))
                            save_log(log_folder, log_file, clean_log_entry(line.decode("utf-8", "replace")))
                            if display_in_terminal:
                                rprint(cleaned_log)
                        else:
                            break
            except Exception as e:
                error_msg = f"Error decoding data: {e}"
                save_log(log_folder, log_file, clean_log_entry(error_msg))
                if display_in_terminal:
                    rprint(f"[red]Error decoding data: {e}[/red]")

    except Exception as e:
        rpc_error_msg = f"RPC error: {e}"
        save_log(log_folder, log_file, clean_log_entry(rpc_error_msg))
        if display_in_terminal:
            rprint(f"[red]RPC error: {e}[/red]")


def nrf52840_uart(log_folder, server_address, display_in_terminal=False):
    """Receives data from the NRF52840 UART stream and saves to a file."""
    try:
        server = get_server_instance(server_address)
        request_queue = Queue()
        request_iterator = iter(request_queue.get, None)
        buffer = ""
        log_file = "nrf52840.log"

        for response in server.nrf52840UartStream(request_iterator):
            try:
                data_str = response.data.decode("utf-8", "replace")
                buffer += data_str

                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    cleaned_log = format_log_entry(line)
                    save_log(log_folder, log_file, clean_log_entry(line))
                    if display_in_terminal:
                        rprint(cleaned_log)
            except Exception as e:
                error_msg = f"Error decoding data: {e}"
                save_log(log_folder, log_file, clean_log_entry(error_msg))
                if display_in_terminal:
                    rprint(f"[red]Error decoding data: {e}[/red]")

    except Exception as e:
        rpc_error_msg = f"RPC error: {e}"
        save_log(log_folder, log_file, clean_log_entry(rpc_error_msg))
        if display_in_terminal:
            rprint(f"[red]RPC error: {e}[/red]")


def start_logging(slot, chip, logs_dir, display_in_terminal=False):
    """Start logging for a given slot and chip, optionally displaying logs in terminal."""
    server_address = SERVER_ADDRESSES[slot]

    # Use the logs_dir directly without creating any additional subdirectories
    if chip == "nrf9160":
        nrf9160_uart(logs_dir, server_address, display_in_terminal=display_in_terminal)
    elif chip == "nrf52840":
        nrf52840_uart(logs_dir, server_address, display_in_terminal=display_in_terminal)


# Environment variables
COREKINECT_DEVICE = os.getenv("COREKINECT_DEVICE", "nrf9160")
COREKINECT_PORT = os.getenv("COREKINECT_PORT", 1)
LOGS_PATH = os.getenv("LOGS_PATH", "/var/tmp/logs")  # Default logs path, can be overridden by environment variable


@app.command()
def log(chip: str = COREKINECT_DEVICE, slot: int = None):
    """Capture logs from the specified chip and slot, while logging data from all slots."""
    # Check for required environment variables
    if not chip or not COREKINECT_PORT:
        typer.echo("COREKINECT_DEVICE and COREKINECT_PORT environment variables are required.")
        raise typer.Exit(code=1)

    try:
        slot = int(COREKINECT_PORT) if slot is None else slot
    except ValueError:
        typer.echo("COREKINECT_PORT must be a valid integer.")
        raise typer.Exit(code=1)

    typer.echo(f"Logging {chip} on slot {slot}")

    # Create the base directory with a timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_logs_dir = os.path.join(LOGS_PATH, timestamp)
    os.makedirs(base_logs_dir, exist_ok=True)

    # Start logging for the specified slot and chip in the terminal
    threads = []
    for s in SERVER_ADDRESSES.keys():
        slot_dir = os.path.join(base_logs_dir, f"slot_{s}")
        os.makedirs(slot_dir, exist_ok=True)

        if s == slot:
            # Log the specified chip in the terminal, and the other one silently
            thread_9160 = threading.Thread(target=start_logging, args=(s, "nrf9160", slot_dir, chip == "nrf9160"))
            thread_52840 = threading.Thread(target=start_logging, args=(s, "nrf52840", slot_dir, chip == "nrf52840"))
            thread_9160.start()
            thread_52840.start()
            threads.extend([thread_9160, thread_52840])
        else:
            # Log both chips silently for other slots
            thread_9160 = threading.Thread(target=start_logging, args=(s, "nrf9160", slot_dir, False))
            thread_52840 = threading.Thread(target=start_logging, args=(s, "nrf52840", slot_dir, False))
            thread_9160.start()
            thread_52840.start()
            threads.extend([thread_9160, thread_52840])

    # Wait for all threads to complete
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    app()
