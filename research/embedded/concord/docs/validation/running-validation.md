---
min_role: DEVELOPER
---
# Running Validation

## Stages at a Glance

| Stage | What It Checks | Blocks Merge? |
|-------|---------------|---------------|
| **Smoke** | Boot, power draw, UART response | Yes |
| **POST** | Sensors, connectivity, peripherals (manufacturing test) | Yes |
| **Functional** | Feature tests with fixture stimulus (button, PPG, temperature) | Yes |
| **FUOTA** | OTA delivery via CoreCloud, MCUboot swap, version verify | Yes |
| **Release** | Regression suite on the release binary | No (nightly) |

Stages run in order -- smoke must pass before POST, and so on.

## Viewing Runs

Open **Validation** in the sidebar. Runs are grouped by product. Each row shows status (running, passed, failed, skipped), the current stage, duration, and a passed/failed/skipped test count. Click a run to drill into individual test results, logs, and timing.

## Triggering a Run

### From the UI

Open **Validation > Runs**, click **New Run**, pick the product, stage, and fixture, then hit **Start**. Concord spawns a K8s Job in the `validation` namespace. The job pulls the test package, connects to the MTIB fixture over gRPC, and runs pytest against the DUT.

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

Results stream back over WebSocket. The UI updates as each test completes.

## Test Packages

A test package bundles the pytest tests, fixture controllers, and config for a product. Concord stores it and the runner pulls it at job start.

Upload with `corectl`:

```bash
corectl validate upload ./my-test-package/
```

See [Writing Tests](writing-tests.md) for package structure and fixture controller patterns.

## FUOTA Testing

FUOTA tests walk the full OTA update path:

1. Device starts on version A (e.g., MFG v0.5.1)
2. CoreCloud delivers version B as a CFW
3. Device writes the CFW to the secondary flash slot
4. Power cycle triggers MCUboot swap
5. Device boots version B -- verified via UART boot logs

A dual-processor update (nRF9151 + nRF52840) takes roughly 10 minutes. The test polls CoreCloud progress endpoints until both targets hit 100%, then power-cycles and checks UART output.

One gotcha: CoreCloud strips the D (debug) flag from FUOTA plan targets. Debug CFWs will not deliver -- always use non-debug builds for FUOTA tests.
