# Fixtures & MTIBs

## What's a Fixture?

A fixture = MTIB + sensors wired for a specific product. It's the physical test bench that talks to the DUT (device under test).

The **MTIB** (Manufacturing Test Interface Board) is the base hardware — a Toradex Verdin module with power supplies, GPIO, UART, ADC, J-Link muxing, and optional motion control. The **fixture** adds product-specific wiring: which GPIOs drive which sensors, power rail config, UART mapping.

## Adding an MTIB Node

Before you can create fixtures, register the MTIB with Concord.

1. Go to **Fixtures > Nodes**
2. Click **Add Node**
3. Fill in:

| Field | Example | Notes |
|-------|---------|-------|
| Name | `MTIB-REV1.2-33` | Human-readable label |
| Address | `10.4.45.33` | IP of the Verdin module |
| Port | `50053` | gRPC port (default) |
| Revision | `REV 1.2` | Hardware revision of the MTIB |

The system will test connectivity when you save. If it can't reach the gRPC server, it'll tell you.

## Creating a Fixture Design

A fixture design describes the hardware layout for a product. It's defined in the product's validation repo as a YAML + Python pair.

The YAML declares capabilities:

```yaml
# fixtures/alpha_b0/fixture.yaml
product: alpha-b0
revision: B0
capabilities: [button, peltier, charger_relay, ppg_simulator]
power:
  battery_installed: false
  ch0_voltage: 4.5
button:
  gpio_pin: 2
  active_low: true
peltier:
  gpio_pin: 4
  temp_adc_channel: 7
```

The Python controller implements the fixture logic:

```python
# fixtures/alpha_b0/controller.py
class AlphaB0Fixture(BaseFixture):
    def press_button(self, duration_s: float = 0.5):
        self.gpio_write(self.config.button.gpio_pin, True)
        time.sleep(duration_s)
        self.gpio_write(self.config.button.gpio_pin, False)
```

Register the design in Concord by uploading it through the UI (**Fixtures > Designs > Add Design**) or via `corectl`:

```bash
corectl fixture upload ./fixtures/alpha_b0/
```

## Creating Fixture Instances

A fixture instance ties a design to a physical MTIB node. One MTIB can host multiple fixture instances if it has the wiring.

1. Go to **Fixtures > Instances**
2. Click **Add Instance**
3. Select the MTIB node (e.g., `MTIB-REV1.2-33`)
4. Select the fixture design (e.g., `Alpha B0`)
5. Set the slot name (e.g., `slot-1`)

## Assigning Devices to Slots

Once a fixture instance exists, assign a DUT to it:

1. Open the fixture instance
2. Click **Assign Device**
3. Enter the device serial number (e.g., `0964`)

The system looks up the device in CoreCloud and links it. Validation runs will target this device on this fixture.

### J-Link Probe Mapping

Each fixture instance needs J-Link probe serial numbers mapped to targets:

| Probe SNR | Family | Target |
|-----------|--------|--------|
| `821009543` | NRF52 | nRF52840 app processor |
| `821009541` | NRF91 | nRF9151 comms coprocessor |

Set these in the fixture instance configuration. The test runner uses them for flashing operations.
