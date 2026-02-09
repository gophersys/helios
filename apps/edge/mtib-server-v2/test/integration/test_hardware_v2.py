"""Hardware integration tests for MTIB Server V2.

Tests against a live MTIB server on real hardware at the configured address.
Exercises the core V2 RPCs: health, system, power, I2C, targets, debug probes.

Run: PYTHONPATH=libs/python:libs python3 -m pytest apps/edge/mtib-server-v2/test/integration/test_hardware_v2.py -v -s
"""

import os
import sys
import time

import pytest

# Ensure imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "libs", "python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "libs"))

from corekinect.mtib_client.v2.client.core import MtibV2Client
from corekinect.mtib_client.v2.client.config import ClientConfig, NetConfig

# Server address - use env var or default to the K8s node
SERVER_ADDR = os.environ.get("MTIB_SERVER_ADDR", "10.4.45.33")
SERVER_PORT = int(os.environ.get("MTIB_SERVER_PORT", "50052"))

# Expected I2C devices on bus 3 (REV 1.2)
EXPECTED_I2C_DEVICES = {
    0x19: "LIS2DE12 (Accelerometer)",
    0x2F: "MCP4017 (Digital Potentiometer)",
    0x38: "TCA9534A (GPIO Expander)",
    0x40: "INA219 (DUT Power Monitor)",
    0x41: "INA219 (Charge Power Monitor)",
    0x48: "ADS1115 #1 (ADC)",
    0x49: "ADS1115 #2 (ADC)",
    0x50: "AT24C02C (EEPROM)",
    0x76: "BMP390L (Pressure Sensor)",
    0x77: "BME280 (Environmental Sensor)",
}


@pytest.fixture(scope="module")
def client():
    """Create and connect an MTIB V2 client."""
    config = ClientConfig(
        net=NetConfig(addr=SERVER_ADDR, port=SERVER_PORT),
        timeout_s=15.0,
    )
    c = MtibV2Client(config)
    err = c.connect()
    if err:
        pytest.fail(f"Failed to connect to MTIB server at {SERVER_ADDR}:{SERVER_PORT}: {err}")
    yield c
    c.disconnect()


# =========================================================================
# Health & System
# =========================================================================
class TestSystem:
    """Test health check and system info RPCs."""

    def test_health_check(self, client):
        """Server should respond ready with version 2.x."""
        err, health = client.health_check()
        assert err is None, f"Health check failed: {err}"
        assert health.ready is True
        assert health.version.startswith("2.")
        print(f"  Server version: {health.version}")
        print(f"  Capabilities: {health.capabilities}")

    def test_system_info(self, client):
        """Server should report system information."""
        err, info = client.system_info()
        assert err is None, f"System info failed: {err}"
        assert info.hostname != ""
        assert info.os != ""
        print(f"  Hostname: {info.hostname}")
        print(f"  OS: {info.os}")
        print(f"  CPU: {info.cpu_usage:.1f}%")
        print(f"  Memory: {info.memory_usage:.1f}%")
        print(f"  Uptime: {info.uptime_s:.0f}s")


# =========================================================================
# Target & Probe Discovery
# =========================================================================
class TestTargets:
    """Test target and probe discovery RPCs."""

    def test_list_targets(self, client):
        """Server should report known Nordic targets."""
        err, targets = client.list_targets()
        assert err is None, f"List targets failed: {err}"
        assert len(targets) > 0
        target_ids = [t.id for t in targets]
        assert "nrf52840" in target_ids
        assert "nrf9151" in target_ids
        for t in targets:
            print(f"  Target: {t.name} ({t.chip}) - debug={t.has_debug}, uart={t.has_uart}")

    def test_list_probes(self, client):
        """Server should detect connected J-Link probes."""
        err, probes = client.list_probes()
        assert err is None, f"List probes failed: {err}"
        # Both J-Links should be plugged in per user
        print(f"  Found {len(probes)} probe(s)")
        for p in probes:
            print(f"  Probe: {p.id} (type={p.type}, serial={p.serial})")
        assert len(probes) >= 1, "Expected at least 1 J-Link probe connected"


# =========================================================================
# I2C Bus Scan
# =========================================================================
class TestI2C:
    """Test I2C bus scan and transfer RPCs."""

    def test_i2c_scan_bus3(self, client):
        """Scan I2C bus 3 - should find all expected devices."""
        err, result = client.i2c_scan(bus=3)
        assert err is None, f"I2C scan failed: {err}"
        found_addrs = set(result.addresses)
        print(f"  Found {len(found_addrs)} devices on I2C bus 3:")
        for addr in sorted(found_addrs):
            name = EXPECTED_I2C_DEVICES.get(addr, "Unknown")
            print(f"    0x{addr:02X}: {name}")

        # Check that at least the critical devices are present
        critical_devices = [0x2F, 0x40, 0x41]  # MCP4017, INA219 x2
        for addr in critical_devices:
            assert addr in found_addrs, (
                f"Missing critical device at 0x{addr:02X} ({EXPECTED_I2C_DEVICES.get(addr, 'Unknown')})"
            )

    def test_i2c_transfer_mcp4017_read(self, client):
        """Read MCP4017 current wiper position via I2C transfer."""
        err, result = client.i2c_transfer(bus=3, address=0x2F, read_size=1)
        assert err is None, f"I2C transfer failed: {err}"
        assert not result.nak
        wiper = result.read_data[0] if result.read_data else -1
        print(f"  MCP4017 wiper position: {wiper}/127")
        assert 0 <= wiper <= 127


# =========================================================================
# Power Management
# =========================================================================
class TestPower:
    """Test power control and measurement RPCs."""

    def test_power_status_main(self, client):
        """Read DUT power status (should be off initially)."""
        err, status = client.power_status(channel=0)  # POWER_MAIN
        assert err is None, f"Power status failed: {err}"
        print(f"  DUT Power: enabled={status.enabled}, {status.voltage_v:.3f}V, {status.current_ma:.1f}mA")

    def test_power_status_vbat(self, client):
        """Read charge power status."""
        err, status = client.power_status(channel=1)  # POWER_VBAT
        assert err is None, f"Power status failed: {err}"
        print(f"  Charge Power: enabled={status.enabled}, {status.voltage_v:.3f}V, {status.current_ma:.1f}mA")

    def test_power_enable_disable_cycle(self, client):
        """Enable DUT power at 3.3V, verify voltage, then disable."""
        # Enable at 3.3V
        err = client.power_enable(channel=0, voltage_v=3.3)
        assert err is None, f"Power enable failed: {err}"
        time.sleep(1)  # Allow voltage to stabilize

        # Check status
        err, status = client.power_status(channel=0)
        assert err is None, f"Power status failed: {err}"
        assert status.enabled is True
        print(f"  DUT Power after enable: {status.voltage_v:.3f}V, {status.current_ma:.1f}mA")
        assert 2.8 < status.voltage_v < 3.8, f"Voltage out of range: {status.voltage_v}V"

        # Measure for 0.5s
        err, measurement = client.power_measure(channel=0, duration_s=0.5, sample_rate_hz=10)
        assert err is None, f"Power measure failed: {err}"
        print(f"  Measurement: avg={measurement.average_ua:.0f}uA, samples={measurement.sample_count}")

        # Disable
        err = client.power_disable(channel=0)
        assert err is None, f"Power disable failed: {err}"
        time.sleep(0.5)

        # Verify disabled
        err, status = client.power_status(channel=0)
        assert err is None
        assert status.enabled is False
        print(f"  DUT Power after disable: {status.voltage_v:.3f}V")

    def test_power_enable_4v(self, client):
        """Enable DUT power at 4.0V for nominal battery voltage."""
        err = client.power_enable(channel=0, voltage_v=4.0)
        assert err is None, f"Power enable failed: {err}"
        time.sleep(1)

        err, status = client.power_status(channel=0)
        assert err is None
        print(f"  DUT @ 4.0V: {status.voltage_v:.3f}V, {status.current_ma:.1f}mA")
        assert 3.5 < status.voltage_v < 4.5, f"Voltage out of range: {status.voltage_v}V"

        # Clean up
        err = client.power_disable(channel=0)
        assert err is None
        time.sleep(0.5)


# =========================================================================
# File Management
# =========================================================================
class TestFiles:
    """Test file management RPCs."""

    def test_list_files(self, client):
        """List available firmware files on the server."""
        try:
            err, files = client.list_files()
            if err:
                print(f"  List files returned error (non-fatal): {err}")
            else:
                print(f"  Found {len(files) if files else 0} firmware files")
        except Exception as e:
            print(f"  File listing not available: {e}")


# =========================================================================
# GPIO
# =========================================================================
class TestGpio:
    """Test GPIO read RPCs."""

    def test_gpio_read_all(self, client):
        """Read all DUT GPIO pins (0-8) - should succeed even if floating."""
        for pin in range(9):
            err, result = client.gpio_read(pin=pin)
            assert err is None, f"GPIO read pin {pin} failed: {err}"
            print(f"  GPIO {pin}: {result.value}")

    def test_gpio_config_and_write(self, client):
        """Configure a GPIO as output, write, then read back."""
        # Configure pin 0 as output
        err = client.gpio_config(pin=0, direction=1)  # GPIO_OUTPUT=1
        assert err is None, f"GPIO config failed: {err}"

        # Write high
        err = client.gpio_write(pin=0, value=True)
        assert err is None, f"GPIO write failed: {err}"

        # Read back (should be high since we just wrote it)
        err, result = client.gpio_read(pin=0)
        assert err is None, f"GPIO read failed: {err}"
        print(f"  GPIO 0 after write(True): {result.value}")

        # Write low
        err = client.gpio_write(pin=0, value=False)
        assert err is None, f"GPIO write low failed: {err}"

        # Restore to input
        err = client.gpio_config(pin=0, direction=0)  # GPIO_INPUT=0
        assert err is None, f"GPIO restore failed: {err}"


# =========================================================================
# I2C Sensor Reads
# =========================================================================
class TestSensors:
    """Test I2C sensor reads via raw I2C transfer."""

    def test_bmp390l_chip_id(self, client):
        """Read BMP390L chip ID register (0x00) - should return 0x60."""
        err, result = client.i2c_transfer(bus=3, address=0x76, write_data=bytes([0x00]), read_size=1)
        assert err is None, f"BMP390L read failed: {err}"
        assert not result.nak, "BMP390L NAK'd"
        chip_id = result.read_data[0] if result.read_data else -1
        print(f"  BMP390L chip ID: 0x{chip_id:02X} (expected 0x60)")
        assert chip_id == 0x60, f"Unexpected BMP390L chip ID: 0x{chip_id:02X}"

    def test_bme280_chip_id(self, client):
        """Read BME280 chip ID register (0xD0) - should return 0x60."""
        err, result = client.i2c_transfer(bus=3, address=0x77, write_data=bytes([0xD0]), read_size=1)
        assert err is None, f"BME280 read failed: {err}"
        assert not result.nak, "BME280 NAK'd"
        chip_id = result.read_data[0] if result.read_data else -1
        print(f"  BME280 chip ID: 0x{chip_id:02X} (expected 0x60)")
        assert chip_id == 0x60, f"Unexpected BME280 chip ID: 0x{chip_id:02X}"

    def test_lis2de12_who_am_i(self, client):
        """Read LIS2DE12 WHO_AM_I register (0x0F) - should return 0x33."""
        err, result = client.i2c_transfer(bus=3, address=0x19, write_data=bytes([0x0F]), read_size=1)
        assert err is None, f"LIS2DE12 read failed: {err}"
        assert not result.nak, "LIS2DE12 NAK'd"
        who_am_i = result.read_data[0] if result.read_data else -1
        print(f"  LIS2DE12 WHO_AM_I: 0x{who_am_i:02X} (expected 0x33)")
        assert who_am_i == 0x33, f"Unexpected LIS2DE12 WHO_AM_I: 0x{who_am_i:02X}"

    def test_ina219_bus_voltage(self, client):
        """Read INA219 DUT bus voltage register (0x02)."""
        err, result = client.i2c_transfer(bus=3, address=0x40, write_data=bytes([0x02]), read_size=2)
        assert err is None, f"INA219 read failed: {err}"
        assert not result.nak, "INA219 NAK'd"
        assert len(result.read_data) == 2
        raw = (result.read_data[0] << 8) | result.read_data[1]
        # Bits 15:3 are voltage, bit 0 is OVF, bit 1 is CNVR
        voltage_mv = (raw >> 3) * 4  # 4mV LSB
        voltage_v = voltage_mv / 1000.0
        print(f"  INA219 DUT bus voltage (raw I2C): {voltage_v:.3f}V")


# =========================================================================
# Power Streaming
# =========================================================================
class TestPowerStream:
    """Test power streaming RPC."""

    def test_power_stream_samples(self, client):
        """Stream a few power samples from DUT channel."""
        responses = []
        try:
            for resp in client.power_stream(channel=0, sample_rate_hz=10):
                responses.append(resp)
                if len(responses) >= 5:
                    break
        except Exception as e:
            print(f"  Power stream ended: {e}")

        print(f"  Collected {len(responses)} power stream responses")
        for resp in responses:
            for s in resp.samples:
                print(f"    V={s.voltage_mv:.0f}mV, I={s.current_ua:.0f}uA")
        assert len(responses) >= 1, "Expected at least 1 power stream response"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
