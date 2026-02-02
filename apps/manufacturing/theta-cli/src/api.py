import json
import threading
from typing import Callable, Dict, List, Optional

import requests
import socketio

# Disable SSL warnings for self-signed certs
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)


class ConcordAPI:
    """Client for the Concord HTTP API + WebSocket."""

    def __init__(self, api_url: str, cluster_uuid: str):
        self.api_url = api_url.rstrip("/")
        self.cluster_uuid = cluster_uuid

    def validate_snr(self, snr: str, singleton: bool) -> Dict[str, str]:
        """
        Validate a serial number and get the hostname->SNR mapping.
        Returns dict like {"verdin-imx8mm-XXXXX": "08YP", ...}
        Raises on error.
        """
        resp = requests.post(
            f"{self.api_url}/v1/devices/snr/validate",
            json={"snr": snr, "singleton": singleton},
            verify=False,
            timeout=10,
        )
        data = resp.json()
        if resp.status_code != 200:
            raise RuntimeError(data.get("error", f"HTTP {resp.status_code}"))
        return data["snrs"]

    def exec_test(
        self,
        test_uuid: str,
        nodes: List[str],
        config: Dict,
        on_step_result: Callable,
        on_done: Callable,
        on_error: Callable,
    ) -> str:
        """
        Trigger a test execution and subscribe to WebSocket for results.
        Returns execution_id. Callbacks are invoked from a background thread.
        """
        # Trigger test via REST
        resp = requests.post(
            f"{self.api_url}/v1/clusters/{self.cluster_uuid}/tests/{test_uuid}/exec",
            json={"config": config, "nodes": nodes},
            verify=False,
            timeout=10,
        )
        data = resp.json()
        if resp.status_code != 202:
            raise RuntimeError(data.get("error", f"HTTP {resp.status_code}"))

        execution_id = data["executionId"]

        # Subscribe via WebSocket
        done_event = threading.Event()

        sio = socketio.Client(ssl_verify=False, logger=False, engineio_logger=False)

        @sio.on("exec_test_response")
        def handle_response(msg):
            if msg.get("done") or msg.get("error"):
                if msg.get("error"):
                    on_error(msg["error"])
                else:
                    on_done(msg.get("results", []))
                done_event.set()
                return

            results = msg.get("results", [])
            sequence = msg.get("sequence", 0)
            on_step_result(sequence, results)

        @sio.event
        def connect():
            sio.emit("exec_test", {"session_id": execution_id})

        def run_ws():
            try:
                ws_url = self.api_url.replace("https://", "wss://").replace("http://", "ws://")
                sio.connect(self.api_url, transports=["websocket"], wait_timeout=10)
                done_event.wait(timeout=600)  # 10 min max per test
            except Exception as e:
                on_error(str(e))
                done_event.set()
            finally:
                if sio.connected:
                    sio.disconnect()

        ws_thread = threading.Thread(target=run_ws, daemon=True)
        ws_thread.start()

        return execution_id, done_event
