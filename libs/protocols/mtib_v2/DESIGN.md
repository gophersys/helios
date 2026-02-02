# MTIB V2 - CoreKinect Embedded Test Bench Design

## Overview

MTIB V2 is a comprehensive hardware abstraction protocol for embedded development and automated testing, specifically targeting Zephyr RTOS applications. It provides a unified gRPC interface to all test bench hardware, enabling:

- **AI-assisted debugging** (MCP integration)
- **Automated CI/CD testing** (Twister integration)
- **Remote development** (work from anywhere)
- **Multi-DUT testing** (test farms)

## Hardware Platform

### Controller Stack

| Layer | Component | Details |
|-------|-----------|---------|
| **SoM** | Toradex Verdin iMX8M Mini | Quad Cortex-A53 @ 1.8GHz, 2GB RAM |
| **Carrier** | Toradex Mallow | Industrial carrier, expansion connector |
| **Expansion** | CoreKinect MTIB Board | Custom test bench interface (REV 1.1 or 1.2) |
| **OS** | Torizon OS | Yocto-based, containerized workloads |

### Hardware Revisions

The MTIB expansion board exists in two revisions. The server auto-detects the revision at startup.

| Feature | REV 1.1 (Feb 2025) | REV 1.2 (Dec 2025) |
|---------|-------------------|-------------------|
| **MCP4017 (voltage control)** | 100kΩ (0x2F) | 10kΩ (0x2F) |
| **TCA9534A GPIO expander** | Not present | Present (0x38) |
| **AT24C02C EEPROM** | Not present | Present (0x50) |
| **J-Link multiplexer** | Not present | SN74CBT3257C |
| **J-Link connectors** | 4-pin UART style | USB Type-C source |
| **iMX8 USB connector** | Internal header | USB Type-C sink |
| **Motor power switch** | Direct (always on) | Switchable (MCP1415T + MOSFET) |
| **Recovery/VIO select** | Pin headers (jumpers) | Sliding switches |
| **ADC input pull-downs** | None | 5MΩ / 10MΩ |

#### Revision Detection

The server detects the hardware revision by probing I2C:

```python
def detect_hardware_revision() -> str:
    """Detect MTIB board revision by probing I2C devices."""
    bus = smbus2.SMBus(1)

    # REV 1.2 has EEPROM at 0x50
    try:
        bus.read_byte(0x50)
        return "1.2"
    except OSError:
        pass

    # REV 1.2 has TCA9534A at 0x38
    try:
        bus.read_byte(0x38)
        return "1.2"
    except OSError:
        pass

    return "1.1"
```

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Verdin iMX8M Mini + Mallow                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                         mtib-server-v2 (gRPC :50054)                    │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│       │         │         │         │         │         │         │              │
│   ┌───┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐       │
│   │ Debug │ │ Power │ │  ADC  │ │ GPIO  │ │ UART  │ │Sensor │ │Motion │       │
│   │Handler│ │Handler│ │Handler│ │Handler│ │Handler│ │Handler│ │Handler│       │
│   └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘       │
└───────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────────┘
        │         │         │         │         │         │         │
        │    I2C-1 (0x40,0x41,0x2F)   │         │         │         │
        │         │         │         │         │         │         │
┌───────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────────┐
│       │         │         │         │         │         │         │              │
│  CoreKinect MTIB Expansion Board                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  USB2514B Hub ──┬── J-Link #1 ──┬── [REV 1.2: SN74CBT3257C Mux]        │    │
│  │                 ├── J-Link #2 ──┤         │                             │    │
│  │                 ├── FluidNC ESP32 (CP2102N UART)                        │    │
│  │                 └── Aux USB-A         └──► SWD to DUT                   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Power System                                                           │    │
│  │  5V ──► TPS63802 Buck-Boost ──► DUT_PWR (0.8-5.5V via MCP4017)        │    │
│  │         MCP4017 (0x2F) ◄── I2C voltage control                         │    │
│  │           REV 1.1: 100kΩ (MCP4017T-104E)                               │    │
│  │           REV 1.2: 10kΩ (MCP4017T-103E)                                │    │
│  │         INA219 (0x40) ◄── DUT current sense (100mΩ shunt)             │    │
│  │         INA219 (0x41) ◄── Charge current sense                         │    │
│  │         SIP32510 Load Switches ◄── GPIO enable                         │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  ADC System                                                             │    │
│  │  ADS1115 (0x48) ──► 4 channels (ADC0-3)                                │    │
│  │  ADS1115 (0x49) ──► 4 channels (ADC4-7)                                │    │
│  │  TLV702475 LDO ──► 4.75V clean ADC reference                           │    │
│  │  OPA2192 + TPS61040 ──► Signal conditioning (82k/33k dividers)        │    │
│  │  [REV 1.2: 5MΩ/10MΩ pull-downs for defined floating state]            │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  GPIO & Level Shifting                                                  │    │
│  │  [REV 1.2 only] TCA9534A (0x38) ──► 8 PCB control GPIOs               │    │
│  │  TXS0108 ──► 7 DUT GPIOs (1.8V ↔ DUT_VIO)                             │    │
│  │  TXS0108 ──► I2C level shift (1.8V ↔ 3.3V)                            │    │
│  │  TXS0108 ──► UART/SPI/I2C to DUT (1.8V ↔ DUT_VIO)                     │    │
│  │  ESD5Z5.0T protection on all DUT signals                               │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Sensors & Storage                                                      │    │
│  │  BME280 (0x77) ──► Pressure, humidity, temperature                     │    │
│  │  BMP390L (0x76) ──► High-precision pressure                            │    │
│  │  LIS2DE12 (0x19) ──► 3-axis accelerometer                              │    │
│  │  [REV 1.2 only] AT24C02C (0x50) ──► 2Kbit EEPROM (board ID)           │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Motion System (FluidNC)                                                │    │
│  │  ESP32-U4WDH ──► FluidNC CNC controller                                │    │
│  │  2x A4988 ──► Stepper motor drivers                                    │    │
│  │  [REV 1.2] MCP1415T + SIS413DN ──► Switchable motor power             │    │
│  │  [REV 1.1] Direct connection to EXT_VMM                                │    │
│  │  Limit switches ──► Homing/safety                                       │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │   Target DUT  │
                              │  (Zephyr App) │
                              └───────────────┘
```

## I2C Device Map

### Common Devices (Both Revisions)

| Address | Device | Function | Kernel Driver |
|---------|--------|----------|---------------|
| 0x19 | LIS2DE12 | 3-axis accelerometer | lis2de12 (IIO) |
| 0x2F | MCP4017 | DUT voltage control (digital pot) | mcp4017 |
| 0x40 | INA219 | DUT current monitor | ina219 (hwmon) |
| 0x41 | INA219 | Charge current monitor | ina219 (hwmon) |
| 0x48 | ADS1115 | 16-bit ADC (ch 0-3) | ads1115 (IIO) |
| 0x49 | ADS1115 | 16-bit ADC (ch 4-7) | ads1115 (IIO) |
| 0x76 | BMP390L | Pressure sensor | bmp390 (IIO) |
| 0x77 | BME280 | Pressure/humidity/temp | bme280 (IIO) |

### REV 1.2 Only Devices

| Address | Device | Function | Kernel Driver |
|---------|--------|----------|---------------|
| 0x38 | TCA9534A | 8-bit GPIO expander | tca9534 (GPIO) |
| 0x50 | AT24C02C | 2Kbit EEPROM | at24 |

## USB Topology

### REV 1.1

```
Verdin USB Host (internal header)
    └── USB2514B Hub (on MTIB board)
        ├── Port 1: J-Link Mini #1 (4-pin connector CN6)
        ├── Port 2: J-Link Mini #2 (4-pin connector CN7)
        ├── Port 3: CP2102N → ESP32 FluidNC (motion controller)
        └── Port 4: Auxiliary USB-A connector
```

### REV 1.2

```
Verdin USB Host (USB Type-C sink U21)
    └── USB2514B Hub (on MTIB board)
        ├── Port 1: J-Link Mini #1 (USB Type-C source USB2)
        ├── Port 2: J-Link Mini #2 (USB Type-C source USB3)
        ├── Port 3: CP2102N → ESP32 FluidNC (motion controller)
        └── Port 4: Auxiliary USB-A connector
```

### J-Link Multiplexer (REV 1.2 Only)

REV 1.2 adds an SN74CBT3257C analog multiplexer that allows routing J-Link signals:

```
                           ┌─────────────────┐
JLINK1_DIO ───────────────►│                 │
JLINK1_CLK ───────────────►│  SN74CBT3257C   │──► JLINK1_OUT_DIO/CLK/RST
JLINK1_RST ───────────────►│                 │
                           │                 │
JLINK2_OUT_DIO ◄──────────│                 │──► JLINK2_OUT_DIO/CLK/RST
JLINK2_OUT_CLK ◄──────────│                 │
JLINK2_OUT_RST ◄──────────│                 │
                           │                 │
JLINK_MULTIPLEX_S ────────►│ S (select)     │
                           └─────────────────┘

S=0: A port connects to B1 port (normal)
S=1: A port connects to B2 port (swapped)
```

Control via TCA9534A GPIO P0 (3V3_PCB_GPIO_0 → JLINK_MUL).

## GPIO Mapping

### iMX8 Native GPIOs (DUT Interface - Both Revisions)

| iMX8 GPIO | Function | DUT Signal |
|-----------|----------|------------|
| GPIO1_IO00 | DUT_GPIO0 | Level-shifted I/O |
| GPIO1_IO01 | DUT_GPIO1 | Level-shifted I/O |
| GPIO1_IO02 | DUT_GPIO2 | Level-shifted I/O |
| GPIO1_IO03 | DUT_GPIO3 | Level-shifted I/O |
| I2S1_D_OUT | DUT_GPIO4 | Level-shifted I/O |
| I2S1_BCLK | DUT_GPIO5 | Level-shifted I/O |
| I2S1_SYNC | DUT_GPIO6 | Level-shifted I/O |

### Power Control GPIOs (Both Revisions)

| iMX8 GPIO | Signal | Function |
|-----------|--------|----------|
| I2C1_DSI_SCL | DUT_PWR_EN_1V8 | Enable DUT power |
| I2C1_DSI_SDA | DUT_CHG_EN_1V8 | Enable charge power |

### TCA9534A GPIOs (REV 1.2 Only)

| Pin | Net Name | Function |
|-----|----------|----------|
| P0 | 3V3_PCB_GPIO_0 | JLINK_MUL - J-Link multiplexer select |
| P1 | 3V3_PCB_GPIO_1 | EEPROM write protect |
| P2 | 3V3_PCB_GPIO_2 | VMM_EN - Motor power enable |
| P3 | 3V3_PCB_GPIO_3 | Reserved |
| P4 | 3V3_PCB_GPIO_4 | Reserved |
| P5 | 3V3_PCB_GPIO_5 | Reserved |
| P6 | 3V3_PCB_GPIO_6 | Reserved |
| P7 | 3V3_PCB_GPIO_7 | Reserved |

## Power System Details

### Voltage Control Loop

```
                    ┌─────────────┐
    5V ────────────►│  TPS63802   │─────────────► DUT_VDD (0.8-5.5V)
                    │ Buck-Boost  │       │
                    └──────▲──────┘       │
                           │              │
                    ┌──────┴──────┐       │
                    │   MCP4017   │◄──────┘
                    │  Digital    │  Feedback divider
                    │    Pot      │  R1=27k, R2=3k (REV 1.2)
                    └──────▲──────┘  R1=270k, R2=30k (REV 1.1)
                           │
                    I2C command from
                    mtib-server
```

### MCP4017 Voltage Calculation

Both revisions use the same voltage range but different pot values:

```python
def calculate_wiper_position(target_voltage: float, revision: str) -> int:
    """Calculate MCP4017 wiper position for target voltage."""
    # TPS63802 feedback equation: Vout = 0.8 * (1 + R1/R2)
    # MCP4017 acts as variable R1 in the feedback divider

    if revision == "1.2":
        pot_max = 10_000   # 10kΩ (MCP4017T-103E)
        r_fixed = 3_000    # R2 = 3kΩ
    else:  # REV 1.1
        pot_max = 100_000  # 100kΩ (MCP4017T-104E)
        r_fixed = 30_000   # R2 = 30kΩ

    # Solve for R1: R1 = R2 * (Vout/0.8 - 1)
    r1_needed = r_fixed * (target_voltage / 0.8 - 1)

    # Clamp to pot range
    r1_needed = max(0, min(pot_max, r1_needed))

    # Convert to wiper position (0-127)
    wiper = int(r1_needed / pot_max * 127)
    return wiper
```

### Current Monitoring

Two INA219 current sense amplifiers with 100mΩ shunts:
- **INA219 @ 0x40**: DUT supply current (0-3.2A range)
- **INA219 @ 0x41**: Charge/battery current

Linux exposes these via hwmon:
```
/sys/class/hwmon/hwmon0/
├── curr1_input    # Current in mA
├── in1_input      # Bus voltage in mV
└── power1_input   # Power in µW
```

### Motor Power Control (REV 1.2 Only)

REV 1.2 adds switchable motor power via TCA9534A P2:

```python
def enable_motor_power(enable: bool):
    """Enable/disable motor power (REV 1.2 only)."""
    # TCA9534A at 0x38, P2 = VMM_EN
    bus = smbus2.SMBus(1)

    # Read current output state
    current = bus.read_byte_data(0x38, 0x01)  # Output register

    if enable:
        bus.write_byte_data(0x38, 0x01, current | 0x04)  # Set P2
    else:
        bus.write_byte_data(0x38, 0x01, current & ~0x04)  # Clear P2
```

On REV 1.1, motor power is always on when EXT_VMM is supplied.

## Server Architecture

Located at: `~/work/concord/concord/apps/edge/mtib-server`

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         mtib-server-v2 (Python/gRPC)                        │
├────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      gRPC Server (Port 50054)                        │  │
│  │  - Bidirectional streaming (UART, power samples)                     │  │
│  │  - Session management per target                                     │  │
│  │  - Request routing via target_id                                     │  │
│  │  - Hardware revision detection at startup                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐ │
│  │                           Handlers                                    │ │
│  ├─────────┬─────────┬─────────┬───┴───┬─────────┬─────────┬───────────┤ │
│  │  Debug  │  Power  │   ADC   │ GPIO  │  UART   │ Sensor  │  Motion   │ │
│  │ Handler │ Handler │ Handler │Handler│ Handler │ Handler │  Handler  │ │
│  └────┬────┴────┬────┴────┬────┴───┬───┴────┬────┴────┬────┴─────┬────┘ │
│       │         │         │        │        │         │          │       │
│  ┌────┴────┬────┴────┬────┴───┬────┴───┬────┴────┬────┴────┬─────┴────┐ │
│  │nrfjprog │  hwmon  │  IIO   │ gpiod  │pyserial │   IIO   │ FluidNC  │ │
│  │         │  sysfs  │ sysfs  │ +smbus │         │  sysfs  │  UART    │ │
│  └─────────┴─────────┴────────┴────────┴─────────┴─────────┴──────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

### Handler Implementations

**DebugHandler (nrfjprog)**
- Flash firmware to Nordic targets
- Recover/erase operations
- Uses nrfjprog CLI (J-Link required)
- REV 1.2: Can switch J-Link routing via multiplexer

**PowerHandler (hwmon + MCP4017)**
```python
class PowerHandler:
    def __init__(self, revision: str):
        self.revision = revision
        self.bus = smbus2.SMBus(1)

    def set_dut_voltage(self, voltage_v: float) -> None:
        """Set DUT voltage via MCP4017."""
        wiper = calculate_wiper_position(voltage_v, self.revision)
        self.bus.write_byte(0x2F, wiper)

    def read_dut_current(self) -> float:
        """Read DUT current from INA219 via hwmon."""
        with open("/sys/class/hwmon/hwmon0/curr1_input") as f:
            return int(f.read()) / 1000.0  # mA to A
```

**ADCHandler (IIO sysfs)**
```python
def read_adc_channel(device: int, channel: int) -> float:
    """Read ADS1115 channel via IIO."""
    base = f"/sys/bus/iio/devices/iio:device{device}"
    with open(f"{base}/in_voltage{channel}_raw") as f:
        raw = int(f.read())
    with open(f"{base}/in_voltage{channel}_scale") as f:
        scale = float(f.read())
    return raw * scale / 1000.0  # Return volts
```

**GPIOHandler (gpiod + smbus for TCA9534A)**
```python
class GPIOHandler:
    def __init__(self, revision: str):
        self.revision = revision
        self.chip = gpiod.Chip("gpiochip0")
        if revision == "1.2":
            self.bus = smbus2.SMBus(1)
            self._init_tca9534a()

    def _init_tca9534a(self):
        """Initialize TCA9534A with all outputs low."""
        self.bus.write_byte_data(0x38, 0x03, 0x00)  # All outputs
        self.bus.write_byte_data(0x38, 0x01, 0x00)  # All low

    def set_jlink_mux(self, swap: bool) -> None:
        """Set J-Link multiplexer (REV 1.2 only)."""
        if self.revision != "1.2":
            raise NotImplementedError("J-Link mux only on REV 1.2")
        current = self.bus.read_byte_data(0x38, 0x01)
        if swap:
            self.bus.write_byte_data(0x38, 0x01, current | 0x01)
        else:
            self.bus.write_byte_data(0x38, 0x01, current & ~0x01)
```

**UARTHandler (pyserial)**
```python
import serial

ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.1)
ser.write(b"command\n")
response = ser.read_until(b"\n")
```

**SensorHandler (IIO sysfs)**
```python
# Read BME280 temperature
with open("/sys/bus/iio/devices/iio:device2/in_temp_input") as f:
    temp_milli_c = int(f.read())
    temp_c = temp_milli_c / 1000.0

# Read LIS2DE12 acceleration
with open("/sys/bus/iio/devices/iio:device3/in_accel_x_raw") as f:
    accel_x = int(f.read())
```

**MotionHandler (FluidNC UART)**
```python
class MotionHandler:
    def __init__(self, revision: str, gpio_handler: GPIOHandler):
        self.revision = revision
        self.gpio = gpio_handler
        self.ser = serial.Serial("/dev/ttyUSB1", 115200)

    def enable_motors(self, enable: bool) -> None:
        """Enable motor power (REV 1.2: via GPIO, REV 1.1: always on)."""
        if self.revision == "1.2":
            self.gpio.set_motor_power(enable)
        # REV 1.1: no-op, power controlled externally

    def send_gcode(self, command: str) -> str:
        """Send G-code to FluidNC."""
        self.ser.write(f"{command}\n".encode())
        return self.ser.read_until(b"ok\n").decode()
```

## DUT Connector Pinout

External DUT connector (CN1/CN2) - same on both revisions:

| Pin | Signal | Description |
|-----|--------|-------------|
| 1 | DUT_VDD | Regulated DUT power (0.8-5.5V) |
| 2 | GND | Ground |
| 3 | SWDIO | J-Link SWD data |
| 4 | SWCLK | J-Link SWD clock |
| 5 | nRESET | Target reset (active low) |
| 6 | SWO | Serial wire output |
| 7 | UART_TX | UART transmit (to DUT RX) |
| 8 | UART_RX | UART receive (from DUT TX) |
| 9-15 | GPIO0-6 | General purpose I/O (level shifted) |
| 16-23 | ADC0-7 | Analog inputs (0-14V range) |
| 24 | I2C_SDA | I2C data (level shifted) |
| 25 | I2C_SCL | I2C clock (level shifted) |
| 26 | SPI_MOSI | SPI data out |
| 27 | SPI_MISO | SPI data in |
| 28 | SPI_SCK | SPI clock |
| 29 | SPI_CS | SPI chip select |
| 30 | DUT_VIO | DUT I/O voltage reference (1.8/3.3V) |

## Kernel Device Tree Overlay

Located at: `~/work/concord/concord-os/meta-corekinect`

Overlays should detect and configure devices based on presence:

```dts
/* Common devices (both revisions) */
&i2c1 {
    mcp4017: mcp4017@2f {
        compatible = "microchip,mcp4017";
        reg = <0x2f>;
    };

    ina219_dut: ina219@40 {
        compatible = "ti,ina219";
        reg = <0x40>;
        shunt-resistor = <100000>; /* 100mΩ in µΩ */
    };

    ina219_charge: ina219@41 {
        compatible = "ti,ina219";
        reg = <0x41>;
        shunt-resistor = <100000>;
    };

    ads1115_0: ads1115@48 {
        compatible = "ti,ads1115";
        reg = <0x48>;
        #address-cells = <1>;
        #size-cells = <0>;
    };

    ads1115_1: ads1115@49 {
        compatible = "ti,ads1115";
        reg = <0x49>;
        #address-cells = <1>;
        #size-cells = <0>;
    };

    /* REV 1.2 only - probed at runtime */
    tca9534a: gpio@38 {
        compatible = "nxp,pca9534";
        reg = <0x38>;
        gpio-controller;
        #gpio-cells = <2>;
    };

    eeprom: eeprom@50 {
        compatible = "atmel,24c02";
        reg = <0x50>;
    };
};
```

## Data Flow Examples

### Power Profiling Session

```
Client                 Server                    Hardware
  │                      │                         │
  │──GetHardwareInfo()──>│                         │
  │<─────{rev: "1.2"}────│ (detects via I2C probe) │
  │                      │                         │
  │──SetDutVoltage(3.3)─>│                         │
  │                      │──I2C write MCP4017─────>│ Set feedback
  │<─────────────────────│   (wiper calc by rev)   │ resistor
  │                      │                         │
  │──EnableDutPower()───>│                         │
  │                      │──GPIO set DUT_PWR_EN───>│ Enable load switch
  │<─────────────────────│                         │
  │                      │                         │
  │──StreamPower()──────>│                         │
  │                      │──read hwmon @ 10Hz─────>│ INA219 samples
  │<─────power_sample────│<──curr/volt/power──────│
```

### J-Link Multiplexer Control (REV 1.2)

```
Client                 Server                    Hardware
  │                      │                         │
  │──SetJlinkMux(swap)──>│                         │
  │                      │──I2C TCA9534A P0=1─────>│ Set mux select
  │<─────────────────────│                         │
  │                      │                         │
  │──FlashFirmware()────>│                         │
  │                      │──nrfjprog via J-Link───>│ Flash via swapped path
```

### Motor Control (REV 1.2)

```
Client                 Server                    Hardware
  │                      │                         │
  │──EnableMotors(true)─>│                         │
  │                      │──I2C TCA9534A P2=1─────>│ Enable VMM_EN
  │<─────────────────────│                         │
  │                      │                         │
  │──Home()─────────────>│                         │
  │                      │──UART "$H"─────────────>│ FluidNC home
  │<─────"ok"────────────│<──────────────────────│
```

## Motion System (FluidNC)

The ESP32-based FluidNC controller enables automated positioning:

### G-Code Interface

```python
# Home all axes
motion.send("$H")

# Move to DUT position
motion.send("G0 X50 Y30 Z5 F3000")

# Probe down until contact
motion.send("G38.2 Z-10 F100")
```

### Stepper Configuration

| Axis | Driver | Steps/mm | Max Speed |
|------|--------|----------|-----------|
| X | A4988 #1 | 80 | 3000 mm/min |
| Y | A4988 #2 | 80 | 3000 mm/min |

## Zephyr Integration

### Shell Automation

```protobuf
rpc ZephyrShell(ZephyrShellRequest) returns (ZephyrShellResponse);
```

### Twister Integration

```protobuf
rpc TwisterRun(TwisterRunRequest) returns (TwisterRunResponse);
```

### Log Streaming

```protobuf
rpc ZephyrLogStream(ZephyrLogStreamRequest) returns (stream ZephyrLogEntry);
```

## Security Considerations

1. **Network isolation**: Test bench on isolated VLAN or VPN
2. **Authentication**: mTLS for gRPC connections
3. **Authorization**: Per-target access control
4. **Audit logging**: All operations logged with timestamps
5. **Resource limits**: Rate limiting to prevent DoS
6. **Physical security**: Test benches in secured lab areas

## References

- Schematic REV 1.1: `mtib_v2/hw_1.1.pdf` (dated 2/27/25)
- Schematic REV 1.2: `mtib_v2/hw_1.2.pdf` (dated 12/05/25)
- Device tree overlays: `~/work/concord/concord-os/meta-corekinect`
- Existing server: `~/work/concord/concord/apps/edge/mtib-server`
- Protocol definition: `mtib_v2/mtib_v2.proto`
