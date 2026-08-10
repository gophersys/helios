# .ci/providers — CI-system shim layer

This directory is the **source of truth** for every CI-system YAML that this
repository uses. Each subdirectory holds 1 CI provider:

```
.ci/providers/
├── github/    # GitHub Actions — .github/workflows/ symlinks in here
└── ...        # future providers (gitlab, buildkite, drone, …)
```

## Why this exists

Each CI provider reads its own directory layout (`.github/workflows/`,
`.gitlab-ci.yml`, `.buildkite/`, `.drone.yml`, …). A repository can need more
than 1 provider. It can also need 1 place for its CI pipelines instead of 4
copies of almost the same YAML. The simplest abstraction is 1
`.ci/providers/<name>/` directory. The path that each provider expects is a
symlink into that directory.

The provider-specific paths stay in place, for example
`.github/workflows/build-and-push.yml`, so the provider still works. Those
paths are symlinks. The committed content is under `.ci/providers/<provider>/`.

Git tracks a symlink on Linux and on macOS. You do not need a pre-commit hook
or a generator. To add a new workflow, edit the file under
`.ci/providers/github/`. Then run `ln -s` to link it into `.github/workflows/`.

## Current providers

| Provider       | Source of truth path                 | Provider-expected path         |
|----------------|--------------------------------------|--------------------------------|
| GitHub Actions | `.ci/providers/github/*.yml`         | `.github/workflows/*.yml` (symlinks) |

## Orchestration

The bash orchestration layer above these YAML files is `.ci/ctl.sh`. See
`.ci/README.md`. Every local developer and every CI job delegates to that
layer. The provider YAML files are thin shells that call
`bash .ci/ctl.sh <verb>`.
