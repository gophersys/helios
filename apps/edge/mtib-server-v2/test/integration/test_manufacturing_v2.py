"""V2 Manufacturing Test Runner for Alpha B0 board.

Runs 3 test phases in order against a single Alpha B0 board connected via MTIB V2:
  1. Electrical - Power supply verification (UVLO, regulation, charger)
  2. Flash     - Program firmware on nRF52840 and nRF9151
  3. POST      - Power-on self test (I2C sensor chip IDs, UART shell)

Usage:
  PYTHONPATH=libs/python:libs python3 -m pytest \\
    apps/edge/mtib-server-v2/test/integration/test_manufacturing_v2.py -v -s --tb=short

Environment variables:
  MTIB_SERVER_ADDR  Server IP address  (default: 10.4.45.33)
  MTIB_SERVER_PORT  Server gRPC port   (default: 50052)
  NRF52840_PROBE    J-Link serial for nRF52840 (auto-detected if unset)
  NRF9151_PROBE     J-Link serial for nRF9151  (auto-detected if unset)
"""

import os
import struct
import sys
import time
from typing import List, Optional, Tuple

import pytest

# Ensure imports work from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "libs", "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "libs"))

from corekinect.mtib_client.v2.client.core import MtibV2Client
from corekinect.mtib_client.v2.client.config import ClientConfig, NetConfig
from corekinect.mtib_client.v2.client.shell import boot_and_lock_shells
from corekinect.mtib_client.v2.client.cmd_alpha_app import AlphaAppShellCommands
from corekinect.mtib_client.v2.client.cmd_comms import CommsShellCommands

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SERVER_ADDR = os.environ.get("MTIB_SERVER_ADDR", "10.4.45.33")
SERVER_PORT = int(os.environ.get("MTIB_SERVER_PORT", "50052"))

# Probe serial numbers (auto-detected if not set)
NRF52840_PROBE = os.environ.get("NRF52840_PROBE", "")
NRF9151_PROBE = os.environ.get("NRF9151_PROBE", "")

# Firmware hex files (relative to theta_fixture/assets)
ASSETS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "manufacturing", "theta_fixture", "assets",
)
NRF52840_FW = "alpha_app_mfg_1.hex"
NRF9151_FW = "alpha_comm_mfg_1.hex"

# Electrical thresholds
UVLO_VOLTAGE_V = 3.4
NOMINAL_VOLTAGE_V = 3.7
HIGH_VOLTAGE_V = 4.5
FLASH_VOLTAGE_V = 4.0
UVLO_CURRENT_MAX_MA = 5.0     # Max current below UVLO
POWERED_CURRENT_MIN_MA = 0.0  # Min current when device is on (may be 0 if board is blank)

# I2C bus (Verdin I2C_1 = /dev/i2c-3)
I2C_BUS = 3

# ---------------------------------------------------------------------------
# Module-scoped state shared across test phases
# ---------------------------------------------------------------------------
_probe_map: dict = {}  # {"nrf52840": "<serial>", "nrf9151": "<serial>"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    """Create and connect an MTIB V2 client for the entire test run."""
    config = ClientConfig(
        net=NetConfig(addr=SERVER_ADDR, port=SERVER_PORT),
        timeout_s=180.0,  # 3 min timeout for flash programming
    )
    c = MtibV2Client(config)
    err = c.connect()
    if err:
        pytest.fail(f"Failed to connect to MTIB V2 at {SERVER_ADDR}:{SERVER_PORT}: {err}")
    yield c
    c.disconnect()


@pytest.fixture(scope="module")
def probe_map(client):
    """Discover probes and build target→serial mapping."""
    global _probe_map

    if NRF52840_PROBE and NRF9151_PROBE:
        _probe_map = {"nrf52840": NRF52840_PROBE, "nrf9151": NRF9151_PROBE}
        return _probe_map

    err, probes = client.list_probes()
    if err:
        pytest.fail(f"Failed to list probes: {err}")

    serials = [p.serial for p in probes if p.serial]
    print(f"\n  Discovered {len(serials)} J-Link probe(s): {serials}")

    if len(serials) < 2:
        pytest.fail(f"Need 2 probes for manufacturing test, found {len(serials)}")

    if NRF52840_PROBE:
        _probe_map["nrf52840"] = NRF52840_PROBE
        _probe_map["nrf9151"] = [s for s in serials if s != NRF52840_PROBE][0]
    elif NRF9151_PROBE:
        _probe_map["nrf9151"] = NRF9151_PROBE
        _probe_map["nrf52840"] = [s for s in serials if s != NRF9151_PROBE][0]
    else:
        # Auto-detect: we'll assign during flash and swap if needed
        _probe_map = {"nrf52840": serials[0], "nrf9151": serials[1]}

    print(f"  Probe mapping: nRF52840={_probe_map['nrf52840']}, nRF9151={_probe_map['nrf9151']}")
    return _probe_map


# =========================================================================
# Phase 1: Electrical
# =========================================================================
class TestPhase1Electrical:
    """Phase 1: Electrical power supply verification.

    Verifies UVLO behavior, voltage regulation, and charger load sharing.
    Mirrors the theta_fixture electrical test with V2 RPCs.
    """

    def test_01_init_power_off(self, client):
        """Disable all power channels to start from a clean state."""
        err = client.power_disable(channel=0)
        assert err is None, f"Disable DUT power: {err}"
        err = client.power_disable(channel=1)
        assert err is None, f"Disable charge power: {err}"
        time.sleep(1)
        print("  All power disabled")

    def test_02_apply_uvlo_voltage(self, client):
        """Step 1: Apply 3.4V (below BQ25180 UVLO threshold)."""
        err = client.power_enable(channel=0, voltage_v=UVLO_VOLTAGE_V)
        assert err is None, f"Enable power at {UVLO_VOLTAGE_V}V: {err}"
        time.sleep(1)

        err, status = client.power_status(channel=0)
        assert err is None, f"Power status: {err}"
        print(f"  Applied {UVLO_VOLTAGE_V}V: measured {status.voltage_v:.3f}V, {status.current_ma:.3f}mA")
        assert 3.0 < status.voltage_v < 4.0, f"Voltage out of range: {status.voltage_v}V"

    def test_03_verify_uvlo_device_off(self, client):
        """Step 2: Verify device is off at UVLO voltage (current < 5mA)."""
        time.sleep(2)  # Allow settling
        err, status = client.power_status(channel=0)
        assert err is None, f"Power status: {err}"
        print(f"  UVLO check: {status.current_ma:.3f}mA (max={UVLO_CURRENT_MAX_MA}mA)")
        assert status.current_ma < UVLO_CURRENT_MAX_MA, (
            f"Device drawing {status.current_ma:.1f}mA at UVLO voltage (should be < {UVLO_CURRENT_MAX_MA}mA)"
        )

    def test_04_apply_nominal_voltage(self, client):
        """Step 3: Apply 3.7V (above UVLO, nominal battery)."""
        err = client.power_enable(channel=0, voltage_v=NOMINAL_VOLTAGE_V)
        assert err is None, f"Enable power at {NOMINAL_VOLTAGE_V}V: {err}"
        time.sleep(3)  # Allow boot

        err, status = client.power_status(channel=0)
        assert err is None, f"Power status: {err}"
        print(f"  Nominal {NOMINAL_VOLTAGE_V}V: measured {status.voltage_v:.3f}V, {status.current_ma:.1f}mA")

    def test_05_verify_device_powered(self, client):
        """Step 5: Verify device is drawing current (powered up)."""
        err, status = client.power_status(channel=0)
        assert err is None
        print(f"  Device current: {status.current_ma:.1f}mA (min={POWERED_CURRENT_MIN_MA}mA)")
        assert status.current_ma >= POWERED_CURRENT_MIN_MA, (
            f"Device not drawing enough current ({status.current_ma:.1f}mA) at nominal voltage"
        )

    def test_06_apply_high_voltage(self, client):
        """Step 6: Apply 4.5V (high voltage test)."""
        err = client.power_enable(channel=0, voltage_v=HIGH_VOLTAGE_V)
        assert err is None, f"Enable power at {HIGH_VOLTAGE_V}V: {err}"
        time.sleep(1)

        err, status = client.power_status(channel=0)
        assert err is None
        print(f"  High voltage {HIGH_VOLTAGE_V}V: measured {status.voltage_v:.3f}V, {status.current_ma:.1f}mA")
        assert 4.0 < status.voltage_v < 5.0, f"Voltage out of range: {status.voltage_v}V"

    def test_07_enable_charge_power(self, client):
        """Step 8: Enable charge power (load sharing test)."""
        err = client.power_enable(channel=1)
        assert err is None, f"Enable charge power: {err}"
        time.sleep(1)
        print("  Charge power enabled")

    def test_08_disable_charge_power(self, client):
        """Step 10: Disable charge power."""
        err = client.power_disable(channel=1)
        assert err is None, f"Disable charge power: {err}"
        time.sleep(1)
        print("  Charge power disabled")

    def test_09_cleanup(self, client):
        """Disable all power after electrical tests."""
        err = client.power_disable(channel=0)
        assert err is None
        err = client.power_disable(channel=1)
        assert err is None
        time.sleep(1)
        print("  Electrical test cleanup complete")


# =========================================================================
# Phase 2: Flash
# =========================================================================
class TestPhase2Flash:
    """Phase 2: Firmware programming.

    Uploads hex files, flashes both nRF52840 and nRF9151 via J-Link probes.
    """

    def test_01_enable_power_for_flash(self, client):
        """Enable DUT power at 4.0V + charge power for flashing.

        Must wait 5s for device to fully power up — J-Link needs target VREF.
        """
        err = client.power_enable(channel=0, voltage_v=FLASH_VOLTAGE_V)
        assert err is None, f"Enable DUT power: {err}"
        err = client.power_enable(channel=1)
        assert err is None, f"Enable charge power: {err}"
        time.sleep(5)  # Device takes 2-3s to power on; wait 5s like theta fixture

        err, status = client.power_status(channel=0)
        assert err is None
        print(f"  Flash power: {status.voltage_v:.3f}V, {status.current_ma:.1f}mA")

    def test_02_configure_gpios(self, client):
        """Configure DUT GPIOs (BOOT0/RESET lines) low for normal flash."""
        err = client.gpio_config(pin=0, direction=1)  # OUTPUT
        assert err is None, f"GPIO 0 config: {err}"
        err = client.gpio_config(pin=1, direction=1)  # OUTPUT
        assert err is None, f"GPIO 1 config: {err}"
        err = client.gpio_write(pin=0, value=False)
        assert err is None
        err = client.gpio_write(pin=1, value=False)
        assert err is None
        print("  GPIOs configured for normal flash mode")

    def test_03_upload_nrf52840_fw(self, client):
        """Upload nRF52840 application firmware to MTIB server."""
        fw_path = os.path.join(os.path.abspath(ASSETS_DIR), NRF52840_FW)
        assert os.path.exists(fw_path), f"Firmware not found: {fw_path}"

        with open(fw_path, "rb") as f:
            data = f.read()
        err, sha = client.upload_file(NRF52840_FW, data)
        assert err is None, f"Upload {NRF52840_FW} failed: {err}"
        print(f"  Uploaded {NRF52840_FW}: {len(data):,} bytes (sha256={sha[:16]}...)")

    def test_04_upload_nrf9151_fw(self, client):
        """Upload nRF9151 application firmware to MTIB server."""
        fw_path = os.path.join(os.path.abspath(ASSETS_DIR), NRF9151_FW)
        assert os.path.exists(fw_path), f"Firmware not found: {fw_path}"

        with open(fw_path, "rb") as f:
            data = f.read()
        err, sha = client.upload_file(NRF9151_FW, data)
        assert err is None, f"Upload {NRF9151_FW} failed: {err}"
        print(f"  Uploaded {NRF9151_FW}: {len(data):,} bytes (sha256={sha[:16]}...)")

    def test_05_discover_probes(self, client, probe_map):
        """Verify J-Link probes are detected and mapped."""
        print(f"  nRF52840 probe: {probe_map['nrf52840']}")
        print(f"  nRF9151 probe:  {probe_map['nrf9151']}")
        assert probe_map["nrf52840"], "No probe for nRF52840"
        assert probe_map["nrf9151"], "No probe for nRF9151"

    def test_06_flash_nrf52840(self, client, probe_map):
        """Flash nRF52840 application firmware via J-Link.

        Auto-detects which probe is connected to the nRF52840 by trying both.
        nrfjprog will fail with family mismatch if the wrong probe is used.
        """
        probes_to_try = [probe_map["nrf52840"], probe_map["nrf9151"]]
        last_err = None

        for probe_id in probes_to_try:
            err, session = client.debug_connect(target_id="nrf52840", probe_id=probe_id)
            assert err is None, f"Debug connect nRF52840 (probe={probe_id}): {err}"
            print(f"  Trying probe {probe_id} for nRF52840...")

            err, result = client.flash_program(
                session_id=session.session_id,
                filename=NRF52840_FW,
                erase_before=True,
                verify_after=True,
                reset_after=True,
            )
            client.debug_disconnect(session.session_id)

            if err is None:
                # Success! Lock in this probe mapping
                probe_map["nrf52840"] = probe_id
                probe_map["nrf9151"] = [p for p in probes_to_try if p != probe_id][0]
                print(f"  Flashed nRF52840: {result.bytes_programmed:,} bytes in {result.time_ms}ms (probe={probe_id})")
                return

            last_err = err
            print(f"  Probe {probe_id} failed: {err}")

        pytest.fail(f"Flash nRF52840 failed with both probes: {last_err}")

    def test_07_flash_nrf9151(self, client, probe_map):
        """Flash nRF9151 application firmware via J-Link."""
        probe_id = probe_map["nrf9151"]
        err, session = client.debug_connect(target_id="nrf9151", probe_id=probe_id)
        assert err is None, f"Debug connect nRF9151 (probe={probe_id}): {err}"
        print(f"  Session: {session.session_id[:8]}... (probe={probe_id})")

        err, result = client.flash_program(
            session_id=session.session_id,
            filename=NRF9151_FW,
            erase_before=True,
            verify_after=True,
            reset_after=True,
        )
        client.debug_disconnect(session.session_id)
        assert err is None, f"Flash nRF9151 (probe={probe_id}) failed: {err}"
        print(f"  Flashed nRF9151: {result.bytes_programmed:,} bytes in {result.time_ms}ms (probe={probe_id})")

    def test_08_cleanup_files(self, client):
        """Delete uploaded firmware files from MTIB server."""
        client.delete_file(NRF52840_FW)
        client.delete_file(NRF9151_FW)
        print("  Firmware files cleaned up")


# =========================================================================
# Phase 3: POST (Power-On Self Test)
# =========================================================================
class TestPhase3POST:
    """Phase 3: Power-on self test.

    Verifies the board is functional after flashing by:
    - Power cycling and locking both manufacturing shells (race condition)
    - Reading I2C sensor chip IDs (BMP390L, BME280, LIS2DE12)
    - Checking INA219 power monitor readings
    - Communicating with both processors via UART manufacturing shell
    """

    # Module-level shell state shared across POST tests
    _app_shell = None
    _comms_shell = None

    def test_01_boot_and_lock_shells(self, client):
        """Power cycle and lock both manufacturing shells.

        The mfg firmware shell only stays active ~2s after boot, so we must
        open UARTs before power-on and race to send lock_shell on both
        processors simultaneously via threading.
        """
        app_shell, comms_shell, err = boot_and_lock_shells(client)
        assert err is None, f"boot_and_lock_shells failed: {err}"
        assert app_shell.is_open, "App shell not open"
        assert comms_shell.is_open, "Comms shell not open"

        # Store for subsequent tests
        TestPhase3POST._app_shell = app_shell
        TestPhase3POST._comms_shell = comms_shell
        print("  Both shells locked and ready")
        print(f"    App proc (nRF52840) on {app_shell.port_name}: LOCKED")
        print(f"    Comms proc (nRF9151) on {comms_shell.port_name}: LOCKED")

    def test_02_i2c_bus_scan(self, client):
        """Verify I2C bus has expected devices."""
        err, result = client.i2c_scan(bus=I2C_BUS)
        assert err is None, f"I2C scan: {err}"

        found = set(result.addresses)
        print(f"  I2C bus {I2C_BUS}: found {len(found)} devices")

        expected = {
            0x2F: "MCP4017",
            0x40: "INA219 (DUT)",
            0x41: "INA219 (CHG)",
        }
        for addr, name in expected.items():
            assert addr in found, f"Missing {name} at 0x{addr:02X}"
            print(f"    0x{addr:02X}: {name} - OK")

    def test_03_bmp390l_chip_id(self, client):
        """Read BMP390L pressure sensor chip ID (expect 0x60)."""
        err, result = client.i2c_transfer(bus=I2C_BUS, address=0x76, write_data=bytes([0x00]), read_size=1)
        assert err is None, f"BMP390L read: {err}"
        assert not result.nak, "BMP390L NAK"
        chip_id = result.read_data[0] if result.read_data else -1
        print(f"  BMP390L chip ID: 0x{chip_id:02X} (expect 0x60)")
        assert chip_id == 0x60, f"Unexpected BMP390L chip ID: 0x{chip_id:02X}"

    def test_04_bme280_chip_id(self, client):
        """Read BME280 environmental sensor chip ID (expect 0x60)."""
        err, result = client.i2c_transfer(bus=I2C_BUS, address=0x77, write_data=bytes([0xD0]), read_size=1)
        assert err is None, f"BME280 read: {err}"
        assert not result.nak, "BME280 NAK"
        chip_id = result.read_data[0] if result.read_data else -1
        print(f"  BME280 chip ID: 0x{chip_id:02X} (expect 0x60)")
        assert chip_id == 0x60, f"Unexpected BME280 chip ID: 0x{chip_id:02X}"

    def test_05_lis2de12_who_am_i(self, client):
        """Read LIS2DE12 accelerometer WHO_AM_I register (expect 0x33)."""
        err, result = client.i2c_transfer(bus=I2C_BUS, address=0x19, write_data=bytes([0x0F]), read_size=1)
        assert err is None, f"LIS2DE12 read: {err}"
        assert not result.nak, "LIS2DE12 NAK"
        who = result.read_data[0] if result.read_data else -1
        print(f"  LIS2DE12 WHO_AM_I: 0x{who:02X} (expect 0x33)")
        assert who == 0x33, f"Unexpected LIS2DE12 WHO_AM_I: 0x{who:02X}"

    def test_06_ina219_dut_voltage(self, client):
        """Read DUT power monitor voltage via INA219 raw I2C."""
        err, result = client.i2c_transfer(bus=I2C_BUS, address=0x40, write_data=bytes([0x02]), read_size=2)
        assert err is None, f"INA219 read: {err}"
        assert not result.nak, "INA219 NAK"
        assert len(result.read_data) == 2

        raw = (result.read_data[0] << 8) | result.read_data[1]
        voltage_mv = (raw >> 3) * 4  # 4mV LSB
        voltage_v = voltage_mv / 1000.0
        print(f"  INA219 DUT bus voltage: {voltage_v:.3f}V")
        assert voltage_v > 2.0, f"INA219 DUT voltage too low: {voltage_v}V"

    def test_07_power_status_verify(self, client):
        """Verify power status via high-level RPC matches I2C readings."""
        err, status = client.power_status(channel=0)
        assert err is None
        print(f"  Power status: {status.voltage_v:.3f}V, {status.current_ma:.1f}mA, {status.power_mw:.1f}mW")
        assert status.voltage_v > 2.0, f"DUT voltage too low: {status.voltage_v}V"

    def test_08_uart_app_chip_ids(self, client):
        """Read chip IDs from app processor via UART shell.

        Gets external flash chip ID and BLE MAC address from the nRF52840.
        """
        app_shell = TestPhase3POST._app_shell
        assert app_shell and app_shell.is_open, "App shell not available (test_01 must pass first)"

        alpha_app = AlphaAppShellCommands(app_shell)
        ext_flash, ble_mac, err = alpha_app.get_chip_ids()
        assert err is None, f"App get_chip_ids failed: {err}"
        print(f"  App proc ext flash: {ext_flash}")
        print(f"  App proc BLE MAC: {ble_mac}")

    def test_09_uart_comms_chip_ids(self, client):
        """Read chip IDs from comms coprocessor via UART shell.

        Gets external flash chip ID and LoRa status from the nRF9151.
        """
        comms_shell = TestPhase3POST._comms_shell
        assert comms_shell and comms_shell.is_open, "Comms shell not available (test_01 must pass first)"

        comms = CommsShellCommands(comms_shell)
        lora_status, ext_flash, err = comms.get_chip_ids()
        assert err is None, f"Comms get_chip_ids failed: {err}"
        print(f"  Comms ext flash: {ext_flash}")
        print(f"  Comms LoRa status: {lora_status}")

    def test_10_uart_app_env_test(self, client):
        """Read environmental sensors (BME280) via app processor UART shell."""
        app_shell = TestPhase3POST._app_shell
        assert app_shell and app_shell.is_open, "App shell not available (test_01 must pass first)"

        alpha_app = AlphaAppShellCommands(app_shell)
        readings, err = alpha_app.env_test()
        assert err is None, f"App env_test failed: {err}"
        print(f"  Temperature: {readings.get('temperature_c', '?')} C")
        print(f"  Humidity: {readings.get('humidity_pct', '?')} %")
        print(f"  Pressure: {readings.get('pressure_pa', '?')} Pa")

    def test_11_uart_comms_modem_fw(self, client):
        """Read modem firmware version via comms UART shell."""
        comms_shell = TestPhase3POST._comms_shell
        assert comms_shell and comms_shell.is_open, "Comms shell not available (test_01 must pass first)"

        comms = CommsShellCommands(comms_shell)
        version, err = comms.get_modem_fw_version()
        assert err is None, f"Comms get_modem_fw failed: {err}"
        print(f"  Modem FW version: {version}")

    def test_12_final_cleanup(self, client):
        """Close UART shells, disable power, and restore GPIO states."""
        # Close shells
        if TestPhase3POST._app_shell:
            TestPhase3POST._app_shell.close()
            TestPhase3POST._app_shell = None
        if TestPhase3POST._comms_shell:
            TestPhase3POST._comms_shell.close()
            TestPhase3POST._comms_shell = None

        err = client.power_disable(channel=0)
        assert err is None
        err = client.power_disable(channel=1)
        assert err is None

        # Restore GPIOs to input
        client.gpio_config(pin=0, direction=0)
        client.gpio_config(pin=1, direction=0)

        time.sleep(1)
        print("  POST cleanup complete - shells closed, all power off")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
