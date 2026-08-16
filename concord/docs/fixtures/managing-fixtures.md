---
min_role: MAINTAINER
---
# Managing Fixtures

## MTIB Nodes

Before creating fixtures, register the MTIB hardware with Concord.

Open **Fixtures > Nodes** and click **Add Node**:

| Field | Example | Notes |
|-------|---------|-------|
| Name | `MTIB-REV1.2-33` | Human-readable label |
| Address | `10.4.45.33` | IP of the Verdin module |
| Port | `50053` | gRPC port (default) |
| Revision | `REV 1.2` | Hardware revision of the MTIB |

Concord tests gRPC connectivity on save and reports failures immediately.

## Fixture Designs

A fixture design describes the hardware layout for a product. It lives in the product's validation repo as a YAML + Python pair.

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

The Python controller implements fixture logic:

```python
# fixtures/alpha_b0/controller.py
class AlphaB0Fixture(BaseFixture):
    def press_button(self, duration_s: float = 0.5):
        self.gpio_write(self.config.button.gpio_pin, True)
        time.sleep(duration_s)
        self.gpio_write(self.config.button.gpio_pin, False)
```

Upload the design through **Fixtures > Designs > Add Design** or via the CLI:

```bash
corectl fixture upload ./fixtures/alpha_b0/
```

## Fixture Instances

A fixture instance ties a design to a physical MTIB node. One MTIB can host multiple instances if it has the wiring.

Open **Fixtures > Instances**, click **Add Instance**, and configure:

1. Select the MTIB node (e.g., `MTIB-REV1.2-33`)
2. Select the fixture design (e.g., `Alpha B0`)
3. Set the slot name (e.g., `slot-1`)

## Device Assignment

Once a fixture instance exists, assign a DUT to it:

1. Open the fixture instance
2. Click **Assign Device**
3. Enter the device serial number (e.g., `0964`)

Concord looks up the device in CoreCloud and links it. Validation runs target this device on this fixture.

### J-Link Probe Mapping

Each fixture instance needs J-Link probe serial numbers mapped to targets:

| Probe SNR | Family | Target |
|-----------|--------|--------|
| `821009543` | NRF52 | nRF52840 app processor |
| `821009541` | NRF91 | nRF9151 comms coprocessor |

Set these in the fixture instance configuration. The test runner uses them for `nrfjprog` flashing operations.
