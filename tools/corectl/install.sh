#!/usr/bin/env bash
#
# corectl installer — the one-liner onboarding path.
#
#   curl -sSL https://concord.ad.corekinect.com/install.sh | bash
#
# What it does:
#   1. Verifies Python ≥ 3.10 and pipx are available (installs pipx if not).
#   2. Trusts the CoreKinect SubCA inside certifi so pip + corectl can
#      speak to the internal PyPI and API over HTTPS.
#   3. Installs corectl from https://pypi.concord.ad.corekinect.com/simple/.
#   4. Runs `corectl auth login` to walk the user through the device-code
#      approval flow.
#
# Assumption: the caller is on the corp network (office LAN, VPN, or Wi-Fi).
# No public-internet fallback — the PyPI host and CA are both internal.

set -euo pipefail

CONCORD_HOST="${CONCORD_HOST:-concord.ad.corekinect.com}"
PYPI_INDEX="${PYPI_INDEX:-https://pypi.${CONCORD_HOST}/simple/}"
CA_URL="${CA_URL:-https://${CONCORD_HOST}/ca.crt}"
MIN_PYTHON="3.10"

say() { printf "  %s\n" "$*"; }
die() { printf "\n  error: %s\n\n" "$*" >&2; exit 1; }
step() { printf "\n▸ %s\n" "$*"; }

# ── 1. Platform checks ────────────────────────────────────────────────

step "Checking platform"

case "$(uname -s)" in
  Darwin) PLATFORM="darwin" ;;
  Linux)  PLATFORM="linux"  ;;
  *) die "Unsupported OS: $(uname -s). corectl installs on macOS and Linux." ;;
esac
say "platform: $PLATFORM"

# Resolve a Python ≥ 3.10. We try the modern names first; on old Ubuntus
# ``python3`` is 3.8 and we want to fail loudly rather than later.
PY=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ver=$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
    # Sort-compare — works because version components are single digits
    # here (we never pick 3.9 or lower).
    if [ "$(printf '%s\n%s\n' "$MIN_PYTHON" "$ver" | sort -V | head -n1)" = "$MIN_PYTHON" ]; then
      PY="$candidate"
      break
    fi
  fi
done
[ -n "$PY" ] || die "Python ≥ ${MIN_PYTHON} is required. Install it and re-run."
say "python:   $PY ($("$PY" --version 2>&1))"

# ── 2. pipx ───────────────────────────────────────────────────────────

step "Ensuring pipx is installed"

if ! command -v pipx >/dev/null 2>&1; then
  if [ "$PLATFORM" = "darwin" ] && command -v brew >/dev/null 2>&1; then
    say "installing pipx via brew…"
    brew install pipx
  elif command -v apt-get >/dev/null 2>&1; then
    say "installing pipx via apt…"
    sudo apt-get update -qq
    sudo apt-get install -y --no-install-recommends pipx
  else
    # Fallback: bootstrap pipx via pip into the user site. This is the
    # PyPA-recommended path on distros without a pipx package.
    say "installing pipx via pip --user…"
    "$PY" -m pip install --user --quiet pipx
  fi
  # Some package managers don't put ~/.local/bin on PATH by default.
  export PATH="$HOME/.local/bin:$PATH"
  command -v pipx >/dev/null 2>&1 || die "pipx install did not land on PATH"
fi
pipx ensurepath >/dev/null 2>&1 || true
say "pipx:     $(pipx --version)"

# ── 3. Trust the CoreKinect SubCA ─────────────────────────────────────
#
# pipx creates isolated venvs, each with their own certifi bundle. We
# append ours to the system certifi store *before* installing corectl so
# the install itself (which hits an internal HTTPS PyPI) succeeds.

step "Trusting CoreKinect SubCA"

# Pull the CA — this is the ONE insecure call. It's fine: the CA is what
# we're bootstrapping trust for; subsequent calls verify against it.
TMP_CA="$(mktemp -t corekinect-ca.XXXXXX.crt)"
trap 'rm -f "$TMP_CA"' EXIT

if ! curl -fsSL --insecure -o "$TMP_CA" "$CA_URL"; then
  die "Could not download CA from $CA_URL. Are you on the corp network?"
fi
say "downloaded $(wc -c < "$TMP_CA") bytes from $CA_URL"

# Find the certifi bundle — pipx's bootstrap python will have one too,
# but this catches the common case where the user's system python
# already has certifi.
CERTIFI_BUNDLE="$("$PY" -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
if [ -n "$CERTIFI_BUNDLE" ] && [ -w "$CERTIFI_BUNDLE" ]; then
  if ! grep -qFx -- "$(head -n2 "$TMP_CA" | tail -n1)" "$CERTIFI_BUNDLE"; then
    cat "$TMP_CA" >> "$CERTIFI_BUNDLE"
    say "appended CA to $CERTIFI_BUNDLE"
  else
    say "CA already trusted in $CERTIFI_BUNDLE"
  fi
fi

# Export for the pip call below — pip's own verification path needs it
# until pipx builds its venv and inherits our cert.
export SSL_CERT_FILE="${CERTIFI_BUNDLE:-$TMP_CA}"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"

# ── 4. Install corectl ────────────────────────────────────────────────

step "Installing corectl from $PYPI_INDEX"

# ``--force`` so re-running this script upgrades in-place instead of
# complaining "package already installed".
pipx install --force \
  --pip-args="--index-url $PYPI_INDEX --trusted-host pypi.${CONCORD_HOST}" \
  corectl

# Append the CA to the fresh corectl venv too, so every corectl HTTPS
# call (login, refresh, uploads) validates against the internal PKI.
VENV_CERTIFI="$(pipx list --json 2>/dev/null \
  | "$PY" -c 'import json,sys; d=json.load(sys.stdin); v=d["venvs"].get("corectl"); print(v["metadata"]["main_package"]["package_or_url"] if v else "", end="")' \
  >/dev/null; \
  find "$HOME/.local/pipx/venvs/corectl" -name 'cacert.pem' 2>/dev/null | head -n1)"
if [ -n "$VENV_CERTIFI" ] && [ -w "$VENV_CERTIFI" ]; then
  if ! grep -qFx -- "$(head -n2 "$TMP_CA" | tail -n1)" "$VENV_CERTIFI"; then
    cat "$TMP_CA" >> "$VENV_CERTIFI"
    say "appended CA to $VENV_CERTIFI"
  fi
fi

command -v corectl >/dev/null 2>&1 || die "corectl not on PATH. Try 'pipx ensurepath' and reopen your shell."
say "corectl:  $(corectl --version 2>&1)"

# ── 5. Log in ─────────────────────────────────────────────────────────

step "Starting login — approve in your browser"

export CONCORD_API_URL="${CONCORD_API_URL:-https://${CONCORD_HOST}}"
corectl auth login

echo
echo "  done. Try: corectl auth status"
echo
