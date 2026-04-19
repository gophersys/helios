# .ci/providers — CI-system shim layer

This directory is the **source of truth** for every CI-system YAML consumed by
this repository. Each subdirectory corresponds to one CI provider:

```
.ci/providers/
├── github/    # GitHub Actions — .github/workflows/ symlinks in here
└── ...        # future providers (gitlab, buildkite, drone, …)
```

## Why this exists

CI providers each insist on reading their own directory layout
(`.github/workflows/`, `.gitlab-ci.yml`, `.buildkite/`, `.drone.yml`, …). When a
repo needs to support more than one provider — or wants to document its CI
pipelines in one place without four copies of effectively the same YAML — the
simplest abstraction is a single `.ci/providers/<name>/` directory that each
provider's expected path **symlinks into**.

The provider-specific paths (e.g. `.github/workflows/build-and-push.yml`)
remain present so the provider still works — but they are symlinks, and the
committed content lives under `.ci/providers/<provider>/`.

Git tracks symlinks natively on Linux/macOS; no pre-commit or generator is
required. When adding a new workflow, edit the file under
`.ci/providers/github/` and `ln -s` it into `.github/workflows/`.

## Current providers

| Provider       | Source of truth path                 | Provider-expected path         |
|----------------|--------------------------------------|--------------------------------|
| GitHub Actions | `.ci/providers/github/*.yml`         | `.github/workflows/*.yml` (symlinks) |

## Orchestration

The bash orchestration layer that sits above these YAMLs lives at `.ci/ctl.sh`
(see `.ci/README.md`). That layer is the entrypoint every local dev and every
CI job ultimately delegates to — the provider YAMLs are thin shells that call
`bash .ci/ctl.sh <verb>`.
