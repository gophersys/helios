#!/usr/bin/env bash
# generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh
#
# Devcontainer post-create — verify the framework toolchain and the project
# scaffolding are coherent. Fails the container start if anything is off so
# nobody develops against a half-set-up environment.

set -euo pipefail

# The base image ships corectl + corekinect from the in-cluster PyPI,
# but the *editable* development workflow assumes the concord monorepo
# is mounted at /workspaces/concord (so changes to libs/python land in
# this container without a wheel rebuild). When that path is missing
# the editable install silently picks up the wheel-from-PyPI version
# and nothing in the dev loop reflects the user's local edits.
#
# Fail loudly here so the operator fixes the layout BEFORE the dev
# loop starts, rather than chasing "why didn't my change land?" later.
if [ ! -d /workspaces/concord/libs/python/corekinect ] && [ "${CONCORD_DEV_MODE:-}" = "1" ]; then
    cat <<'EOF' >&2

✗ /workspaces/concord/libs/python/corekinect is missing.

This devcontainer expects the concord monorepo to be mounted at
/workspaces/concord (alongside the test app) so corekinect changes
land in the container without a wheel rebuild. Fix one of:

  1. Clone concord/concord next to this repo and add it to the
     devcontainer "mounts" section, e.g.:

       "mounts": [
         "source=\${localWorkspaceFolder}/../concord,
          target=/workspaces/concord,type=bind"
       ]

  2. If you do NOT need monorepo edits, set CONCORD_DEV_MODE=0 in
     this devcontainer's "remoteEnv" to skip this check.

EOF
    exit 1
fi

EXPECTED_VERSION="$(cat .claude/.framework-version 2>/dev/null || echo '')"

echo "→ Verifying corectl"
if ! command -v corectl >/dev/null 2>&1; then
    echo "✗ corectl not on PATH inside the devcontainer."
    echo "  Expected the concord base image to ship it. Re-pull the base image"
    echo "  or report the broken image."
    exit 1
fi
corectl --version

echo "→ Verifying corekinect"
python -c "import corekinect; print(f'corekinect {corekinect.__version__}')"

if [ -n "${EXPECTED_VERSION}" ]; then
    INSTALLED_VERSION="$(python -c 'import corekinect; print(corekinect.__version__)')"
    if [ "${INSTALLED_VERSION}" != "${EXPECTED_VERSION}" ]; then
        echo "⚠ Framework version mismatch."
        echo "  This app was scaffolded with framework ${EXPECTED_VERSION}."
        echo "  The container has ${INSTALLED_VERSION}."
        echo "  Run \`corectl update\` then \`corectl test update\` to align."
    fi
fi

echo "→ Installing pre-commit hooks"
if ! command -v pre-commit >/dev/null 2>&1; then
    pip install --quiet pre-commit
fi
# `pre-commit install` only writes .git/hooks/pre-commit if .git exists.
# A fresh clone always has it; the rare `git init` skeleton might not.
if [ -d .git ]; then
    pre-commit install --install-hooks >/dev/null
    echo "  pre-commit hook installed"
else
    echo "  (no .git directory — skipping pre-commit install)"
fi

echo "→ Pre-flight validate"
# corectl test validate exits non-zero on errors; warnings keep exit 0.
# We deliberately fail container start on errors — a half-set-up
# environment is worse than no environment.
if ! corectl test validate; then
    echo
    echo "✗ Validation has errors. Fix the issues above before developing."
    exit 1
fi

echo "✓ Devcontainer ready"
