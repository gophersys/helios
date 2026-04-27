---
min_role: DEVELOPER
---
# corectl CLI

Command-line interface for Concord. Useful for scripting, CI builds, and quick lookups without opening the UI.

## Installation

```bash
pip install corectl --index-url https://pypi.concord.local/simple/
```

## Configuration

Point corectl at your Concord instance:

```bash
corectl config set api-url https://concord.local
corectl config set api-key <your-api-key>
```

Generate an API key from **Settings > API Keys** in the Concord UI.

## Commands

### Products

```bash
corectl products list                    # List all products
corectl products get <id>                # Get product details
```

### Builds

```bash
corectl builds list --product <id>       # List builds for a product
corectl builds trigger --product <id>    # Trigger a new build
corectl builds logs <id>                 # Stream build logs
```

### Validation

```bash
corectl validation runs list             # List validation runs
corectl validation runs get <id>         # Get run details
```

### Test packages

A test package is a versioned tar.gz of your validation or
manufacturing test app, uploaded to Concord and run by the platform
runner. Every product has its own test app; corectl scaffolds,
validates, packages, uploads, and releases it.

```bash
corectl test init --product <slug> --board <board>      # Scaffold a new test app
corectl test init --product <slug> --board <board> --type manufacturing
corectl test validate                                    # Lint manifest, structure, semantics
corectl test package                                     # Build the .tar.gz under dist/
corectl test upload                                      # Upload as DEVELOPMENT
corectl test upload --release                            # Upload + promote to RELEASED
corectl test release <package-id>                        # Promote an existing dev upload
corectl test release --version dev-abc12345-1713100800   # Promote by version string
corectl test versions                                    # List published versions
```

`corectl test init` is backend-aware. It fetches the product list,
verifies the board revision has at least one configured target, and
fails fast if the slug or revision is unknown — the scaffolded
`concord.yaml` can never reference something the platform doesn't
have.

`corectl test upload` always tags dev versions with a fresh
`dev-{sha}-{epoch}` suffix. Each upload lands an immutable row;
re-running on the same SHA produces a distinct version, so a TestRun
captured at scheduling time always references the exact build that
ran.

`corectl test release` strips the `dev-` prefix when promoting:
`dev-abc12345-1713100800` becomes `abc12345-1713100800` as the
released label. Pass `--version` (with the wizard) or
`releasedVersion` in the request body to override with a clean semver
like `1.2.0`.

The runner downloads from
`test-packages/{slug}/{type}/{version}/package.tar.gz` in MinIO and
installs the package via `pip install -e .` before running tests, so
your test app needs a `pyproject.toml` (or `setup.py`).

### Manifest

The single canonical manifest is `concord.yaml` with `schema: "1.0"`.
The legacy `concord.test.yaml` v1 format is no longer accepted —
re-init with `corectl test init` if you have one.

```yaml
schema: "1.0"

package:
  type: validation              # or manufacturing
  version: "1.0.0"
  framework: ">=0.3.0"

product:
  slug: alpha
  board: alpha_b0
  device:
    type_id: 42
    variant_id: 7

fixture:
  design: "Alpha B0 Validation Fixture"
  revision: "1.0"
  controller: fixtures.alpha_b0.controller.AlphaB0Fixture
  profile: fixtures/alpha_b0/fixture.yaml
  multi_slot: false

stages:
  smoke:
    directory: tests/smoke
    timeout_s: 300
    hardware: [mtib]
```

Manufacturing manifests use a `steps:` list keyed by step name +
module path instead of `stages:` — see the template at
`tools/corectl/src/corectl/templates/manufacturing/concord.yaml`.
