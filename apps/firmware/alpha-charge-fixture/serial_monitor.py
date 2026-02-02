#!/usr/bin/env python3
import serial
import sys

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

print(f"Monitoring {port} at {baud} baud. Ctrl+C to exit.")
try:
    with serial.Serial(port, baud, timeout=1) as ser:
        while True:
            line = ser.readline()
            if line:
                try:
                    print(line.decode("utf-8", errors="replace").rstrip())
                except Exception:
                    pass
except KeyboardInterrupt:
    print("\nMonitor stopped.")
except serial.SerialException as e:
    print(f"Serial error: {e}")
