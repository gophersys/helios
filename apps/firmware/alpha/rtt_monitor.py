#!/usr/bin/env python3
"""RTT Monitor using JLinkRTTClient"""
import subprocess
import sys
from datetime import datetime

snr = sys.argv[1] if len(sys.argv) > 1 else '821009546'

print(f"[RTT] Starting JLink RTT Server for device {snr}...")
# Start JLinkRTTLogger which outputs RTT to stdout
cmd = [
    'JLinkRTTLogger',
    '-Device', 'NRF52840_xxAA',
    '-If', 'SWD',
    '-Speed', '4000',
    '-SelectEmuBySN', snr,
    '-RTTChannel', '0',
    '/dev/stdout'
]

try:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print(f"[RTT] Connected. Waiting for data...")

    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if line:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{ts}] {line.rstrip()}", flush=True)
except KeyboardInterrupt:
    proc.terminate()
except Exception as e:
    print(f"[RTT] Error: {e}")
    # Fallback: try JLinkExe with RTT
    print("[RTT] Trying alternative method...")
