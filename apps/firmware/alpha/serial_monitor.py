#!/usr/bin/env python3
"""Simple serial monitor that logs to stdout and a file."""
import serial
import sys
import time

PORTS = ["/dev/ttyUSB1", "/dev/ttyUSB0"]
BAUD = 115200
LOG_FILE = "/workspaces/concord/apps/firmware/alpha/serial_log.txt"

def try_port(port):
    try:
        ser = serial.Serial(port, BAUD, timeout=1)
        ser.reset_input_buffer()
        return ser
    except Exception as e:
        return None

def main():
    ser = None
    for port in PORTS:
        ser = try_port(port)
        if ser:
            print(f"Connected to {port} at {BAUD} baud", flush=True)
            break

    if ser is None:
        print("Could not open any serial port", flush=True)
        sys.exit(1)

    with open(LOG_FILE, "w") as log:
        log.write(f"=== Serial log started at {time.strftime('%Y-%m-%d %H:%M:%S')} on {ser.port} ===\n")
        log.flush()
        try:
            while True:
                line = ser.readline()
                if line:
                    text = line.decode("utf-8", errors="replace").rstrip()
                    ts = time.strftime("%H:%M:%S")
                    out = f"[{ts}] {text}"
                    print(out, flush=True)
                    log.write(out + "\n")
                    log.flush()
        except KeyboardInterrupt:
            pass
        finally:
            ser.close()

if __name__ == "__main__":
    main()
