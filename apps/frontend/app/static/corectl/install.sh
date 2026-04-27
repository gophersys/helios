#!/usr/bin/env bash
# Concord CLI installer — corectl
#
#   curl -fsSL https://concord.ad.corekinect.com/install | bash
#
# Installs (or upgrades) corectl from the Concord internal PyPI into your
# user site-packages. Idempotent — re-run any time to upgrade.
set -euo pipefail

CONCORD_HOST="${CONCORD_HOST:-concord.ad.corekinect.com}"
INDEX_URL="https://pypi.${CONCORD_HOST}/simple/"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but not found on PATH." >&2
  exit 1
fi

if ! command -v pip3 >/dev/null 2>&1 && ! python3 -m pip --version >/dev/null 2>&1; then
  echo "Error: pip is required (try: python3 -m ensurepip --user)." >&2
  exit 1
fi

echo "Installing corectl from ${INDEX_URL}..."
python3 -m pip install --user --upgrade --quiet --index-url "${INDEX_URL}" corectl

# Make sure ~/.local/bin is on PATH for this shell — pip --user installs there.
USER_BIN="$(python3 -c 'import site; print(site.USER_BASE)')/bin"
case ":${PATH}:" in
  *":${USER_BIN}:"*) ;;
  *)
    echo
    echo "Note: ${USER_BIN} is not on your PATH. Add it with:"
    echo "    echo 'export PATH=\"${USER_BIN}:\$PATH\"' >> ~/.bashrc"
    echo "    # or for zsh:"
    echo "    echo 'export PATH=\"${USER_BIN}:\$PATH\"' >> ~/.zshrc"
    ;;
esac

echo
echo "Installed: $(${USER_BIN}/corectl --version 2>/dev/null || corectl --version)"
echo
echo "Next: corectl auth login --url https://${CONCORD_HOST}"
