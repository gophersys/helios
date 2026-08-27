#!/usr/bin/env bash
#
# stop-gate.sh — supervisor plugin shim: delegates to the rendered template's
# .claude/hooks/stop-gate.sh in the project dir (the determinism logic has ONE home, the template).
#
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_shim.sh
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_shim.sh"
sv_shim_delegate "stop-gate.sh"
