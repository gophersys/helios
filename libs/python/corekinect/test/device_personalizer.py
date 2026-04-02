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
import os
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import requests

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig, PowerChannel
from corekinect.shells.alpha_app import AlphaAppShell
from corekinect.shells.comms_coproc import CommsCoprocShell
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

# Allow overriding personalization target via env var when COMMS UART is dead
if os.environ.get("PERSONALIZE_VIA_APP") == "1":
    COMMS_TARGET = APP_TARGET


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
        self._app = AlphaAppShell(mtib)
        self._comms = CommsCoprocShell(mtib)
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

    def _lock_shells_concurrent(self, timeout_s: float = 10.0) -> Tuple[bool, bool]:
        """Lock both shells concurrently using threads.

        The mfg shell activation window is only ~7s (0.4s–7.4s post-boot).
        Concurrent locking sends lock_shell on both UARTs simultaneously to
        fit within the window.

        10s timeout: if the shell doesn't lock within the ~7s activation
        window, it won't. Caller should power cycle and retry rather than
        waiting longer.

        Returns:
            (app_locked, comms_locked) tuple.
        """
        results = {}

        def _lock(name, shell):
            try:
                shell.start()
                results[name] = shell.lock(timeout_s=timeout_s)
            except Exception as e:
                self._log.error("Lock %s exception: %s", name, e)
                results[name] = False

        t_app = threading.Thread(target=_lock, args=("APP", self._app))
        t_comms = threading.Thread(target=_lock, args=("COMMS", self._comms))
        t_app.start()
        t_comms.start()
        t_app.join(timeout=timeout_s + 5)
        t_comms.join(timeout=timeout_s + 5)

        app_ok = results.get("APP", False)
        comms_ok = results.get("COMMS", False)

        self._log.info(
            "Concurrent lock: APP=%s, COMMS=%s",
            "locked" if app_ok else "FAILED",
            "locked" if comms_ok else "FAILED",
        )
        return app_ok, comms_ok

    def _power_cycle_and_lock_shells(
        self, boot_wait_s: float, lock_shells: bool, max_attempts: int = 3,
    ) -> Optional[str]:
        """Power cycle DUT and lock shells using manufacturing pattern.

        Fast fail-and-retry: 10s lock timeout per attempt. If the shell
        doesn't lock in the ~7s activation window, power cycle and try
        again (up to max_attempts). Much faster than a single long timeout.

        GPIO 0+1 must be configured as output LOW before power-on — these
        control the SWD level shifter enable lines.
        """
        for attempt in range(1, max_attempts + 1):
            self._log.debug("Power cycle attempt %d/%d...", attempt, max_attempts)

            # Power off BOTH channels
            err = self._mtib.PowerDisable(channel=PowerChannel.DUT)
            if err:
                return err
            err = self._mtib.PowerDisable(channel=PowerChannel.CHARGER)
            if err:
                return err
            time.sleep(2)

            # Configure GPIOs (required for DUT boot)
            for gpio in (0, 1):
                err = self._mtib.GpioConfig(gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
                if err:
                    return f"GpioConfig({gpio}) failed: {err}"
                err = self._mtib.GpioWrite(gpio, False)
                if err:
                    return f"GpioWrite({gpio}) failed: {err}"

            # Power on BOTH channels
            err = self._mtib.PowerEnable(channel=PowerChannel.DUT, voltage_v=4.5)
            if err:
                return err
            err = self._mtib.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=5.0)
            if err:
                return err

            self._log.debug("DUT powered on (ch0 + ch1)")

            # Wait for boot — shell activates ~0.4s
            time.sleep(min(boot_wait_s, 0.5))

            if not lock_shells:
                break

            # Lock BOTH shells concurrently — 10s timeout, fail fast
            self._log.info("Locking shells (concurrent, attempt %d)...", attempt)
            app_ok, comms_ok = self._lock_shells_concurrent()

            # Disable debug output (reduces UART noise for subsequent commands)
            if app_ok:
                self._app.debug_off()
            if comms_ok:
                self._comms.debug_off()

            if app_ok and comms_ok:
                self._log.debug("Power cycle and shell lock complete")
                return None

            failed = []
            if not app_ok: failed.append("APP")
            if not comms_ok: failed.append("COMMS")
            self._log.warning(
                "%s lock failed (attempt %d/%d) — retrying with fresh power cycle",
                "+".join(failed), attempt, max_attempts,
            )

        return "Shell lock failed after %d attempts" % max_attempts

    def _lock_shells_only(self) -> Optional[str]:
        """Lock shells without power cycling (for when device is already booted)."""
        self._log.debug("Locking shells (no power cycle)...")

        app_ok, comms_ok = self._lock_shells_concurrent()

        if app_ok:
            self._app.debug_off()
        if comms_ok:
            self._comms.debug_off()

        if not comms_ok:
            return "COMMS shell lock failed — device may not have booted or window missed"

        return None

    def _read_imei_iccids(self) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """Read IMEI and ICCIDs from the cellular modem."""
        self._log.debug("Reading IMEI/ICCIDs from modem...")
        sim_info, err = self._comms.get_sim_info()
        if err:
            return None, None, err

        self._log.debug("IMEI: %s, ICCIDs: %s", sim_info.imei, sim_info.iccids)
        return sim_info.imei, sim_info.iccids, None

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
        result, err = self._comms.personalize(device_id)
        if err:
            return None, None, err
        return result.hex_key, result.base64_key, None

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
        success, err = self._comms.rekey_ipc()
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
