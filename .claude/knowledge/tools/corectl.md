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
  - `validate [path]` — walk the project, confirm the contract (manifest schema, fixture.yaml schema, test discovery, marker discipline). Internally invokes `validate_project` / `validate_file` from `test_contracts.py` (schema correctness) and `test_depth.py` (per-stage test coverage). These are internal validators, **not** their own Click subcommands.
  - `upload` — zip the project's `tests/` + `manifest.yaml` + `fixture.yaml` into a structured archive; `POST /v2/test-packages/upload` to register, follow up with chunked uploads via presigned URLs. Status: DEVELOPMENT on success.
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

URL precedence (Bitwarden-style): `$CONCORD_API_URL` → saved `api_url` → hardcoded `https://concord.ad.corekinect.com`.

Env-var overrides: `CONCORD_API_URL`, `CONCORD_VERIFY_SSL`, `CONCORD_API_KEY` (for service-account / CI use — never written to the config file), `REQUESTS_CA_BUNDLE` (standard Python TLS path override). The `--insecure` global flag short-circuits to `CONCORD_VERIFY_SSL=false` for one run.

## Templates

`templates/_shared/` is copied into every scaffolded project unconditionally; `templates/manufacturing/` and `templates/validation/` overlay on top. Notable: `_shared/.claude/` ships a small `.claude/` folder into the new project — rules, skills, and agents oriented at writing tests against the platform, not at modifying the platform itself. Keep that scope distinction in mind when updating the templates.

The `force-include` block in `pyproject.toml` is critical: hatch otherwise excludes anything that isn't `*.py`, which would strip out `concord.yaml`, `fixture.yaml`, `conftest.py`, `.claude/` and the entire templates tree. Tested by `tests/test_template_rendering.py`.

## Version pinning to `corekinect`

`corectl` pins `corekinect~=<MAJOR>.<MINOR>.0` in `pyproject.toml::dependencies`. The intent is that the CLI and the framework SDK stay in lockstep, because corectl's project validation rules (the schema for `concord.yaml`, the expected test discovery, the manifest format) come from the SDK.

**The pin discipline is aspirational, not currently enforced.** `/concord-release` bumps the platform `VERSION` and corekinect's `__init__.py` but does **not** automatically update corectl's pin or version — that's a manual follow-up. The pin can (and currently does) drift behind the platform; whenever you publish a corectl release, update the corekinect pin in `pyproject.toml` to match the current `corekinect` minor before building.

`version_check` (the daily upgrade-availability probe) compares the running `corectl` version to the internal pypi's latest and surfaces a notice; it does not enforce the corekinect pin range, but pip will refuse to install when the constraint can't be satisfied.

## Build + distribution

- Build: `nx build corectl` → wheel in `tools/corectl/dist/`.
- Publish: `nx push corectl -c staging` (or `-c production`) — uploads to the internal PyPI at `pypi.<env>.concord.ad.corekinect.com`.
- Install (engineer machine): `pip install --extra-index-url https://pypi.concord.ad.corekinect.com/ corectl`.

The internal pypi is a `concord-pypi` deployment in each environment (Helm template under `deploy/production/helm/concord/templates/pypi-deployment.yaml`). Auth is htpasswd, configured per-env.

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
- **`Upload failed: schema mismatch`** — the project's `concord.yaml` or `manifest.yaml` violates the contract. Run `corectl validate` first; it surfaces the exact line.
- **`Version check warns about corectl + corekinect skew`** — the `~=` pin caught a drift. Update both with `pip install -U corectl` (which pulls a matching corekinect).
- **Scaffold output is missing `.claude/`** — the `force-include` block in `pyproject.toml` regressed; verify the wheel contains `corectl/templates/` with `python -m zipfile -l <wheel>`. Fixed by re-publishing with the proper hatch config.

## Related knowledge

- [`libs/python-corekinect.md`](../libs/python-corekinect.md) — the SDK corectl wraps; the contract corectl validates comes from there.
- [`apps/backend/http-api.md`](../apps/backend/http-api.md) — the API corectl talks to.
- [`product-domains/validation.md`](../product-domains/validation.md) — the model `corectl run` operates against.
- [`product-domains/manufacturing.md`](../product-domains/manufacturing.md) — the manufacturing equivalent.
- [`workflows/credentials.md`](../workflows/credentials.md) — where the OAuth token lives, how to switch APIs.
