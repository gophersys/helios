# Theta Manufacturing POST Test Suite Summary

## Pre-Test Setup

| Step | Description | Why |
|------|-------------|-----|
| Power cycle | Disable then enable DUT power at 4.0V | Ensures clean boot state |
| Lock shells | Lock both comms & app processor shells | Security - prevents unauthorized shell access |
| Disable debug UART | Disable debug UART on both processors | Security - closes debug interfaces |

## Test Sequence

| # | Test | Hardware/Component | Expected Values | Why |
|---|------|-------------------|-----------------|-----|
| 1 | Comms Chip IDs | nRF9151 external flash (W25Q64) | 0xef 0x40 0x17 | Verifies correct flash chip populated on comms processor |
| 2 | App Chip IDs | LIS2DW12 accelerometer | 0x44 | Verifies accelerometer present and communicating via I2C |
| 3 | BMS Test | MAX17263 gas gauge | Connected: yes, Chip ID: 0x4037 | Verifies battery management IC present, reads charge %, capacity, temp |
| 4 | Charger Test | BQ25622 charger IC | Chip ID: 0x22 (or 0x00 if not on charger) | Verifies charger IC present, reads charging state & battery voltage |
| 5 | GPS Test | SAM-M10Q GNSS module | Shutdown: no, Comms: OK | Verifies GPS module communication (not in shutdown = comms working) |
| 6 | Modem FW Version | nRF9151 modem | mfw_nrf91x1_2.0.2 | Confirms correct modem firmware flashed |
| 7 | IMEI/ICCID | nRF9151 modem + SIM | Valid IMEI (15 digits, Luhn check), valid ICCID from recognized carrier | Verifies modem identity and SIM card present/valid |
| 8 | External Flash | Both processors' external flash | Write/read pattern match | Tests flash read/write/erase on both nRF52840 and nRF9151 (runs in parallel) |
| 9 | Personalization | Device identity | Keys generated & uploaded | Generates device keypair, uploads to proxy server (if params provided) |
| 10 | AP Protect | Both processors | Enabled | Locks down debug access - production security hardening |

## Recognized SIM Carriers

| Carrier | ICCID Prefix |
|---------|--------------|
| Verizon | 89148 |
| Soracom | 894231 |
| Onomondo | 894573 |
| AT&T | 890103 |

## Key Notes

- Flash tests run in parallel on both processors to reduce test time
- IMEI/ICCID has retry logic (5 attempts, 3s delay) because modem takes ~9s to retrieve
- Charger test won't fail if device isn't on charger (chip ID 0x00 with err: -22 is expected)
- GPS test checks communication, not satellite lock (just verifies module responds)

---

## Device Personalization Log

### Summary Table

| SNR | Device ID | IMEI | ICCID | Status |
|-----|-----------|------|-------|--------|
| 08Y8 | 70B3D584C01E1D37 | - | - | **FAIL** |
| 08YA | 70B3D584C01E1D36 | 355025931734642 | 89010303300092784207 | PASS |
| 08YH | 70B3D584C01E1D30 | 355025931737066 | 89010303300092783373 | PASS |
| 08YJ | 70B3D584C01E1D31 | 355025931737082 | 89010303300092783365 | PASS |
| 08YK | 70B3D584C01E1D2E | 355025931737108 | 89010303300092783381 | PASS |
| 08YL | 70B3D584C01E1D2F | 355025931737090 | 89010303300092783399 | PASS |
| 08YY | 70B3D584C01E1D32 | 355025931733883 | 89010303300092783530 | PASS |
| 08YZ | 70B3D584C01E1D33 | 355025931733867 | 89010303300092783522 | PASS |
| 08Z0 | 70B3D584C01E1D35 | 355025931733909 | 89010303300092783548 | PASS |
| 08Z1 | 70B3D584C01E1D34 | - | - | **FAIL** |

### Device Public Keys

#### 08Y8

- **Device ID:** `70B3D584C01E1D37`
- **Status:** **FAILED POST TEST** - Process interrupted before completion

#### 08YA

- **Device ID:** `70B3D584C01E1D36`
- **Hex Public Key:** `0403ed0ed1af405fecf8946e8d949deb6e6f6b2ead237c98f816d8d84f69228a6a2e1075bfcd3fed4a919ea6127388492aad737011feb13da306e077e9b8661f60`
- **Base64 Public Key:** `BAPtDtGvQF/s+JRujZSd625vay6tI3yY+BbY2E9pIopqLhB1v80/7UqRnqYSc4hJKq1zcBH+sT2jBuB36bhmH2A=`

#### 08YH

- **Device ID:** `70B3D584C01E1D30`
- **Hex Public Key:** `046fbc87844aa9b9837a6b20d77e271b263f7e6ea934956f9c8d56a1e0c27c0687a4b3511f11ccc9a94d52f2d9abffa40efb886a2ec9cf9ebc39a43eabaa0bcfe2`
- **Base64 Public Key:** `BG+8h4RKqbmDemsg134nGyY/fm6pNJVvnI1WoeDCfAaHpLNRHxHMyalNUvLZq/+kDvuIai7Jz568OaQ+q6oLz+I=`

#### 08YJ

- **Device ID:** `70B3D584C01E1D31`
- **Hex Public Key:** `04929dd0fc5e08557ad18c3633692a658d7531462aab2367af2dce8db9cdd06984ca1eef700edd753ffcf930550e8bc31ea1a9074ccdceaae13918b02894d0440c`
- **Base64 Public Key:** `BJKd0PxeCFV60Yw2M2kqZY11MUYqqyNnry3OjbnN0GmEyh7vcA7ddT/8+TBVDovDHqGpB0zNzqrhORiwKJTQRAw=`

#### 08YK

- **Device ID:** `70B3D584C01E1D2E`
- **Hex Public Key:** `043da10460f77f87d92ca107719844ab4063a4cc233d0b587c4679f9235c02a5174645fac90c4be0c9965744cd1d8f2efb022944de710f1fd43985e640e10248c1`
- **Base64 Public Key:** `BD2hBGD3f4fZLKEHcZhEq0BjpMwjPQtYfEZ5+SNcAqUXRkX6yQxL4MmWV0TNHY8u+wIpRN5xDx/UOYXmQOECSME=`

#### 08YL

- **Device ID:** `70B3D584C01E1D2F`
- **Hex Public Key:** `047f9265a320440d5d7795aff8cef24796db5935c10e3f5c7045e09f1f9b248cc078f44e4d434f68b863183fc1faf394bad4a71b3ac67fee0e638d5b97b4bf3fe7`
- **Base64 Public Key:** `BH+SZaMgRA1dd5Wv+M7yR5bbWTXBDj9ccEXgnx+bJIzAePROTUNPaLhjGD/B+vOUutSnGzrGf+4OY41bl7S/P+c=`

#### 08YY

- **Device ID:** `70B3D584C01E1D32`
- **Hex Public Key:** `0479ef42952b098b9e788b4a1fcd497c1c08d28afd95e2d0d31a15559646483056ff294552f76d045f11016eaf3c76bf64a49e59dd191fc8e225e63a61ce934245`
- **Base64 Public Key:** `BHnvQpUrCYueeItKH81JfBwI0or9leLQ0xoVVZZGSDBW/ylFUvdtBF8RAW6vPHa/ZKSeWd0ZH8jiJeY6Yc6TQkU=`

#### 08YZ

- **Device ID:** `70B3D584C01E1D33`
- **Hex Public Key:** `044de708bb82589cb264dde2e5be4422fafa0ea4b3471ef8440159f64bd471a4576809bf15120b0eef468ca0e35076b0f1081f0aff45fb8777014fca6fdaa8fd9d`
- **Base64 Public Key:** `BE3nCLuCWJyyZN3i5b5EIvr6DqSzRx74RAFZ9kvUcaRXaAm/FRILDu9GjKDjUHaw8QgfCv9F+4d3AU/Kb9qo/Z0=`

#### 08Z0

- **Device ID:** `70B3D584C01E1D35`
- **Hex Public Key:** `0451795a8d91cfbd2c9ff20894d981824d177e21a3b4ec9187d9e74b519d5f3ed2ac1d8fd083b2feb37e0b0644595dac037d2646bc1b51266dcadb46edfa606004`
- **Base64 Public Key:** `BFF5Wo2Rz70sn/IIlNmBgk0XfiGjtOyRh9nnS1GdXz7SrB2P0IOy/rN+CwZEWV2sA30mRrwbUSZtyttG7fpgYAQ=`

#### 08Z1

- **Device ID:** `70B3D584C01E1D34`
- **Status:** **FAILED POST TEST** - No personalization data available

---

*All devices except 08Y8 and 08Z1 successfully completed POST test suite with IMEI/ICCID verification. ICCIDs indicate AT&T carrier (prefix 890103).*
