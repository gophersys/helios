"""Automated device re-personalization for validation test cycles.

After every firmware flash via J-Link (--chiperase), the device loses
its personalization (EC keypair, device ID, IPC keys). This module
automates the full re-personalization sequence using the V1 MTIB client.

Uses CoreOpsClient for all CoreOps API calls (device ID assignment,
key upload, ICCID registration). CoreOps credentials must be set via
COREOPS_* environment variables.

CRITICAL: The device's public key MUST be uploaded to CoreCloud for:
- FUOTA (firmware updates) to work
- Device telemetry to be authenticated
- Any CoreCloud communication to succeed

The key upload is MANDATORY by default (require_corecloud_key=True).
If the key upload fails, repersonalize() returns an error. This prevents
silent failures where FUOTA appears to work but the device can't communicate.

Typical usage (after firmware flash):
    personalizer = DevicePersonalizer(
        mtib=ctx.mtib,
        snr="0964",
        # db_env defaults to "VAL_1_0"
        # require_corecloud_key defaults to True
    )
    result, error = personalizer.repersonalize()
    assert error is None, f"Re-personalization failed: {error}"

Environment variables required:
    VAL_1_0_API_KEY, VAL_1_0_API_AUTH_SERVER_HOST_NAME,
    VAL_1_0_API_REST_SERVER_HOST_NAME, VAL_1_0_API_AUTH_USERNAME,
    VAL_1_0_API_AUTH_PASSWORD
"""

import datetime
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import os

import requests

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig, PowerChannel
from corekinect.utils import Logger
from corekinect.utils.encoding.byte_str import bytes_to_base64
from corekinect.utils.timeutil.tzutils import dt_to_utc

log = Logger(log_name="device_personalizer")

# TLS verification — enabled by default, can be disabled for local dev with self-signed certs
_TLS_VERIFY = os.environ.get("TLS_VERIFY", "true").lower() in ("1", "true", "yes")

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
    # CRITICAL: Use HOST_TYPE_NRF9151 (value=5), NOT HOST_TYPE_NRF9160 (value=1)
    # Manufacturing uses NRF9151, the proto was updated to add this newer type
    COMMS_TARGET = HostType.HOST_TYPE_NRF9151  # nRF9151 comms coprocessor
    APP_TARGET = HostType.HOST_TYPE_NRF52840   # nRF52840 app processor
except ImportError:
    COMMS_TARGET = 5  # HOST_TYPE_NRF9151
    APP_TARGET = 3    # HOST_TYPE_NRF52840


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
      7. **Upload public key to CoreCloud (REQUIRED for FUOTA)**
      8. Rekey IPC (replace hardcoded keys with device-specific)

    Args:
        mtib: Connected V1 MTIB client.
        snr: Device serial number (J-Link probe serial, e.g., "0964").
        imei: Pre-known IMEI (skip modem read if provided).
        iccids: Pre-known ICCIDs (skip modem read if provided).
        db_env: CoreCloud API environment (default "VAL_1_0"). REQUIRED for FUOTA.
        logger: Parent Logger instance (creates child logger if provided).
        proxy_url: DEPRECATED - no longer used, CoreOpsClient handles this.
        known_device_id: Pre-known device ID (skip CoreOps lookup if provided).
        require_corecloud_key: If True (default), FAIL if key upload fails.
            This prevents silent failures where FUOTA won't work because
            CoreCloud doesn't have the device's public key.
    """

    def __init__(
        self,
        mtib: MtibV1Client,
        snr: str,
        imei: Optional[str] = None,
        iccids: Optional[List[str]] = None,
        db_env: Optional[str] = "VAL_1_0",  # Default to VAL - FUOTA requires key upload
        logger: Optional[Logger] = None,
        proxy_url: Optional[str] = None,  # Deprecated, kept for backward compat
        known_device_id: Optional[str] = None,  # Fallback when CoreOps unavailable
        require_corecloud_key: bool = True,  # FUOTA requires key in CoreCloud - fail if upload fails
    ):
        self._mtib = mtib
        self._snr = snr
        self._imei = imei
        self._iccids = iccids
        self._db_env = db_env
        self._log = logger.from_parent("personalizer") if logger else log
        self._coreops = None  # Lazy init
        self._known_device_id = known_device_id
        self._require_corecloud_key = require_corecloud_key

        if proxy_url:
            self._log.warning(
                "proxy_url is deprecated - CoreOpsClient now connects directly. "
                "Set COREOPS_* env vars instead."
            )

    def _get_coreops(self):
        """Lazy-initialize CoreOpsClient."""
        if self._coreops is None:
            from corekinect.core_ops import CoreOpsClient
            self._coreops = CoreOpsClient(logger=self._log)
            self._coreops.__enter__()
        return self._coreops

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
        # Step 1: Power cycle with shell lock
        # Manufacturing pattern: open UART -> power on -> wait 3s -> lock shells
        if power_cycle:
            err = self._power_cycle_and_lock_shells(boot_wait_s, lock_shells)
            if err:
                return None, f"Power cycle/shell lock failed: {err}"
        elif lock_shells:
            # Just lock shells without power cycle (unusual case)
            err = self._lock_shells_only()
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

        self._log.info("Device ID: %s (SNR: %s)", device_id, self._snr)

        # Step 5: Personalize device via UART
        hex_key, b64_key, err = self._personalize(device_id)
        if err:
            return None, f"UART personalization failed: {err}"
        if not b64_key:
            return None, "Personalization succeeded but no base64 public key returned — cannot upload to CoreCloud"

        self._log.info("Device personalized, pub key (b64): %s...", b64_key[:20])

        # Step 6: Upload keys + SIM info to CoreOps (optional, non-blocking)
        err = self._save_device_info(device_id, hex_key, b64_key, imei, iccids or [])
        if err:
            self._log.warning("CoreOps save skipped: %s — OK for validation", err)

        # Step 6b: Upload public key to CoreCloud (REQUIRED for Socket Server auth)
        if self._db_env and b64_key:
            err = self._save_key_to_corecloud_db(device_id, b64_key)
            if err:
                if self._require_corecloud_key:
                    return None, f"CoreCloud key upload FAILED: {err} — FUOTA will not work without this key"
                else:
                    self._log.warning("CoreCloud key upload failed: %s", err)
        elif self._require_corecloud_key and b64_key and not self._db_env:
            return None, "CoreCloud key upload required but db_env not set"

        # Step 7: IPC rekey SKIPPED — not needed for CoreCloud auth.
        # IPC rekey replaces hardcoded AES-128 key between APP and COMMS processors.
        # It is NOT required for FUOTA or Socket Server authentication.
        # Skipping to avoid any risk of corrupting the EC keypair in flash.
        self._log.info("IPC rekey skipped — not needed for CoreCloud/FUOTA")

        self._log.info("Re-personalization complete for device %s", device_id)

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

    def _power_cycle_and_lock_shells(self, boot_wait_s: float, lock_shells: bool) -> Optional[str]:
        """Power cycle DUT and lock shells using manufacturing pattern.

        Manufacturing sequence:
        0. Drain UART buffers (clear stale backlog from previous sessions)
        1. Power off, wait 2s
        2. Configure GPIOs
        3. Power on
        4. Wait 3s (shell activates ~0.4s after boot, deactivates ~7.4s)
        5. Send lock_shell commands with retry (within the window)

        GPIO 0+1 must be configured as output LOW before power-on — these
        control the SWD level shifter enable lines.

        Batteryless fixture: ch0 ONLY at 4.5V. Ch1 (charger) must NOT be enabled.
        """
        self._log.debug("Power cycling DUT...")

        # Step 0: Quick UART drain (0.5s each) - just clear any pending bytes
        # Don't wait long here - after flash, the device is already booting
        # and we need to catch the shell window (2-7s post-boot)
        self._mtib.alpha_drain_uart(COMMS_TARGET, duration_s=0.5)
        self._mtib.alpha_drain_uart(APP_TARGET, duration_s=0.5)

        # Step 1: Power off BOTH channels (DUT may run on charger when battery_installed)
        err = self._mtib.PowerDisable(channel=PowerChannel.DUT)
        if err:
            return err
        err = self._mtib.PowerDisable(channel=PowerChannel.CHARGER)
        if err:
            return err
        time.sleep(2)

        # Step 2: Configure GPIOs (required for DUT boot)
        for gpio in (0, 1):
            err = self._mtib.GpioConfig(gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
            if err:
                return f"GpioConfig({gpio}) failed: {err}"
            err = self._mtib.GpioWrite(gpio, False)
            if err:
                return f"GpioWrite({gpio}) failed: {err}"

        # Step 3: Power on BOTH channels (battery + charger for battery-installed fixtures)
        err = self._mtib.PowerEnable(channel=PowerChannel.DUT, voltage_v=4.5)
        if err:
            return err
        err = self._mtib.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=5.0)
        if err:
            return err

        self._log.debug("DUT powered on (ch0 + ch1)")

        # Step 4: Wait briefly for boot (shell activates ~0.4s after boot)
        # Don't wait too long - shell deactivates ~7.4s after boot
        # Start spamming at ~1.5s to catch the 0.4-7.4s window
        time.sleep(min(boot_wait_s, 1.5))

        # Step 5: Lock COMMS shell only - personalization runs on COMMS (nRF9151)
        # APP shell lock causes UART contention issues - skip it for FUOTA flows
        if lock_shells:
            self._log.info("Spamming lock_shell on COMMS (5s)...")
            comms_success, comms_out = self._mtib.alpha_spam_lock_shell(target=COMMS_TARGET, duration_s=5.0)

            if comms_success:
                self._log.info("Comms shell locked!")
            else:
                self._log.error("Comms shell lock FAILED - cannot proceed with personalization")
                return "Comms shell lock failed - device may not boot correctly or window missed"

            # Disable debug output on COMMS only
            self._mtib.alpha_cmd_debug_disable_comms()

        self._log.debug("Power cycle and shell lock complete")
        return None

    def _lock_shells_only(self) -> Optional[str]:
        """Lock shells without power cycling (for when device is already booted)."""
        self._log.debug("Locking shells (no power cycle)...")
        success, err = self._mtib.alpha_cmd_lock_shell_comms()
        if not success:
            return f"Comms shell lock failed: {err}"

        success, err = self._mtib.alpha_cmd_lock_shell_app()
        if not success:
            return f"App shell lock failed: {err}"

        self._mtib.alpha_cmd_debug_disable_comms()
        self._mtib.alpha_cmd_debug_disable_app()
        return None

    def _read_imei_iccids(self) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """Read IMEI and ICCIDs from the cellular modem."""
        self._log.debug("Reading IMEI/ICCIDs from modem...")
        imei, iccids_str, err = self._mtib.alpha_cmd_get_imei_iccids(
            target=COMMS_TARGET
        )
        if err:
            return None, None, err

        # Parse ICCIDs (comma-separated string -> list)
        iccids = None
        if iccids_str:
            iccids = [s.strip() for s in iccids_str.split(",") if s.strip()]

        self._log.debug("IMEI: %s, ICCIDs: %s", imei, iccids)
        return imei, iccids, None

    def _get_device_id(self) -> Tuple[Optional[str], Optional[str]]:
        """Get device ID from CoreOps or use known_device_id fallback.

        Priority:
        1. CoreOps API (deterministic SNR → device ID mapping)
        2. known_device_id from fixture profile (if CoreOps unavailable)
        """
        coreops_err = None

        # Try CoreOps first
        try:
            coreops = self._get_coreops()
            device_id = coreops.assign_device_id(self._snr)
            return device_id, None
        except Exception as e:
            coreops_err = str(e)
            self._log.warning("CoreOps failed: %s", coreops_err)

        # Fallback to known device ID from fixture profile
        if self._known_device_id:
            self._log.info(
                "Using known_device_id from fixture profile (CoreOps unavailable): %s",
                self._known_device_id
            )
            return self._known_device_id, None

        return None, f"CoreOps unavailable ({coreops_err}) and no known_device_id fallback provided"

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
        try:
            coreops = self._get_coreops()

            # Save public key
            if b64_key:
                coreops.upload_public_key(device_id, b64_key)

            # Save ICCIDs with carrier mapping
            for iccid in iccids:
                carrier = self._identify_carrier(iccid)
                if not carrier:
                    self._log.warning("Unknown carrier for ICCID %s, skipping", iccid)
                    continue
                coreops.save_iccid(iccid, carrier, self._snr, imei)

            return None
        except Exception as e:
            return f"CoreOps save failed: {e}"

        return None

    def _rekey_ipc(self) -> Optional[str]:
        """Rekey IPC to replace hardcoded keys with device-specific keys."""
        self._log.debug("Rekeying IPC...")
        success, err = self._mtib.cmd_comms_coproc_rekey_ipc(target=COMMS_TARGET)
        if err:
            return err
        if not success:
            return "IPC rekey returned success=False"
        self._log.debug("IPC rekey complete")
        return None

    def _save_key_to_corecloud_db(self, device_id: str, b64_key: str) -> Optional[str]:
        """Upload the device's EC public key to CoreCloud and VERIFY it matches.

        The Socket Server authenticates device uplinks by verifying ECDSA
        signatures against the stored public key. Key must be raw EC point
        in base64 (NOT DER SubjectPublicKeyInfo) — exactly the format the
        device returns from the `personalize` command.

        CRITICAL: Uses b64_key directly from the device. No re-encoding.
        After upload, reads back the stored key and compares byte-for-byte.
        Returns error if the stored key doesn't match what we uploaded.
        """
        try:
            import json as json_mod
            import time as time_mod
            import base64 as b64_mod

            from corekinect.core_cloud.api_interface import CoreCloudRestInterface

            # Log full key for debugging — helps diagnose Invalid Signature issues
            self._log.info("Key to upload (full): %s", b64_key)
            self._log.info("Key length: %d chars, decoded: %d bytes",
                           len(b64_key), len(b64_mod.b64decode(b64_key)))

            with CoreCloudRestInterface(env_namespace=self._db_env) as api:
                token = api._ensure_token()
                key_str = str(api.api.key)
                base_url = api.api.rest_server_host_name

            sess = requests.Session()
            headers = {
                "Authorization": f"Bearer {token}",
                "X-API-KEY": key_str,
                "Content-Type": "application/json",
            }

            # Upload key via Sessions/Profiles endpoint
            url = f"{base_url}/System/Devices/Sessions/Profiles"
            body = {"Profiles": [{"DeviceId": device_id, "PublicKey": b64_key}]}

            self._log.info("Uploading key to %s ...", url)
            resp = sess.post(url, data=json_mod.dumps(body), headers=headers, verify=_TLS_VERIFY, timeout=10)

            if resp.status_code not in (200, 204):
                return f"Key upload failed: {resp.status_code} {resp.text[:300]}"

            self._log.info("Key upload returned %d", resp.status_code)

            # VERIFY: Read back stored key and compare byte-for-byte
            time_mod.sleep(2)

            verify_url = f"{base_url}/System/Devices/Sessions/Profiles"
            verify_body = {"deviceIds": [device_id]}
            verify_resp = sess.get(verify_url, headers=headers, json=verify_body, verify=_TLS_VERIFY, timeout=10)

            if verify_resp.status_code != 200:
                return f"Key verification failed: could not query profiles ({verify_resp.status_code})"

            profiles = verify_resp.json()
            self._log.info("Profiles response: %s", json_mod.dumps(profiles)[:500])

            if isinstance(profiles, list):
                for p in profiles:
                    if p.get('deviceId') == device_id:
                        stored_key = p.get('publicKey')
                        if not stored_key:
                            return "Profile exists but publicKey is empty — upload did not persist"
                        if stored_key != b64_key:
                            return (
                                f"KEY MISMATCH: uploaded key != stored key. "
                                f"Uploaded: {b64_key} Stored: {stored_key}"
                            )
                        self._log.info("Key VERIFIED: stored key matches uploaded key (%d bytes)", len(b64_mod.b64decode(stored_key)))
                        return None

            return f"Profile not found for device {device_id} — key upload may have failed. Response: {json_mod.dumps(profiles)[:300]}"

        except Exception as e:
            return str(e)

    @staticmethod
    def _identify_carrier(iccid: str) -> Optional[str]:
        """Identify carrier from ICCID prefix."""
        for prefix, carrier in CARRIER_PREFIXES.items():
            if iccid.startswith(prefix):
                return carrier
        return None
