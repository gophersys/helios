# .ci/providers — CI-system shim layer

This directory is the **source of truth** for every CI-system YAML that this
repository uses. Each subdirectory holds 1 CI provider:

```
.ci/providers/
├── github/    # GitHub Actions — .github/workflows/ holds a copy of each file
└── ...        # future providers (gitlab, buildkite, drone, …)
```

## Why this exists

Each CI provider reads its own directory layout (`.github/workflows/`,
`.gitlab-ci.yml`, `.buildkite/`, `.drone.yml`, …). A repository can need more
than 1 provider. It can also need 1 place for its CI pipelines instead of 4
copies of almost the same YAML. The simplest abstraction is 1
`.ci/providers/<name>/` directory, which holds the source of truth for that
provider.

The provider-specific paths stay in place, for example
`.github/workflows/build-and-push.yml`, so the provider still works. Each of
those paths holds a **copy**, not a symlink and not generated output. Both files
are tracked, and the 2 must stay byte-for-byte identical.

Nothing makes the copy for you. There is no generator and no pre-commit hook. To
add a new workflow, write the file under `.ci/providers/github/`, then copy it to
`.github/workflows/`. To change one, change both.

`_ctl/tests/platform-policy.test.sh` compares the 2 with `cmp`, and
`bash ./ctl.sh test` runs it in the pull request gate, so a pair that moves apart
fails there. They have drifted twice. **The check now covers EVERY file in this
directory**, found by a glob, so a file added tomorrow is compared on the day it
is added. It used to name `build-and-push.yml` alone, and that narrow rule had
the same hole 1 level up: a second provider file got no check at all until
somebody added 1 for it.

A glob that matched nothing would be a green result that read no file, so that
test also holds a literal list of what this directory contains. **Adding or
renaming a file here means editing `EXPECTED_PROVIDER_FILES` in
`_ctl/tests/platform-policy.test.sh` in the same change.**

The direction of the rule is provider → workflow. `.github/workflows/` may hold
a file this directory does not: `validate.yml` and `pr-review.yml` are
provider-native and have no source-of-truth copy.

## Current providers

| Provider       | Source of truth path                 | Provider-expected path         |
|----------------|--------------------------------------|--------------------------------|
| GitHub Actions | `.ci/providers/github/*.yml`         | `.github/workflows/*.yml` (copies) |

## Orchestration

The bash orchestration layer above these YAML files is `.ci/ctl.sh`. See
`.ci/README.md`. That layer is the entrypoint. Every local developer and every
CI job delegates to it. The provider YAML files are thin shells that call
`bash .ci/ctl.sh <verb>`.
