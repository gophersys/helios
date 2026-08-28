# Validation Device Registry

> Source: `apps/firmware/products/results.json` (extracted from manufacturing batch archives)
> Last updated: 2026-03-01

---

## Device 1: SNR 0964 — REV 1.2

| Field | Value |
|-------|-------|
| **J-Link SNR** | `0964` |
| **MTIB Revision** | REV 1.2 |
| **MTIB Node** | verdin-imx8mm-15005665 (10.4.45.33) |
| **Device ID** | `70B3D584C01E1FCC` |
| **IMEI** | `355025931735979` |
| **ICCID (Verizon)** | `89148000009808558441` |
| **ICCID (Onomondo)** | `89457300000037582833` |
| **Manufacturing Batch** | batch-7 (2026-02-04), 86 pass / 25 fail |
| **Manufacturing Status** | SUCCESSFUL |
| **Firmware at manufacture** | alpha v0.8 |

### REV 1.2 Hardware Notes

- TCA9534A GPIO expander present (I2C 0x38)
- EEPROM present (I2C 0x50)
- J-Link mux via TCA9534A P0
- Motor power switch via TCA9534A P2
- MCP4017 potentiometer: 10k ohm
- UART pins correct in hardware — no DTS pin swap overlay needed

---

## Device 2: SNR 097D — REV 1.1

| Field | Value |
|-------|-------|
| **J-Link SNR** | `097D` |
| **MTIB Revision** | REV 1.1 |
| **MTIB Node** | verdin-imx8mm-15702161 (10.4.45.32) |
| **Device ID** | `70B3D584C01E20A2` |
| **IMEI** | `355025937661526` |
| **ICCID (Verizon)** | `89148000009808567699` |
| **ICCID (Onomondo)** | `89457300000037574012` |
| **Manufacturing Batch** | batch-9 (2026-02-18), 100 pass / 0 fail |
| **Manufacturing Status** | SUCCESSFUL |
| **Firmware at manufacture** | alpha v0.8 |

### REV 1.1 Hardware Notes

- No TCA9534A GPIO expander
- No EEPROM
- No J-Link mux — direct SWD connection
- No motor power switch
- MCP4017 potentiometer: 100k ohm
- **UART pins swapped in hardware** — firmware needs DTS overlay for TX/RX pin swap

---

## Shared Configuration

Both devices share the same CoreCloud personalization config:

| Field | Value |
|-------|-------|
| **CoreCloud Server** | `dev.office.corekinect.cloud` |
| **Rekey Path** | `/api/system/devices/sessions/ssv1` |
| **Session Port** | 2022 |
| **Data Port** | 2023 |
| **Time Port** | 2024 |
| **Coproc FW App ID** | 108 |
| **SIM Activation** | Both Verizon + Onomondo activated |

---

## Identifier Permanence Rules

| Identifier | Permanent? | Notes |
|-----------|-----------|-------|
| J-Link SNR | **Yes** | Hardware serial of the debug probe |
| IMEI | **Yes** | Cellular modem hardware identifier |
| ICCIDs | **Yes** | SIM card identifiers (Verizon + Onomondo) |
| Device ID | **Yes** | CoreOps assigns deterministically from SNR — same SNR always returns same ID |
| EC Public Key | **NO** | Regenerated on-device during each personalization. Changes after every chip erase + re-personalize. |

**Implication for validation:** When comparing CoreCloud data across firmware
variants (debug vs release, mfg vs production), use Device ID as the stable
identifier. The public key will differ between flash cycles, but the Device ID
remains the same. CoreCloud must be updated with the new public key after each
re-personalization for the device to authenticate.

---

## Environment Variables for Test Runner

```bash
# Device 1: SNR 0964 on REV 1.2
export MTIB_HOST=10.4.45.33
export MTIB_PORT=50053
export DEVICE_ID=70B3D584C01E1FCC
export CORECLOUD_DB_ENV=VAL_1_0
export FIXTURE_PROFILE_PATH=libs/python/corekinect/test/validation/fixtures/alpha_b0.json

# Device 2: SNR 097D on REV 1.1
export MTIB_HOST=10.4.45.32
export MTIB_PORT=50053
export DEVICE_ID=70B3D584C01E20A2
export CORECLOUD_DB_ENV=VAL_1_0
export FIXTURE_PROFILE_PATH=libs/python/corekinect/test/validation/fixtures/alpha_b0.json
```
