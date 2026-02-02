# Theta Manufacturing CLI

Terminal UI for running the theta manufacturing workflow (Electrical → Flash → POST) against the Concord HTTP API.

## Setup

```bash
nx run manufacturing-theta-cli:setup
```

Then edit `.env` with your environment values if the defaults don't match.

## Usage

```bash
# Activate venv
source .venv/bin/activate && source .env

# Panel mode (4 devices)
python -m src.main --panel

# Singleton mode (1 device)
python -m src.main --singleton
```

Or via nx:

```bash
nx run manufacturing-theta-cli:start
```

## How it works

1. Scan/enter a board serial number when prompted
2. The CLI validates the SNR against the HTTP API and resolves the hostname→SNR mapping
3. Runs three tests in sequence: **Electrical**, **Firmware Flash**, **POST**
4. Each test executes in parallel across all panel slots via WebSocket
5. If a device fails a step, it's removed from subsequent tests — the rest continue
6. A live table shows per-device progress and errors in real time
7. After completion, scan another serial number to repeat

## Environment variables

| Variable | Description |
|----------|-------------|
| `API_URL` | Concord HTTP API base URL (concordproxy) |
| `CLUSTER_UUID` | Theta fixture cluster UUID |
| `ELECTRICAL_TEST_UUID` | UUID for the electrical test |
| `FW_FLASH_TEST_UUID` | UUID for the firmware flash test |
| `POST_TEST_UUID` | UUID for the POST test |
