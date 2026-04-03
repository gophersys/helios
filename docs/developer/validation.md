# Validation

## What Are Validation Stages?

Validation is a multi-stage pipeline that tests firmware on real hardware. Each stage checks something different:

| Stage | What It Tests |
|-------|--------------|
| **Smoke** | Board boots, power draw is sane, UART responds |
| **POST** | Manufacturing production test — sensors, connectivity, peripherals |
| **Functional** | Full feature testing with fixture stimulus (button, PPG, temperature) |
| **FUOTA** | Over-the-air firmware update — CFW delivery, MCUboot swap, version verify |
| **Release** | Final gate before production — regression suite on release firmware |

Stages run in order. A board has to pass smoke before it moves to POST, and so on.

## Viewing Runs

Go to **Validation** in the sidebar. You'll see runs grouped by product. Each run shows:

- **Status** — running, passed, failed, or skipped
- **Stage** — which validation stage
- **Duration** — how long it took
- **Test count** — passed / failed / skipped breakdown

Click a run to see individual test results, logs, and timing.

## Triggering a Validation Run

### From the UI

1. Go to **Validation > Runs**
2. Click **New Run**
3. Select product, stage, and fixture
4. Click **Start**

The system spawns a K8s Job in the `validation` namespace. The job pulls the test package, connects to the MTIB fixture, and runs pytest against the DUT.

### From the API

```bash
curl -X POST https://concord.local/v2/validation/runs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "productId": "<product-id>",
    "stage": "smoke",
    "fixtureId": "<fixture-id>"
  }'
```

Results stream back in real time via WebSocket. The UI updates as each test completes.

## Test Packages

Test packages contain the pytest tests, fixture controllers, and config for a specific product. They're uploaded to Concord and pulled by the runner at job start.

Upload a test package with `corectl`:

```bash
corectl validate upload ./my-test-package/
```

See [Writing Tests](writing-tests.md) for how to structure a test package.

## FUOTA Testing

FUOTA (Firmware Update Over The Air) tests verify the OTA update path:

1. Device starts on version A (e.g., MFG v0.5.1)
2. FUOTA delivers version B (e.g., MFG v0.5.2) via CoreCloud
3. Device receives CFW, writes to secondary flash slot
4. Power cycle triggers MCUboot swap
5. Device boots on version B — verified via UART boot logs

FUOTA delivery takes ~10 minutes for a dual-processor update (nRF9151 + nRF52840). The test watches CoreCloud progress endpoints until both targets hit 100%, then power-cycles and checks UART output.

Important: CoreCloud strips the D (debug) flag from FUOTA plan targets. Debug CFWs don't work for FUOTA — always use non-debug builds.
