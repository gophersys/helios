"""Unit tests for CloudClient — pure logic paths without network.

Tests constructor validation, device ID format checking, baseline tracking,
stub methods, and the boot-reason predicate logic.
"""

from unittest.mock import MagicMock, patch

import pytest

from corekinect.test.cloud_client import CloudClient, validate_device_id
from corekinect.utils import Logger


# ---------------------------------------------------------------------------
# validate_device_id (module-level function)
# ---------------------------------------------------------------------------

class TestValidateDeviceId:
    """Tests for the validate_device_id() helper."""

    def test_valid_16_char_hex_uppercase(self):
        assert validate_device_id("70B3D584C01E1FCC") is True

    def test_valid_16_char_hex_lowercase(self):
        assert validate_device_id("70b3d584c01e1fcc") is True

    def test_valid_16_char_hex_mixed_case(self):
        assert validate_device_id("70B3d584c01E1fCc") is True

    def test_valid_all_zeros(self):
        assert validate_device_id("0000000000000000") is True

    def test_valid_all_f(self):
        assert validate_device_id("FFFFFFFFFFFFFFFF") is True

    def test_too_short(self):
        assert validate_device_id("70B3D584C01E1FC") is False

    def test_too_long(self):
        assert validate_device_id("70B3D584C01E1FCCA") is False

    def test_empty_string(self):
        assert validate_device_id("") is False

    def test_non_hex_chars(self):
        assert validate_device_id("70B3D584C01E1FGG") is False

    def test_spaces(self):
        assert validate_device_id("70B3 D584 C01E 1FC") is False

    def test_with_0x_prefix(self):
        assert validate_device_id("0x70B3D584C01E1F") is False


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestCloudClientConstructor:
    """Tests for CloudClient.__init__() validation and state setup."""

    def test_valid_integer_device_id(self):
        """Constructor accepts a valid integer device ID."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        assert client.device_id == 0x70B3D584C01E1FCC
        assert client._device_id_hex == "70B3D584C01E1FCC"

    def test_zero_device_id(self):
        """Zero is a valid 16-hex-char ID (all zeros)."""
        client = CloudClient(device_id=0)
        assert client._device_id_hex == "0000000000000000"

    def test_max_device_id(self):
        """Maximum 64-bit value is valid."""
        client = CloudClient(device_id=0xFFFFFFFFFFFFFFFF)
        assert client._device_id_hex == "FFFFFFFFFFFFFFFF"

    def test_negative_device_id_raises(self):
        """Negative integers produce invalid hex and should raise ValueError."""
        with pytest.raises((ValueError, OverflowError)):
            CloudClient(device_id=-1)

    def test_api_env_default(self):
        """Default api_env is VAL_1_0."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        assert client._api_env == "VAL_1_0"

    def test_api_env_custom(self):
        """Custom api_env is stored."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC, api_env="PROD_1_0")
        assert client._api_env == "PROD_1_0"

    def test_db_env_fallback(self):
        """When api_env is empty, falls back to db_env."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC, api_env="", db_env="STAGING")
        assert client._api_env == "STAGING"

    def test_both_empty_defaults_to_val(self):
        """When both api_env and db_env are empty, defaults to VAL_1_0."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC, api_env="", db_env="")
        assert client._api_env == "VAL_1_0"

    def test_logger_child_created(self):
        """When a parent logger is passed, creates a child logger."""
        parent = Logger(log_name="test_parent")
        client = CloudClient(device_id=0x70B3D584C01E1FCC, logger=parent)
        # Logger.from_parent returns a Logger — just verify it was called
        assert client._log is not None

    def test_baseline_initially_none(self):
        """Baseline should be None before mark_test_start()."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        assert client._baseline is None

    def test_api_initially_none(self):
        """API client should not be initialized eagerly."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        assert client._api is None

    def test_db_env_property(self):
        """The db_env property returns the stored api_env."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC, api_env="TEST")
        assert client.db_env == "TEST"


# ---------------------------------------------------------------------------
# mark_test_start
# ---------------------------------------------------------------------------

class TestMarkTestStart:
    """Tests for mark_test_start() baseline capture."""

    def test_sets_baseline_from_fetch(self):
        """Baseline is set to the fetched status dict."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        status = {"bootInfo": {"recordId": 42}, "positionInfo": {"recordId": 7}}
        with patch.object(client, "_fetch_status", return_value=status):
            client.mark_test_start()
        assert client._baseline == status

    def test_baseline_none_when_api_unavailable(self):
        """Baseline is None when _fetch_status returns None (no API)."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        with patch.object(client, "_fetch_status", return_value=None):
            client.mark_test_start()
        assert client._baseline is None

    def test_mark_test_start_overwrites_previous(self):
        """Calling mark_test_start() again replaces the old baseline."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        first = {"bootInfo": {"recordId": 1}}
        second = {"bootInfo": {"recordId": 99}}
        with patch.object(client, "_fetch_status", return_value=first):
            client.mark_test_start()
        assert client._baseline == first
        with patch.object(client, "_fetch_status", return_value=second):
            client.mark_test_start()
        assert client._baseline == second


# ---------------------------------------------------------------------------
# Stub methods — NotImplementedError
# ---------------------------------------------------------------------------

class TestStubMethods:
    """Verify that unimplemented methods raise NotImplementedError."""

    def setup_method(self):
        self.client = CloudClient(device_id=0x70B3D584C01E1FCC)

    def test_wait_for_biometric_raises(self):
        with pytest.raises(NotImplementedError, match="Biometric"):
            self.client.wait_for_biometric()

    def test_wait_for_biometric_with_predicate_raises(self):
        with pytest.raises(NotImplementedError):
            self.client.wait_for_biometric(predicate=lambda x: True, timeout_s=10)

    def test_wait_for_network_status_raises(self):
        with pytest.raises(NotImplementedError, match="Network status"):
            self.client.wait_for_network_status()

    def test_wait_for_network_status_with_timeout_raises(self):
        with pytest.raises(NotImplementedError):
            self.client.wait_for_network_status(timeout_s=5)

    def test_query_messages_raises(self):
        with pytest.raises(NotImplementedError, match="Message queries"):
            self.client.query_messages()

    def test_query_messages_with_args_raises(self):
        with pytest.raises(NotImplementedError):
            self.client.query_messages("some_type", limit=10)


# ---------------------------------------------------------------------------
# check_hw_failures / check_comms_hw_failures
# ---------------------------------------------------------------------------

class TestHwFailureChecks:
    """Tests for hardware failure status check methods."""

    def test_check_hw_failures_returns_section(self):
        """Returns the appHwFailInfo section from status."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        status = {"appHwFailInfo": {"gps": True, "ble": False}}
        with patch.object(client, "_fetch_status", return_value=status):
            result = client.check_hw_failures()
        assert result == {"gps": True, "ble": False}

    def test_check_hw_failures_returns_empty_when_no_api(self):
        """Returns empty dict when API is unavailable."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        with patch.object(client, "_fetch_status", return_value=None):
            result = client.check_hw_failures()
        assert result == {}

    def test_check_hw_failures_returns_empty_when_section_missing(self):
        """Returns empty dict when status lacks appHwFailInfo key."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        with patch.object(client, "_fetch_status", return_value={"bootInfo": {}}):
            result = client.check_hw_failures()
        assert result == {}

    def test_check_comms_hw_failures_returns_section(self):
        """Returns the commsHwFailInfo section from status."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        status = {"commsHwFailInfo": {"modem": True}}
        with patch.object(client, "_fetch_status", return_value=status):
            result = client.check_comms_hw_failures()
        assert result == {"modem": True}

    def test_check_comms_hw_failures_returns_empty_when_no_api(self):
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        with patch.object(client, "_fetch_status", return_value=None):
            result = client.check_comms_hw_failures()
        assert result == {}


# ---------------------------------------------------------------------------
# _poll_status_change — predicate and baseline logic
# ---------------------------------------------------------------------------

class TestPollStatusChange:
    """Tests for the _poll_status_change polling engine."""

    def test_detects_record_id_change(self):
        """Returns section data when recordId increases above baseline."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        client._baseline = {"bootInfo": {"recordId": 10}}
        new_status = {"bootInfo": {"recordId": 20, "bootReason": "Normal"}}

        with patch.object(client, "_fetch_status", return_value=new_status), \
             patch("corekinect.test.cloud_client.time.sleep"):
            result = client._poll_status_change("bootInfo", None, timeout_s=5)

        assert result["recordId"] == 20
        assert result["bootReason"] == "Normal"

    def test_ignores_same_record_id(self):
        """Times out when recordId hasn't changed from baseline."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        client._baseline = {"bootInfo": {"recordId": 10}}
        same_status = {"bootInfo": {"recordId": 10}}

        with patch.object(client, "_fetch_status", return_value=same_status), \
             patch("corekinect.test.cloud_client.time.sleep"), \
             patch("corekinect.test.cloud_client.time.monotonic", side_effect=[
                 0, 0, 0.5, 1.0, 1.5, 2.0, 2.5,
             ]):
            with pytest.raises(TimeoutError, match="No bootInfo change"):
                client._poll_status_change("bootInfo", None, timeout_s=2)

    def test_predicate_filters_results(self):
        """Only returns when predicate is satisfied."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        client._baseline = {"bootInfo": {"recordId": 5}}

        call_count = 0

        def fetch_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"bootInfo": {"recordId": 10, "bootReason": "Normal"}}
            return {"bootInfo": {"recordId": 15, "bootReason": "Fuota"}}

        predicate = lambda data: data.get("bootReason") == "Fuota"

        with patch.object(client, "_fetch_status", side_effect=fetch_side_effect), \
             patch("corekinect.test.cloud_client.time.sleep"):
            result = client._poll_status_change("bootInfo", predicate, timeout_s=60)

        assert result["bootReason"] == "Fuota"

    def test_no_baseline_uses_zero(self):
        """When baseline is None, any recordId > 0 triggers detection."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        client._baseline = None  # no baseline
        new_status = {"bootInfo": {"recordId": 1}}

        with patch.object(client, "_fetch_status", return_value=new_status), \
             patch("corekinect.test.cloud_client.time.sleep"):
            result = client._poll_status_change("bootInfo", None, timeout_s=5)

        assert result["recordId"] == 1

    def test_predicate_exception_continues_polling(self):
        """If predicate raises, polling continues instead of crashing."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        client._baseline = {"bootInfo": {"recordId": 0}}

        call_count = 0

        def fetch_side_effect():
            nonlocal call_count
            call_count += 1
            return {"bootInfo": {"recordId": call_count * 10, "data": call_count}}

        pred_calls = 0

        def bad_then_good(data):
            nonlocal pred_calls
            pred_calls += 1
            if pred_calls == 1:
                raise RuntimeError("Predicate blew up")
            return True

        with patch.object(client, "_fetch_status", side_effect=fetch_side_effect), \
             patch("corekinect.test.cloud_client.time.sleep"):
            result = client._poll_status_change("bootInfo", bad_then_good, timeout_s=60)

        assert result is not None
        assert pred_calls >= 2


# ---------------------------------------------------------------------------
# wait_for_boot — reason mapping
# ---------------------------------------------------------------------------

class TestWaitForBoot:
    """Tests for boot reason integer-to-string mapping."""

    def test_boot_reason_map_normal(self):
        """boot_reason=0 maps to 'Normal'."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        client._baseline = {"bootInfo": {"recordId": 1}}
        boot_data = {"recordId": 5, "bootReason": "Normal"}

        with patch.object(client, "_fetch_status",
                          return_value={"bootInfo": boot_data}), \
             patch("corekinect.test.cloud_client.time.sleep"):
            result = client.wait_for_boot(boot_reason=0, timeout_s=5)

        assert result["bootReason"] == "Normal"

    def test_boot_reason_map_fuota(self):
        """boot_reason=2 maps to 'Fuota'."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        client._baseline = {"bootInfo": {"recordId": 1}}
        boot_data = {"recordId": 5, "bootReason": "Fuota"}

        with patch.object(client, "_fetch_status",
                          return_value={"bootInfo": boot_data}), \
             patch("corekinect.test.cloud_client.time.sleep"):
            result = client.wait_for_boot(boot_reason=2, timeout_s=5)

        assert result["bootReason"] == "Fuota"

    def test_boot_reason_none_accepts_any(self):
        """boot_reason=None accepts any boot reason."""
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        client._baseline = {"bootInfo": {"recordId": 1}}
        boot_data = {"recordId": 5, "bootReason": "Exception"}

        with patch.object(client, "_fetch_status",
                          return_value={"bootInfo": boot_data}), \
             patch("corekinect.test.cloud_client.time.sleep"):
            result = client.wait_for_boot(boot_reason=None, timeout_s=5)

        assert result["bootReason"] == "Exception"


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    """Tests for the get_status() passthrough."""

    def test_returns_fetch_result(self):
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        status = {"bootInfo": {"recordId": 1}}
        with patch.object(client, "_fetch_status", return_value=status):
            assert client.get_status() == status

    def test_returns_none_when_unavailable(self):
        client = CloudClient(device_id=0x70B3D584C01E1FCC)
        with patch.object(client, "_fetch_status", return_value=None):
            assert client.get_status() is None
