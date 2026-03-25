# Device Personalization and Key Provisioning

## Overview

Device personalization is the process of giving each device a unique identity and cryptographic credentials so it can securely communicate with CoreCloud. This happens during manufacturing and must be replicated (or simulated) in the validation pipeline.

Every device that leaves the factory has:
- A **unique Device ID** (EUI-64 format)
- An **ECDSA P-256 key pair** generated on-device (private key never leaves the device)
- A **registration record** in CoreCloud linking the Device ID to its public key
- **Encrypted IPC** between the app processor and comms processor
- **TLS client certificate** and **session keys** for CoreCloud communication

This document traces the full lifecycle from bare silicon through production deployment, then maps the implications for the validation pipeline.

---

## Personalization Flow (Manufacturing)

### Step 1: Device ID Assignment

CoreOps API (or Concord) assigns a unique Device ID in EUI-64 format.

```
Example EUI: 70B3D584C0201234
```

The EUI is sent to the comms processor via UART:

```
personalize <device_id>
```

- The device stores the ID in non-volatile storage (ZMS/NVS on the nRF9151)
- This ID is **permanent** and persists across firmware updates
- The ID is the device's primary identity across all CoreCloud environments

### Step 2: Key Generation (On-Device)

The device generates an ECDSA P-256 key pair internally on the comms processor:

- **Private key** is generated and stored in secure storage on the nRF9151
- **Private key NEVER leaves the device** -- there is no command or mechanism to export it
- **Public key** is exported via UART using the `get_pub_key` command

```
> get_pub_key
PUB_KEY:<base64-encoded ECDSA P-256 public key>
```

The key pair is bound to the device's identity. The comms processor manages all cryptographic operations.

### Step 3: Public Key Upload to CoreCloud

The test fixture (MTIB or manufacturing station) reads the public key from UART output and uploads it to the CoreCloud REST API:

```
POST /System/Devices/Register
Content-Type: application/json

{
  "deviceId": "70B3D584C0201234",
  "deviceType": 2,
  "deviceVariant": 3,
  "publicKey": "<base64-encoded public key>"
}
```

Registration parameters:
| Field | Value | Description |
|-------|-------|-------------|
| `deviceId` | EUI-64 string | Unique device identifier |
| `deviceType` | `2` | Alpha product family |
| `deviceVariant` | `3` | B0 hardware revision |
| `publicKey` | Base64 string | ECDSA P-256 public key from Step 2 |

This creates the device record in CoreCloud's database, associating the device's identity with its public key.

### Step 4: IPC Rekey

The `rekey_ipc` UART command establishes encrypted communication between the two processors:

```
> rekey_ipc
IPC_REKEY:OK
```

- **App processor**: nRF52840 (sensors, BLE, application logic)
- **Comms processor**: nRF9151 (LTE-M, CoreCloud communication)
- **IPC channel**: LPUART between the two processors

New AES keys are generated for the LPUART IPC channel. This ensures inter-processor messages cannot be sniffed even with physical access to the UART lines.

---

## Post-Manufacturing Key Exchange

After personalization, the device must establish secure communication with CoreCloud. This is a multi-step handshake.

### Step 5: Time Server Contact

The device boots with manufacturing firmware and connects to the manufacturing CoreCloud environment:

1. Device powers on and connects to the cellular network (LTE-M)
2. Contacts CoreCloud Time Server to get accurate UTC time
3. Accurate time is required for TLS certificate validation (expiry checks, certificate chain verification)

Without accurate time, the device cannot validate server certificates and will fail to establish TLS connections.

### Step 6: TLS Certificate Acquisition

The device uses its ECDSA key pair to authenticate with CoreCloud:

1. Device presents its Device ID and signs a challenge with its private key
2. CoreCloud verifies the signature against the registered public key
3. CoreCloud's CA issues a TLS client certificate for the device
4. Device stores the client certificate in secure storage

The client certificate enables mutual TLS (mTLS) for all subsequent HTTPS communication with CoreCloud.

### Step 7: Rekey via HTTPS

The device performs an HTTPS POST to the CoreCloud REST Server using its client certificate:

1. Server validates the client certificate against the registered public key
2. Server generates and returns session keys:
   - **AES-256 session key** for payload encryption
   - **HMAC-SHA-256 key** for message authentication
3. Device stores the session keys in secure storage

These session keys are used for all subsequent Socket Server communications (the persistent bidirectional channel).

### Step 8: Socket Server Connection

The device connects to the CoreCloud Socket Server using the session keys:

- All uplink messages (sensor data, status reports) are encrypted with AES-256 and authenticated with HMAC-SHA-256
- All downlink messages (configuration, commands, FUOTA triggers) use the same encryption
- The device is now fully operational on the manufacturing CoreCloud environment

```
Device ──[AES-256 + HMAC-SHA-256]──> CoreCloud Socket Server
Device <──[AES-256 + HMAC-SHA-256]── CoreCloud Socket Server
```

---

## Transition to Production (via FUOTA)

### Step 9: Production Firmware OTA

A FUOTA (Firmware Update Over The Air) plan transitions the device from manufacturing firmware to production firmware:

1. CoreCloud creates a FUOTA plan targeting the device
2. FUOTA plan is delivered via Socket Server downlink
3. Device downloads the production firmware image
4. Device verifies the image signature (MCUBoot)
5. Device reboots with production firmware

### Step 10: Production Server Migration

After the production firmware is running, the device must be migrated to the production CoreCloud environment:

1. **Public key upload**: The device's public key must be uploaded to the PRODUCTION CoreCloud REST API (same `POST /System/Devices/Register` call, different server)
2. **Configuration downlink**: A downlink message changes the device's server endpoints from manufacturing to production URLs
3. **Production rekey**: The device performs the same rekey sequence (Steps 5-8) with the production CoreCloud
4. **Operational**: The device is now connected to production infrastructure

This is a one-way transition. Moving a device back to manufacturing requires re-personalization.

---

## Complete Lifecycle Diagram

```
Manufacturing Line
    │
    ├─ Step 1: personalize <EUI>           → Device ID in NVS
    ├─ Step 2: (on-device key gen)         → ECDSA P-256 key pair in secure storage
    ├─ Step 3: get_pub_key → API upload    → Device registered in MFG CoreCloud
    ├─ Step 4: rekey_ipc                   → Encrypted IPC between processors
    │
    ▼
Manufacturing CoreCloud
    │
    ├─ Step 5: Time Server contact         → Accurate UTC time
    ├─ Step 6: TLS certificate             → mTLS client cert
    ├─ Step 7: HTTPS rekey                 → AES-256 + HMAC session keys
    ├─ Step 8: Socket Server connect       → Fully operational (MFG environment)
    │
    ▼
Production Transition (FUOTA)
    │
    ├─ Step 9: Production FW OTA           → New firmware, reboot
    ├─ Step 10: Production server migration → Rekey with production CoreCloud
    │
    ▼
Production CoreCloud
    └─ Device operational in production
```

---

## CoreCloud Device Management REST API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/System/Devices/Register` | POST | Register new device with type, variant, and public key |
| `/System/Devices/Search` | GET | Search devices with filters (type, variant, ID) |
| `/System/Devices/Update` | PATCH | Update device type or variant |
| `/System/Devices/Set-Account` | POST | Transfer device between accounts |
| `/System/Devices/Move-To-System-Account` | POST | Reset device to system account (unassign from user) |

### Registration Request

```http
POST /System/Devices/Register
Content-Type: application/json

{
  "deviceId": "70B3D584C0201234",
  "deviceType": 2,
  "deviceVariant": 3,
  "publicKey": "<base64-encoded ECDSA P-256 public key>"
}
```

### Search Request

```http
GET /System/Devices/Search?deviceId=70B3D584C0201234
```

These endpoints are available on all CoreCloud instances (manufacturing, validation, production). The validation pipeline will need authenticated access to the validation CoreCloud's REST API.

---

## Validation Pipeline Implications

For Stage 4 validation (end-to-end CoreCloud connectivity testing), the personalization lifecycle has direct impact on how the pipeline is designed and operated.

### Dedicated Validation CoreCloud

A separate CoreCloud instance (VAL_1_0 namespace) is required so that validation devices connect to an isolated environment. This keeps validation traffic completely separate from manufacturing and production.

| Environment | CoreCloud Instance | Purpose |
|-------------|-------------------|---------|
| Manufacturing | MFG CoreCloud | Factory line personalization and initial provisioning |
| Validation | VAL_1_0 CoreCloud | Automated test pipeline (Stage 4) |
| Production | PROD CoreCloud | End-user devices in the field |

### Device Registration Strategy

Each validation DUT must be registered with the validation CoreCloud before testing begins. Two approaches are possible:

**Option A: Pre-registered persistent test devices**
- A fixed set of DUTs are personalized once and permanently registered with the validation CoreCloud
- Devices stay in the validation environment across test runs
- Simpler operationally; no per-run registration overhead
- Risk: keys or NVS state may drift over time with repeated reflashing

**Option B: Dynamically registered per test run**
- Fresh devices are personalized and registered at the start of each test run
- Requires manufacturing firmware to be flashed before each run
- More realistic (tests the full personalization flow) but slower
- Better for testing the personalization flow itself

For most validation work, **Option A is recommended** with periodic re-personalization if key state becomes corrupted.

### Key Management Constraints

- If devices are already personalized (from manufacturing), their ECDSA key pairs are already generated and stored on-device
- The **public key must be registered with the VALIDATION CoreCloud**, not the manufacturing or production instance
- Session keys (AES-256, HMAC-SHA-256) will be established with the validation server during the rekey flow
- **Private keys cannot be extracted** -- if a device's key state is corrupted, re-personalization (reflash + `personalize` + `rekey_ipc`) is required

### Server Configuration

Devices must be configured to point to the validation CoreCloud endpoints. Two approaches:

1. **Build-time configuration**: The validation firmware build has validation server URLs compiled in (preferred for simplicity)
2. **Runtime configuration downlink**: After FUOTA, a configuration downlink redirects the device to validation server endpoints

For the validation pipeline, build-time configuration is simpler and avoids the chicken-and-egg problem of needing a CoreCloud connection to configure the CoreCloud connection.

### FUOTA Interaction

FUOTA plans in the validation CoreCloud control firmware transitions during testing:

- The device **must be registered and have valid session keys BEFORE FUOTA can work** (the device must be connected to the Socket Server to receive FUOTA downlinks)
- After each FUOTA, the device reboots and re-establishes its connection with the new firmware
- FUOTA testing validates both the firmware update mechanism and the post-update reconnection flow

### Validation Personalization Sequence

For a fresh device entering the validation pipeline:

```
1. Flash manufacturing firmware (nrfjprog --recover + --program)
2. Open UART, power on DUT at 4.5V
3. Lock manufacturing shell (lock_shell within 2s of boot)
4. Send: personalize <EUI>
5. Send: get_pub_key → capture base64 public key
6. Upload public key to VAL CoreCloud: POST /System/Devices/Register
7. Send: rekey_ipc
8. Device connects to VAL CoreCloud (Steps 5-8 of lifecycle)
9. Device is ready for validation test sequences
```

For a pre-registered device returning for another test run:

```
1. Flash test firmware (nrfjprog --recover + --program)
2. Power on DUT at 4.5V
3. Device boots, connects to VAL CoreCloud using existing keys
4. Device is ready for validation test sequences
```

---

## Security Considerations

### Private Key Protection

- Private keys **never leave the device** -- the validation pipeline cannot extract or inject keys
- All cryptographic operations (signing, key agreement) happen on the comms processor (nRF9151)
- There is no debug command or JTAG interface to read the private key from secure storage

### Re-personalization

If a device needs new keys (e.g., corrupted state, moving between environments):

1. Flash manufacturing firmware onto the comms processor (nRF9151)
2. Run `nrfjprog --recover` to clear APPROTECT and reset the debug port
3. Flash the manufacturing firmware image
4. Re-run the full personalization sequence (Steps 1-4)
5. Re-register the new public key with the target CoreCloud

### APPROTECT

- **Production firmware** enables APPROTECT, which locks the debug port (SWD/JTAG)
- **Debug/validation firmware** should NOT enable APPROTECT to allow iterative flashing
- Recovery (`nrfjprog --recover --speed 4000`) clears APPROTECT but **erases all flash**, including keys
- After recovery, the device must be fully re-personalized

### Session Key Rotation

- Session keys (AES-256, HMAC-SHA-256) are generated during the rekey flow
- Keys can be rotated by repeating the HTTPS rekey (Step 7)
- If session keys are compromised, the device can rekey without re-personalization (the ECDSA identity key pair remains valid)

---

## Open Questions

The following items need resolution before the validation pipeline can fully automate device personalization:

1. **Device reuse across test runs**: Can validation devices be pre-registered once and reused across test runs, or does each reflash cycle invalidate the stored keys?

2. **Key persistence across reflash**: Does reflashing manufacturing firmware (via `nrfjprog --program --chiperase`) reset the device's ECDSA keys, or are they preserved in NVS/secure storage? If `--chiperase` wipes NVS, the device must be re-personalized after every flash.

3. **Factory reset capability**: Is there a "factory reset" command that wipes keys and requires re-personalization? If so, what is the command and what exactly does it erase?

4. **Validation CoreCloud API access**: What CoreCloud REST endpoints are needed for automated device registration in the validation pipeline? Are there service account credentials or API keys available for machine-to-machine access?

5. **API parity**: Does the validation CoreCloud instance have the same device management APIs as production, or is it a reduced subset?

6. **Concurrent device registration**: Can the validation pipeline register multiple devices in parallel, or are there rate limits on the `/System/Devices/Register` endpoint?

7. **Device deregistration**: Is there an API to deregister a device from one CoreCloud instance before registering it with another? Or can the same Device ID be registered on multiple CoreCloud instances simultaneously?

8. **Key state inspection**: Is there a UART command to check whether a device has valid keys without triggering a rekey? Something like `key_status` that reports whether ECDSA keys, IPC keys, and session keys are present and valid.
