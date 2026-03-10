"""Integration tests for the test bench profile endpoint."""

import json
from datetime import datetime, timezone

from tests.conftest import make_obj


NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_design(**overrides):
    """Create a mock FixtureDesign object."""
    defaults = dict(
        id="design-1",
        name="alpha-fixture-v1.2",
        product="alpha",
        revision="1.2",
        capabilities=["button", "peltier", "charger_relay"],
        profileTemplate={
            "battery_installed": False,
            "power_channel": 0,
            "power_voltage_v": 4.5,
            "gpio": {
                "button": 2,
                "peltier": 4,
            },
        },
        schematicUrl=None,
        bomUrl=None,
        assemblyGuide=None,
        notes=None,
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


def _make_bench(**overrides):
    """Create a mock TestBench object."""
    defaults = dict(
        id="bench-1",
        stationId="station-33",
        name="Alpha B0 Bench 1",
        mtibAddress="10.4.45.33:50053",
        mtibRevision="REV1.2",
        fixtureDesignId="design-1",
        fixtureDesign=_make_design(),
        profileOverrides={
            "power_voltage_v": 4.6,  # Override the design default
            "custom_setting": "test",
        },
        capabilities=["button", "peltier", "charger_relay", "ppg_servo"],
        dutProduct="alpha",
        dutRevision="b0",
        dutDeviceId="70B3D584C01E1FCC",
        dutSnr="0964",
        dutImei="355025931735979",
        dutIccids=["89148000009808558441", "89457300000037582833"],
        jlinkAppSerial="821009546",
        jlinkCommsSerial="821009537",
        uartAppPath="/dev/verdin-uart2",
        uartCommsPath="/dev/verdin-uart1",
        status="AVAILABLE",
        lockedBy=None,
        lockedAt=None,
        lastHealthCheck=None,
        metadata=None,
        createdAt=NOW,
        updatedAt=NOW,
    )
    defaults.update(overrides)
    return make_obj(**defaults)


# ── Get Bench Profile ───────────────────────────────────────


def test_get_profile_returns_merged_data(authed_client, mock_db):
    """Test getting a bench profile returns merged design + overrides + DUT info."""
    bench = _make_bench()
    mock_db.testbench.find_unique.return_value = bench

    response = authed_client.get("/v2/validation/benches/bench-1/profile")
    assert response.status_code == 200

    data = json.loads(response.data)
    profile = data["data"]

    # Design template values should be present
    assert profile["battery_installed"] is False
    assert profile["power_channel"] == 0
    assert profile["gpio"]["button"] == 2
    assert profile["gpio"]["peltier"] == 4

    # Overridden values from bench should take precedence
    assert profile["power_voltage_v"] == 4.6  # Overridden from 4.5
    assert profile["custom_setting"] == "test"

    # DUT info should be injected
    assert profile["station_id"] == "station-33"
    assert profile["dut"]["device_id"] == "70B3D584C01E1FCC"
    assert profile["dut"]["snr"] == "0964"
    assert profile["dut"]["imei"] == "355025931735979"
    assert profile["dut"]["iccids"] == ["89148000009808558441", "89457300000037582833"]

    # Hardware paths should be injected
    assert profile["uart_app_path"] == "/dev/verdin-uart2"
    assert profile["uart_comms_path"] == "/dev/verdin-uart1"
    assert profile["jlink_app_serial"] == "821009546"
    assert profile["jlink_comms_serial"] == "821009537"

    # Capabilities from bench
    assert profile["capabilities"] == ["button", "peltier", "charger_relay", "ppg_servo"]


def test_get_profile_without_design_returns_bench_only(authed_client, mock_db):
    """Test getting a bench profile without fixture design returns bench data only."""
    bench = _make_bench(
        fixtureDesignId=None,
        fixtureDesign=None,
        profileOverrides={"standalone_config": True},
    )
    mock_db.testbench.find_unique.return_value = bench

    response = authed_client.get("/v2/validation/benches/bench-1/profile")
    assert response.status_code == 200

    data = json.loads(response.data)
    profile = data["data"]

    # No design template values
    assert "battery_installed" not in profile

    # Override values should still be present
    assert profile["standalone_config"] is True

    # DUT info should still be injected
    assert profile["station_id"] == "station-33"
    assert profile["dut"]["device_id"] == "70B3D584C01E1FCC"


def test_get_profile_without_design_or_overrides(authed_client, mock_db):
    """Test getting a bench profile with neither design nor overrides."""
    bench = _make_bench(
        fixtureDesignId=None,
        fixtureDesign=None,
        profileOverrides=None,
    )
    mock_db.testbench.find_unique.return_value = bench

    response = authed_client.get("/v2/validation/benches/bench-1/profile")
    assert response.status_code == 200

    data = json.loads(response.data)
    profile = data["data"]

    # Should have station_id and DUT info only
    assert profile["station_id"] == "station-33"
    assert profile["dut"]["device_id"] == "70B3D584C01E1FCC"


def test_get_profile_bench_not_found_returns_404(authed_client, mock_db):
    """Test getting profile for non-existent bench returns 404."""
    mock_db.testbench.find_unique.return_value = None

    response = authed_client.get("/v2/validation/benches/bad-id/profile")
    assert response.status_code == 404

    data = json.loads(response.data)
    assert "errors" in data
    assert len(data["errors"]) > 0


def test_get_profile_requires_auth(client):
    """Test getting profile without auth returns 401."""
    response = client.get("/v2/validation/benches/bench-1/profile")
    assert response.status_code == 401


def test_get_profile_deep_merges_nested_objects(authed_client, mock_db):
    """Test that nested objects in profile are deep merged, not replaced."""
    design = _make_design(
        profileTemplate={
            "gpio": {
                "button": 2,
                "peltier": 4,
                "charger_relay": 5,
            },
            "power": {
                "channel": 0,
                "voltage_v": 4.5,
            },
        }
    )
    bench = _make_bench(
        fixtureDesign=design,
        profileOverrides={
            "gpio": {
                "peltier": 7,  # Override just this one
            },
            "power": {
                "voltage_v": 4.6,  # Override voltage, keep channel
            },
        },
    )
    mock_db.testbench.find_unique.return_value = bench

    response = authed_client.get("/v2/validation/benches/bench-1/profile")
    assert response.status_code == 200

    data = json.loads(response.data)
    profile = data["data"]

    # Deep merge should preserve unmodified values
    assert profile["gpio"]["button"] == 2  # From design
    assert profile["gpio"]["peltier"] == 7  # Overridden
    assert profile["gpio"]["charger_relay"] == 5  # From design

    assert profile["power"]["channel"] == 0  # From design
    assert profile["power"]["voltage_v"] == 4.6  # Overridden


def test_get_profile_with_partial_dut_info(authed_client, mock_db):
    """Test getting profile when some DUT fields are missing."""
    bench = _make_bench(
        dutDeviceId="70B3D584C01E1FCC",
        dutSnr=None,
        dutImei=None,
        dutIccids=None,
    )
    mock_db.testbench.find_unique.return_value = bench

    response = authed_client.get("/v2/validation/benches/bench-1/profile")
    assert response.status_code == 200

    data = json.loads(response.data)
    profile = data["data"]

    # Should have device_id but not other DUT fields
    assert profile["dut"]["device_id"] == "70B3D584C01E1FCC"
    assert "snr" not in profile["dut"]
    assert "imei" not in profile["dut"]
    assert "iccids" not in profile["dut"]
