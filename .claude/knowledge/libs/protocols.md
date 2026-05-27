# `libs/protocols` — knowledge

Protobuf definitions for cross-process contracts in Concord. Today there is
exactly one service — **MTIB v1** — defined here and consumed by
`mtib-server` (Go), the http-api MTIB client (Python), runner pods (Python),
and Zephyr firmware (nanopb).

Refresh this file when: a new `.proto` is added; a new RPC method is added
or removed; the code generation flow (`ctl.sh`) is reshaped; the proto
versioning policy in `mtib/CHANGELOG.md` changes; nanopb plugin path moves.

## Location

```
libs/protocols/
├── __init__.py             # empty marker
├── ctl.sh                  # codegen entry — invoked by nx
├── project.json            # nx targets: create, clean
└── mtib/
    ├── __init__.py
    ├── VERSION             # "1.0.0" — proto wire-format version
    ├── CHANGELOG.md        # versioning policy + change log
    ├── mtib.proto          # source of truth — package mtib.v1
    ├── mtib_pb2.py         # generated, gitignored under .gitignore
    ├── mtib_pb2_grpc.py    # generated
    └── mtib_pb2.pyi        # generated stubs (for type checkers)
```

`.gitignore` at the libs/protocols root excludes generated `*.py` (except
`__init__.py`), `*.c`, and `*.h`. Generated code is shipped via the
`corekinect` wheel (see [`python-corekinect.md`](python-corekinect.md)) and
generated into firmware build trees at build time, never committed.

## What it covers

| Component | Use |
|---|---|
| `mtib/mtib.proto` | Defines `service MtibV1` (port 50053) + every message type for power, GPIO, ADC, sensors, motion, firmware programming, UART streaming, NFC, observability. |
| `mtib/VERSION` | Wire-format version. Bumped per the policy in `CHANGELOG.md`. Surfaces in `Release.protoVersion` for release tracking. |
| `mtib/CHANGELOG.md` | Versioning policy: patch=docs, minor=additive, major=breaking. |
| `ctl.sh` | Bash codegen orchestrator. Discovers `.proto` files under `libs/protocols/`, dedups duplicates, drives both Python (`grpc_tools.protoc`) and nanopb codegen. |

## MtibV1 service — RPC inventory

Source: `libs/protocols/mtib/mtib.proto`. Port `50053`.

| RPC | Streaming | Purpose |
|---|---|---|
| `HealthCheck` | — | Readiness + capabilities + hw_revision. |
| `GpioConfig` / `GpioWrite` / `GpioRead` | — | Direct GPIO control. |
| `GpioWatch` | server-stream | Edge-triggered watch (`GpioEdge`). |
| `AdcRead` / `AdcReadAll` | — | Single-shot ADC. |
| `AdcStream` | server-stream | Multi-channel ADC at configurable interval. |
| `AltimeterRead` / `AccelRead` | — | On-board sensors. |
| `GetMotionStatus` / `MotionStart` (stream) / `MotionHome` / `MotionStop` | mixed | FluidNC linear-rail control. `VALIDATION` fixtures only. |
| `ListProgrammers` / `ListFwFiles` / `UploadFwFile` (client-stream) / `DeleteFwFile` / `FlashFwFile` / `EraseFlash` / `EnableAppProtect` | mixed | J-Link / Black Magic firmware programming. |
| `UartStream` | bidi-stream | UART to DUT. |
| `PowerEnable` / `PowerDisable` / `PowerRead` / `PowerMeasure` | — | INA219 / MCP4017 / Joulescope power channels. |
| `PowerStream` | server-stream | Continuous power samples. |
| `NfcPoll` / `NfcReadNdef` | — | NFC reader. |
| `GetSnapshot` | — | Full observability snapshot (all power, gpio, adc state). |

Power channels: `POWER_CHANNEL_DUT` (INA219 @ 0x40 + MCP4017),
`POWER_CHANNEL_CHARGER` (INA219 @ 0x41), `POWER_CHANNEL_JOULESCOPE` (USB
JS220 — always-on, optional). Host types for programming:
`HOST_TYPE_NRF9160 / NRF9160_MODEM / NRF52840 / NRF5340 / NRF9151 /
NRF9151_MODEM`.

## Codegen flow

Driven by `libs/protocols/ctl.sh`. The Nx wrapper is in
`libs/protocols/project.json`:

| Nx target | Command | Effect |
|---|---|---|
| `nx run protocols:create` | `./libs/protocols/ctl.sh generate` | Generates Python `*_pb2.py`, `*_pb2_grpc.py`, and nanopb `*.pb.c/h` next to each `.proto`. |
| `nx run protocols:clean` | `./libs/protocols/ctl.sh clean` | Removes all generated files (Python `*.py` except `__init__.py`, `*.c`, `*.h`). |

### Auto-run before every consumer build (since v0.12.12)

The generated `*_pb2.py` / `*_pb2_grpc.py` files are gitignored
(`libs/protocols/.gitignore` excludes `**/*.py` except `__init__.py`).
Every consumer Nx target that builds an artifact depending on these
stubs declares `protocols:create` as a `dependsOn`, so the codegen runs
automatically before the build — no manual step required.

| Consumer | Nx target with the dependency |
|---|---|
| `http-api` | `containerize` (consumes `protocols.mtib.mtib_pb2` in `services/devices/mtib_observability.py`) |
| `build-service` | `containerize` (defensive — has `PYTHONPATH` reference) |
| `git-poller` | `containerize` (defensive — has `PYTHONPATH` reference) |
| `mtib-server` | `containerize` (gRPC server side of MtibV1) |
| `test-runner` | `containerize` (bakes the runner image with corekinect + protocols) |
| `corekinect` | `build` (the wheel ships protocols via `force-include`) |

Plus the matching `implicitDependencies: ["protocols"]` so Nx's
affected-graph marks each consumer dirty when `libs/protocols/**`
changes — that's how `/concord-release`'s Phase 1.5 runner-rebuild gate
fires correctly on proto edits.

This wiring was introduced after a v0.12.11 production deploy crashed
the http-api on `ModuleNotFoundError: No module named
'protocols.mtib.mtib_pb2'` — the gitignored generated module was
missing from the build context because no Nx target had forced
`protocols:create` to run. See v0.12.12 commit `chore(nx): wire
protocols:create as dependsOn for every consumer build`.

`ctl.sh` notes:

- Walks `libs/protocols` with `find -name '*.proto'`. Duplicate basenames
  warn and only the first wins.
- For Python: requires `grpc_tools.protoc`. After generation it rewrites
  `import foo_pb2 as foo` lines in the generated file to
  `import protocols.foo.foo_pb2 as foo` so the package path resolves under
  `corekinect`'s force-included `protocols/` directory.
- For nanopb: looks for the nanopb generator at
  `/ncs/modules/lib/nanopb/generator/protoc-gen-nanopb` (the path inside
  the firmware devcontainers). If missing, skips with a warning rather
  than failing — Python-only consumers can regenerate without the firmware
  toolchain.
- Each proto's `package mtib.v1;` line decides where the file imports from
  in the generated rewrite.

The generated Python stubs are shipped to all Python consumers via the
`corekinect` wheel (`[tool.hatch.build.targets.wheel.force-include]` in
`libs/python/pyproject.toml` copies `../protocols` into the built wheel).
No service depends directly on `libs/protocols` at runtime — they all get
the stubs through the wheel.

Firmware consumers regenerate nanopb during their own build (inside their
firmware devcontainer where the nanopb plugin lives).

## Versioning policy

From `mtib/CHANGELOG.md`:

| Bump | When |
|---|---|
| Patch | Documentation, comment-only changes inside `.proto`. |
| Minor | Additive — new fields with default values, new RPCs, new enum values. Existing clients keep working. |
| Major | Breaking — removing/renaming fields, changing field numbers or types. Requires lockstep update of every consumer + a platform release that bundles them. |

The `mtib/VERSION` file is the authority; `mtib.proto` keeps
`package mtib.v1;` and a future major bump moves it to `mtib.v2` with a
side-by-side service definition during the migration window.

## How to add common things

### Add a new RPC method to MtibV1

1. Add the `rpc` line under `service MtibV1 { … }` in `mtib/mtib.proto`.
2. Add the request + response messages below.
3. If the RPC is purely additive, bump `mtib/VERSION` to a new minor.
4. `nx run protocols:create` — regenerates the Python stubs locally so
   imports resolve.
5. Implement on the server side in `apps/edge/mtib-server/` (Go).
6. Implement on the client side in
   `libs/python/corekinect/mtib_client/v1/client/core.py`.
7. Republish the `corekinect` wheel
   (`nx run corekinect:build && nx run corekinect:push`) so consumers get
   the new stubs.
8. Update the firmware consumer if it needs the new RPC (rebuild + ship).
9. Update `mtib/CHANGELOG.md` describing the change.

### Add a new proto file (a second service)

1. `mkdir libs/protocols/<service>/` and add the `.proto`. Declare a
   distinct `package <service>.v1;`.
2. Add a `VERSION` file and a `CHANGELOG.md` mirroring `mtib/`'s.
3. `nx run protocols:create` — the script discovers all `.proto` files
   under `libs/protocols/` automatically.
4. Decide whether the new service is shipped via the `corekinect` wheel
   (it already force-includes the entire `protocols/` tree, so the answer
   is yes by default).
5. Add this knowledge file to the structure block.

### Regenerate stubs locally for debugging

`nx run protocols:create`. Generated files land in
`libs/protocols/<svc>/*.py` and are gitignored. If something looks stale,
`nx run protocols:clean` first.

## Common failure modes

- **`ModuleNotFoundError: No module named 'protocols.mtib.mtib_pb2'`** in a
  service that pip-installed `corekinect`. The wheel was built without the
  force-include block — see [`python-corekinect.md`](python-corekinect.md).
- **`import grpc_tools.protoc` fails during `nx run protocols:create`.**
  `grpcio-tools` is missing from the devcontainer Python env. The script
  prints a warning and skips Python generation; Python consumers will keep
  whatever stubs they already have.
- **`protoc-gen-nanopb` not executable.** Path
  `/ncs/modules/lib/nanopb/generator/protoc-gen-nanopb` doesn't exist in
  the current container. nanopb generation is skipped with a warning —
  this is fine for Python-only work but breaks firmware builds. Run
  inside the firmware devcontainer.
- **Generated `*_pb2.py` imports don't resolve at runtime.** The `sed`
  rewrite step in `generate_python` failed silently — usually because
  the `package` line is missing or malformed. Add `package <name>.v1;`
  to the `.proto`.
- **Two `.proto` files with the same basename.** `gather_proto_files`
  warns and silently drops one. Rename so basenames are unique.

## Related knowledge

- [`python-corekinect.md`](python-corekinect.md) — wheel-level
  redistribution of the generated stubs.
- [`../apps/edge/mtib-server.md`](../apps/edge/mtib-server.md) — Go
  implementation of `MtibV1`.
- [`../apps/backend/http-api.md`](../apps/backend/http-api.md) — uses
  the Python MTIB client for fixture observability polling.
- [`../glossary.md`](../glossary.md) — MTIB / DUT / Fixture / Verdin
  definitions.

## v0.12.12 (continued) — `gather_proto_files` under `set -u`

The `ctl.sh generate` path silently no-op'd under `set -u` because `${proto_map[$name]}` errored on first-key lookup (unbound). Fixed by using `:-` default-empty: `${proto_map[$name]:-}`. Without this fix, the `nx run protocols:create` target reported success but produced zero `*_pb2.py` files — which is what made the v0.12.11 production outage so confusing (the Nx dry-run showed "[proto] Generating..." but the on-disk files never appeared).
