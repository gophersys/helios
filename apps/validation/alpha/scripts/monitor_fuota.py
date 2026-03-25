#!/usr/bin/env python3
"""FUOTA monitoring script - dual thread monitoring for Stage 4 validation.

Thread 1: UART monitor - captures modem/LTE/CoreCloud/FUOTA events from device
Thread 2: CoreCloud API poll - checks FUOTA progress and device status

Usage:
    python monitor_fuota.py --mtib 10.4.45.33 --device 70B3D584C01E1DDD

Requires VAL_1_0_API_* environment variables for CoreCloud access.
"""

import argparse
import os
import sys
import threading
import time
from datetime import datetime
from typing import Optional

sys.path.insert(0, "/workspaces/concord/libs/python")
sys.path.insert(0, "/workspaces/concord/libs/protocols")
sys.path.insert(0, "/workspaces/concord/libs")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ANSI colors for terminal output
class C:
    RESET = "\033[0m"
    CYAN = "\033[36m"     # UART output
    YELLOW = "\033[33m"   # API status
    GREEN = "\033[32m"    # Good status
    RED = "\033[31m"      # Errors
    MAGENTA = "\033[35m"  # Important events
    DIM = "\033[2m"       # Timestamps


def ts():
    """Current timestamp."""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


class UartMonitor(threading.Thread):
    """Monitor UART for modem/LTE/CoreCloud/FUOTA events."""

    # Keywords to highlight
    HIGHLIGHT_KEYWORDS = [
        "LTE", "FUOTA", "CoreCloud", "FOTA", "OTA",
        "connected", "disconnected", "error", "ERROR",
        "fw_update", "firmware", "download", "flash",
        "PSM", "RRC", "attach", "detach", "PDN",
        "modem", "nrf91", "AT+", "CEREG", "CGATT",
    ]

    def __init__(self, mtib_addr: str, mtib_port: int = 50053):
        super().__init__(daemon=True)
        self._mtib_addr = mtib_addr
        self._mtib_port = mtib_port
        self._stop_event = threading.Event()
        self._client = None
        self._buffer = ""

    def stop(self):
        self._stop_event.set()

    def run(self):
        from corekinect.mtib_client.v1.client.core import MtibV1Client
        from corekinect.mtib_client.v1.client.config import NetConfig
        from protocols.mtib.mtib_pb2 import UartStreamRequest, HostType

        print(f"{C.CYAN}[UART] Connecting to MTIB {self._mtib_addr}:{self._mtib_port}...{C.RESET}")

        cfg = MtibV1Client.Config(net=NetConfig(addr=self._mtib_addr, port=self._mtib_port))
        self._client = MtibV1Client(cfg)
        err = self._client.connect()
        if err:
            print(f"{C.RED}[UART] Connect failed: {err}{C.RESET}")
            return

        print(f"{C.GREEN}[UART] Connected - monitoring nRF9151 (COMMS) UART{C.RESET}")

        # Monitor COMMS UART (nRF9151) for LTE/modem events
        target = HostType.HOST_TYPE_NRF9151

        def req_gen():
            yield UartStreamRequest(target=target)
            while not self._stop_event.is_set():
                time.sleep(0.05)
                yield UartStreamRequest(target=target)

        try:
            for resp in self._client.UartStream(target, req_gen()):
                if self._stop_event.is_set():
                    break
                if resp.data:
                    self._process_data(resp.data)
        except Exception as e:
            if not self._stop_event.is_set():
                print(f"{C.RED}[UART] Stream error: {e}{C.RESET}")

    def _process_data(self, data: bytes):
        """Process UART data and highlight important keywords."""
        text = data.decode("utf-8", errors="replace")
        self._buffer += text

        # Process complete lines
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            # Determine if line contains important keywords
            highlight = any(kw.lower() in line.lower() for kw in self.HIGHLIGHT_KEYWORDS)
            color = C.MAGENTA if highlight else C.CYAN

            print(f"{C.DIM}[{ts()}]{C.RESET} {color}[UART] {line}{C.RESET}")


class ApiMonitor(threading.Thread):
    """Poll CoreCloud API for FUOTA progress and device status."""

    def __init__(self, device_id: str, poll_interval: float = 30.0):
        super().__init__(daemon=True)
        self._device_id = device_id
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._client = None
        self._last_status = None

    def stop(self):
        self._stop_event.set()

    def run(self):
        from corekinect.test.fuota_client import FuotaClient

        print(f"{C.YELLOW}[API] Starting CoreCloud API monitor for {self._device_id}{C.RESET}")
        print(f"{C.YELLOW}[API] Poll interval: {self._poll_interval}s{C.RESET}")

        self._client = FuotaClient(api_env="VAL_1_0")

        while not self._stop_event.is_set():
            try:
                self._poll()
            except Exception as e:
                print(f"{C.RED}[API] Poll error: {e}{C.RESET}")

            # Wait for next poll or stop
            self._stop_event.wait(self._poll_interval)

    def _poll(self):
        """Poll FUOTA settings and progress."""
        # Query FUOTA settings
        resp = self._client._singleton_request(
            "GET", "firmwareupdates/settings",
            json={"deviceIds": [self._device_id]}
        )

        if resp.status_code != 200:
            print(f"{C.RED}[API] Settings query failed: {resp.status_code}{C.RESET}")
            return

        data = resp.json()
        devices = data.get("devicesFound", [])

        if not devices:
            print(f"{C.YELLOW}[API] No FUOTA settings for device{C.RESET}")
            return

        device = devices[0]
        plan_id = device.get("planId")
        enabled = device.get("isEnabled")
        current_stage = device.get("currentStageIndex")
        max_stage = device.get("maxStageIndex")

        # Check for progress
        resp2 = self._client._singleton_request(
            "GET", f"firmwareupdates/progress?deviceId={self._device_id}"
        )

        progress_info = ""
        if resp2.status_code == 200:
            prog = resp2.json()
            if prog:
                pct = prog.get("percentComplete", 0)
                state = prog.get("state", "unknown")
                progress_info = f" | Progress: {pct}% ({state})"

        # Build status string
        status = f"plan={plan_id} enabled={enabled} stage={current_stage}/{max_stage}{progress_info}"

        # Only print if status changed
        if status != self._last_status:
            color = C.GREEN if enabled else C.YELLOW
            print(f"{C.DIM}[{ts()}]{C.RESET} {color}[API] FUOTA: {status}{C.RESET}")
            self._last_status = status
        else:
            # Print heartbeat every 5 minutes
            pass

        # Also check device status
        try:
            resp3 = self._client._api_request(
                "GET", "System/Devices/Status",
                json={"deviceIds": [self._device_id]}
            )
            if resp3.status_code == 200:
                dev_data = resp3.json()
                if isinstance(dev_data, dict) and "devices" in dev_data:
                    for d in dev_data["devices"]:
                        if d.get("deviceId") == self._device_id:
                            last_seen = d.get("lastMessageTime")
                            if last_seen:
                                print(f"{C.DIM}[{ts()}]{C.RESET} {C.YELLOW}[API] Last seen: {last_seen}{C.RESET}")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Monitor FUOTA for Stage 4 validation")
    parser.add_argument("--mtib", required=True, help="MTIB address (e.g., 10.4.45.33)")
    parser.add_argument("--device", required=True, help="Device ID (DevEUI)")
    parser.add_argument("--poll", type=float, default=30.0, help="API poll interval (seconds)")
    args = parser.parse_args()

    print(f"""
{'='*60}
  FUOTA Monitor - Stage 4 Validation
{'='*60}
  MTIB:    {args.mtib}
  Device:  {args.device}
  API:     VAL_1_0
{'='*60}

Press Ctrl+C to stop monitoring.
""")

    # Start monitors
    uart_mon = UartMonitor(args.mtib)
    api_mon = ApiMonitor(args.device, args.poll)

    uart_mon.start()
    api_mon.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Stopping monitors...{C.RESET}")
        uart_mon.stop()
        api_mon.stop()
        uart_mon.join(timeout=2)
        api_mon.join(timeout=2)
        print(f"{C.GREEN}Done.{C.RESET}")


if __name__ == "__main__":
    main()
