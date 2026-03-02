"""Automated device re-personalization for validation test cycles.

After every firmware flash via J-Link (--chiperase), the device loses
its personalization (EC keypair, device ID, IPC keys). This module
automates the full re-personalization sequence using the V1 MTIB client.

Bridges the V1/V2 client gap: manufacturing uses V2 client with
boot_and_lock_shells(); validation uses V1 client with built-in
alpha_cmd_* methods. This class wraps the V1 methods and adds the
CoreOps API calls to form a complete re-personalization flow.

Typical usage (after firmware flash):
    personalizer = DevicePersonalizer(
        mtib=ctx.mtib,
        proxy_url="http://10.4.45.30:8001",
        snr="0964",
    )
    device_id, error = personalizer.repersonalize()
    assert error is None, f"Re-personalization failed: {error}"
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import requests

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig

log = logging.getLogger(__name__)

# ICCID carrier prefix mapping (from manufacturing step_9)
CARRIER_PREFIXES = {
    "891480": "Verizon",
    "8942310": "Soracom",
    "894573": "Onomondo",
    "890103": "Att",
}

# UART targets for Alpha B0
try:
    from protocols.mtib.mtib_pb2 import HostType
    COMMS_TARGET = HostType.HOST_TYPE_NRF9160  # nRF9151 comms coprocessor
    APP_TARGET = HostType.HOST_TYPE_NRF52840   # nRF52840 app processor
except ImportError:
    COMMS_TARGET = 1
    APP_TARGET = 2


@dataclass
class PersonalizationResult:
    """Result of a full re-personalization cycle."""
    device_id: str = ""
    pub_key_hex: str = ""
    pub_key_base64: str = ""
    imei: str = ""
    iccids: List[str] = field(default_factory=list)


class DevicePersonalizer:
    """Automated re-personalization using V1 MTIB client.

    Wraps the full post-flash personalization sequence:
      1. Power cycle + lock manufacturing shells
      2. Read IMEI/ICCIDs from modem (if not provided)
      3. Get device ID from CoreOps (deterministic per SNR)
      4. Personalize device via UART (generates new EC keypair)
      5. Upload public key to CoreOps
      6. Save SIM info to CoreOps
      7. Rekey IPC (replace hardcoded keys with device-specific)

    Args:
        mtib: Connected V1 MTIB client.
        proxy_url: CoreOps proxy server URL (e.g., "http://10.4.45.30:8001").
        snr: Device serial number (J-Link probe serial, e.g., "0964").
        imei: Pre-known IMEI (skip modem read if provided).
        iccids: Pre-known ICCIDs (skip modem read if provided).
    """

    def __init__(
        self,
        mtib: MtibV1Client,
        proxy_url: str,
        snr: str,
        imei: Optional[str] = None,
        iccids: Optional[List[str]] = None,
    ):
        self._mtib = mtib
        self._proxy_url = proxy_url.rstrip("/")
        self._snr = snr
        self._imei = imei
        self._iccids = iccids

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def repersonalize(
        self,
        power_cycle: bool = True,
        lock_shells: bool = True,
        boot_wait_s: float = 3.0,
    ) -> Tuple[Optional[PersonalizationResult], Optional[str]]:
        """Execute full re-personalization sequence.

        Args:
            power_cycle: Whether to power cycle the DUT first.
            lock_shells: Whether to lock manufacturing shells.
            boot_wait_s: Seconds to wait after power-on for boot.

        Returns:
            (PersonalizationResult, None) on success.
            (None, error_string) on failure.
        """
        # Step 1: Power cycle
        if power_cycle:
            err = self._power_cycle(boot_wait_s)
            if err:
                return None, f"Power cycle failed: {err}"

        # Step 2: Lock shells
        if lock_shells:
            err = self._lock_comms_shell()
            if err:
                return None, f"Shell lock failed: {err}"

        # Step 3: Read IMEI/ICCIDs if not provided
        imei = self._imei
        iccids = self._iccids
        if not imei or not iccids:
            read_imei, read_iccids, err = self._read_imei_iccids()
            if err:
                return None, f"IMEI/ICCID read failed: {err}"
            imei = imei or read_imei
            iccids = iccids or read_iccids

        if not imei:
            return None, "No IMEI available (neither provided nor read from modem)"

        # Step 4: Get device ID from CoreOps
        device_id, err = self._get_device_id()
        if err:
            return None, f"CoreOps device ID assignment failed: {err}"

        log.info("Device ID: %s (SNR: %s)", device_id, self._snr)

        # Step 5: Personalize device via UART
        hex_key, b64_key, err = self._personalize(device_id)
        if err:
            return None, f"UART personalization failed: {err}"

        log.info("Device personalized, pub key: %s...", b64_key[:20] if b64_key else "?")

        # Step 6: Upload keys + SIM info to CoreOps
        err = self._save_device_info(device_id, hex_key, b64_key, imei, iccids or [])
        if err:
            return None, f"CoreOps save failed: {err}"

        # Step 7: Rekey IPC
        err = self._rekey_ipc()
        if err:
            return None, f"IPC rekey failed: {err}"

        log.info("Re-personalization complete for device %s", device_id)

        return PersonalizationResult(
            device_id=device_id,
            pub_key_hex=hex_key or "",
            pub_key_base64=b64_key or "",
            imei=imei or "",
            iccids=iccids or [],
        ), None

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _power_cycle(self, boot_wait_s: float) -> Optional[str]:
        """Power cycle the DUT (4.5V on ch0 per Alpha B0 BQ25180 requirement).

        GPIO 0+1 must be configured as output LOW before power-on — these
        control the SWD level shifter enable lines. Without them the DUT
        draws 0mA despite correct voltage.
        """
        log.debug("Power cycling DUT...")
        err = self._mtib.PowerDisable(channel=0)
        if err:
            return err
        err = self._mtib.PowerDisable(channel=1)
        if err:
            return err

        time.sleep(2)

        # GPIO 0+1 must be output LOW for DUT to boot (SWD level shifter enable)
        for gpio in (0, 1):
            err = self._mtib.GpioConfig(gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
            if err:
                return f"GpioConfig({gpio}) failed: {err}"
            err = self._mtib.GpioWrite(gpio, False)
            if err:
                return f"GpioWrite({gpio}) failed: {err}"

        err = self._mtib.PowerEnable(channel=0, voltage_v=4.5)
        if err:
            return err
        err = self._mtib.PowerEnable(channel=1)
        if err:
            return err

        time.sleep(boot_wait_s)
        log.debug("DUT powered on, waited %.1fs", boot_wait_s)
        return None

    def _lock_comms_shell(self) -> Optional[str]:
        """Lock the comms coprocessor manufacturing shell."""
        log.debug("Locking comms shell...")
        success, err = self._mtib.cmd_comms_coproc_lock_shell(target=COMMS_TARGET)
        if err:
            return err
        if not success:
            return "Shell lock returned success=False"
        log.debug("Comms shell locked")

        # Disable debug output to reduce noise
        self._mtib.cmd_comms_coproc_debug_uart_disable(target=COMMS_TARGET)
        return None

    def _read_imei_iccids(self) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """Read IMEI and ICCIDs from the cellular modem."""
        log.debug("Reading IMEI/ICCIDs from modem...")
        imei, iccids_str, err = self._mtib.alpha_cmd_get_imei_iccids(
            device_id="", target=COMMS_TARGET
        )
        if err:
            return None, None, err

        # Parse ICCIDs (comma-separated string → list)
        iccids = None
        if iccids_str:
            iccids = [s.strip() for s in iccids_str.split(",") if s.strip()]

        log.debug("IMEI: %s, ICCIDs: %s", imei, iccids)
        return imei, iccids, None

    def _get_device_id(self) -> Tuple[Optional[str], Optional[str]]:
        """Get device ID from CoreOps (deterministic per SNR)."""
        url = f"{self._proxy_url}/v1/devices/ids/assign"
        try:
            resp = requests.post(url, json={"snr": self._snr}, verify=False, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                device_id = data.get("deviceId")
                if not device_id:
                    return None, f"CoreOps returned empty deviceId: {data}"
                return device_id, None
            return None, f"CoreOps status {resp.status_code}: {resp.content[:200]}"
        except Exception as e:
            return None, f"CoreOps request failed: {e}"

    def _personalize(self, device_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Send personalize command via UART, returns (hex_key, b64_key, error)."""
        return self._mtib.alpha_cmd_personalize(
            device_id=device_id, target=COMMS_TARGET
        )

    def _save_device_info(
        self,
        device_id: str,
        hex_key: Optional[str],
        b64_key: Optional[str],
        imei: str,
        iccids: List[str],
    ) -> Optional[str]:
        """Upload public key and SIM info to CoreOps."""
        # Save public key
        if b64_key:
            url = f"{self._proxy_url}/v1/devices/keys/upload"
            try:
                resp = requests.post(
                    url,
                    json={"deviceId": device_id, "pubKey": b64_key},
                    verify=False,
                    timeout=10,
                )
                if resp.status_code != 200:
                    return f"Key upload failed: status {resp.status_code}"
            except Exception as e:
                return f"Key upload request failed: {e}"

        # Save ICCIDs with carrier mapping
        for iccid in iccids:
            carrier = self._identify_carrier(iccid)
            if not carrier:
                log.warning("Unknown carrier for ICCID %s, skipping", iccid)
                continue

            url = f"{self._proxy_url}/v1/devices/iccids/save"
            try:
                resp = requests.post(
                    url,
                    json={
                        "iccid": iccid,
                        "carrier": carrier,
                        "snr": self._snr,
                        "imei": imei,
                    },
                    verify=False,
                    timeout=10,
                )
                if resp.status_code != 200:
                    return f"ICCID save failed for {iccid}: status {resp.status_code}"
            except Exception as e:
                return f"ICCID save request failed: {e}"

        return None

    def _rekey_ipc(self) -> Optional[str]:
        """Rekey IPC to replace hardcoded keys with device-specific keys."""
        log.debug("Rekeying IPC...")
        success, err = self._mtib.cmd_comms_coproc_rekey_ipc(target=COMMS_TARGET)
        if err:
            return err
        if not success:
            return "IPC rekey returned success=False"
        log.debug("IPC rekey complete")
        return None

    @staticmethod
    def _identify_carrier(iccid: str) -> Optional[str]:
        """Identify carrier from ICCID prefix."""
        for prefix, carrier in CARRIER_PREFIXES.items():
            if iccid.startswith(prefix):
                return carrier
        return None
