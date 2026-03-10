"""Tests for API-based fixture profile loading.

Tests the FixtureProfile.from_api() method and TestContext.from_env()
integration with API-based profile fetching.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from corekinect.test.validation.profiles import (
    Capability,
    FixtureProfile,
    PowerConfig,
    DutConfig,
)
from corekinect.test.validation.test_context import TestContext


class TestFixtureProfileFromApi:
    """Tests for FixtureProfile.from_api()."""

    @pytest.fixture
    def sample_profile_data(self) -> dict:
        """Sample profile data as returned by API."""
        return {
            "station_id": "station-33",
            "product": "alpha",
            "board": "alpha_b0",
            "mtib_revision": "1.2",
            "capabilities": ["button", "peltier"],
            "power": {
                "battery_installed": False,
                "dut_voltage": 4.5,
                "charger_voltage": 5.0,
                "boot_settle_s": 10.0,
            },
            "dut": {
                "device_id": "70B3D584C01E1FCC",
                "snr": "0964",
                "imei": "355025931735979",
                "iccids": ["89148000009808558441"],
            },
            "button": {
                "gpio_pin": 2,
                "active_low": True,
            },
        }

    def test_from_api_success_by_bench_id(self, sample_profile_data):
        """Successfully load profile by bench ID (CUID)."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": sample_profile_data}

        with patch("requests.get", return_value=mock_response) as mock_get:
            profile = FixtureProfile.from_api(
                bench_id="cmmgsdsnh0001sktijmewtmwg",
                api_url="https://staging.concord.local",
                api_key="ck_run_test_abc123",
            )

            # Verify API call
            mock_get.assert_called_once_with(
                "https://staging.concord.local/v2/validation/benches/cmmgsdsnh0001sktijmewtmwg/profile",
                headers={"Authorization": "Bearer ck_run_test_abc123"},
                timeout=30,
            )

            # Verify parsed profile
            assert profile.station_id == "station-33"
            assert profile.product == "alpha"
            assert profile.has_capability(Capability.BUTTON)
            assert profile.has_capability(Capability.PELTIER)
            assert profile.dut.device_id == "70B3D584C01E1FCC"
            assert profile.dut.snr == "0964"

    def test_from_api_fallback_to_station_id(self, sample_profile_data):
        """Falls back to station_id lookup when bench ID returns 404."""
        # First call (by ID) returns 404
        mock_404_response = MagicMock()
        mock_404_response.ok = False
        mock_404_response.status_code = 404

        # Second call (list by station_id) returns bench
        mock_list_response = MagicMock()
        mock_list_response.ok = True
        mock_list_response.json.return_value = {
            "data": [{"id": "cmmgsdsnh0001sktijmewtmwg", "stationId": "station-33"}]
        }

        # Third call (get profile by resolved ID) returns profile
        mock_profile_response = MagicMock()
        mock_profile_response.ok = True
        mock_profile_response.status_code = 200
        mock_profile_response.json.return_value = {"data": sample_profile_data}

        with patch("requests.get") as mock_get:
            mock_get.side_effect = [
                mock_404_response,
                mock_list_response,
                mock_profile_response,
            ]

            profile = FixtureProfile.from_api(
                bench_id="station-33",  # Using station_id, not CUID
                api_url="https://staging.concord.local",
                api_key="ck_run_test_abc123",
            )

            # Verify all three API calls
            assert mock_get.call_count == 3

            # First call: try by ID
            assert mock_get.call_args_list[0][0][0].endswith("/station-33/profile")

            # Second call: lookup by station_id
            assert mock_get.call_args_list[1][1]["params"] == {"station_id": "station-33"}

            # Third call: get profile by resolved ID
            assert "cmmgsdsnh0001sktijmewtmwg/profile" in mock_get.call_args_list[2][0][0]

            # Verify parsed profile
            assert profile.station_id == "station-33"

    def test_from_api_failure_raises_value_error(self):
        """Raises ValueError when API request fails."""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("requests.get", return_value=mock_response):
            with pytest.raises(ValueError) as exc_info:
                FixtureProfile.from_api(
                    bench_id="invalid-id",
                    api_url="https://staging.concord.local",
                    api_key="ck_run_test_abc123",
                )

            assert "500" in str(exc_info.value)
            assert "Internal Server Error" in str(exc_info.value)

    def test_from_api_bench_not_found(self):
        """Raises ValueError when bench is not found by ID or station_id."""
        # First call (by ID) returns 404
        mock_404_response = MagicMock()
        mock_404_response.ok = False
        mock_404_response.status_code = 404
        mock_404_response.text = "Not found"

        # Second call (station_id lookup) returns empty list
        mock_empty_response = MagicMock()
        mock_empty_response.ok = True
        mock_empty_response.json.return_value = {"data": []}

        with patch("requests.get") as mock_get:
            # First call returns 404, second returns empty list
            # Since list is empty, we keep the 404 response and raise
            mock_get.side_effect = [mock_404_response, mock_empty_response]

            with pytest.raises(ValueError) as exc_info:
                FixtureProfile.from_api(
                    bench_id="nonexistent",
                    api_url="https://staging.concord.local",
                    api_key="ck_run_test_abc123",
                )

            assert "404" in str(exc_info.value)

    def test_from_api_normalizes_url(self, sample_profile_data):
        """API URL is normalized (trailing slash removed)."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": sample_profile_data}

        with patch("requests.get", return_value=mock_response) as mock_get:
            FixtureProfile.from_api(
                bench_id="bench-123",
                api_url="https://staging.concord.local/",  # With trailing slash
                api_key="ck_run_test_abc123",
            )

            # Should NOT have double slash
            called_url = mock_get.call_args[0][0]
            assert "//" not in called_url.replace("https://", "")

    def test_from_api_handles_flat_response(self, sample_profile_data):
        """Handles API responses where data is at root (no 'data' wrapper)."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = sample_profile_data  # No "data" wrapper

        with patch("requests.get", return_value=mock_response):
            profile = FixtureProfile.from_api(
                bench_id="bench-123",
                api_url="https://staging.concord.local",
                api_key="ck_run_test_abc123",
            )

            assert profile.station_id == "station-33"


class TestTestContextFromEnv:
    """Tests for TestContext.from_env() profile loading modes."""

    @pytest.fixture
    def sample_profile_data(self) -> dict:
        """Sample profile data."""
        return {
            "station_id": "test-station",
            "product": "alpha",
            "board": "alpha_b0",
            "mtib_revision": "1.2",
            "capabilities": ["button"],
            "power": {"battery_installed": False},
            "dut": {"device_id": "ABC123", "snr": "0001"},
        }

    @pytest.fixture
    def base_env(self):
        """Base environment variables required for TestContext."""
        return {
            "MTIB_ADDRESS": "10.4.45.33:50053",
            "DEVICE_ID": "70B3D584C01E1FCC",
            "CORECLOUD_DB_ENV": "DEV_1_0",
        }

    def test_from_env_prefers_api_over_file(self, base_env, sample_profile_data):
        """API mode takes precedence when all API env vars are set."""
        env = {
            **base_env,
            "BENCH_ID": "bench-123",
            "CONCORD_API_URL": "https://staging.concord.local",
            "CONCORD_API_KEY": "ck_run_test_abc123",
            "FIXTURE_PROFILE_PATH": "/path/to/file.json",  # Should be ignored
        }

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": sample_profile_data}

        with patch.dict(os.environ, env, clear=True):
            with patch("requests.get", return_value=mock_response) as mock_get:
                # Mock the MtibV1Client to avoid actual gRPC setup
                with patch("corekinect.test.validation.test_context.MtibV1Client"):
                    with patch("corekinect.test.validation.test_context.CloudClient"):
                        with patch("corekinect.test.validation.test_context.FixtureController"):
                            with patch("corekinect.test.validation.test_context.UartDemuxer"):
                                with patch("corekinect.test.validation.test_context.PowerProfiler"):
                                    ctx = TestContext.from_env()

                # Verify API was called (not file)
                mock_get.assert_called()
                assert "bench-123" in mock_get.call_args[0][0]

    def test_from_env_falls_back_to_file(self, base_env, sample_profile_data):
        """Falls back to file loading when API env vars are missing."""
        # Write temp profile file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_profile_data, f)
            profile_path = f.name

        try:
            env = {
                **base_env,
                "FIXTURE_PROFILE_PATH": profile_path,
                # No BENCH_ID, CONCORD_API_URL, CONCORD_API_KEY
            }

            with patch.dict(os.environ, env, clear=True):
                # Mock the MTIB and other components
                with patch("corekinect.test.validation.test_context.MtibV1Client"):
                    with patch("corekinect.test.validation.test_context.CloudClient"):
                        with patch("corekinect.test.validation.test_context.FixtureController"):
                            with patch("corekinect.test.validation.test_context.UartDemuxer"):
                                with patch("corekinect.test.validation.test_context.PowerProfiler"):
                                    ctx = TestContext.from_env()

                # Should have loaded from file
                assert ctx.fixture is not None
        finally:
            os.unlink(profile_path)

    def test_from_env_requires_api_key_for_api_mode(self, base_env):
        """API mode requires all three env vars: BENCH_ID, API_URL, API_KEY."""
        env = {
            **base_env,
            "BENCH_ID": "bench-123",
            "CONCORD_API_URL": "https://staging.concord.local",
            # Missing CONCORD_API_KEY
        }

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError) as exc_info:
                TestContext.from_env()

            assert "FIXTURE_PROFILE_PATH" in str(exc_info.value)

    def test_from_env_missing_all_profile_sources(self, base_env):
        """Raises ValueError when neither API nor file config is provided."""
        with patch.dict(os.environ, base_env, clear=True):
            with pytest.raises(ValueError) as exc_info:
                TestContext.from_env()

            assert "BENCH_ID" in str(exc_info.value)
            assert "FIXTURE_PROFILE_PATH" in str(exc_info.value)

    def test_from_env_partial_api_config_falls_back_to_file_error(self, base_env):
        """Partial API config (missing one var) falls back to file mode."""
        env = {
            **base_env,
            "BENCH_ID": "bench-123",
            # Missing CONCORD_API_URL and CONCORD_API_KEY
        }

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError) as exc_info:
                TestContext.from_env()

            # Should fail because file path not set either
            assert "FIXTURE_PROFILE_PATH" in str(exc_info.value)
