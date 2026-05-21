# tools/corectl — knowledge

`corectl` is the Concord platform CLI. It's the tool engineers use from inside a validation or manufacturing test project directory to validate, upload, run, and inspect Concord resources. It's packaged as a Python wheel, distributed via the internal PyPI, and version-pinned to the `corekinect` SDK by major.minor — the CLI and the framework ship in lockstep.

Refresh this file when: a new top-level `corectl <verb>` command is added, the template-scaffold output shape changes, the `corekinect` version pin discipline changes, the auth flow changes, or a new project type beyond `manufacturing` / `validation` appears under `templates/`.

## Location

- Code: `tools/corectl/`
- Entry point: `tools/corectl/src/corectl/cli.py` (`corectl.cli:main`)
- Templates: `tools/corectl/src/corectl/templates/{_shared,manufacturing,validation}/`
- Tests: `tools/corectl/tests/`
- Package: `corectl` on the internal PyPI, built by `nx build corectl`

## What corectl is for

corectl is the developer-facing CLI for everything that happens **inside** a test project (a manufacturing or validation app cloned from the templates). It is not a platform-admin tool — operator-only flows (creating products, registering MTIBs, releasing packages) live in the web UI.

Typical lifecycle:

```bash
cd alpha-validation/             # a project bootstrapped from the validation template
corectl validate                 # check the project structure matches the contract
corectl upload                   # package + upload as DEVELOPMENT to the platform
corectl run smoke                # execute the smoke stage against a real fixture
corectl run regression -m health_check     # run a stage filtered by marker
corectl versions                 # list published versions of this package
```

When the user is outside a project, the commands are resource-qualified:

```bash
corectl auth login               # browser-based OAuth flow → ~/.concord/token
corectl auth status              # who am I, against which API
corectl budgets                  # show test-run budgets (CI time, fixture-hours)
corectl test validate /path      # validate any project by path
corectl test release <pkg-id>    # promote DEVELOPMENT → RELEASED
corectl test init [PATH] --type <type> --product <id> --board <name>   # scaffold a new project from a template
```

## Structure

```
tools/corectl/
├── pyproject.toml          # hatchling build, version dynamic from __init__.py
├── project.json            # nx targets: build, test, push, lint, typecheck
├── src/corectl/
│   ├── __init__.py         # __version__ — single source for the wheel version
│   ├── cli.py              # click main group; --insecure + --no-version-check flags; registers each `test` subcommand as a top-level alias too
│   ├── config.py           # ~/.corectl/config.yaml (tokens stored in same file) + env-var overrides + OS CA-bundle auto-detect
│   ├── api.py              # thin HTTP client (requests) for the Concord http-api
│   ├── version_check.py    # daily "upgrade available?" probe vs internal pypi
│   ├── commands/
│   │   ├── auth.py         # login, logout, status, token
│   │   ├── budgets.py      # show / refresh test-run budgets
│   │   ├── runs.py         # list / show / cancel TestRuns
│   │   ├── test.py         # init, validate, upload, release, versions
│   │   ├── test_contracts.py   # AST validator for manifest / fixture.yaml — called inside `test validate`, not a Click command
│   │   ├── test_depth.py       # AST analyzer for per-stage test coverage — same: called inside `test validate`
│   │   └── update.py       # self-update via internal pypi
│   └── templates/
│       ├── _shared/        # files copied into every scaffolded project
│       │   ├── .claude/    # the scaffolded project gets its own .claude/ folder
│       │   ├── .devcontainer/
│       │   ├── conftest.py
│       │   └── pyproject.toml
│       ├── manufacturing/  # `corectl test init manufacturing` source
│       └── validation/     # `corectl test init validation` source
└── tests/
    ├── test_auth_session.py
    ├── test_budgets_command.py
    ├── test_config_resolution.py
    ├── test_runs_command.py
    ├── test_template_rendering.py
    ├── test_validate_test_contracts.py
    └── test_validate_test_depth.py
```

`cli.py` also exposes each `corectl test <verb>` as a **top-level alias** — `corectl init`, `corectl validate`, `corectl run`, `corectl upload`, `corectl release`, `corectl versions`, etc. Both forms work; engineers default to the shorter alias when standing inside a project directory.

## Command groups

- **`corectl auth`** — OAuth login flow. Mints an access token (15-min) + refresh token (30-day rotated). Both are written into `~/.corectl/config.yaml` along with `expires_at`. `status` reports the active user + which API the tokens target. There is no separate token file — corectl keeps one shape and one shape only (the legacy `api_token` field has been removed).
- **`corectl test`** — the bulk of the tool. Each subcommand is also aliased at the top level (`corectl init`, `corectl validate`, …). Subcommands:
  - `init [PATH] --type <manufacturing|validation> --product <id> --board <name>` — scaffold a new project from `templates/<type>/`. Renders Jinja-style placeholders.
  - `validate [path]` — walk the project, confirm the contract (manifest schema, testbed declaration, test discovery, marker discipline). Internally invokes `validate_project` / `validate_file` from `test_contracts.py` (schema correctness) and `test_depth.py` (per-stage test coverage). These are internal validators, **not** their own Click subcommands.
  - `upload [-m MESSAGE]` — zip the project's `tests/` + `concord.yaml` + `concord.yaml` `testbed:` block into a structured archive; `POST /v2/test-packages/upload` to register, follow up with chunked uploads via presigned URLs. Status: DEVELOPMENT on success. The `-m / --message` flag skips the interactive prompt for scripted / CI use; without it, corectl prompts for a free-form upload message.
  - `sync` — pull `product` + `board` + `testbed.module` from the backend and reconcile `concord.yaml`. The authoritative-fields list lives in `commands/test.py::_authoritative_fields` — keyed on `testbed.module` (not the legacy `fixture.module`). The expected module prefix is `testbeds.<board>.testbed:` and the default class name is `<BoardClass>{MfgTestBed|TestBed}` based on package type. Touching this function silently changes which manifest fields the platform owns; treat additions as a deliberate policy call.
  - `release <pkg-id>` — promote DEVELOPMENT → RELEASED (operator-level permission required).
  - `versions` — list published versions of the current project's package.
- **`corectl runs`** — list / show / cancel `TestRun`s, filtered by package, fixture, or status. Useful for CI scripts.
- **`corectl budgets`** — show test-run budgets (fixture-hours, CI time) for the current user / product. Pulls from `/v2/budgets`.
- **`corectl update`** — self-update by re-installing the latest wheel from the internal pypi.

## Configuration

`~/.corectl/config.yaml` is created on first login with `0600` perms and carries:

- `api_url` — `http://localhost:9001` for dev, `https://staging.concord.ad.corekinect.com` / `https://concord.ad.corekinect.com` for staging/prod.
- `access_token`, `refresh_token`, `expires_at` — the active session. Refresh tokens are long-lived (30 days) and rotated.
- `tls_verify` — `true`, `false`, or a **path string** to a CA bundle. `false` disables cert verification (for WSL with self-signed CA in dev). When unset, `config.py::_system_ca_bundle()` walks four standard Linux trust-store paths and falls back to `certifi` if none exist — this auto-detection is what makes the internal CoreKinect CA work without manual config on most Linux distros.

URL precedence (env-first): `$CONCORD_API_URL` → saved `api_url` in `~/.corectl/config.yaml` → hardcoded `https://concord.ad.corekinect.com`.

Env-var overrides: `CONCORD_API_URL`, `CONCORD_VERIFY_SSL`, `CONCORD_API_KEY` (for service-account / CI use — never written to the config file), `REQUESTS_CA_BUNDLE` (standard Python TLS path override). The `--insecure` global flag short-circuits to `CONCORD_VERIFY_SSL=false` for one run.

## Templates

`templates/_shared/` is copied into every scaffolded project unconditionally; `templates/manufacturing/` and `templates/validation/` overlay on top. Notable: `_shared/.claude/` ships a small `.claude/` folder into the new project — rules, skills, and agents oriented at writing tests against the platform, not at modifying the platform itself. Keep that scope distinction in mind when updating the templates.

The `force-include` block in `pyproject.toml` is critical: hatch otherwise excludes anything that isn't `*.py`, which would strip out `concord.yaml`, `concord.yaml` `testbed:` block, `conftest.py`, `.claude/` and the entire templates tree. Tested by `tests/test_template_rendering.py`.

## Version pinning to `corekinect`

`corectl` pins `corekinect~=<MAJOR>.<MINOR>.0` in `pyproject.toml::dependencies`. PEP 440 `~=` means "compatible release": `~=0.9.0` is `>=0.9.0, <0.10.0`. The intent is that the CLI and the framework SDK stay in lockstep, because corectl's project validation rules (the schema for `concord.yaml`, the expected test discovery, the manifest format) come from the SDK.

**The pin discipline is manual.** `/concord-release` bumps the platform `VERSION` and corekinect's `__init__.py` but does **not** automatically update corectl's pin — that's a follow-up to do in the same commit. Pip will refuse to install corectl if the pin can't resolve against the available corekinect version, so leaving the pin stale eventually breaks fresh installs.

Current pin: `corekinect~=0.10.0` (matches the platform's 0.10.x minor). When the platform bumps to 0.10.0, update this pin to `~=0.10.0` in the same commit as the corekinect `__init__.py` bump.

`version_check` (the daily upgrade-availability probe) compares the running `corectl` version to the internal pypi's latest and surfaces a notice; it does not enforce the corekinect pin range.

The separate **runtime framework-version check** inside `corectl test validate` (`commands/test.py::_validate_compatibility`) reads `framework` from the test app's `concord.yaml` (e.g., `corekinect>=0.3.0`) and compares the installed `corekinect.__version__` against the lower bound using PEP 440 parsing (`packaging.version.Version`). String comparison was previously used and produced false negatives at the 1.x→0.10.x boundary (`'0.10.4' < '0.3.0'` lex-wise). Always use Version-aware parsing for any new version check added to the validator.

## Build + distribution

- Build: `nx build corectl` → wheel in `tools/corectl/dist/`.
- Publish: `nx push corectl -c staging` (or `-c production`) — uploads to the internal PyPI at `pypi.<env>.concord.ad.corekinect.com`.
- Install (engineer machine): `pip install --extra-index-url https://pypi.concord.ad.corekinect.com/ corectl`.

The internal pypi is a `concord-pypi` deployment in each environment (Helm template under `deploy/production/helm/concord/templates/pypi-deployment.yaml`). Auth is htpasswd, configured per-env.

## Backward-compat discipline when publishing

`nx update platform` does **not** rebuild or republish corectl — corectl is on its own release cadence. Publishing a new corectl wheel can force-upgrade `corekinect` on every existing engineer install via the `~=` pin, which is a real source of "my tooling broke this morning" incidents.

Before running `nx push corectl -c production`:

1. **Bump corectl's `__init__.py` version** to a new semver (don't republish under an existing version).
2. **Confirm the corekinect pin** matches the platform minor you want users to land on. Today the pin is `corekinect~=0.10.0` and the platform ships corekinect 0.10.x — congruent.
3. **Confirm the corekinect version on the target pypi** is at least the lower bound of the pin (`pip` will error otherwise).
4. **Stage first**: `nx push corectl -c staging`. Test `pip install --extra-index-url https://pypi.staging.concord.ad.corekinect.com/ corectl` in a clean venv. Confirm the install resolves and `corectl --help` runs.
5. **Communicate**: if the new corectl forces a corekinect-minor upgrade on existing users, post a release note before pushing to production. Otherwise their next `corectl update` will pull both a new corectl and a new corekinect together, breaking any local Python code that imported the old corekinect surface.
6. **Then production**: `nx push corectl -c production`.

The current state (as of the pin fix landing in main): the source tree has corectl `0.9.6` with `corekinect~=0.10.0`. The production pypi has **not** received a new wheel yet — existing installs still pull corectl `0.9.5` with the old `corekinect~=0.8.0` pin, which resolves against the still-published corekinect 0.8.0. Status quo until someone explicitly republishes.

## How to add a new corectl command

1. Add a new file under `src/corectl/commands/<verb>.py` exposing a Click group or command.
2. Register it in `src/corectl/cli.py::main.add_command(...)`.
3. Add tests under `tools/corectl/tests/test_<verb>_command.py`.
4. If the command touches the API, add the request method to `src/corectl/api.py` (don't inline `requests.get` calls in commands).
5. Update `.claude/knowledge/tools/corectl.md` (this file) under "Command groups".
6. Bump the version in `src/corectl/__init__.py` if the command is user-facing. Re-publish the wheel.

## How to add a new project template

1. Add `templates/<type>/` with the layout you want the scaffold to produce. Re-use `_shared/` for anything cross-type.
2. Wire it into `commands/test.py::test_init` so `corectl test init <type>` is discoverable.
3. Add a `tests/test_template_rendering.py` case that validates the scaffold output.
4. Update this file's "Templates" section.

## Common failure modes

- **`corectl: command not found`** — the wheel installs `corectl` as a `[project.scripts]` entry; if `pip install` succeeded but the binary is missing, the `~/.local/bin` (or virtualenv `bin/`) isn't on `PATH`.
- **`401 Unauthorized` on first command** — token expired or never logged in. `corectl auth login`.
- **`SSL: CERTIFICATE_VERIFY_FAILED`** — local machine doesn't trust the internal CA. Run with `--insecure` for one-off, or install the CA chain into the OS trust store for permanence.
- **`Upload failed: schema mismatch`** — the project's `concord.yaml` or `concord.yaml` violates the contract. Run `corectl validate` first; it surfaces the exact line.
- **`Version check warns about corectl + corekinect skew`** — the `~=` pin caught a drift. Update both with `pip install -U corectl` (which pulls a matching corekinect).
- **Scaffold output is missing `.claude/`** — the `force-include` block in `pyproject.toml` regressed; verify the wheel contains `corectl/templates/` with `python -m zipfile -l <wheel>`. Fixed by re-publishing with the proper hatch config.

## Related knowledge

- [`libs/python-corekinect.md`](../libs/python-corekinect.md) — the SDK corectl wraps; the contract corectl validates comes from there.
- [`apps/backend/http-api.md`](../apps/backend/http-api.md) — the API corectl talks to.
- [`product-domains/validation.md`](../product-domains/validation.md) — the model `corectl run` operates against.
- [`product-domains/manufacturing.md`](../product-domains/manufacturing.md) — the manufacturing equivalent.
- [`workflows/credentials.md`](../workflows/credentials.md) — where the OAuth token lives, how to switch APIs.


**Version 0.10.1** (2026-05-14): lockstep bump alongside corekinect 0.10.1 and the FixtureDesign → TestBedDesign Concord-side rename. corectl's templates and CLI text were already updated in 0.10.0; this is a no-shape-change ride-along.


**v0.10.3** (2026-05-14): `_shared/.claude/` framework templates (rules + skills + agents) sweep — every `slot.fixture` → `slot.testbed`, every `fixtures/{{board}}/fixture.py` → `testbeds/{{board}}/testbed.py`, every "fixture controller" → "testbed controller". `corectl test update --apply` propagates this to existing scaffolded projects.


## DEV_HOLD claim commands

A local-dev workflow that leases real hardware (a fixture or a set of nodes) for the duration of a TDD session, surfaced via three new `corectl test` subcommands. The lease is held by a sliding 5-minute TTL backed by a detached heartbeat daemon, with an 8-hour hard ceiling. See `.claude/specs/dev-hold-claim.md` for the canonical contract.

### Surface

| Command | What it does |
|---|---|
| `corectl test claim --fixture NAME` | Lease a fixture for local dev. Single-slot or panel. |
| `corectl test claim --node NAME [--node NAME …]` | Lease specific nodes ad-hoc (node-mode — no fixture row required). |
| `corectl test unclaim` | Release the current claim and stop the heartbeat daemon. |
| `corectl test status` | Show the active claim: id, status, slot bindings, time remaining. Reconciles local state file with backend live status. |

All three are also exposed as top-level aliases (`corectl claim`, `corectl unclaim`, `corectl status`) so they work from a project root the same way `corectl validate` does.

Flags on `claim`:

- `--fixture NAME` xor `--node NAME …` — pick exactly one mode. Node mode accepts repeated `--node` for multi-slot.
- `--ttl SECONDS` — lease TTL, default 3600 (1 h), clamped to `[60, 28800]` (matches backend hard ceiling). Out-of-range values are clamped silently with a yellow notice.
- `--description STRING` — free-form note attached to the audit event.
- `--replace` — release any pre-existing local claim before re-claiming. Without it, `claim` refuses when `.concord-claim.json` already exists.

### Files

- `tools/corectl/src/corectl/claim_state.py` — atomic read/write/remove of `.concord-claim.json`, the on-disk record of an active claim. Stores **only immutable fields**: claim id, fixture id (or null for node mode), slot bindings (each with label / nodeId / mtibHost), `hardCeilingAt`, heartbeat PID, `createdAt`. `expiresAt` is intentionally NOT persisted — it's sliding (`lastHeartbeatAt + 5min`) and changes with every heartbeat, so caching it would create a "state says alive, backend already expired" drift class. `corectl test status` reads `expiresAt` live from the backend each time.
- `tools/corectl/src/corectl/heartbeat_daemon.py` — standalone script (`python -m corectl.heartbeat_daemon <project> --api-url URL [--token T | --api-key K]`) that POSTs `/v2/fixture-claims/<id>/heartbeat` every 60 s. Exits cleanly on state-file deletion, HTTP 410, or SIGTERM. Logs to `.concord-claim.log` via `RotatingFileHandler` (1 MB cap, 2 backups).
- `tools/corectl/src/corectl/commands/test.py` — the three `@test.command()` definitions (`claim`, `unclaim`, `status`), the resolver helpers (`_resolve_fixture_id`, `_resolve_node_ids`), the daemon launcher (`_spawn_heartbeat_daemon`), and the env-injector (`_env_with_claim_bindings`).

### Run-time env injection

`corectl test run <stage>` now consults `.concord-claim.json` before invoking pytest. When the file exists it injects:

- `CONCORD_CLAIM_ID=<id>` — always, so the SDK / reporter can correlate test runs with their lease in audit logs.
- `MTIB_HOST=<host>` — single-slot claims (one entry in `slotBindings`).
- `MTIB_HOSTS=h1,h2,…` — multi-slot claims (>1 entry), comma-joined in slot order.

When the state file is missing, `run` is unchanged — the operator's ambient `MTIB_HOST` / `MTIB_HOSTS` shell env wins, preserving the pre-claim workflow for devs who haven't adopted it yet.

### Daemon lifecycle

Spawn: `subprocess.Popen` with `start_new_session=True` (detaches from controlling tty) and `stdin/stdout/stderr=DEVNULL` (so the parent shell isn't tethered). The daemon's PID is recorded in the state file before `claim` returns, so `unclaim` and `status` know who's heartbeating.

Exit conditions (all clean):

1. State file deleted → cooperative shutdown (the CLI signals "stop" by removing the file the daemon polls).
2. HTTP 410 from `/heartbeat` → backend says the claim is terminal (EXPIRED / RELEASED / ABANDONED). Daemon wipes the state file and exits.
3. SIGTERM / SIGINT → orderly shutdown; the main loop checks an exit flag every second so a kill lands fast.

Transient failures (network errors, 5xx) trigger a 15-second retry backoff. After 20 consecutive failures (~5 min) the daemon gives up and exits — the lease has expired anyway by that point.

### Reconciliation

`corectl test status` GETs `/v2/fixture-claims/<id>` and compares the live `status` to the implicit "ACTIVE" assumption of the on-disk file. Any mismatch wipes the state file and emits a yellow WARNING — the dev was about to run pytest against hardware they no longer own.

### Gitignore

`.concord-claim.json` and `.concord-claim.log` are added to:

- `tools/corectl/src/corectl/templates/_shared/.gitignore` — the template all scaffolded projects inherit.
- `validation/sigma5_validation/.gitignore` — backfill for the one already-existing project that needs the entry today.

Other already-scaffolded validation / manufacturing projects pick up the template change on their next `corectl test update --apply`.

### When to refresh this section

Refresh when: the daemon's exit conditions change, the env-injection contract changes, the TTL clamp changes, a new flag is added to `claim`, or the state file shape changes.
