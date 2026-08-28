"""Unit tests for CoreCloud typed response models.

Tests from_api() parsing, to_api() round-tripping, default construction,
edge cases (empty data, missing keys, None), and computed properties.
"""

import pytest

from corekinect.core_cloud.models import (
    BootInfo,
    CommsHwFailInfo,
    DeviceInfo,
    DeviceStatus,
    FuotaAssignResult,
    FuotaDeviceSettings,
    FuotaPlan,
    FuotaProgress,
    FuotaStage,
    GroundModeConfig,
    HwFailInfo,
    PositionInfo,
    RegistrationResult,
)


# ═══════════════════════════════════════════════════════════════════════════
# BootInfo
# ═══════════════════════════════════════════════════════════════════════════


class TestBootInfo:
    """Tests for BootInfo."""
    def test_from_api_full(self):
        """Test from api full."""
        data = {
            "recordId": 42,
            "timeOfBoot": "2026-03-11T12:00:00Z",
            "bootReason": "Normal",
        }
        info = BootInfo.from_api(data)
        assert info.record_id == 42
        assert info.time_of_boot == "2026-03-11T12:00:00Z"
        assert info.boot_reason == "Normal"

    def test_from_api_empty(self):
        """Test from api empty."""
        info = BootInfo.from_api({})
        assert info.record_id == 0
        assert info.time_of_boot == ""
        assert info.boot_reason == ""

    def test_from_api_none(self):
        """Test from api none."""
        info = BootInfo.from_api(None)
        assert info.record_id == 0

    def test_from_api_partial(self):
        """Test from api partial."""
        info = BootInfo.from_api({"recordId": 10})
        assert info.record_id == 10
        assert info.time_of_boot == ""
        assert info.boot_reason == ""

    def test_to_api_round_trip(self):
        """Test to api round trip."""
        original = {"recordId": 5, "timeOfBoot": "2026-01-01", "bootReason": "Fuota"}
        info = BootInfo.from_api(original)
        assert info.to_api() == original

    def test_default_constructor(self):
        """Test default constructor."""
        info = BootInfo()
        assert info.record_id == 0
        assert info.time_of_boot == ""
        assert info.boot_reason == ""


# ═══════════════════════════════════════════════════════════════════════════
# PositionInfo
# ═══════════════════════════════════════════════════════════════════════════


class TestPositionInfo:
    """Tests for PositionInfo."""
    def test_from_api_full(self):
        """Test from api full."""
        data = {
            "recordId": 100,
            "timeOfFix": "2026-03-11T14:30:00Z",
            "latitude": 43.6532,
            "longitude": -79.3832,
            "gpsAltitude": 150.5,
            "horizontalAccuracy": 10,
            "verticalAccuracy": 15,
            "battPercent": 85,
            "battVoltage": 4.2,
            "updateReason": "Heartbeat Message",
            "isInMotion": True,
            "numSat": 8,
            "groundSpeed": 5,
            "heading": 180,
            "temperature": 22.5,
            "onCharger": False,
        }
        pos = PositionInfo.from_api(data)
        assert pos.record_id == 100
        assert pos.latitude == 43.6532
        assert pos.longitude == -79.3832
        assert pos.gps_altitude == 150.5
        assert pos.horizontal_accuracy == 10
        assert pos.vertical_accuracy == 15
        assert pos.batt_percent == 85
        assert pos.batt_voltage == 4.2
        assert pos.update_reason == "Heartbeat Message"
        assert pos.is_in_motion is True
        assert pos.num_sat == 8
        assert pos.ground_speed == 5
        assert pos.heading == 180
        assert pos.temperature == 22.5
        assert pos.on_charger is False

    def test_from_api_empty(self):
        """Test from api empty."""
        pos = PositionInfo.from_api({})
        assert pos.latitude == 0.0
        assert pos.longitude == 0.0

    def test_from_api_none(self):
        """Test from api none."""
        pos = PositionInfo.from_api(None)
        assert pos.record_id == 0

    def test_to_api_round_trip(self):
        """Test to api round trip."""
        data = {
            "recordId": 7,
            "timeOfFix": "2026-01-01",
            "latitude": 40.0,
            "longitude": -74.0,
            "gpsAltitude": 100.0,
            "horizontalAccuracy": 5,
            "verticalAccuracy": 10,
            "battPercent": 90,
            "battVoltage": 4.1,
            "updateReason": "Stop Motion Event",
            "isInMotion": False,
            "numSat": 12,
            "groundSpeed": 0,
            "heading": 0,
            "temperature": 25.0,
            "onCharger": True,
        }
        pos = PositionInfo.from_api(data)
        assert pos.to_api() == data


# ═══════════════════════════════════════════════════════════════════════════
# HwFailInfo
# ═══════════════════════════════════════════════════════════════════════════


class TestHwFailInfo:
    """Tests for HwFailInfo."""
    def test_from_api_full(self):
        """Test from api full."""
        data = {
            "recordId": 1,
            "timeOfEvent": "2026-03-10",
            "xlrFails": 128,
            "altFails": 0,
            "gpsFails": 64,
            "bmsFails": 0,
            "extFlashFails": 0,
            "battChargerFails": 0,
            "ppgFails": 0,
            "imuFails": 0,
            "irFails": 0,
        }
        info = HwFailInfo.from_api(data)
        assert info.xlr_fails == 128
        assert info.gps_fails == 64
        assert info.alt_fails == 0

    def test_has_failures_true(self):
        """Test has failures true."""
        info = HwFailInfo(gps_fails=1)
        assert info.has_failures is True

    def test_has_failures_false(self):
        """Test has failures false."""
        info = HwFailInfo()
        assert info.has_failures is False

    def test_has_failures_multiple(self):
        """Test has failures multiple."""
        info = HwFailInfo(xlr_fails=128, gps_fails=64, ppg_fails=1)
        assert info.has_failures is True

    def test_from_api_empty(self):
        """Test from api empty."""
        info = HwFailInfo.from_api({})
        assert info.has_failures is False

    def test_from_api_none(self):
        """Test from api none."""
        info = HwFailInfo.from_api(None)
        assert info.has_failures is False

    def test_to_api_round_trip(self):
        """Test to api round trip."""
        data = {
            "recordId": 5,
            "timeOfEvent": "2026-03-10",
            "xlrFails": 128,
            "altFails": 0,
            "gpsFails": 0,
            "bmsFails": 0,
            "extFlashFails": 0,
            "battChargerFails": 0,
            "ppgFails": 0,
            "imuFails": 0,
            "irFails": 0,
        }
        info = HwFailInfo.from_api(data)
        assert info.to_api() == data


# ═══════════════════════════════════════════════════════════════════════════
# CommsHwFailInfo
# ═══════════════════════════════════════════════════════════════════════════


class TestCommsHwFailInfo:
    """Tests for CommsHwFailInfo."""
    def test_from_api_full(self):
        """Test from api full."""
        data = {
            "recordId": 3,
            "timeOfEvent": "2026-03-10",
            "simFails": 0,
            "loraFails": 128,
            "ipcFails": 0,
            "extFlashFails": 0,
            "secElemFails": 0,
            "satModemFails": 0,
        }
        info = CommsHwFailInfo.from_api(data)
        assert info.lora_fails == 128
        assert info.sim_fails == 0

    def test_has_failures_true(self):
        """Test has failures true."""
        info = CommsHwFailInfo(sim_fails=1)
        assert info.has_failures is True

    def test_has_failures_false(self):
        """Test has failures false."""
        info = CommsHwFailInfo()
        assert info.has_failures is False

    def test_from_api_none(self):
        """Test from api none."""
        info = CommsHwFailInfo.from_api(None)
        assert info.has_failures is False

    def test_to_api_round_trip(self):
        """Test to api round trip."""
        data = {
            "recordId": 1,
            "timeOfEvent": "2026-03-10",
            "simFails": 0,
            "loraFails": 0,
            "ipcFails": 0,
            "extFlashFails": 128,
            "secElemFails": 0,
            "satModemFails": 0,
        }
        info = CommsHwFailInfo.from_api(data)
        assert info.to_api() == data


# ═══════════════════════════════════════════════════════════════════════════
# DeviceStatus
# ═══════════════════════════════════════════════════════════════════════════


class TestDeviceStatus:
    """Tests for DeviceStatus."""
    def test_from_api_full(self):
        """Test from api full."""
        data = {
            "deviceId": "70B3D584C01E1FCC",
            "bootInfo": {
                "recordId": 42,
                "timeOfBoot": "2026-03-11T12:00:00Z",
                "bootReason": "Normal",
            },
            "positionInfo": {
                "recordId": 100,
                "timeOfFix": "2026-03-11T14:30:00Z",
                "latitude": 43.6532,
                "longitude": -79.3832,
            },
            "appHwFailInfo": {
                "recordId": 1,
                "xlrFails": 0,
                "gpsFails": 0,
            },
            "commsHwFailInfo": {
                "recordId": 2,
                "simFails": 0,
            },
        }
        status = DeviceStatus.from_api(data)
        assert status.device_id == "70B3D584C01E1FCC"
        assert status.boot_info is not None
        assert status.boot_info.record_id == 42
        assert status.boot_info.boot_reason == "Normal"
        assert status.position_info is not None
        assert status.position_info.latitude == 43.6532
        assert status.app_hw_fail_info is not None
        assert status.comms_hw_fail_info is not None

    def test_from_api_partial_no_boot(self):
        """Test from api partial no boot."""
        data = {
            "deviceId": "ABC",
            "positionInfo": {"recordId": 5, "latitude": 40.0},
        }
        status = DeviceStatus.from_api(data)
        assert status.device_id == "ABC"
        assert status.boot_info is None
        assert status.position_info is not None
        assert status.position_info.latitude == 40.0
        assert status.app_hw_fail_info is None
        assert status.comms_hw_fail_info is None

    def test_from_api_empty(self):
        """Test from api empty."""
        status = DeviceStatus.from_api({})
        assert status.device_id == ""
        assert status.boot_info is None
        assert status.position_info is None

    def test_from_api_none(self):
        """Test from api none."""
        status = DeviceStatus.from_api(None)
        assert status.device_id == ""


# ═══════════════════════════════════════════════════════════════════════════
# DeviceInfo
# ═══════════════════════════════════════════════════════════════════════════


class TestDeviceInfo:
    """Tests for DeviceInfo."""
    def test_from_api_full(self):
        """Test from api full."""
        data = {
            "deviceId": "70B3D584C01E1FCC",
            "deviceType": 2,
            "deviceVariantId": 3,
            "isActive": True,
        }
        info = DeviceInfo.from_api(data)
        assert info.device_id == "70B3D584C01E1FCC"
        assert info.device_type == 2
        assert info.device_variant_id == 3
        assert info.is_active is True

    def test_from_api_empty(self):
        """Test from api empty."""
        info = DeviceInfo.from_api({})
        assert info.device_id == ""
        assert info.device_type == 0
        assert info.is_active is False

    def test_from_api_none(self):
        """Test from api none."""
        info = DeviceInfo.from_api(None)
        assert info.device_id == ""


# ═══════════════════════════════════════════════════════════════════════════
# GroundModeConfig
# ═══════════════════════════════════════════════════════════════════════════


class TestGroundModeConfig:
    """Tests for GroundModeConfig."""
    FULL_API_DATA = {
        "deviceId": "70B3D584C01E1FCC",
        "gpsHeartbeatPeriod": 60,
        "continuousMotionPeriod": 300,
        "stopMotionTimeout": 30,
        "heartbeatAcquisitionTimeout": 60,
        "motionAcquisitionTimeout": 30,
        "motionAcquisitionOnTime": 30,
        "motionInitialAcquisitionOnTime": 60,
        "xlrMotionThreshold": 29,
        "xlrMotionDuration": 2,
        "startMotionWindowStart": 3,
        "startMotionWindowEnd": 10,
    }

    def test_from_api_full(self):
        """Test from api full."""
        config = GroundModeConfig.from_api(self.FULL_API_DATA)
        assert config.device_id == "70B3D584C01E1FCC"
        assert config.gps_heartbeat_period == 60
        assert config.continuous_motion_period == 300
        assert config.stop_motion_timeout == 30
        assert config.heartbeat_acquisition_timeout == 60
        assert config.motion_acquisition_timeout == 30
        assert config.motion_acquisition_on_time == 30
        assert config.motion_initial_acquisition_on_time == 60
        assert config.xlr_motion_threshold == 29
        assert config.xlr_motion_duration == 2
        assert config.start_motion_window_start == 3
        assert config.start_motion_window_end == 10

    def test_from_api_empty(self):
        """Test from api empty."""
        config = GroundModeConfig.from_api({})
        assert config.device_id == ""
        assert config.gps_heartbeat_period == 0

    def test_from_api_none(self):
        """Test from api none."""
        config = GroundModeConfig.from_api(None)
        assert config.gps_heartbeat_period == 0

    def test_from_api_partial(self):
        """Test from api partial."""
        config = GroundModeConfig.from_api({"gpsHeartbeatPeriod": 120})
        assert config.gps_heartbeat_period == 120
        assert config.stop_motion_timeout == 0

    def test_to_api_round_trip(self):
        """Test to api round trip."""
        config = GroundModeConfig.from_api(self.FULL_API_DATA)
        assert config.to_api() == self.FULL_API_DATA

    def test_with_updates_single_field(self):
        """Test with updates single field."""
        config = GroundModeConfig.from_api(self.FULL_API_DATA)
        updated = config.with_updates(gps_heartbeat_period=120)
        assert updated.gps_heartbeat_period == 120
        # Other fields unchanged
        assert updated.stop_motion_timeout == 30
        assert updated.device_id == "70B3D584C01E1FCC"

    def test_with_updates_multiple_fields(self):
        """Test with updates multiple fields."""
        config = GroundModeConfig.from_api(self.FULL_API_DATA)
        updated = config.with_updates(
            gps_heartbeat_period=120,
            stop_motion_timeout=60,
            xlr_motion_threshold=50,
        )
        assert updated.gps_heartbeat_period == 120
        assert updated.stop_motion_timeout == 60
        assert updated.xlr_motion_threshold == 50
        # Unchanged
        assert updated.continuous_motion_period == 300

    def test_with_updates_returns_new_instance(self):
        """Test with updates returns new instance."""
        config = GroundModeConfig.from_api(self.FULL_API_DATA)
        updated = config.with_updates(gps_heartbeat_period=120)
        # Original unchanged
        assert config.gps_heartbeat_period == 60
        assert updated is not config

    def test_to_api_includes_device_id(self):
        """Test to api includes device id."""
        config = GroundModeConfig(device_id="ABC", gps_heartbeat_period=60)
        payload = config.to_api()
        assert payload["deviceId"] == "ABC"
        assert payload["gpsHeartbeatPeriod"] == 60

    def test_default_constructor(self):
        """Test default constructor."""
        config = GroundModeConfig()
        assert config.device_id == ""
        assert config.gps_heartbeat_period == 0


# ═══════════════════════════════════════════════════════════════════════════
# FuotaStage
# ═══════════════════════════════════════════════════════════════════════════


class TestFuotaStage:
    """Tests for FuotaStage."""
    def test_from_api_full(self):
        """Test from api full."""
        data = {
            "targets": ["108.0.8.2-BMD", "109.0.8.2-BMD"],
            "description": "Stage 1: target firmware",
            "isSkippable": False,
        }
        stage = FuotaStage.from_api(data)
        assert stage.targets == ["108.0.8.2-BMD", "109.0.8.2-BMD"]
        assert stage.description == "Stage 1: target firmware"
        assert stage.is_skippable is False

    def test_from_api_empty(self):
        """Test from api empty."""
        stage = FuotaStage.from_api({})
        assert stage.targets == []
        assert stage.description == ""
        assert stage.is_skippable is False

    def test_from_api_none(self):
        """Test from api none."""
        stage = FuotaStage.from_api(None)
        assert stage.targets == []

    def test_to_api_round_trip(self):
        """Test to api round trip."""
        data = {
            "targets": ["108.0.5.0-BM"],
            "description": "From",
            "isSkippable": True,
        }
        stage = FuotaStage.from_api(data)
        assert stage.to_api() == data

    def test_constructor(self):
        """Test constructor."""
        stage = FuotaStage(
            targets=["108.0.8.2-BMD"],
            description="test stage",
            is_skippable=True,
        )
        assert stage.targets == ["108.0.8.2-BMD"]
        assert stage.to_api()["isSkippable"] is True


# ═══════════════════════════════════════════════════════════════════════════
# FuotaPlan
# ═══════════════════════════════════════════════════════════════════════════


class TestFuotaPlan:
    """Tests for FuotaPlan."""
    def test_from_api_full(self):
        """Test from api full."""
        data = {
            "planId": 42,
            "description": "Alpha B0 v0.5.1 -> v0.5.2",
            "deviceTypeId": 2,
            "deviceVariantId": 3,
            "stages": [
                {"targets": ["108.0.5.1-BM"], "description": "From", "isSkippable": False},
                {"targets": ["108.0.5.2-BM"], "description": "To", "isSkippable": False},
            ],
        }
        plan = FuotaPlan.from_api(data)
        assert plan.plan_id == 42
        assert plan.description == "Alpha B0 v0.5.1 -> v0.5.2"
        assert plan.device_type_id == 2
        assert plan.device_variant_id == 3
        assert len(plan.stages) == 2
        assert plan.stages[0].targets == ["108.0.5.1-BM"]
        assert plan.stages[1].targets == ["108.0.5.2-BM"]

    def test_from_api_no_stages(self):
        """Test from api no stages."""
        data = {"planId": 1, "description": "empty"}
        plan = FuotaPlan.from_api(data)
        assert plan.plan_id == 1
        assert plan.stages == []

    def test_from_api_empty(self):
        """Test from api empty."""
        plan = FuotaPlan.from_api({})
        assert plan.plan_id == 0

    def test_from_api_none(self):
        """Test from api none."""
        plan = FuotaPlan.from_api(None)
        assert plan.plan_id == 0
        assert plan.stages == []


# ═══════════════════════════════════════════════════════════════════════════
# FuotaProgress
# ═══════════════════════════════════════════════════════════════════════════


class TestFuotaProgress:
    """Tests for FuotaProgress."""
    def test_from_api_full(self):
        """Test from api full."""
        data = {
            "deviceId": "70B3D584C01E1FCC",
            "version": "108.0.5.2-BM",
            "percentComplete": 75,
            "pagesApplied": 19792,
            "totalPages": 26389,
            "timeStarted": "2026-03-11T06:30:00Z",
            "lastUpdated": "2026-03-11T06:40:00Z",
        }
        progress = FuotaProgress.from_api(data)
        assert progress.device_id == "70B3D584C01E1FCC"
        assert progress.version == "108.0.5.2-BM"
        assert progress.percent_complete == 75
        assert progress.pages_applied == 19792
        assert progress.total_pages == 26389
        assert progress.is_complete is False

    def test_is_complete_true(self):
        """Test is complete true."""
        progress = FuotaProgress(percent_complete=100, pages_applied=26389, total_pages=26389)
        assert progress.is_complete is True

    def test_is_complete_false(self):
        """Test is complete false."""
        progress = FuotaProgress(percent_complete=50)
        assert progress.is_complete is False

    def test_is_complete_over_100(self):
        """Edge case: percent_complete > 100 still counts as complete."""
        progress = FuotaProgress(percent_complete=101)
        assert progress.is_complete is True

    def test_from_api_empty(self):
        """Test from api empty."""
        progress = FuotaProgress.from_api({})
        assert progress.percent_complete == 0
        assert progress.is_complete is False

    def test_from_api_none(self):
        """Test from api none."""
        progress = FuotaProgress.from_api(None)
        assert progress.device_id == ""


# ═══════════════════════════════════════════════════════════════════════════
# FuotaDeviceSettings
# ═══════════════════════════════════════════════════════════════════════════


class TestFuotaDeviceSettings:
    """Tests for FuotaDeviceSettings."""
    def test_from_api_full(self):
        """Test from api full."""
        data = {
            "deviceId": "70B3D584C01E1FCC",
            "planId": 42,
            "enableFuota": True,
            "maxStage": 1,
        }
        settings = FuotaDeviceSettings.from_api(data)
        assert settings.device_id == "70B3D584C01E1FCC"
        assert settings.plan_id == 42
        assert settings.enable_fuota is True
        assert settings.max_stage == 1

    def test_from_api_empty(self):
        """Test from api empty."""
        settings = FuotaDeviceSettings.from_api({})
        assert settings.plan_id == 0
        assert settings.enable_fuota is False

    def test_from_api_none(self):
        """Test from api none."""
        settings = FuotaDeviceSettings.from_api(None)
        assert settings.device_id == ""


# ═══════════════════════════════════════════════════════════════════════════
# FuotaAssignResult
# ═══════════════════════════════════════════════════════════════════════════


class TestFuotaAssignResult:
    """Tests for FuotaAssignResult."""
    def test_from_api_full(self):
        """Test from api full."""
        data = {"numDevicesUpdated": 3}
        result = FuotaAssignResult.from_api(data)
        assert result.num_devices_updated == 3

    def test_from_api_empty(self):
        """Test from api empty."""
        result = FuotaAssignResult.from_api({})
        assert result.num_devices_updated == 0

    def test_from_api_none(self):
        """Test from api none."""
        result = FuotaAssignResult.from_api(None)
        assert result.num_devices_updated == 0


# ═══════════════════════════════════════════════════════════════════════════
# RegistrationResult
# ═══════════════════════════════════════════════════════════════════════════


class TestRegistrationResult:
    """Tests for RegistrationResult."""
    def test_from_api_newly_registered(self):
        """Test from api newly registered."""
        data = {
            "registeredDevices": ["70B3D584C01E1FCC"],
            "devicesAlreadyRegistered": [],
        }
        result = RegistrationResult.from_api(data)
        assert result.registered_devices == ["70B3D584C01E1FCC"]
        assert result.already_registered == []
        assert result.any_newly_registered is True

    def test_from_api_already_registered(self):
        """Test from api already registered."""
        data = {
            "registeredDevices": [],
            "devicesAlreadyRegistered": ["70B3D584C01E1FCC"],
        }
        result = RegistrationResult.from_api(data)
        assert result.registered_devices == []
        assert result.already_registered == ["70B3D584C01E1FCC"]
        assert result.any_newly_registered is False

    def test_from_api_empty(self):
        """Test from api empty."""
        result = RegistrationResult.from_api({})
        assert result.registered_devices == []
        assert result.already_registered == []
        assert result.any_newly_registered is False

    def test_from_api_none(self):
        """Test from api none."""
        result = RegistrationResult.from_api(None)
        assert result.any_newly_registered is False

    def test_from_api_mixed(self):
        """Test from api mixed."""
        data = {
            "registeredDevices": ["AAA"],
            "devicesAlreadyRegistered": ["BBB"],
        }
        result = RegistrationResult.from_api(data)
        assert result.any_newly_registered is True
        assert len(result.registered_devices) == 1
        assert len(result.already_registered) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Cross-model: DeviceStatus with nested sub-models
# ═══════════════════════════════════════════════════════════════════════════


class TestDeviceStatusNested:
    """Test DeviceStatus parsing with realistic nested API responses."""

    def test_realistic_api_response(self):
        """Parse a realistic full API response matching what CoreCloud returns."""
        api_response = {
            "deviceId": "70B3D584C01E1FCC",
            "bootInfo": {
                "recordId": 1234,
                "timeOfBoot": "2026-03-11T06:22:00Z",
                "bootReason": "Normal",
            },
            "positionInfo": {
                "recordId": 5678,
                "timeOfFix": "2026-03-11T06:25:00Z",
                "latitude": 43.6532,
                "longitude": -79.3832,
                "gpsAltitude": 150.0,
                "horizontalAccuracy": 10,
                "verticalAccuracy": 15,
                "battPercent": 85,
                "battVoltage": 4.2,
                "updateReason": "Heartbeat Message",
                "isInMotion": False,
                "numSat": 8,
                "groundSpeed": 0,
                "heading": 0,
                "temperature": 22.5,
                "onCharger": False,
            },
            "appHwFailInfo": {
                "recordId": 10,
                "timeOfEvent": "2026-03-10T12:00:00Z",
                "xlrFails": 0,
                "altFails": 0,
                "gpsFails": 0,
                "bmsFails": 0,
                "extFlashFails": 0,
                "battChargerFails": 0,
                "ppgFails": 0,
                "imuFails": 0,
                "irFails": 0,
            },
            "commsHwFailInfo": {
                "recordId": 11,
                "timeOfEvent": "2026-03-10T12:00:00Z",
                "simFails": 0,
                "loraFails": 0,
                "ipcFails": 0,
                "extFlashFails": 0,
                "secElemFails": 0,
                "satModemFails": 0,
            },
        }

        status = DeviceStatus.from_api(api_response)

        # Top level
        assert status.device_id == "70B3D584C01E1FCC"

        # Boot
        assert status.boot_info.record_id == 1234
        assert status.boot_info.boot_reason == "Normal"

        # Position
        assert status.position_info.latitude == 43.6532
        assert status.position_info.batt_percent == 85
        assert status.position_info.is_in_motion is False

        # HW failures -- no failures
        assert status.app_hw_fail_info.has_failures is False
        assert status.comms_hw_fail_info.has_failures is False

    def test_device_with_hw_failures(self):
        """Verify has_failures detects non-zero counters."""
        api_response = {
            "deviceId": "70B3D584C01E1FCC",
            "appHwFailInfo": {
                "recordId": 99,
                "timeOfEvent": "2026-03-10T12:00:00Z",
                "xlrFails": 128,
                "gpsFails": 64,
            },
        }
        status = DeviceStatus.from_api(api_response)
        assert status.app_hw_fail_info.has_failures is True
        assert status.app_hw_fail_info.xlr_fails == 128
        assert status.app_hw_fail_info.gps_fails == 64

    def test_multiple_devices_from_api_list(self):
        """Parse multiple devices from a Search/Status response."""
        api_devices = [
            {"deviceId": "AAA", "bootInfo": {"recordId": 1, "bootReason": "Normal"}},
            {"deviceId": "BBB", "bootInfo": {"recordId": 2, "bootReason": "Fuota"}},
        ]
        statuses = [DeviceStatus.from_api(d) for d in api_devices]
        assert len(statuses) == 2
        assert statuses[0].device_id == "AAA"
        assert statuses[0].boot_info.boot_reason == "Normal"
        assert statuses[1].device_id == "BBB"
        assert statuses[1].boot_info.boot_reason == "Fuota"


# ═══════════════════════════════════════════════════════════════════════════
# Cross-model: GroundModeConfig with_updates immutability
# ═══════════════════════════════════════════════════════════════════════════


class TestGroundModeConfigImmutability:
    """Verify with_updates creates independent instances."""

    def test_chained_updates(self):
        """Test chained updates."""
        base = GroundModeConfig(gps_heartbeat_period=60, stop_motion_timeout=30)
        v1 = base.with_updates(gps_heartbeat_period=120)
        v2 = v1.with_updates(stop_motion_timeout=60)

        assert base.gps_heartbeat_period == 60
        assert base.stop_motion_timeout == 30
        assert v1.gps_heartbeat_period == 120
        assert v1.stop_motion_timeout == 30
        assert v2.gps_heartbeat_period == 120
        assert v2.stop_motion_timeout == 60

    def test_update_to_same_value(self):
        """Test update to same value."""
        config = GroundModeConfig(gps_heartbeat_period=60)
        updated = config.with_updates(gps_heartbeat_period=60)
        assert updated is not config
        assert updated.gps_heartbeat_period == 60


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases: extra keys, wrong types, etc."""

    def test_extra_keys_ignored_by_from_api(self):
        """Unknown API keys should not crash from_api."""
        data = {
            "recordId": 1,
            "timeOfBoot": "2026-01-01",
            "bootReason": "Normal",
            "unknownField": "should be ignored",
            "anotherExtra": 999,
        }
        info = BootInfo.from_api(data)
        assert info.record_id == 1
        assert info.boot_reason == "Normal"

    def test_wrong_type_stored_as_is(self):
        """If API returns a string where int is expected, we store it as-is.

        Models are lenient -- they trust the API shape but don't crash
        on type mismatches. Validation is the caller's responsibility.
        """
        data = {"recordId": "not_an_int", "bootReason": "Normal"}
        info = BootInfo.from_api(data)
        assert info.record_id == "not_an_int"

    def test_fuota_progress_zero_total_pages(self):
        """Zero total_pages should not cause division errors."""
        progress = FuotaProgress(total_pages=0, pages_applied=0, percent_complete=0)
        assert progress.is_complete is False

    def test_registration_result_multiple_devices(self):
        """Test registration result multiple devices."""
        data = {
            "registeredDevices": ["AAA", "BBB", "CCC"],
            "devicesAlreadyRegistered": ["DDD"],
        }
        result = RegistrationResult.from_api(data)
        assert len(result.registered_devices) == 3
        assert len(result.already_registered) == 1
        assert result.any_newly_registered is True
