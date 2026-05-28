"""Unit tests for MtibV1Client gRPC methods.

Tests verify that each RPC method correctly calls the gRPC stub
and handles responses/errors properly.
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock

import grpc

from corekinect.mtib_client.v1.client.core import MtibV1Client, DEFAULT_GRPC_TIMEOUT_SECONDS
from corekinect.mtib_client.v1.client.config import NetConfig
from corekinect.mtib_client.v1.client.types import (
    GpioDirection,
    GpioResistorConfig,
    MotionStatus,
    PowerChannel,
    PowerReadResult,
    PowerMeasureResult,
    HealthCheckExtendedResponse,
    SnapshotResult,
)
from protocols.mtib.mtib_pb2 import FwFileInfo, HostType


def _make_client():
    """Create a MtibV1Client with a mocked stub and logger."""
    client = MtibV1Client(MtibV1Client.Config(net=NetConfig(addr="10.0.0.1", port=50051)))
    client.client = MagicMock()  # mock the gRPC stub
    client.logger = MagicMock()
    return client


def _make_rpc_error(details="server unavailable"):
    """Create a mock grpc.RpcError."""
    err = grpc.RpcError()
    err.details = MagicMock(return_value=details)
    # Make it a proper grpc.RpcError that can be caught
    return err


class TestConnect(unittest.TestCase):
    """Tests for connect/disconnect."""

    @patch("corekinect.mtib_client.v1.client.core.insecure_channel")
    @patch("corekinect.mtib_client.v1.client.core.MtibClientV1")
    def test_connect_success(self, mock_stub_cls, mock_channel):
        """Test connect success."""
        client = MtibV1Client(MtibV1Client.Config(net=NetConfig(addr="10.0.0.1", port=50051)))
        client.logger = MagicMock()

        mock_stub = MagicMock()
        mock_stub_cls.return_value = mock_stub

        # HealthCheck response
        health_resp = MagicMock()
        health_resp.ready = True
        health_resp.errors = []
        mock_stub.HealthCheck.return_value = health_resp

        err = client.connect()
        assert err is None
        mock_channel.assert_called_once_with("10.0.0.1:50051")

    @patch("corekinect.mtib_client.v1.client.core.insecure_channel")
    @patch("corekinect.mtib_client.v1.client.core.MtibClientV1")
    def test_connect_lenient_when_healthcheck_unimplemented(self, mock_stub_cls, mock_channel):
        """When HealthCheck RPC returns UNIMPLEMENTED, connect() should
        log a warning and proceed (older MTIB servers may not expose
        the RPC yet). The channel is still considered open.
        """
        client = MtibV1Client(MtibV1Client.Config(net=NetConfig(addr="10.0.0.1", port=50051)))
        client.logger = MagicMock()

        mock_stub = MagicMock()
        mock_stub_cls.return_value = mock_stub

        # Build a real-looking RpcError that reports UNIMPLEMENTED so the
        # client can detect the status code path. grpc.Call exposes
        # ``code()`` / ``details()``; the simplest stand-in here is a
        # MagicMock that satisfies isinstance(grpc.RpcError).
        rpc_err = grpc.RpcError()
        rpc_err.code = MagicMock(return_value=grpc.StatusCode.UNIMPLEMENTED)
        rpc_err.details = MagicMock(return_value="HealthCheck not implemented")
        mock_stub.HealthCheck.side_effect = rpc_err

        err = client.connect()
        assert err is None, f"connect() should be lenient on UNIMPLEMENTED, got: {err}"
        # Warning surfaced to operator
        assert client.logger.warning.called

    @patch("corekinect.mtib_client.v1.client.core.insecure_channel")
    @patch("corekinect.mtib_client.v1.client.core.MtibClientV1")
    def test_connect_health_not_ready(self, mock_stub_cls, mock_channel):
        """Test connect health not ready."""
        client = MtibV1Client(MtibV1Client.Config(net=NetConfig(addr="10.0.0.1", port=50051)))
        client.logger = MagicMock()

        mock_stub = MagicMock()
        mock_stub_cls.return_value = mock_stub

        health_resp = MagicMock()
        health_resp.ready = False
        health_resp.errors = ["not initialized"]
        mock_stub.HealthCheck.return_value = health_resp

        err = client.connect()
        assert err is not None
        assert "Error checking health" in err

    def test_disconnect_no_channel(self):
        """Test disconnect no channel."""
        client = _make_client()
        client.channel = None
        err = client.disconnect()
        assert err is None

    def test_disconnect_with_channel(self):
        """Test disconnect with channel."""
        client = _make_client()
        client.channel = MagicMock()
        err = client.disconnect()
        assert err is None
        client.channel.close.assert_called_once()


class TestHealthCheck(unittest.TestCase):
    """Tests for HealthCheck and HealthCheckExtended."""

    def test_health_check_success(self):
        """Test health check success."""
        client = _make_client()
        resp = MagicMock()
        resp.ready = True
        resp.errors = []
        client.client.HealthCheck.return_value = resp

        ready, errors, err = client.HealthCheck(timeout=5)
        assert err is None
        assert ready is True
        assert errors == []

    def test_health_check_grpc_error(self):
        """Test health check grpc error."""
        client = _make_client()
        rpc_err = _make_rpc_error("connection refused")
        client.client.HealthCheck.side_effect = rpc_err

        ready, errors, err = client.HealthCheck()
        assert ready is None
        assert errors is None
        assert "connection refused" in err

    def test_health_check_unimplemented_surfaces_token(self):
        """An MTIB without the HealthCheck RPC returns UNIMPLEMENTED with
        gRPC's auto-generated details ('Method not found!') — which has
        no 'UNIMPLEMENTED' token. HealthCheck() must detect the status
        code and surface 'UNIMPLEMENTED' in the error so the runner's
        slot-connect lenient path (substring match) fires against a real
        older MTIB build.
        """
        client = _make_client()
        rpc_err = grpc.RpcError()
        rpc_err.code = MagicMock(return_value=grpc.StatusCode.UNIMPLEMENTED)
        rpc_err.details = MagicMock(return_value="Method not found!")
        client.client.HealthCheck.side_effect = rpc_err

        ready, errors, err = client.HealthCheck()
        assert ready is None
        assert errors is None
        assert err is not None and "UNIMPLEMENTED" in err

    def test_health_check_extended_success(self):
        """Test health check extended success."""
        client = _make_client()
        resp = MagicMock()
        resp.ready = True
        resp.errors = []
        resp.hw_revision = "1.2"
        resp.capabilities = ["gpio", "adc"]
        client.client.HealthCheck.return_value = resp

        result, err = client.HealthCheckExtended()
        assert err is None
        assert result.ready is True
        assert result.hw_revision == "1.2"
        assert result.capabilities == ["gpio", "adc"]


class TestGpio(unittest.TestCase):
    """Tests for GPIO methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = _make_client()

    def test_gpio_config_success(self):
        """Test gpio config success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        self.client.client.GpioConfig.return_value = resp

        err = self.client.GpioConfig(
            gpio=0,
            direction=GpioDirection.OUTPUT,
            resistor=GpioResistorConfig.NONE,
        )
        assert err is None

    def test_gpio_config_invalid_pin(self):
        """Test gpio config invalid pin."""
        err = self.client.GpioConfig(gpio=99, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
        assert err is not None
        assert "99" in err

    def test_gpio_config_negative_pin(self):
        """Test gpio config negative pin."""
        err = self.client.GpioConfig(gpio=-1, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
        assert err is not None
        assert "-1" in err

    def test_gpio_config_server_error(self):
        """Test gpio config server error."""
        resp = MagicMock()
        resp.success = False
        resp.message = "pin busy"
        self.client.client.GpioConfig.return_value = resp

        err = self.client.GpioConfig(gpio=0, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
        assert err is not None
        assert "pin busy" in err

    def test_gpio_write_success(self):
        """Test gpio write success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        self.client.client.GpioWrite.return_value = resp

        err = self.client.GpioWrite(gpio=0, state=True)
        assert err is None

    def test_gpio_write_invalid_pin(self):
        """Test gpio write invalid pin."""
        err = self.client.GpioWrite(gpio=8, state=True)
        assert err is not None
        assert "8" in err

    def test_gpio_write_grpc_error(self):
        """Test gpio write grpc error."""
        rpc_err = _make_rpc_error("deadline exceeded")
        self.client.client.GpioWrite.side_effect = rpc_err

        err = self.client.GpioWrite(gpio=0, state=True)
        assert err is not None
        assert "deadline exceeded" in err

    def test_gpio_read_success(self):
        """Test gpio read success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.state = True
        self.client.client.GpioRead.return_value = resp

        state, err = self.client.GpioRead(gpio=3)
        assert err is None
        assert state is True

    def test_gpio_read_invalid_pin(self):
        """Test gpio read invalid pin."""
        state, err = self.client.GpioRead(gpio=10)
        assert state is None
        assert err is not None
        assert "10" in err

    def test_gpio_read_server_failure(self):
        """Test gpio read server failure."""
        resp = MagicMock()
        resp.success = False
        resp.message = "not configured"
        self.client.client.GpioRead.return_value = resp

        state, err = self.client.GpioRead(gpio=0)
        assert state is None
        assert "not configured" in err


class TestAdc(unittest.TestCase):
    """Tests for ADC methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = _make_client()

    def test_adc_read_success(self):
        """Test adc read success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.voltage_v = 3.3
        self.client.client.AdcRead.return_value = resp

        voltage, err = self.client.AdcRead(channel=0)
        assert err is None
        assert voltage == 3.3

    def test_adc_read_invalid_channel(self):
        """Test adc read invalid channel."""
        voltage, err = self.client.AdcRead(channel=8)
        assert voltage is None
        assert err is not None
        assert "8" in err

    def test_adc_read_negative_channel(self):
        """Test adc read negative channel."""
        voltage, err = self.client.AdcRead(channel=-1)
        assert voltage is None
        assert err is not None

    def test_adc_read_grpc_error(self):
        """Test adc read grpc error."""
        rpc_err = _make_rpc_error("timeout")
        self.client.client.AdcRead.side_effect = rpc_err

        voltage, err = self.client.AdcRead(channel=0)
        assert voltage is None
        assert "timeout" in err

    def test_adc_read_all_success(self):
        """Test adc read all success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.voltages_v = [3.3, 2.5, 4.5, 0.0, 0.0, 0.0, 0.0, 3.3]
        self.client.client.AdcReadAll.return_value = resp

        voltages, err = self.client.AdcReadAll()
        assert err is None
        assert len(voltages) == 8
        assert voltages[0] == 3.3

    def test_adc_read_all_server_error(self):
        """Test adc read all server error."""
        resp = MagicMock()
        resp.success = False
        resp.message = "ADC not ready"
        self.client.client.AdcReadAll.return_value = resp

        voltages, err = self.client.AdcReadAll()
        assert voltages is None
        assert "ADC not ready" in err


class TestPower(unittest.TestCase):
    """Tests for Power methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = _make_client()

    def test_power_enable_success(self):
        """Test power enable success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        self.client.client.PowerEnable.return_value = resp

        err = self.client.PowerEnable(channel=0, voltage_v=4.5)
        assert err is None

    def test_power_enable_invalid_channel(self):
        """Test power enable invalid channel."""
        err = self.client.PowerEnable(channel=3, voltage_v=4.5)
        assert err is not None
        assert "3" in err

    def test_power_enable_invalid_voltage(self):
        """Test power enable invalid voltage."""
        err = self.client.PowerEnable(channel=0, voltage_v=7.0)
        assert err is not None
        assert "7.0" in err

    def test_power_enable_negative_voltage(self):
        """Test power enable negative voltage."""
        err = self.client.PowerEnable(channel=0, voltage_v=-1.0)
        assert err is not None

    def test_power_disable_success(self):
        """Test power disable success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        self.client.client.PowerDisable.return_value = resp

        err = self.client.PowerDisable(channel=0)
        assert err is None

    def test_power_disable_invalid_channel(self):
        """Test power disable invalid channel."""
        err = self.client.PowerDisable(channel=5)
        assert err is not None
        assert "5" in err

    def test_power_read_success(self):
        """Test power read success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.enabled = True
        resp.voltage_v = 4.5
        resp.current_ma = 17.0
        resp.power_mw = 76.5
        resp.current_na = 0.0
        self.client.client.PowerRead.return_value = resp

        result, err = self.client.PowerRead(channel=0)
        assert err is None
        assert result.enabled is True
        assert result.voltage_v == 4.5
        assert result.current_ma == 17.0
        assert result.power_mw == 76.5
        assert result.current_na == 0.0  # INA219 has no nA reading

    def test_power_read_maps_current_na(self):
        """PowerRead must map current_na from response to result."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.enabled = True
        resp.voltage_v = 4.5
        resp.current_ma = 0.025
        resp.power_mw = 0.1125
        resp.current_na = 25000.0  # Joulescope nanoamp reading
        self.client.client.PowerRead.return_value = resp

        result, err = self.client.PowerRead(channel=2)  # Joulescope channel
        assert err is None
        assert result.current_na == 25000.0
        assert result.current_ma == 0.025

    def test_power_read_joulescope_channel_makes_grpc_call(self):
        """PowerRead on channel 2 should pass through to gRPC."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.enabled = True
        resp.voltage_v = 3.3
        resp.current_ma = 0.001
        resp.power_mw = 0.0033
        resp.current_na = 1000.0
        self.client.client.PowerRead.return_value = resp

        result, err = self.client.PowerRead(channel=2)
        assert err is None
        self.client.client.PowerRead.assert_called_once()

    def test_power_read_invalid_channel(self):
        """Test power read invalid channel."""
        result, err = self.client.PowerRead(channel=3)
        assert result is None
        assert err is not None

    def test_power_read_server_error(self):
        """Test power read server error."""
        resp = MagicMock()
        resp.success = False
        resp.message = "INA219 not responding"
        self.client.client.PowerRead.return_value = resp

        result, err = self.client.PowerRead(channel=0)
        assert result is None
        assert "INA219" in err

    def test_power_measure_success(self):
        """Test power measure success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.duration_s = 1.0
        resp.average_ma = 20.0
        resp.min_ma = 15.0
        resp.max_ma = 30.0
        resp.average_mv = 4500.0
        resp.sample_count = 100
        resp.average_na = 0.0
        resp.min_na = 0.0
        resp.max_na = 0.0
        self.client.client.PowerMeasure.return_value = resp

        result, err = self.client.PowerMeasure(channel=0, duration_s=1.0)
        assert err is None
        assert result.average_ma == 20.0
        assert result.sample_count == 100
        assert result.average_na == 0.0  # INA219 channels have no nA data

    def test_power_measure_maps_nanoamp_fields(self):
        """PowerMeasure must map average_na, min_na, max_na from response."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.duration_s = 5.0
        resp.average_ma = 0.025
        resp.min_ma = 0.01
        resp.max_ma = 0.05
        resp.average_mv = 4500.0
        resp.sample_count = 5000
        resp.average_na = 25000.0
        resp.min_na = 10000.0
        resp.max_na = 50000.0
        self.client.client.PowerMeasure.return_value = resp

        result, err = self.client.PowerMeasure(channel=2, duration_s=5.0)
        assert err is None
        assert result.average_na == 25000.0
        assert result.min_na == 10000.0
        assert result.max_na == 50000.0
        assert result.average_ma == 0.025

    def test_power_enable_joulescope_channel(self):
        """PowerEnable on channel 2 should make the gRPC call."""
        resp = MagicMock()
        resp.success = True
        resp.message = "always-on"
        self.client.client.PowerEnable.return_value = resp

        err = self.client.PowerEnable(channel=2, voltage_v=0.0)
        assert err is None
        self.client.client.PowerEnable.assert_called_once()

    def test_power_disable_joulescope_channel(self):
        """PowerDisable on channel 2 should make the gRPC call."""
        resp = MagicMock()
        resp.success = True
        resp.message = "always-on"
        self.client.client.PowerDisable.return_value = resp

        err = self.client.PowerDisable(channel=2)
        assert err is None
        self.client.client.PowerDisable.assert_called_once()


class TestPowerTypes(unittest.TestCase):
    """Test PowerReadResult and PowerMeasureResult construction."""

    def test_power_read_result_defaults(self):
        """Test power read result defaults."""
        r = PowerReadResult()
        assert r.enabled is False
        assert r.voltage_v == 0.0
        assert r.current_ma == 0.0
        assert r.power_mw == 0.0
        assert r.current_na == 0.0

    def test_power_measure_result_defaults(self):
        """Test power measure result defaults."""
        r = PowerMeasureResult()
        assert r.average_na == 0.0
        assert r.min_na == 0.0
        assert r.max_na == 0.0

    def test_power_channel_enum_values(self):
        """Test power channel enum values."""
        assert PowerChannel.DUT == 0
        assert PowerChannel.CHARGER == 1
        assert PowerChannel.JOULESCOPE == 2


class TestSensors(unittest.TestCase):
    """Tests for sensor methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = _make_client()

    def test_altimeter_read_success(self):
        """Test altimeter read success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.temperature_f = 72.0
        resp.pressure_hg = 29.92
        resp.altitude_ft = 500.0
        self.client.client.AltimeterRead.return_value = resp

        temp, pressure, altitude, err = self.client.AltimeterRead()
        assert err is None
        assert temp == 72.0
        assert pressure == 29.92
        assert altitude == 500.0

    def test_altimeter_read_grpc_error(self):
        """Test altimeter read grpc error."""
        rpc_err = _make_rpc_error("sensor offline")
        self.client.client.AltimeterRead.side_effect = rpc_err

        temp, pressure, altitude, err = self.client.AltimeterRead()
        assert temp is None
        assert pressure is None
        assert altitude is None
        assert "sensor offline" in err

    def test_accel_read_success(self):
        """Test accel read success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.x_g = 0.01
        resp.y_g = -0.02
        resp.z_g = 1.0
        self.client.client.AccelRead.return_value = resp

        x, y, z, err = self.client.AccelRead()
        assert err is None
        assert x == 0.01
        assert y == -0.02
        assert z == 1.0

    def test_accel_read_server_failure(self):
        """Test accel read server failure."""
        resp = MagicMock()
        resp.success = False
        resp.message = "accelerometer not found"
        self.client.client.AccelRead.return_value = resp

        x, y, z, err = self.client.AccelRead()
        assert x is None
        assert "accelerometer not found" in err


class TestFirmware(unittest.TestCase):
    """Tests for firmware methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = _make_client()

    def test_list_programmers_success(self):
        """Test list programmers success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.programmers = [MagicMock(), MagicMock()]
        self.client.client.ListProgrammers.return_value = resp

        programmers, err = self.client.ListProgrammers()
        assert err is None
        assert len(programmers) == 2

    def test_list_programmers_grpc_error(self):
        """Test list programmers grpc error."""
        rpc_err = _make_rpc_error("not connected")
        self.client.client.ListProgrammers.side_effect = rpc_err

        programmers, err = self.client.ListProgrammers()
        assert programmers is None
        assert "not connected" in err

    def test_list_fw_files_success(self):
        """Test list fw files success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.files = [MagicMock(name="fw.hex")]
        self.client.client.ListFwFiles.return_value = resp

        files, err = self.client.ListFwFiles()
        assert err is None
        assert len(files) == 1

    def test_list_fw_files_empty(self):
        """Test list fw files empty."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.files = []
        self.client.client.ListFwFiles.return_value = resp

        files, err = self.client.ListFwFiles()
        assert err is None
        assert len(files) == 0

    def test_delete_fw_file_success(self):
        """Test delete fw file success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        self.client.client.DeleteFwFile.return_value = resp

        file_info = FwFileInfo(name="fw.hex", target=HostType.HOST_TYPE_NRF52840)
        err = self.client.DeleteFwFile(file_info)
        assert err is None

    def test_flash_fw_file_success(self):
        """Test flash fw file success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.time_ms = 3500
        self.client.client.FlashFwFile.return_value = resp

        file_info = FwFileInfo(name="fw.hex", target=HostType.HOST_TYPE_NRF52840)
        time_ms, err = self.client.FlashFwFile(file_info, sector_erase=True)
        assert err is None
        assert time_ms == 3500

    def test_erase_flash_success(self):
        """Test erase flash success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        self.client.client.EraseFlash.return_value = resp

        err = self.client.EraseFlash(target=1, recover=True)
        assert err is None

    def test_enable_app_protect_success(self):
        """Test enable app protect success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        self.client.client.EnableAppProtect.return_value = resp

        success, err = self.client.EnableAppProtect(target=1)
        assert err is None
        assert success is True


class TestNfc(unittest.TestCase):
    """Tests for NFC methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = _make_client()

    def test_nfc_poll_tag_present(self):
        """Test nfc poll tag present."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.tag_present = True
        resp.uid = b"\x04\x01\x02\x03"
        self.client.client.NfcPoll.return_value = resp

        present, uid, err = self.client.NfcPoll(timeout_ms=500)
        assert err is None
        assert present is True
        assert uid == b"\x04\x01\x02\x03"

    def test_nfc_poll_no_tag(self):
        """Test nfc poll no tag."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.tag_present = False
        resp.uid = b""
        self.client.client.NfcPoll.return_value = resp

        present, uid, err = self.client.NfcPoll()
        assert err is None
        assert present is False

    def test_nfc_poll_grpc_error(self):
        """Test nfc poll grpc error."""
        rpc_err = _make_rpc_error("NFC hardware not found")
        self.client.client.NfcPoll.side_effect = rpc_err

        present, uid, err = self.client.NfcPoll()
        assert present is None
        assert uid is None
        assert "NFC hardware not found" in err


class TestMotion(unittest.TestCase):
    """Tests for motion methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = _make_client()

    def test_get_motion_status_idle(self):
        """Test get motion status idle."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.status = MotionStatus.IDLE
        self.client.client.GetMotionStatus.return_value = resp

        status, err = self.client.GetMotionStatus()
        assert err is None
        assert status == MotionStatus.IDLE

    def test_get_motion_status_error(self):
        """Test get motion status error."""
        resp = MagicMock()
        resp.success = False
        resp.message = "motor driver fault"
        self.client.client.GetMotionStatus.return_value = resp

        status, err = self.client.GetMotionStatus()
        assert status is None
        assert "motor driver fault" in err

    def test_motion_home_success(self):
        """Test motion home success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        self.client.client.MotionHome.return_value = resp

        err = self.client.MotionHome()
        assert err is None

    def test_motion_stop_success(self):
        """Test motion stop success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        self.client.client.MotionStop.return_value = resp

        err = self.client.MotionStop()
        assert err is None


class TestValidation(unittest.TestCase):
    """Tests for input validation helpers."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = _make_client()

    def test_validate_gpio_valid_range(self):
        """Test validate gpio valid range."""
        for pin in range(8):
            assert self.client._validate_gpio(pin) is None

    def test_validate_gpio_out_of_range(self):
        """Test validate gpio out of range."""
        assert self.client._validate_gpio(8) is not None
        assert self.client._validate_gpio(-1) is not None
        assert self.client._validate_gpio(100) is not None

    def test_validate_adc_channel_valid(self):
        """Test validate adc channel valid."""
        for ch in range(8):
            assert self.client._validate_adc_channel(ch) is None

    def test_validate_adc_channel_invalid(self):
        """Test validate adc channel invalid."""
        assert self.client._validate_adc_channel(8) is not None
        assert self.client._validate_adc_channel(-1) is not None

    def test_validate_power_channel_valid(self):
        """Test validate power channel valid."""
        assert self.client._validate_power_channel(0) is None
        assert self.client._validate_power_channel(1) is None
        assert self.client._validate_power_channel(2) is None  # Joulescope

    def test_validate_power_channel_invalid(self):
        """Test validate power channel invalid."""
        assert self.client._validate_power_channel(3) is not None
        assert self.client._validate_power_channel(-1) is not None

    def test_validate_voltage_valid(self):
        """Test validate voltage valid."""
        assert self.client._validate_voltage(0.0) is None
        assert self.client._validate_voltage(4.5) is None
        assert self.client._validate_voltage(6.0) is None

    def test_validate_voltage_invalid(self):
        """Test validate voltage invalid."""
        assert self.client._validate_voltage(6.1) is not None
        assert self.client._validate_voltage(-0.1) is not None
        assert self.client._validate_voltage(12.0) is not None


class TestGetSnapshot(unittest.TestCase):
    """Tests for GetSnapshot."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = _make_client()

    def test_get_snapshot_success(self):
        """Test get snapshot success."""
        resp = MagicMock()
        resp.success = True
        resp.message = ""
        resp.timestamp_ms = 123456
        resp.hw_revision = "1.2"
        resp.power = [MagicMock()]
        resp.gpio = [MagicMock()]
        resp.adc = [MagicMock()]
        self.client.client.GetSnapshot.return_value = resp

        result, err = self.client.GetSnapshot()
        assert err is None
        assert result.timestamp_ms == 123456
        assert result.hw_revision == "1.2"

    def test_get_snapshot_server_error(self):
        """Test get snapshot server error."""
        resp = MagicMock()
        resp.success = False
        resp.message = "snapshot unavailable"
        self.client.client.GetSnapshot.return_value = resp

        result, err = self.client.GetSnapshot()
        assert result is None
        assert "snapshot unavailable" in err


if __name__ == "__main__":
    unittest.main()
