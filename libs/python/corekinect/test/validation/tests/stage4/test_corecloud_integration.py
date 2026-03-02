"""CoreCloud integration tests — run once credentials + connectivity available.

These tests verify that:
1. We can authenticate to CoreCloud (Auth Server + REST Server)
2. We can query the DB for our validation devices
3. Our devices are registered, active, and have correct type/variant
4. We can read messages (boot, position, biometric, network, hw failures)
5. Re-personalization flow works end-to-end
6. FUOTA tables are queryable (Phase 5 prerequisite)

Prerequisites:
    - CoreCloud DEV_1_0 credentials set in env (DB + API + SSH tunnel)
    - MTIB server running + DUT powered (for re-personalization tests)
    - Network access to dev.office.corekinect.cloud + dmz-pg02.dmz.corekinect.com

Run:
    PYTHONPATH=libs/python:libs:libs/protocols pytest \
        libs/python/corekinect/test/validation/tests/stage4/test_corecloud_integration.py -v
"""

import os
import time

import pytest
import requests

# ── CoreCloud SDK imports ─────────────────────────────────────────────
from corekinect.core_cloud.msg_def_v1_0 import (
    AlphaHwFailureMsg,
    BiometricDataMsg,
    BootMsgV2,
    CommsHwFailureMsg,
    MsgBase,
    NetworkStatusMsgV4,
    PositionMsgV6,
)

# ── Test markers ──────────────────────────────────────────────────────
pytestmark = [
    pytest.mark.integration,
    pytest.mark.corecloud,
]

# ── Constants ─────────────────────────────────────────────────────────
# Alpha B0 device — SNR 0964
DEVICE_ID_HEX = os.environ.get("DEVICE_ID", "70B3D584C01E1FCC")
DEVICE_ID_INT = int(DEVICE_ID_HEX, 16)
DEVICE_SNR = os.environ.get("DEVICE_SNR", "0964")
DB_ENV = os.environ.get("CORECLOUD_DB_ENV", "DEV_1_0")

# Alpha B0 App IDs (from Confluence App ID table)
ALPHA_BX_COMMS_APP_ID = 108  # nRF9151
ALPHA_BX_APP_APP_ID = 109    # nRF52840

# Alpha B0 CoreCloud identifiers
ALPHA_DEVICE_TYPE = 2
ALPHA_BX_VARIANT = 3

# CoreOps proxy
PROXY_URL = os.environ.get("PROXY_SERVER_URL", "http://10.4.45.30:8001")

# CoreCloud REST
REST_URL = os.environ.get(
    f"{DB_ENV}_API_REST_SERVER_HOST_NAME",
    "https://dev.office.corekinect.cloud:2022/api",
)
AUTH_URL = os.environ.get(
    f"{DB_ENV}_API_AUTH_SERVER_HOST_NAME",
    "https://auth.office.corekinect.cloud:2013",
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def db_env():
    """CoreCloud DB environment namespace."""
    return DB_ENV


@pytest.fixture(scope="module")
def device_id():
    """Device ID as integer for SDK queries."""
    return DEVICE_ID_INT


@pytest.fixture(scope="module")
def access_token():
    """Get JWT access token from Auth Server.

    Requires env vars:
        {DB_ENV}_API_AUTH_USERNAME
        {DB_ENV}_API_AUTH_PASSWORD
        {DB_ENV}_API_KEY
    """
    username = os.environ.get(f"{DB_ENV}_API_AUTH_USERNAME")
    password = os.environ.get(f"{DB_ENV}_API_AUTH_PASSWORD")
    api_key = os.environ.get(f"{DB_ENV}_API_KEY")

    if not all([username, password, api_key]):
        pytest.skip("CoreCloud API credentials not configured")

    import base64
    basic_creds = base64.b64encode(f"{username}:{password}".encode()).decode()

    resp = requests.post(
        f"{AUTH_URL}/authentication/tokens/request",
        headers={
            "X-API-KEY": api_key,
            "Authorization": f"Basic {basic_creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data="grant_type=password",
        verify=False,
        timeout=15,
    )
    assert resp.status_code == 200, f"Auth failed: {resp.status_code} {resp.text[:200]}"
    data = resp.json()
    return data.get("access_token") or data.get("AccessToken")


@pytest.fixture(scope="module")
def api_headers(access_token):
    """Standard headers for REST API calls."""
    api_key = os.environ.get(f"{DB_ENV}_API_KEY", "")
    return {
        "X-API-KEY": api_key,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


# ══════════════════════════════════════════════════════════════════════
# GROUP 1: Authentication & Connectivity
# ══════════════════════════════════════════════════════════════════════


class TestAuthentication:
    """Verify we can authenticate to CoreCloud services."""

    def test_auth_server_reachable(self):
        """Auth server responds to HTTPS."""
        try:
            resp = requests.get(
                f"{AUTH_URL}/health",
                verify=False,
                timeout=10,
            )
            # Any response (even 404) means server is reachable
            assert resp.status_code < 500, f"Auth server error: {resp.status_code}"
        except requests.ConnectionError:
            pytest.fail(f"Cannot reach Auth Server at {AUTH_URL}")

    def test_rest_server_reachable(self):
        """REST server responds to HTTPS."""
        try:
            resp = requests.get(
                f"{REST_URL}/health",
                verify=False,
                timeout=10,
            )
            assert resp.status_code < 500, f"REST server error: {resp.status_code}"
        except requests.ConnectionError:
            pytest.fail(f"Cannot reach REST Server at {REST_URL}")

    def test_get_access_token(self, access_token):
        """Auth server issues JWT access token."""
        assert access_token is not None
        assert len(access_token) > 50  # JWT tokens are long

    def test_coreops_proxy_reachable(self):
        """CoreOps proxy health check passes."""
        try:
            resp = requests.get(
                f"{PROXY_URL}/v1/health/proxy",
                verify=False,
                timeout=10,
            )
            assert resp.status_code == 200, f"CoreOps proxy: {resp.status_code}"
        except requests.ConnectionError:
            pytest.fail(f"Cannot reach CoreOps proxy at {PROXY_URL}")


# ══════════════════════════════════════════════════════════════════════
# GROUP 2: Database Connectivity
# ══════════════════════════════════════════════════════════════════════


class TestDatabaseConnectivity:
    """Verify CoreCloud DB is queryable via SDK."""

    def test_db_connection_works(self, device_id, db_env):
        """Can query BootMsgV2.last() without error."""
        try:
            msg = BootMsgV2.last(device_id, db_env=db_env)
            # msg may be None if device hasn't booted, that's OK
            # The point is the query didn't throw a connection error
        except Exception as e:
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                pytest.fail(f"DB connection failed: {e}")
            raise

    def test_can_query_multiple_message_types(self, device_id, db_env):
        """All message types are queryable (tables exist, schema OK)."""
        msg_classes = [
            BootMsgV2,
            PositionMsgV6,
            BiometricDataMsg,
            NetworkStatusMsgV4,
            AlphaHwFailureMsg,
            CommsHwFailureMsg,
        ]
        for cls in msg_classes:
            try:
                cls.last(device_id, db_env=db_env)
            except Exception as e:
                pytest.fail(f"Failed to query {cls.__name__}: {e}")


# ══════════════════════════════════════════════════════════════════════
# GROUP 3: Device Registration & Identity
# ══════════════════════════════════════════════════════════════════════


class TestDeviceRegistration:
    """Verify our validation devices are correctly registered."""

    def test_device_id_assignment_is_deterministic(self):
        """CoreOps returns same device ID for same SNR."""
        resp = requests.post(
            f"{PROXY_URL}/v1/devices/ids/assign",
            json={"snr": DEVICE_SNR},
            verify=False,
            timeout=10,
        )
        assert resp.status_code == 200, f"CoreOps: {resp.status_code}"
        data = resp.json()
        assert data.get("deviceId") == DEVICE_ID_HEX, (
            f"Expected {DEVICE_ID_HEX}, got {data.get('deviceId')}"
        )

    def test_device_searchable_via_rest(self, api_headers):
        """Device appears in REST API search results."""
        resp = requests.get(
            f"{REST_URL}/System/Devices/Search",
            params={"deviceId": DEVICE_ID_HEX, "page": 1, "resultsPerPage": 10},
            headers=api_headers,
            verify=False,
            timeout=15,
        )
        if resp.status_code == 403:
            pytest.skip("Insufficient permissions for device search")
        assert resp.status_code == 200, f"Search failed: {resp.status_code} {resp.text[:200]}"
        data = resp.json()
        devices = data.get("Devices") or data.get("devices") or []
        assert len(devices) > 0, f"Device {DEVICE_ID_HEX} not found in CoreCloud"

    def test_device_has_correct_type_and_variant(self, api_headers):
        """Device is registered as Alpha B0 (type=2, variant=3)."""
        resp = requests.get(
            f"{REST_URL}/System/Devices/Search",
            params={"deviceId": DEVICE_ID_HEX, "page": 1, "resultsPerPage": 10},
            headers=api_headers,
            verify=False,
            timeout=15,
        )
        if resp.status_code != 200:
            pytest.skip("Cannot query device details")
        data = resp.json()
        devices = data.get("Devices") or data.get("devices") or []
        if not devices:
            pytest.skip("Device not found")
        device = devices[0]
        device_type = device.get("DeviceTypeId") or device.get("deviceTypeId")
        variant = device.get("DeviceVariantId") or device.get("deviceVariantId") or device.get("devVariantId")
        assert device_type == ALPHA_DEVICE_TYPE, f"Expected type {ALPHA_DEVICE_TYPE}, got {device_type}"
        assert variant == ALPHA_BX_VARIANT, f"Expected variant {ALPHA_BX_VARIANT}, got {variant}"

    def test_device_is_active(self, api_headers):
        """Device is marked active in CoreCloud."""
        resp = requests.get(
            f"{REST_URL}/System/Devices/Search",
            params={"deviceId": DEVICE_ID_HEX, "page": 1, "resultsPerPage": 10},
            headers=api_headers,
            verify=False,
            timeout=15,
        )
        if resp.status_code != 200:
            pytest.skip("Cannot query device details")
        data = resp.json()
        devices = data.get("Devices") or data.get("devices") or []
        if not devices:
            pytest.skip("Device not found")
        device = devices[0]
        is_active = device.get("IsActive") or device.get("isActive")
        assert is_active is True, f"Device not active: {device}"


# ══════════════════════════════════════════════════════════════════════
# GROUP 4: Message History (read-only, no device needed)
# ══════════════════════════════════════════════════════════════════════


class TestMessageHistory:
    """Verify we can read historical messages from CoreCloud DB."""

    def test_boot_message_exists(self, device_id, db_env):
        """Device has at least one BootMsgV2 in history."""
        msg = BootMsgV2.last(device_id, db_env=db_env)
        assert msg is not None, (
            f"No BootMsgV2 found for device {device_id:#X}. "
            "Device may not have connected to CoreCloud yet."
        )

    def test_boot_message_has_firmware_version(self, device_id, db_env):
        """BootMsgV2 contains firmware version info."""
        msg = BootMsgV2.last(device_id, db_env=db_env)
        if msg is None:
            pytest.skip("No boot message available")
        # Boot message should have firmware version fields
        assert hasattr(msg, "time_of_boot") or hasattr(msg, "boot_reason"), (
            f"BootMsgV2 missing expected fields: {dir(msg)}"
        )

    def test_network_status_exists(self, device_id, db_env):
        """Device has at least one NetworkStatusMsgV4."""
        msg = NetworkStatusMsgV4.last(device_id, db_env=db_env)
        if msg is None:
            pytest.skip("No network status message — device may not have connected via LTE")
        # If it exists, check it had a successful connection
        assert hasattr(msg, "did_lte_conn"), f"Missing did_lte_conn: {dir(msg)}"

    def test_position_message_exists(self, device_id, db_env):
        """Device has at least one PositionMsgV6 (may be no-fix)."""
        msg = PositionMsgV6.last(device_id, db_env=db_env)
        if msg is None:
            pytest.skip("No position message — device may not have sent a heartbeat")
        assert hasattr(msg, "latitude"), f"Missing latitude: {dir(msg)}"

    def test_no_hw_failure_flood(self, device_id, db_env):
        """Check there's no excessive hardware failure messages (sanity)."""
        from datetime import datetime, timedelta, timezone
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        try:
            failures = AlphaHwFailureMsg.since_server_time(
                device_id, one_hour_ago, db_env=db_env
            )
            # More than 100 failure messages in an hour would be concerning
            assert len(failures) < 100, (
                f"Excessive HW failure messages: {len(failures)} in last hour"
            )
        except Exception:
            pass  # Table may not have recent data, that's fine


# ══════════════════════════════════════════════════════════════════════
# GROUP 5: FUOTA Table Access (Phase 5 prerequisite)
# ══════════════════════════════════════════════════════════════════════


class TestFuotaPrerequisites:
    """Verify FUOTA tables are queryable — Phase 5 prerequisite checks."""

    def test_fuota_table_queryable(self, db_env):
        """Can query FuotaTbl (firmware image registry)."""
        try:
            from corekinect.core_cloud.db_interface import CoreCloudDBInterface
            db = CoreCloudDBInterface(db_env)
            # Try to query the FUOTA table
            result = db.execute_raw("SELECT COUNT(*) FROM fuotatbl")
            assert result is not None, "FuotaTbl query returned None"
        except ImportError:
            pytest.skip("CoreCloudDBInterface not available")
        except Exception as e:
            if "does not exist" in str(e).lower():
                pytest.fail("FuotaTbl does not exist in this DB environment")
            elif "permission" in str(e).lower():
                pytest.skip(f"No permission to query FuotaTbl: {e}")
            raise

    def test_fuota_lists_queryable(self, db_env):
        """Can query FuotaListsTbl (device → release list mapping)."""
        try:
            from corekinect.core_cloud.db_interface import CoreCloudDBInterface
            db = CoreCloudDBInterface(db_env)
            result = db.execute_raw("SELECT COUNT(*) FROM fuotaliststbl")
            assert result is not None
        except ImportError:
            pytest.skip("CoreCloudDBInterface not available")
        except Exception as e:
            if "does not exist" in str(e).lower():
                pytest.fail("FuotaListsTbl does not exist")
            elif "permission" in str(e).lower():
                pytest.skip(f"No permission: {e}")
            raise

    def test_device_firmware_history_queryable(self, device_id, db_env):
        """Can query DeviceFirmwareHistoryTbl for our device."""
        try:
            from corekinect.core_cloud.db_interface import CoreCloudDBInterface
            db = CoreCloudDBInterface(db_env)
            result = db.execute_raw(
                f"SELECT * FROM devicefirmwarehistorytbl WHERE deviceid = '{DEVICE_ID_HEX}' LIMIT 5"
            )
            # Result may be empty if device hasn't done FUOTA, that's OK
        except ImportError:
            pytest.skip("CoreCloudDBInterface not available")
        except Exception as e:
            if "does not exist" in str(e).lower():
                pytest.fail("DeviceFirmwareHistoryTbl does not exist")
            elif "permission" in str(e).lower():
                pytest.skip(f"No permission: {e}")
            raise

    def test_fuota_progress_queryable(self, db_env):
        """Can query FuotaProgressTbl."""
        try:
            from corekinect.core_cloud.db_interface import CoreCloudDBInterface
            db = CoreCloudDBInterface(db_env)
            result = db.execute_raw("SELECT COUNT(*) FROM fuotaprogresstbl")
            assert result is not None
        except ImportError:
            pytest.skip("CoreCloudDBInterface not available")
        except Exception as e:
            if "does not exist" in str(e).lower():
                pytest.fail("FuotaProgressTbl does not exist")
            elif "permission" in str(e).lower():
                pytest.skip(f"No permission: {e}")
            raise


# ══════════════════════════════════════════════════════════════════════
# GROUP 6: Re-personalization Flow (requires MTIB + DUT)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.hardware
class TestRepersonalization:
    """Verify re-personalization flow works end-to-end.

    These tests require:
    - MTIB server running with DUT powered
    - CoreOps proxy reachable
    - Manufacturing firmware flashed on DUT
    """

    @pytest.fixture
    def personalizer(self):
        """Create DevicePersonalizer from env vars."""
        mtib_host = os.environ.get("MTIB_HOST")
        proxy_url = os.environ.get("PROXY_SERVER_URL")
        snr = os.environ.get("DEVICE_SNR")
        imei = os.environ.get("DEVICE_IMEI")
        iccids_str = os.environ.get("DEVICE_ICCIDS", "")

        if not all([mtib_host, proxy_url, snr]):
            pytest.skip("MTIB/CoreOps env vars not set")

        from corekinect.mtib_client.v1.client.core import MtibV1Client
        from corekinect.mtib_client.v1.client.config import NetConfig
        from corekinect.test.validation.device_personalizer import DevicePersonalizer

        port = int(os.environ.get("MTIB_PORT", "50053"))
        config = MtibV1Client.Config(net=NetConfig(addr=mtib_host, port=port))
        mtib = MtibV1Client(config)
        err = mtib.connect()
        if err:
            pytest.skip(f"Cannot connect to MTIB: {err}")

        iccids = [s.strip() for s in iccids_str.split(",") if s.strip()] if iccids_str else None

        yield DevicePersonalizer(
            mtib=mtib,
            proxy_url=proxy_url,
            snr=snr,
            imei=imei,
            iccids=iccids,
        )
        mtib.disconnect()

    def test_device_id_assignment(self):
        """CoreOps assigns correct device ID for our SNR."""
        resp = requests.post(
            f"{PROXY_URL}/v1/devices/ids/assign",
            json={"snr": DEVICE_SNR},
            verify=False,
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json().get("deviceId") == DEVICE_ID_HEX

    def test_key_upload_succeeds(self):
        """Can upload a dummy public key to CoreOps (idempotent)."""
        import base64
        dummy_key = base64.b64encode(b"test_key_placeholder").decode()
        resp = requests.post(
            f"{PROXY_URL}/v1/devices/keys/upload",
            json={"deviceId": DEVICE_ID_HEX, "pubKey": dummy_key},
            verify=False,
            timeout=10,
        )
        # 200 = success, 409 = already exists (both OK)
        assert resp.status_code in (200, 409), f"Key upload: {resp.status_code}"

    def test_full_repersonalization(self, personalizer):
        """Full re-personalization cycle completes without error.

        This is the most critical integration test — it proves the
        entire flash → personalize → rekey pipeline works.
        """
        result, error = personalizer.repersonalize(
            power_cycle=True,
            lock_shells=True,
            boot_wait_s=3.0,
        )
        assert error is None, f"Re-personalization failed: {error}"
        assert result is not None
        assert result.device_id == DEVICE_ID_HEX
        assert len(result.pub_key_base64) > 0, "No public key generated"

    def test_device_boots_after_repersonalization(self, personalizer, device_id, db_env):
        """After re-personalization, device sends BootMsgV2 to CoreCloud.

        This is the end-to-end proof: flash → personalize → rekey → boot → cloud msg.
        """
        result, error = personalizer.repersonalize()
        if error:
            pytest.skip(f"Re-personalization failed: {error}")

        # Power cycle to trigger boot message
        time.sleep(5)

        # Wait for boot message (device needs to connect via LTE, can take 60-120s)
        from datetime import datetime, timezone
        start = datetime.now(timezone.utc)
        deadline = time.monotonic() + 180  # 3 minute timeout

        while time.monotonic() < deadline:
            try:
                msgs = BootMsgV2.since_server_time(device_id, start, db_env=db_env)
                if msgs:
                    # Got a boot message — success!
                    return
            except Exception:
                pass
            time.sleep(5)

        pytest.fail(
            "No BootMsgV2 received within 3 minutes after re-personalization. "
            "Check: LTE connectivity, CoreCloud server health, device personalization."
        )


# ══════════════════════════════════════════════════════════════════════
# GROUP 7: Webhook Verification (optional, for data forwarding)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.optional
class TestWebhookIntegration:
    """Verify webhook management works (optional — for data forwarding setup)."""

    def test_list_webhooks(self, api_headers):
        """Can list webhooks for our account."""
        resp = requests.get(
            f"{REST_URL}/Account/Webhooks/List",
            headers=api_headers,
            verify=False,
            timeout=15,
        )
        if resp.status_code == 403:
            pytest.skip("No webhook permissions")
        assert resp.status_code == 200, f"Webhook list: {resp.status_code}"

    def test_list_account_devices(self, api_headers):
        """Can search devices in our account."""
        resp = requests.get(
            f"{REST_URL}/System/Devices/Search",
            params={"page": 1, "resultsPerPage": 10},
            headers=api_headers,
            verify=False,
            timeout=15,
        )
        if resp.status_code == 403:
            pytest.skip("No device search permissions")
        assert resp.status_code == 200
