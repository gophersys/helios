#!/usr/bin/env bash
#
# verb_conservation_test.sh — the BEFORE/AFTER record that a unification changes NOTHING.
#
# `go/_ctl/lib.sh` and `templates/_ctl/template.sh` are 2 parallel gate libraries sharing 22
# function names, of which only 4 are byte-identical. Folding them into one home (10 §9) is a
# refactor, and a refactor's whole claim is that nothing observable moves. This suite makes
# that claim mechanical instead of asserted.
#
# What is recorded, per project and per verb: the EXIT CODE, and the exact argv of every
# external GATE TOOL the verb invoked, in order. That pair is the verb's observable behaviour
# — the tool it chose, the flags it passed, the status it returned. A unification that
# silently drops `-race`, reorders a gate, loses a `--config`, changes a coverage floor, or
# stops propagating a failure moves one of those bytes and fails here.
#
# Every gate tool (go, gofumpt, golangci-lint, govulncheck, gosec, gitleaks, hnslint,
# benchstat, gremlins, rg, oapi-codegen, docker, k3d, kind, git) is replaced by a stub that
# records its own argv and exits a CHOSEN code, so the record is hermetic, fast, and depends
# on nothing this host has installed. Two profiles are captured for every verb:
#
#   pass  every tool exits 0 — the happy-path argv sequence.
#   fail  every tool exits 1 — the FAILURE PROPAGATION record. This is the half that catches
#         a gate which stops reporting a red verb (templates/_ctl/template.sh reports PASS
#         over a failing `go build` today; that is recorded here as fact, so a change to it
#         is deliberate and visible in the diff).
#
# The verbs run against a COPY of go/ and templates/ under mktemp -d, never this working
# tree, so a recording run cannot write a .benchbaseline or an .apibaseline into the repo.
#
# 2 phases, after go/_ctl/lib_test.sh and ctl_test.sh:
#
#   phase 1  behaviour      — the live capture must equal the recorded golden, byte for byte.
#   phase 2  discrimination — the capture is re-run against a MUTATED copy of the shared
#                             library, and must DIFFER. A recording that matches a mutant is
#                             a record of nothing.
#
# Usage:
#   bash verb_conservation_test.sh                 run both phases
#   bash verb_conservation_test.sh <project>       run one project (e.g. go/errors)
#   EDEN_CONSERVATION_RECORD=1 bash verb_conservation_test.sh
#                                                  RE-RECORD the goldens. Only ever run this
#                                                  when the change to the verbs is deliberate,
#                                                  and review the diff — the same discipline
#                                                  as bench-record and apidiff-record.
#
# shellcheck shell=bash
set -Eeuo pipefail
IFS=$'\n\t'

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GOLDEN_DIR="$HERE/testdata/verb-conservation"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

RECORD="${EDEN_CONSERVATION_RECORD:-0}"

# The gate tools both libraries reach for. Every one is stubbed on every run.
TOOLS=(go gofumpt golangci-lint govulncheck gosec gitleaks hnslint benchstat gremlins rg oapi-codegen docker k3d kind git)

# The ordinary utilities the verbs call. The sandbox PATH holds ONLY these and the stubs, so
# no verb can reach a real gate tool through a longer path.
COREUTILS=(dirname basename mktemp cat tail head rm cp mkdir touch chmod ln sed awk grep tr sort uniq wc find env printf cut xargs date true false)

# The projects under record. Each entry is a path relative to the repository root holding a
# ctl.sh that sources one of the 2 shared libraries. The list is EXPLICIT: a lib added or
# removed must be added or removed here, and `t_every_dispatcher_is_recorded` fails until it
# is, so a project can never fall out of the record unnoticed.
PROJECTS=(
  go/agentruntime go/agentsession go/codeinsight go/configuration go/dependencies
  go/edenhttp go/envelope go/errors go/forge go/gitrepository go/objectstorage
  go/observability go/orchestrator go/secrets go/testing go/workspaceprovider
  templates/go/http-gateway
)

# The verbs each shared library dispatches, EXPLICIT for the same reason as PROJECTS. An
# entry may carry arguments: `phase-gate` takes a phase, and each phase is recorded
# SEPARATELY, because the phase's exit code is the whole point of this feature — a gate that
# reports GREEN over a red dimension is invisible in the bare `phase-gate` record, which
# short-circuits, and visible the moment each phase is asked on its own.
GO_VERBS=(build test lint vet fmt cover property leak lifecycle integration load vuln sast
  secretscan bench bench-guard bench-record maintainability mutate cover-floor apidiff
  apidiff-record phase-gate
  "phase-gate architecture" "phase-gate implementation" "phase-gate testing" "phase-gate qa")
TEMPLATE_VERBS=(build test lint vet fmt cover generate openapi verify-openapi gen-client
  integration vuln sast secretscan maintainability phase-gate
  "phase-gate architecture" "phase-gate implementation" "phase-gate testing" "phase-gate qa")

# MUTANT is the phase-2 counter-stimulus: the name of a mutation applied to the shared library
# in the sandbox copy. Empty means the library is copied verbatim.
MUTANT=""

info() { printf '\033[0;36m[test]\033[0m %s\n' "$*"; }
ok()   { printf '\033[0;32m  ok  \033[0m %s\n' "$*"; }
bad()  { printf '\033[0;31m FAIL \033[0m %s\n' "$*" >&2; }
die()  { printf '\033[0;31m[test]\033[0m %s\n' "$*" >&2; exit 1; }
fail() { printf '       %s\n' "$*" >&2; exit 1; }

# FAIL-NOT-SKIP (ADR-0020): a missing tool is a failure that names the tool, never a skip.
for _tool in mktemp diff sed grep cp; do
  command -v "$_tool" >/dev/null || die "this host has no $_tool; the suite cannot run"
done
[[ "${BASH_VERSINFO[0]}" -ge 4 ]] ||
  die "this host's bash is $BASH_VERSION; the suite (and ctl.sh) need bash 4+ — run it in ghcr.io/gophersys/base"

# ── the sandbox ─────────────────────────────────────────────────────────────

# The ordinary utilities are resolved ONCE into a single directory that every sandbox shares.
# Resolving them per sandbox cost 25 forks × 780 sandboxes, which dominated the run.
COREUTILS_DIR="$WORK/coreutils"
mkdir -p "$COREUTILS_DIR"
ln -s "$(command -v bash)" "$COREUTILS_DIR/bash"
for _utility in "${COREUTILS[@]}"; do
  _path="$(command -v "$_utility")" ||
    die "this host has no $_utility; the sandbox cannot be built (FAIL-NOT-SKIP)"
  ln -s "$_path" "$COREUTILS_DIR/$_utility"
done

# verbs_of <project> prints the verb list for a project's dispatcher.
verbs_of() {
  case "$1" in
    go/*)        printf '%s\n' "${GO_VERBS[@]}" ;;
    templates/*) printf '%s\n' "${TEMPLATE_VERBS[@]}" ;;
    *) die "no verb list is declared for project '$1'" ;;
  esac
}

# apply_mutant <library-path> edits the sandbox COPY of a shared library. Each mutation is a
# single-token change a careless unification could plausibly make, so a golden that survives
# one is a golden that reads nothing.
apply_mutant() {
  local library="$1"
  case "$MUTANT" in
    "") : ;;
    # The race detector silently dropped from the test lane — the change that would make the
    # suite green and the libraries unguarded.
    drop-race)    sed -i.bak 's/ -race -count=1/ -count=1/g' "$library" ;;
    # A verb that stops propagating its failure: the exact class this feature exists to fix.
    swallow-fail) sed -i.bak 's/^\( *\)go_in_lib \(.*\)$/\1go_in_lib \2 || true/' "$library" ;;
    *) die "unknown mutant: $MUTANT" ;;
  esac
  rm -f "$library.bak"
}

# shared_library_of <project> prints the shared gate library a project's dispatcher sources.
shared_library_of() {
  case "$1" in
    go/*)        printf 'go/_ctl/lib.sh' ;;
    templates/*) printf 'templates/_ctl/template.sh' ;;
    *) die "no shared library is declared for project '$1'" ;;
  esac
}

# stage <project> prints a staging tree holding ONLY the project directory, the shared gate
# library beside it, and the shared golangci config — built once per project and copied per
# verb. Copying the whole of go/ per verb read ~5 MB across the bind mount 780 times; the
# staged subtree is the same inputs at a fraction of the I/O.
stage() {
  local project="$1" staged shared
  staged="$WORK/stage/$project"
  if [[ ! -d "$staged" ]]; then
    shared="$(shared_library_of "$project")"
    mkdir -p "$staged/$project" "$staged/${shared%/*}"
    cp -R "$HERE/$project/." "$staged/$project/"
    cp -R "$HERE/${shared%/*}/." "$staged/${shared%/*}/"
    cp "$HERE/.golangci.yml" "$staged/.golangci.yml"
  fi
  printf '%s' "$staged"
}

# make_sandbox <project> <tool-exit-code> prints the path of a fresh sandbox holding a COPY of
# the staged tree (so a verb writes into the copy, never into this working tree) plus a bin/
# of recording stubs.
make_sandbox() {
  local project="$1" rc="$2" sb tool staged
  sb="$(mktemp -d "$WORK/sb.XXXXXX")"
  mkdir -p "$sb/bin" "$sb/tree"
  : > "$sb/argv"

  staged="$(stage "$project")"
  cp -R "$staged/." "$sb/tree/"
  apply_mutant "$sb/tree/$(shared_library_of "$project")"

  for tool in "${TOOLS[@]}"; do
    {
      printf '#!/usr/bin/env bash\n'
      # argv alone is not the whole invocation: `property` and `load` carry their scale in the
      # ENVIRONMENT (`env RAPID_CHECKS=… go test`, `env EDEN_LOAD_N=… go test`), and GOWORK
      # decides which modules resolve. A unification that dropped one of those would leave
      # argv untouched, so the named environment is recorded beside it.
      # shellcheck disable=SC2016 # the stub body is emitted verbatim, expanded when it runs
      printf '%s\n' 'environment=""'
      # shellcheck disable=SC2016 # likewise
      printf '%s\n' 'for name in RAPID_CHECKS EDEN_LOAD_N GOWORK GOFLAGS CGO_ENABLED; do'
      # shellcheck disable=SC2016 # likewise
      printf '%s\n' '  [[ -n "${!name:-}" ]] && environment="$environment $name=${!name}"'
      # shellcheck disable=SC2016 # likewise
      printf '%s\n' 'done'
      # shellcheck disable=SC2016 # likewise
      printf 'printf "%%s\\t%%s%%s\\n" "%s" "$*" "$environment" >> "%s"\n' "$tool" "$sb/argv"
      if [[ "$tool" == "go" ]]; then
        # have_cmd's fallback asks `go env GOPATH`; it must answer, never hang.
        # shellcheck disable=SC2016 # the stub body is emitted verbatim, expanded when it runs
        printf 'if [[ "${1:-}" == "env" ]]; then printf "%%s\\n" "%s/gopath"; exit 0; fi\n' "$sb"
      fi
      printf 'exit %s\n' "$rc"
    } > "$sb/bin/$tool"
    chmod +x "$sb/bin/$tool"
  done

  printf '%s' "$sb"
}

# normalize reads a raw capture on stdin and prints it with every host-specific token
# replaced, so the golden is a property of the verbs and not of this machine or this run.
normalize() {
  local sb="$1"
  sed -e "s#${sb}#<sandbox>#g" \
      -e "s#${HERE}#<repository>#g" \
      -e 's#tmp\.[A-Za-z0-9]\{6,\}#<tmp>#g' \
      -e 's#\(cover\)\.[A-Za-z0-9]\{6,\}#\1.<tmp>#g' \
      -e 's#[A-Za-z0-9_.-]*\.\(XXXXXX\)*[A-Za-z0-9]\{6\}\b#<tmp>#g'
}

# capture <project> <profile> prints the conservation record for one project: for each verb,
# its exit code and the argv of every gate tool it invoked, in order.
capture() {
  local project="$1" profile="$2" rc verb sb out verb_rc
  case "$profile" in
    pass) rc=0 ;;
    fail) rc=1 ;;
    *) die "unknown profile '$profile' (pass|fail)" ;;
  esac

  printf '# verb-conservation record — project=%s profile=%s\n' "$project" "$profile"
  printf '# every gate tool exits %s; each block is one verb: its exit code, then the argv\n' "$rc"
  printf '# of every external gate tool it invoked, in order.\n'

  local arguments
  while read -r verb; do
    [[ -n "$verb" ]] || continue
    # A verb entry may carry arguments ("phase-gate testing"); split it on spaces, which the
    # file-scoped IFS deliberately excludes.
    IFS=' ' read -r -a arguments <<< "$verb"
    sb="$(make_sandbox "$project" "$rc")"
    verb_rc=0
    out="$(cd "$sb/tree/$project" && env -i \
      PATH="$sb/bin:$COREUTILS_DIR" HOME="$sb" TMPDIR="$sb" \
      EDEN_GOWORK="$sb/absent.go.work" \
      EDEN_GOLANGCI_CONFIG="$sb/tree/.golangci.yml" \
      bash "$sb/tree/$project/ctl.sh" "${arguments[@]}" 2>&1)" || verb_rc=$?
    printf '\n### verb %s\n' "$verb"
    printf 'exit %s\n' "$verb_rc"
    normalize "$sb" < "$sb/argv"
    # `out` is deliberately NOT recorded: the human-readable log is prose that a refactor may
    # legitimately reword. The tool argv and the exit code are the contract.
    : "$out"
    rm -rf "$sb"
  done < <(verbs_of "$project")
}

# golden_path <project> prints where a project's record lives. The slash in a project path
# becomes a directory, so the record mirrors the tree it describes.
golden_path() { printf '%s/%s.txt' "$GOLDEN_DIR" "$1"; }

# ── the tests ───────────────────────────────────────────────────────────────

# CONSERVATION. The live capture must equal the recorded golden, byte for byte.
t_the_recorded_verbs_are_unchanged() {
  local project="$1" golden live difference
  golden="$(golden_path "$project")"
  [[ -f "$golden" ]] ||
    fail "$project has no conservation record at ${golden#"$HERE"/}; re-record with EDEN_CONSERVATION_RECORD=1"
  live="$WORK/live.txt"
  { capture "$project" pass; capture "$project" fail; } > "$live"
  # A record with no tool invocations at all would match a golden of the same emptiness and
  # prove nothing, so the capture must contain at least one gate-tool line.
  grep -qE '^(go|gofumpt|golangci-lint|govulncheck|gosec|gitleaks|hnslint|benchstat|gremlins|rg|oapi-codegen|docker|k3d|kind|git)\b' "$live" ||
    fail "$project: the capture recorded no gate-tool invocation at all, so it proves nothing"
  if ! difference="$(diff -u "$golden" "$live")"; then
    fail "$project: the verbs moved vs ${golden#"$HERE"/}:"$'\n'"$difference"
  fi
}

# CONSERVATION. Every dispatcher in the tree must be under record. A project that exists but
# is absent from PROJECTS is a whole library the guard is blind to.
t_every_dispatcher_is_recorded() {
  local found missing=() directory
  found="$(cd "$HERE" && find go templates -mindepth 1 -maxdepth 3 -name ctl.sh -not -path '*/_ctl/*' | sed 's#/ctl.sh$##' | sort)"
  [[ -n "$found" ]] || fail "no dispatcher was found under go/ or templates/; the search is broken"
  while read -r directory; do
    [[ -n "$directory" ]] || continue
    # Codegen sub-projects (persistence, clients/go) carry their own standalone ctl.sh and do
    # not source either shared library, so they are outside this record by construction.
    [[ -f "$HERE/$directory/project.json" ]] || continue
    grep -q "_ctl/lib.sh\|_ctl/template.sh" "$HERE/$directory/ctl.sh" || continue
    printf '%s\n' "${PROJECTS[@]}" | grep -Fxq "$directory" || missing+=("$directory")
  done <<< "$found"
  [[ ${#missing[@]} -eq 0 ]] ||
    fail "these dispatchers source a shared gate library but carry no conservation record: ${missing[*]}"
}

# ── the driver ──────────────────────────────────────────────────────────────

selected_projects=("${PROJECTS[@]}")
if [[ $# -gt 0 ]]; then
  selected_projects=()
  for p in "${PROJECTS[@]}"; do
    [[ "$p" == "$1" ]] && selected_projects+=("$p")
  done
  [[ ${#selected_projects[@]} -gt 0 ]] ||
    die "no project is named '$1'; the record covers: ${PROJECTS[*]}"
fi

# assert_capture_is_not_empty <file> <project> — the same floor the verify path applies, on
# the RECORD path. A capture that reached no tool is indistinguishable from a matching golden
# once it is committed, so a broken recording must fail here rather than become the baseline.
assert_capture_is_not_empty() {
  local file="$1" project="$2"
  grep -qE '^(go|gofumpt|golangci-lint|govulncheck|gosec|gitleaks|hnslint|benchstat|gremlins|rg|oapi-codegen|docker|k3d|kind|git)\b' "$file" ||
    die "$project: the capture recorded no gate-tool invocation at all — recording it would freeze a record of nothing"
}

if [[ "$RECORD" == "1" ]]; then
  info "RE-RECORDING ${#selected_projects[@]} project(s) — review the diff before committing"
  for p in "${selected_projects[@]}"; do
    mkdir -p "$(dirname "$(golden_path "$p")")"
    { capture "$p" pass; capture "$p" fail; } > "$WORK/record.txt"
    assert_capture_is_not_empty "$WORK/record.txt" "$p"
    cp "$WORK/record.txt" "$(golden_path "$p")"
    info "  recorded $p"
  done
  exit 0
fi

failures=0
MUTANT=""

info "phase 1 — behaviour: ${#selected_projects[@]} project(s) against their recorded verbs"
if ( set -Eeuo pipefail; t_every_dispatcher_is_recorded ); then
  ok "t_every_dispatcher_is_recorded"
else
  bad "t_every_dispatcher_is_recorded"
  failures=$((failures + 1))
fi
for p in "${selected_projects[@]}"; do
  if ( set -Eeuo pipefail; t_the_recorded_verbs_are_unchanged "$p" ); then
    ok "t_the_recorded_verbs_are_unchanged $p"
  else
    bad "t_the_recorded_verbs_are_unchanged $p"
    failures=$((failures + 1))
  fi
done

# Phase 2 mutates the shared library in the sandbox copy and requires the record to notice.
# One project per shared library is enough: the mutation is applied to the library, and the
# libraries are what the record is guarding.
info "phase 2 — discrimination: each shared library under a mutant must break its record"
proven=0
for spec in "go/errors drop-race" "go/errors swallow-fail" "templates/go/http-gateway drop-race"; do
  IFS=' ' read -r p MUTANT <<< "$spec"
  printf '%s\n' "${selected_projects[@]}" | grep -Fxq "$p" || continue
  if ( set -Eeuo pipefail; t_the_recorded_verbs_are_unchanged "$p" ); then
    bad "$p survived the '$MUTANT' mutant; the record does not read what it claims to read"
    failures=$((failures + 1))
  else
    ok "$p breaks under the '$MUTANT' mutant"
    proven=$((proven + 1))
  fi
done
MUTANT=""

if [[ "$failures" -ne 0 ]]; then
  die "$failures failure(s) across both phases"
fi
info "${#selected_projects[@]} project record(s) hold; $proven mutant(s) caught"
