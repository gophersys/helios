#!/usr/bin/env bash
# .ci/lib/log.sh — structured output for CI stages.

_RED='\033[0;31m'
_GREEN='\033[0;32m'
_YELLOW='\033[0;33m'
_BLUE='\033[0;34m'
_BOLD='\033[1m'
_DIM='\033[2m'
_RESET='\033[0m'

# Disable colors in non-interactive / dumb terminals
if [[ "${NO_COLOR:-}" == "1" ]] || [[ ! -t 1 && "${FORCE_COLOR:-}" != "1" ]]; then
  _RED="" _GREEN="" _YELLOW="" _BLUE="" _BOLD="" _DIM="" _RESET=""
fi

bold()      { echo -e "${_BOLD}$*${_RESET}"; }
log_info()  { echo -e "${_BLUE}info${_RESET}  $*"; }
log_ok()    { echo -e "${_GREEN}ok${_RESET}    $*"; }
log_warn()  { echo -e "${_YELLOW}warn${_RESET}  $*"; }
log_err()   { echo -e "${_RED}err${_RESET}   $*"; }
log_skip()  { echo -e "${_DIM}skip${_RESET}  $*"; }

# Section header with timing.
# Usage: log_stage "description"
#        <commands>
#        log_stage_end
_STAGE_START=""

log_stage() {
  _STAGE_START=$(date +%s)
  echo ""
  echo -e "${_BOLD}── $* ──${_RESET}"
}

log_stage_end() {
  local elapsed=$(( $(date +%s) - _STAGE_START ))
  echo -e "${_DIM}   done in ${elapsed}s${_RESET}"
}

# Run a command with a label. Fails fast.
# Usage: run "description" command arg1 arg2
run() {
  local label="$1"; shift
  log_info "$label"
  "$@"
}
