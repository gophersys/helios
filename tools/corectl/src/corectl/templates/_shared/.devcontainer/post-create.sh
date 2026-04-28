#!/usr/bin/env bash
# generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh
#
# Devcontainer post-create — verify the framework toolchain and the project
# scaffolding are coherent. Fails the container start if anything is off so
# nobody develops against a half-set-up environment.

set -euo pipefail

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

echo "→ Pre-flight validate (warnings allowed)"
corectl test validate || echo "(validate found issues — fix and re-run)"

echo "✓ Devcontainer ready"
