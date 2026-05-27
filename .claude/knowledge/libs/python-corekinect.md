# `corekinect` Python SDK — knowledge

The shared Python library at `libs/python/`. Used by every Python service in
the platform (build-service, git-poller, http-api indirectly via the test
runner, validation/manufacturing runner pods, `corectl`). Distributed as a
wheel published to the in-cluster PyPI.

Refresh this file when: a subpackage is added/removed/renamed; the public
surface re-exported from `corekinect/__init__.py` changes; the wheel build
process or PyPI publishing flow changes; the `database` generator output path
moves.

## Location

```
libs/python/
├── corekinect/             # the SDK package itself
├── database/               # GENERATED — prisma-client-py output, do not edit
├── pyproject.toml          # hatchling build, force-includes ../protocols
├── project.json            # nx targets (build, push, test, coverage, security)
├── MANIFEST.in
├── pytest.ini
└── dist/                   # wheel output (gitignored)
```

The generated Prisma client at `libs/python/database/` is produced by
`nx run database:generate-client` (which runs `yarn prisma generate` in
`prisma/`). The Prisma `generator python` block in `prisma/schema.prisma`
points `output = "../libs/python/database"`. Consumers import as
`from database import db, enums`. See [`../prisma/schema-overview.md`].

## What's in the SDK

- Domain glue for validation/manufacturing flows that runs in pods (not in
  the http-api).
- MTIB gRPC client (the only thing that talks to `mtib-server`).
- External-service clients: CoreOps, CoreCloud.
- The `Fixture` declarative typing layer (so a product's test code can
  describe its DUT-side wiring in one class).
- The pytest-based test framework and reporter that runner pods invoke.
- Manifest schema (`concord.yaml`) loader + validator, shared with
  `corectl` and the backend upload handler.
- Product shell wrappers (Alpha app, Comms coproc, Theta, Sigma5).
- Firmware utilities — CFW packer, validators, version parsers.
- Hardware-agnostic utilities: env config, logger, serde, NFC helpers,
  encoding, units, geo.

## What's intentionally outside

- **No Flask, no SQLAlchemy app code.** The http-api uses the generated
  Prisma client directly; `corekinect` doesn't wrap it.
- **No K8s scheduling.** Backend uses the `kubernetes` Python client; the
  SDK doesn't.
- **No MinIO upload helpers.** Backend uses `minio` directly; the SDK
  publishes results via the http-api, not direct bucket writes.
- **No frontend types.** Frontend `models.ts` is hand-maintained; see
  [`../conventions.md`].

## Structure

```
libs/python/corekinect/
├── __init__.py             # top-level re-exports: errors, Stage, stage helpers
├── errors.py               # CloudError, ConfigError, FirmwareError, HardwareError,
│                           # TimeoutError, ValidationError
├── stages.py               # Stage, StageType, StageBuildDef, STAGE_NAMES, default
│                           # build matrices. NOTE: SMOKE default is ztest-on-hardware
│                           # (labels: smoke_app_ztest, smoke_comms_ztest, fw_type=test_app/
│                           # test_comms, variant=ztest) — runner dispatches to ztest_runner
│                           # via TestPackage.framework. Per-product override via API.
├── validation/             # re-exports stages.* (back-compat shim)
│   └── stage_defs.py       # legacy stage definitions
├── mtib_client/            # gRPC client to mtib-server
│   └── v1/
│       ├── client/         # MtibV1Client (core.py), config, types
│       └── ...
├── core_cloud/             # CoreCloud REST client + auth
│   ├── client.py           # CoreCloudClient
│   ├── models.py           # DeviceStatus, FuotaPlan, RegistrationResult, …
│   ├── unified_core/, messages/, environments/, Auth/, msg_def_v1_0.py
│   └── db_orm_v1_0.py
├── core_ops/               # CoreOps proxy client
│   └── client.py           # CoreOpsClient, CoreOpsConfig
├── testbed/                # declarative TestBed-wiring DSL
│   ├── base.py             # class Fixture
│   ├── types.py            # ADC, GPIO, UART, JLink, Power, I2C, SPI + Bound* + errors
│   ├── topology.py         # MTIB physical pin/channel limits
│   └── extractor.py
├── firmware/               # CFW format + firmware-package validation
│   ├── cfw.py              # generate_cfw, parse_cfw, TRACK_*, APPID_*
│   ├── validator.py        # FirmwarePackageValidator, validate_package
│   └── version.py
├── manifest/               # concord.yaml schema + loader
│   ├── loader.py           # load_manifest, find_manifest
│   ├── schema.py           # validate_manifest, SchemaVersion
│   ├── types.py            # Manifest, PackageConfig, StageConfig, …
│   └── schemas/            # JSON Schema files
├── shells/                 # MTIB-UART shell command wrappers
│   ├── base.py             # ShellCommander (line assembly), hex_addr helper
│   ├── _uart_cmd.py
│   ├── alpha_app.py        # AlphaAppShell
│   ├── comms_coproc.py     # CommsCoprocShell (shared)
│   ├── sigma5.py           # Sigma5AppShell (incl. {write,read,erase}_ext_flash)
│   ├── theta.py            # ThetaAppShell
│   └── tests/              # unit tests for shell wrappers (mock send())
├── test/                   # validation/manufacturing pytest framework
│   ├── runner.py           # top-level run loop (validation runner pod entry)
│   ├── mfg_runner.py       # manufacturing runner pod entry
│   ├── ztest_runner.py     # Zephyr ztest entry — flash via MTIB,
│   │                       #   capture UART, parse, POST results
│   ├── sequential.py / slot_parallel.py
│   ├── context.py          # TestContext (per-target state)
│   ├── slot.py / slot_binding.py / slot_context.py / slot_env.py
│   ├── stage_assets.py     # StageAssets, BuildAsset
│   ├── artifact_resolver.py / artifact_writer.py / artifact_uploader.py
│   ├── firmware.py / cfw.py / version_detector.py / firmware_set.py
│   ├── fuota_client.py / fuota_orchestrator.py / cloud_client.py
│   ├── device_personalizer.py / autoconf.py / env.py / errors.py
│   ├── reporter.py         # writes back to http-api
│   ├── power_profiler.py / acceleration_profiler.py
│   ├── pytest_integration.py / conftest.py / assertions.py / timing.py / stages.py
│   ├── uart_demuxer.py / mock_hardware.py / mock_cloud.py / telemetry.py / post.py
│   └── tests/              # framework self-tests
│       └── fixtures/       # canned ztest UART captures for parser tests
└── utils/                  # cross-cutting helpers
    ├── banner.py           # print_banner, BuildInfo, collect_build_info
    ├── config/env.py       # EnvConfig
    ├── logx/logger.py      # Logger (Singleton, thread-safe)
    ├── patterns/           # SingletonThreadSafeMeta
    ├── serde/              # Serializable
    ├── bits/, cli/, device/, encoding/, geo/, nfc/, secrets/,
    │   timeutil/, units/, tests/
    └── setup.py            # legacy install hook
```

## Subpackages and what they own

| Subpackage | Owns | Typical import |
|---|---|---|
| `corekinect` (top) | Re-exports `Stage`, error classes, stage helpers — convenience entry. | `from corekinect import Stage, ValidationError` |
| `corekinect.errors` | Domain error hierarchy. | `from corekinect.errors import HardwareError` |
| `corekinect.stages` | `Stage` enum, `StageBuildDef`, label/build-def helpers used by build-service and the test framework. | `from corekinect.stages import get_stage_build_defs` |
| `corekinect.mtib_client.v1.client` | `MtibV1Client` — the gRPC client. The only sanctioned way to call `mtib-server`. | `from corekinect.mtib_client.v1.client import MtibV1Client` |
| `corekinect.core_cloud` | `CoreCloudClient` + DTOs for telemetry / FUOTA / registration. | `from corekinect.core_cloud import CoreCloudClient, FuotaPlan` |
| `corekinect.core_ops` | `CoreOpsClient` — SNR→deviceId, public-key upload, ICCID registration. | `from corekinect.core_ops import CoreOpsClient` |
| `corekinect.testbed` | Declarative `TestBed` base class + typed channel wrappers. Each product subclasses `TestBed` to declare DUT-side wiring. | `from corekinect.testbed import TestBed, ADC, GPIO, UART` |
| `corekinect.fixture` | **Deprecated shim.** Re-exports everything from `corekinect.testbed` and emits a `DeprecationWarning` on import. Lets pre-rename test apps keep working for one minor release while users migrate their imports. Slated for removal in the next minor. | (avoid in new code; the warning points at the new path) |
| `corekinect.firmware` | CFW generation/parsing + firmware-package validator. | `from corekinect.firmware import generate_cfw, parse_cfw, validate_package` |
| `corekinect.manifest` | `concord.yaml` typed loader + JSON Schema validation. Shared with `corectl` and the http-api upload handler. | `from corekinect.manifest import load_manifest, validate_manifest` |
| `corekinect.shells` | One class per processor target. Wraps MTIB UART for manufacturing-shell commands. ``Sigma5AppShell`` covers the nRF52840 app processor, including ``{write,read,erase}_ext_flash`` helpers that mirror the firmware shell commands in ``sigma5_mfg_fw/src/app/sensor_handler.c``. The ``hex_addr`` helper in ``shells/base`` formats addresses ``0x{:08x}`` so the wire format matches firmware log lines exactly. Both ``read_ext_flash`` and ``erase_ext_flash`` (Sigma5 and Comms shells) deliberately pass ``success_patterns=None`` to ``ShellCommander.send()`` and wait for the prompt — the firmware prints ``Reading N bytes from address: 0x…`` / ``Erasing flash. N pages, ...`` BEFORE the SPI op runs, so any premature success-pattern match would arm ``send()``'s 3 s fallback before the op completes (this was the failure mode in runs cmpnbxt5y and cmpnd4ifm on panel 0AW2 — read returning ``None`` and erase reporting ``ok=True`` while the chip was still busy, respectively). ``erase_ext_flash`` defaults to ``timeout_s=150`` to accommodate the MX25L6406E datasheet ceiling (100 s max). **v0.12.5 (2026-05-27):** Two cadence races fixed in ``ShellCommander`` itself so both shells inherit them: (1) ``send()`` now triple-clears with 50 ms settles between AND scopes all success-pattern / prompt matching to the substring AFTER the command echo — a trailing ``Mfg shell:`` left in flight by the *previous* command no longer terminates the new one (visible in run cmpob5vz on panel 0AW6 test_13 slot-0 as ``read_data_repr=b'\x00\x00\x00\x00\x00\x00\x00\x00'`` when the chip actually held ``a5 5a ff ...``). (2) ``lock()`` now spams ``lock_shell`` at 200 ms cadence for the first ``min(timeout_s, 6 s)`` instead of the broken "one-shot + one retry at 8 s" pattern that was actually one-shot in practice (the retry was guarded by ``text == ""`` and the boot banner always suppressed it — every slot of run cmpoawlf500ob on 0AW6 dead-stuck at 21.2 s = 20 s firmware ``CONFIG_SHELL_TIMEOUT_SEC`` + ~1 s overhead). See ``shells/tests/test_lock_and_send_race.py`` for both regression fixtures, and ``shells/tests/test_read_ext_flash_cadence.py`` for the prior cadence fixtures still in force. | `from corekinect.shells import AlphaAppShell, CommsCoprocShell, Sigma5AppShell` |
| `corekinect.test` | The pytest framework runner pods execute. Owns context, artifact upload, reporter, FUOTA orchestrator, slot binding, power profiler. Also hosts `ztest_runner` for the Zephyr ztest dispatch path. | `from corekinect.test.context import TestContext` / `python -m corekinect.test.ztest_runner` |
| `corekinect.utils` | Logger, env config, singletons, serde, encoding, units, etc. | `from corekinect.utils import EnvConfig, Logger` |
| `corekinect.validation` | Back-compat shim — re-exports from `corekinect.stages`. Don't add to it. | (avoid in new code; import from `corekinect.stages`) |

## Build & publish

Wheel is built and published via Nx targets defined in
`libs/python/project.json`:

| Target | What it does |
|---|---|
| `nx run corekinect:build` | Copies `libs/protocols/` into `libs/python/protocols/`, runs `python3 -m build --wheel`, removes the copy. The proto stubs ship inside the wheel via the `force-include` block in `pyproject.toml`. |
| `nx run corekinect:push -c development` | Uploads to local PyPI on `http://localhost:8091`. |
| `nx run corekinect:push -c staging` | Port-forwards `concord-pypi` in the `staging` namespace and uploads. |
| `nx run corekinect:push -c production` | Same against `production`. |
| `nx run corekinect:test` | `pytest` against `libs/python/`. |
| `nx run corekinect:coverage` | pytest with `--cov=corekinect --cov-fail-under=60`. |
| `nx run corekinect:security` | bandit scan at `-lll -iii`. |
| `nx run corekinect:complexity` | Repo-wide complexity check, average threshold 6. |

Version lives in `corekinect/__init__.py` as `__version__`. `pyproject.toml`
reads it dynamically via `[tool.hatch.version]`. Bumping the version requires
a `push` afterwards or downstream services will pin the old wheel. The
`/concord-release` skill handles this automatically.

## `corekinect.test.ztest_runner` — Zephyr ztest dispatch

When a `TestPackage` declares `framework: ztest` in its `concord.yaml`, the
backend's runner Job dispatches to this module instead of the pytest path
(see `apps/backend/http-api.md` for the dispatch flow). The module owns:

| Concern | Implementation |
|---|---|
| Parser | `parse_ztest_output(text)` — defensive regex over Zephyr ztest UART output. Tolerates Zephyr log noise, ANSI escapes, variable whitespace, missing project markers. Returns a `ZTestSummary` with per-suite, per-test breakdown. |
| AssetSet discovery | `discover_hex_files(asset_set_dir, labels)` — locates `<label>.hex` for each requested label, infers processor role from the label suffix (`_app_ztest` / `_comms_ztest`). |
| MTIB I/O | `MtibClientLike` Protocol — production wires `MtibV1Adapter` around the existing `MtibV1Client` (no reinvention); tests inject a recorded-fixture stand-in. Adapter handles UploadFwFile → FlashFwFile → UartStream. |
| HTTP reporter | `ZTestReporter` — POSTs to the same `/v2/runs/<id>/report/{execution-start,execution-result,finish,log-chunk}` endpoints the pytest reporter uses. Body shape identical, so the backend doesn't branch on framework. `requests.Session` is injectable for tests. |
| Heartbeat | Background thread POSTs an empty `report/log-chunk` every 30 s so the scheduler's stale-runner reaper doesn't kill the Job mid-capture. |
| CLI | `python -m corekinect.test.ztest_runner --run-id <id> --target-id <tid> --asset-set <dir> --api-url <url> --api-key <key> --mtib-host <host> --labels <l1,l2,...> [--timeout-s 600]` — production invocation. |
| Replay / dry-run | `--replay-uart <path>` parses a captured UART log file instead of talking to hardware; `--dry-run-http` prints what would be POSTed instead of sending. Combined, they enable hardware-free debugging from the host. |
| Exit codes | 0 all-pass, 1 any test failure, 2 infra error (asset missing, flash failed, UART lost, parse failed). |

The MTIB adapter sits at `MtibV1Adapter` and exposes only the four methods
the runner needs (`connect`, `disconnect`, `flash_hex`, `stream_uart`). This
seam is the only test-substitution point — every other component (parser,
reporter wire shape, asset discovery) runs the real production code in
unit tests.

Production deploy path:

1. Test package author writes `framework: ztest` in `concord.yaml`.
2. `corectl test upload` POSTs to `/v2/products/<slug>/test-packages`.
3. Upload handler persists `TestPackage.framework = ZTEST`.
4. Scheduler picks the package, calls `create_kubernetes_job(framework="ztest", ...)`.
5. K8s Job spec has `container.command = ["python3", "-m", "corekinect.test.ztest_runner", ...]` and `TEST_FRAMEWORK=ZTEST` env.
6. Runner pod starts, the module discovers hexes, flashes via MTIB, captures UART, parses, POSTs back.

Demo / port-forward path (no Job needed): port-forward the target fixture's
MTIB pod to localhost and run the CLI from the host:

```
kubectl -n production port-forward svc/mtib-<verdin-id>-s0 50053:50053
python -m corekinect.test.ztest_runner \
    --run-id <id> --target-id <tid> \
    --asset-set <dir-with-hex-files> \
    --api-url <api> --api-key <key> \
    --mtib-host localhost --mtib-port 50053 \
    --labels <label> [--dry-run-http]
```

## Wheel layout caveat (force-include)

`pyproject.toml` force-includes `../protocols` into the wheel under
`protocols/`. This is critical: every `corekinect` import that does
`from protocols.mtib.mtib_pb2 import ...` (notably the MTIB client) breaks
on a fresh install without it. Do not move the protocols dir, and do not
delete the `force-include` block.

## How to add common things

### Add a new subpackage

1. `mkdir libs/python/corekinect/<name>/` and add `__init__.py` with a
   docstring describing the package + an `__all__` block.
2. If the subpackage has a stable public surface, re-export from
   `libs/python/corekinect/__init__.py` and add to its `__all__`.
3. Add unit tests under `libs/python/corekinect/<name>/tests/`.
4. Update this knowledge file's structure table.

### Bump the version + publish to PyPI

1. Edit `corekinect/__init__.py` → `__version__ = "x.y.z"`.
2. `nx run corekinect:build` (verify the wheel name).
3. `nx run corekinect:push -c staging` then `-c production`.
4. Bump consumers (any `requirements.txt` pinning `corekinect==...`).

`/concord-release` does steps 1–4 in lockstep with the platform version
bump.

### Add a CFW flag / new track / new app ID

Touch `corekinect/firmware/cfw.py` (the `TRACK_*` and `APPID_*` constants
and the `encode_flags` packing logic). Re-export the new constants from
`corekinect/firmware/__init__.py` and update consumer codepaths
(build-service, the `corectl` CFW tool).

## Backward-compat: `fixture:` key in `concord.yaml`

`corekinect.manifest.schema.validate_manifest()` accepts manifests
that still use the legacy `fixture:` block (pre-rename projects).
The pre-processor rewrites `fixture:` to the canonical `testbed:` key
and emits a deprecation warning so the operator sees the cue to
rename. When both keys are present, `testbed:` wins and `fixture:`
is dropped with a louder warning. One-minor-version compat — slated
for removal alongside the `corekinect.fixture` import shim.

## Resilience contracts

- **`SlotContext` surfaces pod state on connect failures.** When
  `connect()` runs out of retries and `pod_state_lookup` is wired on
  the slot, the helper is consulted from attempt 2 onwards (transient
  single failures don't pay the K8s round trip). Its return value
  (`ImagePullBackOff`, `CrashLoopBackOff`, `Pending`, …) appears in
  the final `ConnectionError` so the operator sees *why* gRPC was
  unreachable instead of a generic "connection failed". Pods running
  without K8s read access simply leave the hook unset.
- **`MtibV1Client.connect()` is lenient on `HealthCheck` UNIMPLEMENTED.**
  Older `mtib-server` builds did not expose the `HealthCheck` RPC. When the
  channel opens but the readiness probe returns
  `grpc.StatusCode.UNIMPLEMENTED`, the client logs a warning and returns
  success rather than refusing to bind. Any other gRPC error path still
  returns the usual `Optional[str]` error string. `SlotContext.connect()`
  in `corekinect.test.slot` mirrors the same lenient behaviour so test
  runners aren't blocked by an old MTIB image.
- **`corekinect.test.autoconf` FAILS LOUDLY on a malformed manifest.**
  Branch `fix/manifest-load-failure-visibility`, P2.1. The pre-fix code
  in `pytest_configure` caught every `Exception` from `load_manifest`,
  emitted a `warnings.warn`, and returned early — which turned schema
  mismatches and missing-key bugs into silent no-ops that surfaced
  downstream as "all tests skipped, zero failures, zero errors"
  (see `.claude/knowledge/workflows/version-skew.md` case study 1).
  Current contract:
    - No `concord.yaml` in tree → silent no-op (legitimate
      standalone test scripts).
    - `concord.yaml` present, `find_manifest` returned it, but the
      file vanished by the time we open it → silent no-op
      (race / symlink defence).
    - Any other failure (yaml.YAMLError, KeyError, ValueError, schema
      mismatch, empty `package.type`) → PROPAGATES. `pytest_configure`
      raises and collection hard-fails. Runner pod exits non-zero.
  Pinned by `libs/python/corekinect/test/tests/test_autoconf_loud_failure.py`
  (5 tests: no-manifest no-op, malformed YAML, missing required
  `package:` key, empty `package.type`, valid-manifest sanity).

## Common failure modes

- **`ImportError: No module named 'protocols.mtib.mtib_pb2'` after pip
  install.** The wheel was built without the protocols force-include — the
  Hatch block in `pyproject.toml` was edited or the build cwd was wrong.
  Rebuild with `nx run corekinect:build` from the workspace root.
- **`from database import db` fails inside a runner pod.** The Python
  Prisma client wasn't generated into `libs/python/database/`. Run
  `nx run database:generate-client`. Inside a deployed pod, this is baked
  into the image at build time.
- **`twine` upload hangs forever during `push`.** The kubectl port-forward
  in the staging/production push commands didn't establish in two seconds.
  Verify the `concord-pypi` service exists in the target namespace, then
  rerun.
- **Wheel install picks up the wrong `corekinect` version.** Local pip
  cache. `pip install --no-cache-dir corekinect` or bump the version.
- **Pytest collection errors inside `corekinect/test/`.** The framework's
  own self-tests under `corekinect/test/tests/` require the dev compose
  stack (real Postgres). Use `pytest -m "not integration"` locally if you
  don't have it up.

## Related knowledge

- [`protocols.md`](protocols.md) — protobuf schema, codegen, the
  `force-include` partner.
- [`../prisma/schema-overview.md`](../prisma/schema-overview.md) — the
  generated client `corekinect` does not own but always imports.
- [`../apps/backend/build-service.md`](../apps/backend/build-service.md) —
  primary consumer of stage build defs.
- [`../apps/edge/mtib-server.md`](../apps/edge/mtib-server.md) — the gRPC
  server the MTIB client targets.
- [`../conventions.md`](../conventions.md) — logging, env config, code
  patterns shared with backend.


**Version 0.10.1** (2026-05-14): patch alongside the platform's FixtureDesign → TestBedDesign rename. The SDK itself doesn't change shape — the extractor still produces a `TestBedSummary` from a user `TestBed` class — but the Concord-side row name in the response was renamed (see `apps/backend/http-api.md`).

**Version 0.10.5** (2026-05-15): completes the `Fixture → TestBed` rename inside the test framework. `SlotContext.fixture` → `SlotContext.testbed`, `ValidationContext.fixture` → `ValidationContext.testbed`, `FuotaOrchestrator(fixture=...)` → `FuotaOrchestrator(testbed=...)`. The templates have shipped `slot.testbed.power_on()` since 0.10.0; pre-0.10.5 runtimes carried the legacy `.fixture` attribute, so any user copying template snippets verbatim hit `AttributeError`. `pytest_integration._find_testbed` accepts both `"testbed"` (canonical) and `"fixture"` / `"validation_fixture"` (legacy) kwargs to keep older test apps working. Runner + http-api images bake corekinect at build time — any deploy on or after 0.10.5 must include a fresh image build, otherwise pods still attempt to read the old `slot.fixture` attribute that the SDK no longer exposes.

## v0.12.12 — protobuf codegen pre-wired

The `corekinect:build` target now declares `dependsOn: ["protocols:create"]` and `implicitDependencies: ["protocols"]`. The wheel's build step (`cp -r ../protocols protocols`) needs the gitignored `mtib_pb2.py` / `mtib_pb2_grpc.py` stubs to be present, which previously only worked if a past session had generated them on disk. Now Nx generates them automatically. See [`protocols.md`](protocols.md) § Codegen flow.
