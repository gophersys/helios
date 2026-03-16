# Re-personalization Workflow

## When Re-personalization Is Required

**After EVERY firmware flash via J-Link** — manufacturing firmware, production
debug, or production release. AP protect on the nRF52840 requires `--chiperase`
which wipes the entire flash including the personalization space.

## The Standard Sequence

```
1. Flash firmware       → nrfjprog --recover --chiperase --program <hex> --verify --reset --speed 4000
2. Power cycle + boot   → power_off, sleep(2), power_on, sleep(3)
3. Lock shells          → Open UARTs BEFORE power-on, spam lock_shell within ~2s window
4. Personalize          → CoreOps assigns device ID, device generates new EC keypair
5. Upload keys          → POST public key + SIM info to CoreOps proxy
6. Rekey IPC            → Replace hardcoded keys with device-specific keys
7. Enable AP protect    → (if production, not needed for validation cycling)
8. Power cycle          → Device ready for CoreCloud communication
```

## CoreOps API Calls (step 4-5)

- **Get device ID:** `POST https://10.4.45.3:443/v1/devices/ids/assign` body: `{"snr": "<SNR>"}`
  - Always returns the same device ID for the same SNR
- **Upload public key:** `POST https://10.4.45.3:443/v1/devices/keys/upload` body: `{"deviceId": "<ID>", "pubKey": "<base64>"}`
- **Save SIM info:** `POST https://10.4.45.3:443/v1/devices/iccids/save` body: `{"iccid": "<ICCID>", "carrier": "<carrier>", "snr": "<SNR>", "imei": "<IMEI>"}`

## What Changes vs What Stays

| Identifier | After re-flash | After re-personalize |
|-----------|---------------|---------------------|
| J-Link SNR | Same | Same |
| IMEI | Same | Same |
| Device ID | Same | Same (CoreOps is deterministic) |
| EC Public Key | **ERASED** | **NEW** (regenerated on device) |
| Server config | **ERASED** | Restored from personalization template |

## Validation Impact

During validation, we flash different firmware variants (mfg, debug, release)
multiple times. After each flash:
1. Device cannot talk to CoreCloud until re-personalized
2. CoreCloud needs the new public key to authenticate the device
3. OTA, telemetry, and all cloud features require active personalization

**The test framework's flash_firmware() path must either:**
- Include automatic re-personalization as part of the flash cycle
- OR require an explicit `repersonalize()` call after each flash

## Reference Code

Manufacturing POST test implements this:
- `apps/manufacturing/alpha/src/tests/post/step_9.py` — personalize + save keys
- `apps/manufacturing/alpha/src/tests/post/step_10.py` — rekey IPC
- `apps/manufacturing/alpha/src/tests/post/step_0.py` — boot + lock shells
