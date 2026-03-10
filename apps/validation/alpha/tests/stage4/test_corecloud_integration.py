"""CoreCloud integration tests — verify API connectivity and device state.

These tests verify that:
1. We can authenticate to CoreCloud via CoreCloudRestInterface
2. Our devices are registered, active, and have correct type/variant
3. We can read device status (boot, position, hw failures) via REST API
4. Re-personalization flow works end-to-end
5. CoreOps server is reachable (direct access, not via proxy)

All CoreCloud interactions go through the REST API — no direct DB access.

Prerequisites:
    - CoreCloud API credentials set in env (VAL_1_0_API_* namespace)
    - CoreOps credentials set in env (COREOPS_* namespace)
    - MTIB server running + DUT powered (for re-personalization tests)

Run:
    PYTHONPATH=libs/python:libs:libs/protocols pytest \
        apps/validation/alpha/tests/stage4/test_corecloud_integration.py -v
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional

import pytest
import requests

# TLS verification — enabled by default, can be disabled for local dev with self-signed certs
_TLS_VERIFY = os.environ.get("TLS_VERIFY", "true").lower() in ("1", "true", "yes")

# ── Corekinect Utils ─────────────────────────────────────────────────
from corekinect.utils import EnvConfig, Logger
from corekinect.utils.encoding.byte_str import bytes_to_base64
from corekinect.utils.timeutil.tzutils import dt_to_utc
from corekinect.utils.timeutil.formaters import auto_format_time_elapsed

# ── CoreCloud REST API ───────────────────────────────────────────────
from corekinect.core_cloud.api_interface import CoreCloudRestInterface

# ── CoreOps Client ───────────────────────────────────────────────────
from corekinect.core_ops import CoreOpsClient

# ── Test markers ──────────────────────────────────────────────────────
pytestmark = [
    pytest.mark.integration,
    pytest.mark.corecloud,
]

log = Logger(log_name="test_corecloud")


# ── Configuration via EnvConfig ──────────────────────────────────────
class _TestConfig(EnvConfig):
    """Validation test config — loaded from env vars / .env file."""
    ENV_PREFIX = ""

    DEVICE_ID: str = "70B3D584C01E1FCC"
    DEVICE_SNR: str = "0964"
    CORECLOUD_DB_ENV: str = "VAL_1_0"
    MTIB_HOST: Optional[str] = None
    MTIB_PORT: int = 50053
    DEVICE_IMEI: Optional[str] = None
    DEVICE_ICCIDS: Optional[str] = None


_cfg = _TestConfig()

# ── Derived constants ────────────────────────────────────────────────
DEVICE_ID_HEX = _cfg.DEVICE_ID
DEVICE_ID_INT = int(DEVICE_ID_HEX, 16)
DEVICE_SNR = _cfg.DEVICE_SNR
API_ENV = _cfg.CORECLOUD_DB_ENV

# Alpha B0 App IDs (from Confluence App ID table)
ALPHA_BX_COMMS_APP_ID = 108  # nRF9151
ALPHA_BX_APP_APP_ID = 109    # nRF52840

# Alpha B0 CoreCloud identifiers
ALPHA_DEVICE_TYPE = 2
ALPHA_BX_VARIANT = 3


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def api():
    """CoreCloud REST API client (auto-authenticated).

    Uses CoreCloudRestInterface which handles token fetch, refresh, and
    namespaced env var loading automatically.
    """
    try:
        with CoreCloudRestInterface(env_namespace=API_ENV) as client:
            yield client
    except (ValueError, RuntimeError) as e:
        pytest.skip(f"CoreCloud API not configured: {e}")


@pytest.fixture(scope="module")
def device_status(api):
    """Fetch current device status from REST API."""
    resp = api.request("GET", "/System/Devices/Status",
                       json={"deviceIds": [DEVICE_ID_HEX]})
    if resp.status_code != 200:
        pytest.skip(f"Cannot fetch device status: {resp.status_code}")
    data = resp.json()
    devices = data.get("devices", [])
    if not devices:
        pytest.skip(f"Device {DEVICE_ID_HEX} not found in status response")
    return devices[0]


# ══════════════════════════════════════════════════════════════════════
# GROUP 1: Authentication & Connectivity
# ══════════════════════════════════════════════════════════════════════


class TestAuthentication:
    """Verify we can authenticate to CoreCloud services."""

    def test_auth_server_reachable(self):
        """Infrastructure: Auth server responds to HTTPS."""
        auth_url = os.environ.get(
            f"{API_ENV}_API_AUTH_SERVER_HOST_NAME",
            "https://auth.office.corekinect.cloud:2013",
        )
        try:
            resp = requests.get(f"{auth_url}/health", verify=_TLS_VERIFY, timeout=10)
            assert resp.status_code < 500, f"Auth server error: {resp.status_code}"
        except requests.ConnectionError:
            pytest.fail(f"Cannot reach Auth Server at {auth_url}")

    def test_rest_server_reachable(self):
        """Infrastructure: REST server responds to HTTPS."""
        rest_url = os.environ.get(
            f"{API_ENV}_API_REST_SERVER_HOST_NAME",
            "https://val.office.corekinect.cloud:2018/api",
        )
        try:
            resp = requests.get(f"{rest_url}/health", verify=_TLS_VERIFY, timeout=10)
            assert resp.status_code < 500, f"REST server error: {resp.status_code}"
        except requests.ConnectionError:
            pytest.fail(f"Cannot reach REST Server at {rest_url}")

    def test_get_access_token(self, api):
        """Infrastructure: CoreCloudRestInterface acquires JWT access token."""
        assert api._token is not None
        assert len(api._token) > 50

    @pytest.mark.skip(reason="CoreOps credentials not available - skipping until configured")
    def test_coreops_server_reachable(self):
        """Infrastructure: CoreOps server is reachable (device ID assignment works)."""
        try:
            with CoreOpsClient() as client:
                device_id = client.assign_device_id(DEVICE_SNR)
                assert device_id == DEVICE_ID_HEX, f"Expected {DEVICE_ID_HEX}, got {device_id}"
        except ValueError as e:
            pytest.skip(f"CoreOps credentials not configured: {e}")
        except Exception as e:
            pytest.fail(f"CoreOps server error: {e}")


# ══════════════════════════════════════════════════════════════════════
# GROUP 2: API Connectivity
# ══════════════════════════════════════════════════════════════════════


class TestApiConnectivity:
    """Verify CoreCloud REST API is queryable."""

    def test_device_types_queryable(self, api):
        """Infrastructure: Can list device types via /System/Devices."""
        resp = api.request("GET", "/System/Devices")
        assert resp.status_code == 200, f"Device types query failed: {resp.status_code}"
        data = resp.json()
        assert "deviceTypes" in data, f"Unexpected response: {list(data.keys())}"
        assert len(data["deviceTypes"]) > 0, "No device types registered"

    def test_device_search_works(self, api):
        """Infrastructure: Can search for devices via REST API."""
        resp = api.request(
            "GET", "/System/Devices/Search",
            params={"page": 1, "resultsPerPage": 5},
            json={"DeviceId": DEVICE_ID_HEX},
        )
        assert resp.status_code == 200, f"Search failed: {resp.status_code}"

    def test_device_status_queryable(self, api):
        """Infrastructure: Can query device status via /System/Devices/Status."""
        resp = api.request(
            "GET", "/System/Devices/Status",
            json={"deviceIds": [DEVICE_ID_HEX]},
        )
        assert resp.status_code == 200, f"Status query failed: {resp.status_code}"
        data = resp.json()
        devices = data.get("devices", [])
        assert len(devices) > 0, f"Device {DEVICE_ID_HEX} not found in status"


# ══════════════════════════════════════════════════════════════════════
# GROUP 3: Device Registration & Identity
# ══════════════════════════════════════════════════════════════════════


class TestDeviceRegistration:
    """Verify our validation devices are correctly registered."""

    @pytest.mark.skip(reason="CoreOps credentials not available - skipping until configured")
    def test_device_id_assignment_is_deterministic(self):
        """Infrastructure: CoreOps returns same device ID for same SNR."""
        try:
            with CoreOpsClient() as client:
                device_id = client.assign_device_id(DEVICE_SNR)
                assert device_id == DEVICE_ID_HEX, (
                    f"Expected {DEVICE_ID_HEX}, got {device_id}"
                )
        except ValueError as e:
            pytest.skip(f"CoreOps credentials not configured: {e}")

    def test_device_searchable_via_rest(self, api):
        """Infrastructure: Device appears in REST API search results."""
        resp = api.request(
            "GET", "/System/Devices/Search",
            params={"page": 1, "resultsPerPage": 10},
            json={"DeviceId": DEVICE_ID_HEX},
        )
        if resp.status_code == 403:
            pytest.skip("Insufficient permissions for device search")
        assert resp.status_code == 200, f"Search failed: {resp.status_code} {resp.text[:200]}"
        data = resp.json()
        devices = data.get("devices", [])
        assert len(devices) > 0, f"Device {DEVICE_ID_HEX} not found in CoreCloud"

    def test_device_has_correct_type_and_variant(self, api):
        """Infrastructure: Device is registered as Alpha B0 (type=2, variant=3)."""
        resp = api.request(
            "GET", "/System/Devices/Search",
            params={"page": 1, "resultsPerPage": 10},
            json={"DeviceId": DEVICE_ID_HEX},
        )
        if resp.status_code != 200:
            pytest.skip("Cannot query device details")
        devices = resp.json().get("devices", [])
        if not devices:
            pytest.skip("Device not found")
        device = devices[0]
        device_type = device.get("deviceType")
        variant = device.get("deviceVariantId")
        assert device_type == ALPHA_DEVICE_TYPE, f"Expected type {ALPHA_DEVICE_TYPE}, got {device_type}"
        assert variant == ALPHA_BX_VARIANT, f"Expected variant {ALPHA_BX_VARIANT}, got {variant}"

    def test_device_is_active(self, api):
        """Infrastructure: Device is marked active in CoreCloud."""
        resp = api.request(
            "GET", "/System/Devices/Search",
            params={"page": 1, "resultsPerPage": 10},
            json={"DeviceId": DEVICE_ID_HEX},
        )
        if resp.status_code != 200:
            pytest.skip("Cannot query device details")
        devices = resp.json().get("devices", [])
        if not devices:
            pytest.skip("Device not found")
        assert devices[0].get("isActive") is True, f"Device not active: {devices[0]}"


# ══════════════════════════════════════════════════════════════════════
# GROUP 4: Device Status (via REST API)
# ══════════════════════════════════════════════════════════════════════


class TestDeviceStatus:
    """Verify device status via /System/Devices/Status REST endpoint."""

    def test_boot_info_available(self, device_status):
        """Infrastructure: Device status includes boot info."""
        boot = device_status.get("bootInfo")
        assert boot is not None, "No bootInfo in device status"
        assert "bootReason" in boot, f"bootInfo missing bootReason: {boot}"
        assert "timeOfBoot" in boot, f"bootInfo missing timeOfBoot: {boot}"
        log.info("Boot: reason=%s, time=%s", boot["bootReason"], boot["timeOfBoot"])

    def test_position_info_available(self, device_status):
        """Infrastructure: Device status includes position info."""
        pos = device_status.get("positionInfo")
        assert pos is not None, "No positionInfo in device status"
        assert "latitude" in pos, f"positionInfo missing latitude: {pos}"
        assert "longitude" in pos, f"positionInfo missing longitude: {pos}"

    def test_hw_failure_info_available(self, device_status):
        """Infrastructure: Device status includes hardware failure info."""
        app_fail = device_status.get("appHwFailInfo")
        comms_fail = device_status.get("commsHwFailInfo")
        assert app_fail is not None, "No appHwFailInfo in device status"
        assert comms_fail is not None, "No commsHwFailInfo in device status"

    def test_no_active_hw_failures(self, device_status):
        """Infrastructure: Device has no active hardware failures."""
        app_fail = device_status.get("appHwFailInfo", {})
        comms_fail = device_status.get("commsHwFailInfo", {})
        assert not app_fail.get("hasFailures"), f"App HW failures: {app_fail}"
        assert not comms_fail.get("hasFailures"), f"Comms HW failures: {comms_fail}"

    @pytest.mark.xfail(reason="Device may not have booted since last personalization")
    def test_boot_time_is_recent(self, device_status):
        """Infrastructure: Most recent boot was within the last 24 hours."""
        boot = device_status.get("bootInfo", {})
        time_of_boot = boot.get("timeOfBoot", "1970-01-01T00:00:00Z")
        if time_of_boot == "1970-01-01T00:00:00Z":
            pytest.skip("No boot recorded (epoch default)")
        boot_dt = datetime.fromisoformat(time_of_boot.replace("Z", "+00:00"))
        now = dt_to_utc(datetime.utcnow())
        age = now - boot_dt
        assert age < timedelta(hours=24), f"Last boot was {age} ago"


# ══════════════════════════════════════════════════════════════════════
# GROUP 5: Re-personalization Flow (requires MTIB + DUT)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.hardware
class TestRepersonalization:
    """Verify re-personalization flow works end-to-end.

    These tests require:
    - MTIB server running with DUT powered
    - CoreOps credentials configured (COREOPS_* env vars)
    - Manufacturing firmware flashed on DUT
    """

    @pytest.fixture
    def personalizer(self):
        """Create DevicePersonalizer from config."""
        if not all([_cfg.MTIB_HOST, _cfg.DEVICE_SNR]):
            pytest.skip("MTIB env vars not set")

        from corekinect.mtib_client.v1.client.core import MtibV1Client
        from corekinect.mtib_client.v1.client.config import NetConfig
        from corekinect.test.validation.device_personalizer import DevicePersonalizer

        config = MtibV1Client.Config(net=NetConfig(addr=_cfg.MTIB_HOST, port=_cfg.MTIB_PORT))
        mtib = MtibV1Client(config)
        err = mtib.connect()
        if err:
            pytest.skip(f"Cannot connect to MTIB: {err}")

        iccids = [s.strip() for s in _cfg.DEVICE_ICCIDS.split(",") if s.strip()] if _cfg.DEVICE_ICCIDS else None

        yield DevicePersonalizer(
            mtib=mtib,
            snr=_cfg.DEVICE_SNR,
            imei=_cfg.DEVICE_IMEI,
            iccids=iccids,
            logger=log,
        )
        mtib.disconnect()

    @pytest.mark.skip(reason="CoreOps credentials not available - skipping until configured")
    def test_device_id_assignment(self):
        """Infrastructure: CoreOps assigns correct device ID for our SNR."""
        try:
            with CoreOpsClient() as client:
                device_id = client.assign_device_id(DEVICE_SNR)
                assert device_id == DEVICE_ID_HEX
        except ValueError as e:
            pytest.skip(f"CoreOps credentials not configured: {e}")

    @pytest.mark.skip(reason="CoreOps credentials not available - skipping until configured")
    def test_key_upload_succeeds(self):
        """Infrastructure: Can upload a dummy public key to CoreOps (idempotent)."""
        dummy_key = bytes_to_base64(b"test_key_placeholder")
        try:
            with CoreOpsClient() as client:
                client.upload_public_key(DEVICE_ID_HEX, dummy_key)
        except ValueError as e:
            pytest.skip(f"CoreOps credentials not configured: {e}")

    @pytest.mark.skip(reason="Requires freshly flashed mfg firmware — run manually after J-Link flash")
    def test_full_repersonalization(self, personalizer):
        """Infrastructure: Full re-personalization cycle completes without error."""
        result, error = personalizer.repersonalize(
            power_cycle=True,
            lock_shells=True,
            boot_wait_s=3.0,
        )
        assert error is None, f"Re-personalization failed: {error}"
        assert result is not None
        assert result.device_id == DEVICE_ID_HEX
        assert len(result.pub_key_base64) > 0, "No public key generated"

    @pytest.mark.skip(reason="Requires freshly flashed mfg firmware — run manually after J-Link flash")
    def test_device_boots_after_repersonalization(self, personalizer, api):
        """Infrastructure: After re-personalization, device sends boot info to CoreCloud.

        Polls /System/Devices/Status for a new boot record.
        """
        # Get current boot recordId before re-personalization
        resp = api.request("GET", "/System/Devices/Status",
                           json={"deviceIds": [DEVICE_ID_HEX]})
        if resp.status_code != 200:
            pytest.skip("Cannot query device status")
        devices = resp.json().get("devices", [])
        prev_record_id = 0
        if devices:
            prev_record_id = devices[0].get("bootInfo", {}).get("recordId", 0)

        result, error = personalizer.repersonalize()
        if error:
            pytest.skip(f"Re-personalization failed: {error}")

        time.sleep(5)

        # Poll for new boot record
        deadline = time.monotonic() + 180
        t0 = time.monotonic()

        while time.monotonic() < deadline:
            resp = api.request("GET", "/System/Devices/Status",
                               json={"deviceIds": [DEVICE_ID_HEX]})
            if resp.status_code == 200:
                devices = resp.json().get("devices", [])
                if devices:
                    new_record_id = devices[0].get("bootInfo", {}).get("recordId", 0)
                    if new_record_id > prev_record_id:
                        elapsed = auto_format_time_elapsed(time.monotonic() - t0)
                        log.info("Boot detected after %s (recordId %d -> %d)",
                                 elapsed, prev_record_id, new_record_id)
                        return
            time.sleep(5)

        pytest.fail(
            "No new boot detected within 3 minutes after re-personalization. "
            "Check: LTE connectivity, CoreCloud server health, device personalization."
        )
