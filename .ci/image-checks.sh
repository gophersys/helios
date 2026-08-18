#!/usr/bin/env bash
#
# .ci/image-checks.sh — the checks that run INSIDE a built image.
#
# .ci/smoke.sh is the HOST driver: it classifies every pin, resolves each one
# out of the file that owns it, and sends this file to the container on stdin
# together with the fixtures the functional checks need. This file compares and
# exercises; it never reads a pin file, because inside the image there is none.
#
# It is a FILE and not a heredoc for 1 reason: a heredoc runs in exactly 1
# place — inside a container, after a build, on the publish path — so nothing on
# the pull request path can run it, and the comparator itself would be tested by
# nothing. `_ctl/tests/guest-checks.test.sh` runs this file on the host against a
# stub PATH, so the comparator is checked at pull request time and the image only
# supplies the tools.
#
# The contract:
#
#   PIN_TABLE      1 row per pin, `<PIN>|<expected>|<command>[|extractor]`.
#                  REQUIRED: an empty table exits non-zero, because a comparator
#                  that compares nothing must never report success.
#   ABSENT_TABLE   1 row per binary that must NOT be in this image,
#                  `<PIN>|<binary>`. The driver builds it from every pin it
#                  classifies `not-in-this-image:<binary>`, which until ledger
#                  #103 was a class nothing checked — a tool that leaked into an
#                  image read exactly like a tool that stayed out. Empty means no
#                  negative check, which is how the pull request gate runs this
#                  file; the host driver always sends rows, and REFUSES an image
#                  whose whole table names no probe.
#   SMOKE_CHECKS   space-separated names of the functional groups to run. An
#                  unknown name FAILS naming it. Empty means the comparator
#                  alone, which is how the pull request gate runs this file; the
#                  host driver always names its groups, and refuses an image it
#                  has no group list for.
#   SMOKE_IMAGE    the image the driver was asked about. GOPHERSYS_DEVCONTAINER
#                  must equal it. Empty means no marker check, which is how the
#                  pull request gate runs this file; the host driver always sends
#                  it, because it took the name from its own argv.
#   SMOKE_FIXTURE_DIR  where the driver wrote the embedded fixtures. A group that
#                  needs them FAILS naming the file it could not find.
#   SMOKE_KICAD_ROOT  the root of the KiCad share tree the content-hardware
#                  floors count under. Optional, and the default is the image's
#                  own /usr/share/kicad, so a real run never sets it. It is a
#                  TEST SEAM: an absolute path is drivable only from inside a
#                  built image, so the branch that reports a thin library had no
#                  hermetic stimulus until this name existed.
#
# The extractor field, and why the default is not enough on its own:
#
#   (empty)        the first `<digits>.<digits>[...]` token of the output, compared
#                  exactly. This reads gh, node, helm, kubectl and 25 others.
#   prefix         the same token, compared as a prefix. For a pin apt resolves
#                  (`zsh=5.9*` installs 5.9-6ubuntu2) and for a pin that names a
#                  package rather than a version (PYTHON_PACKAGE=python3.12,
#                  python3 reports 3.12.3).
#   line:<text>    the first token on the first line holding <text>. `govulncheck
#                  -version` prints `Go: go1.26.5` first, and the runner prints
#                  `RuntimeInformation: Ubuntu 24.04.4 LTS` before its own version —
#                  a first-token reader asserts the wrong number and passes.
#
# Every failure is collected rather than fatal, at BOTH levels: a failing step
# does not stop the remaining steps of its group, and a failing group does not
# stop the groups after it. 44 pins with 3 drifts must report 3 drifts, and a run
# that ends at the first one reports 1.
#
# That is why `run_step` never returns non-zero. This file runs under `set -e`,
# where a bare command that returns 1 ends the guest where it stands, so a
# verdict carried in an exit status is a verdict that stops the run. The verdict
# is carried in FAILURES instead: `fail` counts, `failed_since` is how a step
# asks whether the step it depends on failed, `skip_step` is how a step that
# therefore cannot run says so by name, and the only exit is at the bottom.
#
set -Eeuo pipefail
IFS=$'\n\t'

FAILURES=0

function say()  { printf '%s\n' "$*"; }

# fail <message> — record a failure and carry on. Nothing here exits.
function fail() { printf 'FAIL: %s\n' "$*"; FAILURES=$((FAILURES + 1)); }

# failed_since <mark> — was a failure recorded after <mark>, which a caller read
# out of FAILURES before the step it depends on? This is the only way one step
# reports to another, and it reads the same counter the exit status is read from.
function failed_since() { [[ "$FAILURES" -ne "$1" ]]; }

# skip_step <label> <reason> — a step whose input a failed step was to produce.
# It prints itself, so a reader never has to infer that something did not run.
#
# A skip is honest only once something else has already failed: the run is red
# either way, and the reader is told which tool went unproven. In a run where
# nothing failed, a step that neither ran nor failed is a check that cannot fail,
# so that case is recorded AS a failure.
function skip_step() {
  if [[ "$FAILURES" -eq 0 ]]; then
    fail "${1}: not run because ${2} — and nothing else failed, so this step reported neither pass nor fail"
    return 0
  fi
  say "SKIP: ${1} — ${2}"
}

# -------- the comparator --------

# probe_tool <command> — the executable a command line runs. Leading `NAME=value`
# assignments are skipped: the pnpm row carries COREPACK_HOME, so the tool of
# that row is `pnpm` and not an assignment nothing can resolve.
function probe_tool() {
  local remaining="$1" word
  while :; do
    word="${remaining%% *}"
    case "$word" in
      [A-Za-z_]*=*)
        [[ "$remaining" == *' '* ]] || { printf '%s' "$word"; return 0; }
        remaining="${remaining#* }"
        ;;
      *) printf '%s' "$word"; return 0 ;;
    esac
  done
}

# extract_version <text> <extractor> — the version the output reports, empty when
# this reader cannot find one. awk and not grep: grep exits 1 when it matches
# nothing, and an empty match is a case this file REPORTS rather than aborts on.
function extract_version() {
  local text="$1" extractor="$2" scope="$1"
  case "$extractor" in
    line:*)
      scope="$(printf '%s\n' "$text" | awk -v needle="${extractor#line:}" 'index($0, needle) { print; exit }')"
      ;;
    *) ;;
  esac
  printf '%s\n' "$scope" | awk 'match($0, /[0-9]+\.[0-9]+(\.[0-9]+)*/) { print substr($0, RSTART, RLENGTH); exit }'
}

# compare_pin <pin> <expected> <command> <extractor> — 1 row of the table.
function compare_pin() {
  local pin="$1" expected="$2" probe="$3" extractor="${4:-}"
  local tool status=0 output="" observed="" errors=""

  if [[ -z "$expected" ]]; then
    fail "${pin}: the driver sent an empty expected version, so '${probe}' would be compared against nothing"
    return 0
  fi

  case "$extractor" in
    ""|prefix|line:?*) ;;
    *)
      fail "${pin}: unknown extractor '${extractor}' — the readers are: (empty), prefix, line:<text>"
      return 0
      ;;
  esac

  tool="$(probe_tool "$probe")"
  # An absent tool is a version that cannot be compared, and a skip there is the
  # green-while-broken result this whole file exists to prevent.
  if ! command -v "$tool" >/dev/null 2>&1; then
    fail "${pin}: ${tool} is not on PATH, so '${probe}' cannot report a version to compare against ${expected}"
    return 0
  fi

  # stderr is kept apart from stdout: `bw --version` writes 2 lines of noise to
  # stderr and the runner writes its whole log to stdout, so a merged stream
  # feeds the reader tokens the tool never meant as its version. The stderr is
  # printed when something fails, because that is where the reason usually is.
  errors="$(mktemp)"
  output="$(eval "$probe" 2>"$errors")" || status=$?
  if [[ "$status" -ne 0 ]]; then
    fail "${pin}: '${probe}' exited ${status}"
    say "      it printed: ${output}"
    say "      stderr:     $(cat "$errors")"
    rm -f "$errors"
    return 0
  fi

  observed="$(extract_version "$output" "$extractor")"
  # stdout first, then stderr. `grpcurl -version` and `java -version` both write
  # their version to stderr, and a reader that only ever looks at stdout reports
  # a working tool as unreadable. Measured on grpcurl 1.9.3.
  if [[ -z "$observed" ]]; then
    observed="$(extract_version "$(cat "$errors")" "$extractor")"
  fi
  if [[ -z "$observed" ]]; then
    fail "${pin}: '${probe}' printed no version this check can read${extractor:+ with extractor ${extractor}}"
    say "      it printed: ${output}"
    say "      stderr:     $(cat "$errors")"
    rm -f "$errors"
    return 0
  fi
  rm -f "$errors"

  local matched=0
  case "$extractor" in
    prefix) [[ "$observed" == "${expected}"* ]] && matched=1 ;;
    *)      [[ "$observed" == "$expected" ]] && matched=1 ;;
  esac
  if [[ "$matched" -ne 1 ]]; then
    fail "version drift: '${probe}' reports ${observed}, and ${pin} pins ${expected}"
    return 0
  fi
  say "ok   ${pin} = ${observed}   ('${probe}')"
}

function run_comparator() {
  if [[ -z "${PIN_TABLE:-}" ]]; then
    fail "PIN_TABLE is empty — a comparator that compares nothing must never report success"
    return 0
  fi
  local pin expected probe extractor
  say "--- versions: every pin the driver classified asserted ---"
  while IFS='|' read -r pin expected probe extractor; do
    [[ -z "$pin" ]] && continue
    compare_pin "$pin" "$expected" "$probe" "${extractor:-}"
  done <<< "$PIN_TABLE"
}

# absence_of <pin> <binary> — 1 row of ABSENT_TABLE. The tool must resolve
# NOWHERE on PATH, and the failure prints the path it was found at, because
# "terraform is present" sends the reader looking and
# "/usr/local/bin/terraform is present" names the layer that put it there.
function absence_of() {
  local pin="$1" binary="$2" found=""
  if [[ -z "$binary" ]]; then
    fail "${pin}: the driver sent an absence row with no binary, so nothing was probed"
    return 0
  fi
  if found="$(command -v "$binary" 2>/dev/null)"; then
    fail "${pin}: ${binary} is at ${found}, and this image classifies ${pin} not-in-this-image"
    return 0
  fi
  say "ok   ${pin}: ${binary} is absent"
}

# Every image of this repository exports GOPHERSYS_DEVCONTAINER=<its own name>,
# so a development script and a project CI job can detect which image they run
# inside. This is the check that the marker says what the driver was asked
# about.
#
# It is a check of its own and not a line in a content group, because it is true
# of EVERY image while a content group belongs to one. Written into
# checks_content_cloud it asserted the literal `cloud`, which meant 4 of the 6
# images asserted no marker at all, and the first image to inherit that group
# would have had to lie about its own name to pass.
#
# Empty SMOKE_IMAGE means no marker check, the way an empty ABSENT_TABLE means
# no absence check: that is how the pull request gate runs this file, with no
# image at all. The host driver always sends it.
function run_devcontainer_marker() {
  if [[ -z "${SMOKE_IMAGE:-}" ]]; then
    return 0
  fi
  if [[ "${GOPHERSYS_DEVCONTAINER:-}" != "$SMOKE_IMAGE" ]]; then
    fail "GOPHERSYS_DEVCONTAINER is '${GOPHERSYS_DEVCONTAINER:-}', and the driver smoked '${SMOKE_IMAGE}'"
    return 0
  fi
  say "ok   GOPHERSYS_DEVCONTAINER = ${SMOKE_IMAGE}"
}

# The negative half of the classification. `not-in-this-image` was an assertion
# nobody checked until this group: the driver said the image does not install the
# tool, no command ran, and a leak read like a clean image. Measured on
# 2026-08-17 — ghcr.io/gophersys/base:latest carries /usr/local/bin/terraform and
# /usr/local/bin/aws while base/Dockerfile installs neither.
function run_absence_checks() {
  if [[ -z "${ABSENT_TABLE:-}" ]]; then
    return 0
  fi
  local pin binary
  say "--- absence: every pin the driver classified not-in-this-image with a probe ---"
  while IFS='|' read -r pin binary; do
    [[ -z "$pin" ]] && continue
    absence_of "$pin" "$binary"
  done <<< "$ABSENT_TABLE"
}

# -------- the functional groups --------

# fixture <relative path> — an embedded fixture, or a FAILURE naming it. The
# fixtures travel in the same stdin stream this file does, so an absent one means
# the driver did not send what it said it sent.
FIXTURE_PATH=""
function fixture() {
  FIXTURE_PATH="${SMOKE_FIXTURE_DIR:-}/$1"
  if [[ -z "${SMOKE_FIXTURE_DIR:-}" || ! -e "$FIXTURE_PATH" ]]; then
    fail "the fixture ${1} is not in the image: ${FIXTURE_PATH}"
    return 1
  fi
  return 0
}

# run_step <label> <command...> — a functional step. It runs the real tool on a
# real input, and its output is printed when it fails. It never returns
# non-zero: see the header — a status is a verdict that would end the guest.
function run_step() {
  run_step_in "." "$@"
}

# run_step_in <directory> <label> <command...> — the same step, run somewhere
# else. Only the `cd` is in a subshell, and the recording stays in THIS shell: a
# failure recorded inside a subshell dies with the subshell, which is how this
# file once printed `FAIL: go build` and `every check passed` in the same run.
function run_step_in() {
  local directory="$1" label="$2"
  shift 2
  local status=0 output=""
  output="$( { cd "$directory" && "$@"; } 2>&1 )" || status=$?
  if [[ "$status" -ne 0 ]]; then
    # `$*` joins on the FIRST character of IFS, and this file runs with
    # IFS=$'\n\t', so the plain form printed the command 1 word per line.
    fail "${label}: exited ${status}"
    say "      command: $(IFS=' '; printf '%s' "$*")"
    say "      output:  ${output}"
    return 0
  fi
  say "ok   ${label}"
  return 0
}

# The Go gate on a real module: the tools that print a version above have to
# COMPILE, VET, FORMAT and LINT something here. GOPROXY=off and a dependency-free
# fixture mean this reaches no network, and the caches are temporary so the image
# the smoke asserts about is not modified by the assertion.
GO_FIXTURE_BINARY=""
function checks_go_gate() {
  fixture smoke || return 0
  local module="$FIXTURE_PATH"
  local work
  work="$(mktemp -d)"
  GO_FIXTURE_BINARY="${work}/smoke"
  export GOPROXY=off GOFLAGS=-mod=mod
  export GOCACHE="${work}/go-build" GOMODCACHE="${work}/go-mod" GOLANGCI_LINT_CACHE="${work}/golangci"

  say "--- the Go gate toolchain, on a real module ---"
  run_step_in "$module" "go build" go build -o "$GO_FIXTURE_BINARY" ./cmd/smoke
  # A failed build does not stop the 4 steps below. Each one proves a DIFFERENT
  # tool runs in this image, none of them reads the binary, and a step that did
  # not run proves nothing about its tool. The one step that really needs the
  # binary is in the debugger group, and it is gated there, where it is used.
  run_step_in "$module" "go vet" go vet ./...
  # gofumpt reports by PRINTING the files it would change and exiting 0, so the
  # status says nothing about formatting and the output is that verdict. The
  # status does say whether gofumpt RAN, and read through a bare `$(...)` a
  # gofumpt that crashed ended the whole guest here, with no message at all.
  local unformatted="" gofumpt_status=0
  unformatted="$(cd "$module" && gofumpt -l .)" || gofumpt_status=$?
  if [[ "$gofumpt_status" -ne 0 ]]; then
    fail "gofumpt: it exited ${gofumpt_status} on the fixture module, so it did not report on the formatting at all"
    say "      it printed: ${unformatted}"
  elif [[ -n "$unformatted" ]]; then
    fail "gofumpt: the fixture is not gofumpt-clean, so this check cannot tell a working gofumpt from a broken one"
    say "      it listed: ${unformatted}"
  else
    say "ok   gofumpt"
  fi
  run_step_in "$module" "golangci-lint run" golangci-lint run ./...
  run_step "hnslint" hnslint "$module"
}

function checks_dockerfile_lint() {
  fixture Dockerfile || return 0
  say "--- hadolint, on a real Dockerfile ---"
  run_step "hadolint" hadolint "$FIXTURE_PATH"
}

function checks_compose() {
  fixture compose.yaml || return 0
  say "--- the docker compose cli-plugin, on a real file ---"
  # `config` resolves and prints the model. It reaches no daemon, so it is
  # meaningful in a plain docker run with no dind sidecar.
  run_step "docker compose config" docker compose -f "$FIXTURE_PATH" config
}

function checks_debugger() {
  if [[ -z "$GO_FIXTURE_BINARY" ]]; then
    fail "delve has no binary to trace: the go-gate group builds it, and it must run before this one"
    return 0
  fi
  if [[ ! -x "$GO_FIXTURE_BINARY" ]]; then
    # The go-gate group ran and its build wrote nothing, which that group has
    # already counted. Reporting delve as broken here would name the wrong tool;
    # saying nothing would leave delve reading as checked.
    skip_step "dlv exec" "the go-gate build wrote no binary to trace"
    return 0
  fi
  say "--- delve, running the fixture binary under the debugger ---"
  local work
  work="$(mktemp -d)"
  printf 'continue\nexit\n' > "${work}/delve-commands"
  # dlv launches the binary under ptrace, continues it and reports the status it
  # exited with. A container that denies ptrace cannot attach at all and this
  # FAILS, which is the honest answer: a debugger that cannot attach is not a
  # working debugger.
  #
  # `dlv trace`, which is the stronger operation, is NOT used: setting a
  # tracepoint writes to the traced process, and that write fails with
  # "input/output error" when the image runs emulated on a developer host. The
  # check would then pass on a CI runner and fail on every mac — measured on
  # 2026-08-16 against ghcr.io/gophersys/cloud:latest under linux/amd64
  # emulation. Attach-and-run behaves the same in both places.
  local output="" status=0
  output="$(dlv exec "$GO_FIXTURE_BINARY" --allow-non-terminal-interactive=true --init "${work}/delve-commands" 2>&1)" || status=$?
  if [[ "$status" -ne 0 || "$output" != *"has exited with status 0"* ]]; then
    fail "dlv exec: the debugger did not run the fixture to its exit (status ${status})"
    say "      output: ${output}"
    return 0
  fi
  say "ok   dlv exec (the fixture ran to exit under the debugger)"
}

function checks_protocols() {
  fixture echo.proto || return 0
  local fixtures="${SMOKE_FIXTURE_DIR}"
  local work
  work="$(mktemp -d)"
  say "--- buf and grpcurl, on a real proto ---"
  local mark="$FAILURES"
  run_step_in "$fixtures" "buf build" buf build --output "${work}/echo.binpb" --as-file-descriptor-set
  if failed_since "$mark"; then
    # This is the one real dependency inside the group: grpcurl reads the file
    # buf writes. Running it anyway would report grpcurl broken over a missing
    # input, and blame the tool that works.
    skip_step "grpcurl list" "buf build wrote no descriptor set to read"
    return 0
  fi
  # grpcurl reads the descriptor set buf just wrote and lists what is in it. No
  # server is dialled, so this is a real operation with no network at all.
  local listed="" status=0
  listed="$(grpcurl -protoset "${work}/echo.binpb" list 2>&1)" || status=$?
  if [[ "$status" -ne 0 ]]; then
    fail "grpcurl: reading the descriptor set exited ${status}"
    say "      output: ${listed}"
    return 0
  fi
  case "$listed" in
    *smoke.v1.EchoService*) say "ok   grpcurl list = ${listed}" ;;
    *) fail "grpcurl: the descriptor set does not name smoke.v1.EchoService; it listed: ${listed}" ;;
  esac
}

# -------- the content groups: what a version cannot say --------

# check_benchstat — the 1 gate tool no pin can compare. BENCHSTAT_REF tracks
# `@latest`, so the binary reports no version to hold against anything, and its
# presence is the whole proof. Every image that installs the gate toolchain runs
# this, cloud included.
#
# The `X && echo ok` form is BANNED here: under `set -e` a failure inside an
# AND-list does not abort the script, so that form is a check that cannot fail —
# proven by drill during the size-lever work, where a wrong binary name still
# ended in a green smoke. The explicit `if` is what makes it fail loudly.
function check_benchstat() {
  if benchstat -h >/dev/null 2>&1; then
    say "ok   benchstat"
  else
    fail "benchstat: it does not run in this image"
  fi
}

function checks_content_base() {
  say "--- base content ---"
  say "architecture: $(uname -m)"
  # RUST_CHANNEL pins a channel and not a version, so the toolchain is proven by
  # running rather than by comparing.
  run_step "rustc" rustc --version
  run_step "cargo" cargo --version
  check_benchstat
  if [[ -d /usr/local/lib/docker/cli-plugins ]]; then
    say "ok   docker cli-plugins: $(find /usr/local/lib/docker/cli-plugins -maxdepth 1 -type f -exec basename {} \; | tr '\n' ' ')"
  else
    fail "docker cli-plugins: /usr/local/lib/docker/cli-plugins is not in this image"
  fi
}

function checks_content_cloud() {
  say "--- cloud content ---"
  say "architecture: $(uname -m)"
  # The GOPHERSYS_DEVCONTAINER assertion left this group and is
  # run_devcontainer_marker below, which every image runs. It was written here
  # as the literal `cloud`, and `hardware` builds FROM cloud and takes this
  # group — so the check would have demanded that a hardware image call itself
  # cloud, which is the one thing the marker exists to make impossible.
  # The gate-tools layer measured 2.06 GB in base because the RUN never removed
  # the module and build caches. The cleanup is MANDATORY in cloud, and a green
  # smoke on an image that silently kept them would bless the exact regression.
  # This runs BEFORE the Go gate group, whose caches are temporary by design.
  if [[ -d "${GOPATH:-}/pkg/mod" ]]; then
    fail "${GOPATH}/pkg/mod is still in the image (the 1.6 GB regression)"
  elif [[ -d "${HOME:-}/.cache/go-build" ]]; then
    fail "${HOME}/.cache/go-build is still in the image (the 1.6 GB regression)"
  else
    say "ok   go caches: absent, as built"
  fi
  check_benchstat
  # The tool groups that carry no pin of their own: the data clients and the
  # comforts the census kept. A version there would be an apt version nobody
  # declared, so what is asserted is that they run.
  local tool
  for tool in psql sqlite3 redis-cli bat htop btop http; do
    run_step "$tool" "$tool" --version
  done
}

function checks_content_runner() {
  say "--- the Actions runner layout ---"
  # The runner writes .runner and .credentials into /home/runner at
  # registration. An unwritable directory makes every pod fail to start, and it
  # is invisible until a job is queued — the first runner build shipped that.
  [[ -x /home/runner/run.sh ]] || fail "/home/runner/run.sh is not executable"
  [[ -w /home/runner ]]       || fail "/home/runner is not writable"
  [[ -d /home/runner/externals ]] || fail "/home/runner/externals is not in the image"
  [[ -w /home/runner/_work ]] || fail "/home/runner/_work is not writable"
  # A pod that runs as root needs this or run.sh exits 1 in under a second.
  [[ "${RUNNER_ALLOW_RUNASROOT:-}" == "1" ]] || fail "RUNNER_ALLOW_RUNASROOT is not 1; run.sh refuses to start as root"
  # node must resolve in a NON-login shell: CI jobs run bash, not an interactive zsh.
  command -v node >/dev/null || fail "node is not on PATH"
  # The review agent needs the Claude CLI. Its absence was found only when a
  # review job failed with "missing required tool: claude".
  command -v claude >/dev/null || fail "claude is not on PATH"
  run_step "cictl" cictl help
  say "ok   runner layout"
  # Deliberately NOT asserted here: membership of the docker group. The pod
  # grants it with securityContext.supplementalGroups, because the dind sidecar
  # chooses the socket's gid, and a docker run has no dind sidecar.
}

function checks_content_flutter() {
  say "--- flutter content ---"
  run_step "flutter" flutter --version
  run_step "adb" adb --version
  run_step "java" java -version
}

function checks_content_zephyr() {
  say "--- zephyr content ---"
  run_step "west" west --version
}

# kicad_library_floor <label> <directory> <pattern> <floor> — the KiCad share
# tree holds at least <floor> files of that shape.
#
# The directory is tested BEFORE find runs, so an absent package is reported as
# an absent package. `find ... 2>/dev/null | wc -l` would answer 0 for it and the
# reader would be told the library is thin when it is not there at all.
#
# A FLOOR and never an equality: the libraries grow with every KiCad release, so
# an equality would go red on a bump that added a footprint.
function kicad_library_floor() {
  local label="$1" directory="$2" pattern="$3" floor="$4"
  if [[ ! -d "$directory" ]]; then
    fail "${label}: ${directory} is not in this image, so its package did not install"
    return 0
  fi
  local count="" status=0
  count="$(find "$directory" -name "$pattern" | wc -l | tr -d ' ')" || status=$?
  if [[ "$status" -ne 0 ]]; then
    fail "${label}: counting ${pattern} under ${directory} exited ${status}"
    return 0
  fi
  if [[ "$count" -lt "$floor" ]]; then
    fail "${label}: ${count} files under ${directory}, and the floor is ${floor}"
    return 0
  fi
  say "ok   ${label}: ${count} (floor ${floor})"
}

# The KiCad toolchain, and the 3 floors are the whole point of the group.
#
# `kicad` does NOT pull the symbol, footprint and 3D-model packages in under
# --no-install-recommends. Without them /usr/share/kicad EXISTS and is empty, so
# an image with kicad-cli passes every presence check and then fails the
# consumer's entire resolver suite at runtime on `assert 0 > 10000` — which
# reads like a code bug rather than a missing package. The 3 numbers are
# gophersys/research-hardware's own, from the assertion at the foot of its
# ci/Dockerfile.
#
# The VERSION is deliberately not compared here: KICAD_PPA_VERSION is an
# `asserted` row of the driver's table, which holds `kicad-cli version` against
# the pin. What this step adds is that the binary RUNS AT ALL — kicad ships as a
# GUI package and a headless invocation is the thing this image exists to
# provide, so "it executes" and "it is the pinned major" are 2 questions and each
# is asked once.
#
# SMOKE_KICAD_ROOT is the SEAM, and the default is the image's own path, so a
# real run is byte-identical to the one before this variable existed. It exists
# because the 3 floors were untestable: an absolute path can only be driven from
# inside a built image, so the branch that REPORTS a thin library had no
# hermetic stimulus and the harness had to say so in writing. With the root as a
# variable the suite points it at a fixture tree and drives all 3 branches —
# absent directory, under the floor, over it. A check nothing can make fail is
# not a check that passed.
function checks_content_hardware() {
  local kicad_root="${SMOKE_KICAD_ROOT:-/usr/share/kicad}"
  say "--- hardware content ---"
  run_step "kicad-cli" kicad-cli version
  kicad_library_floor "kicad footprints" "${kicad_root}/footprints" '*.kicad_mod' 10000
  kicad_library_floor "kicad symbol libraries" "${kicad_root}/symbols" '*.kicad_sym' 100
  kicad_library_floor "kicad STEP models" "${kicad_root}/3dmodels" '*.step' 1000
}

# The ui image, and the 4 things no version comparison can say about it.
#
# The VERSION is deliberately not compared here: CHROME_MAJOR_VERSION is an
# `asserted` row of the driver's table, and that row already reads the browser
# through ${DENSUI_CHROME}. What this group adds is why, when it breaks — an
# unset variable, a dangling symlink, a missing font and a PATH are 4 different
# defects and "sh exited 127" names none of them.
#
# THE TOOLCHAIN PAIR IS THE POINT OF THIS GROUP. node, npm and uv are on the
# image's ENV PATH, so a check that ran only as the container's own user stays
# GREEN with the /usr/local/bin exposure deleted — and that exposure is the whole
# reason this image carries no second Node. `sudo` is the second reader, because
# it replaces PATH with sudoers' secure_path, which is the same reset
# /etc/profile makes in every LOGIN shell — and `bash -lc` is how the consumer's
# gates invoke themselves. Both of those PATHs hold /usr/local/bin and neither
# holds /home/dev/.nvm, so the pair fails exactly when the symlinks are gone.
function checks_content_ui() {
  say "--- ui content ---"
  say "architecture: $(uname -m)"
  local browser="${DENSUI_CHROME:-}"
  if [[ -z "$browser" ]]; then
    fail "DENSUI_CHROME is not set: densui probe.py treats that the same as an empty value and searches for a browser of its own, so a gate can pass without ever using the one this image baked"
  elif [[ ! -x "$browser" ]]; then
    fail "DENSUI_CHROME is ${browser}, and there is no executable there"
  else
    say "ok   DENSUI_CHROME = ${browser}"
  fi
  local font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
  if [[ -f "$font" ]]; then
    say "ok   fallback font: ${font}"
  else
    fail "the fallback font ${font} is not in this image, so a layout that is COMPUTED from font metrics has nothing to measure off macOS"
  fi
  # An ENV and not a tool, and it is asserted for the reason it exists: without
  # it a piped gate block-buffers, and 9.5 silent minutes read as a stall and got
  # cancelled once.
  if [[ "${PYTHONUNBUFFERED:-}" == "1" ]]; then
    say "ok   PYTHONUNBUFFERED = 1"
  else
    fail "PYTHONUNBUFFERED is '${PYTHONUNBUFFERED:-}' and not 1, so a gate that pipes its output buffers it and a slow step is indistinguishable from a hung one"
  fi
  local tool
  for tool in node npm uv; do
    run_step "${tool} (this user)" "$tool" --version
    run_step "${tool} (root, through sudo's secure_path)" sudo "$tool" --version
  done
}

# sdk_toolchain_gcc <name> — the gcc of a Zephyr SDK toolchain, wherever this
# SDK release puts it. It prints nothing when there is none, and the caller
# turns that into a FAILURE.
#
# The path is SEARCHED and not templated. Zephyr SDK 1.0 moved the GNU
# toolchains from ${ZEPHYR_SDK_INSTALL_DIR}/<name>/ down to
# ${ZEPHYR_SDK_INSTALL_DIR}/gnu/<name>/, and the templated form reported all 4
# toolchains missing from an image that carries all 5 it installs — measured on
# ghcr.io/gophersys/zephyr-devbox:latest, SDK 1.0.1, on 2026-08-17. maxdepth 4
# reaches both layouts (gnu/<name>/bin/<name>-gcc, <name>/bin/<name>-gcc) and
# nothing deeper, so a stray copy in a sysroot cannot answer for the toolchain.
function sdk_toolchain_gcc() {
  find "${ZEPHYR_SDK_INSTALL_DIR}" -maxdepth 4 -type f -name "${1}-gcc" -print -quit
}

function checks_content_devbox() {
  say "--- zephyr-devbox content ---"
  run_step "openocd" openocd --version
  run_step "st-info" st-info --version
  run_step "esptool" esptool version
  run_step "picocom" picocom --help
  run_step "gdb-multiarch" gdb-multiarch --version
  run_step "clangd" clangd --version
  run_step "code-server" code-server --version
  # Baked-in extension seed (the entrypoint copies it onto a fresh PVC home).
  local extensions="" status=0
  extensions="$(code-server --extensions-dir "${CODE_SERVER_SEED_EXTENSIONS}" --list-extensions 2>&1)" || status=$?
  if [[ "$status" -ne 0 || "$extensions" != *llvm-vs-code-extensions.vscode-clangd* ]]; then
    fail "code-server: the seed extensions dir does not carry the clangd extension; it listed: ${extensions}"
  else
    say "ok   code-server clangd extension"
  fi
  # west extension commands, blob fetchers and `west espressif monitor` import
  # these at runtime.
  run_step "west venv deps" /opt/west-venv/bin/python -c "import requests, jsonschema"
  run_step "west venv esptool" /opt/west-venv/bin/python -c "import esptool, serial"
  local toolchain gcc status
  for toolchain in xtensa-espressif_esp32_zephyr-elf xtensa-espressif_esp32s2_zephyr-elf xtensa-espressif_esp32s3_zephyr-elf riscv64-zephyr-elf; do
    gcc=""
    status=0
    gcc="$(sdk_toolchain_gcc "$toolchain")" || status=$?
    if [[ "$status" -ne 0 ]]; then
      fail "sdk toolchain ${toolchain}: the search under ${ZEPHYR_SDK_INSTALL_DIR} exited ${status}"
    elif [[ -x "$gcc" ]]; then
      say "ok   sdk toolchain ${toolchain}: ${gcc}"
    else
      fail "sdk toolchain ${toolchain}: no executable ${toolchain}-gcc under ${ZEPHYR_SDK_INSTALL_DIR}"
    fi
  done
  # Throwaway host keys, so `sshd -t` validates the full effective config,
  # HostKey paths included.
  run_step "sshd host keys" sudo mkdir -p /etc/ssh/hostkeys
  run_step "sshd host key ed25519" sudo ssh-keygen -q -N '' -t ed25519 -f /etc/ssh/hostkeys/ssh_host_ed25519_key
  run_step "sshd host key rsa" sudo ssh-keygen -q -N '' -t rsa -f /etc/ssh/hostkeys/ssh_host_rsa_key
  # /run/sshd is a RUNTIME prerequisite that PID 1 supplies — embedded-entrypoint.sh
  # creates it just before it execs sshd — and `sshd -t` refuses to read the
  # config at all without it ("Missing privilege separation directory"). The
  # smoke sends its own argv, which the entrypoint execs INSTEAD of running that
  # preparation, so nothing here has created it. Creating it is what lets -t do
  # the job it exists for, which is to validate the CONFIG.
  run_step "sshd privsep dir" sudo install -d -m 0755 /run/sshd
  run_step "sshd -t" sudo /usr/sbin/sshd -t
}

function run_functional_groups() {
  local group
  # The split is explicit: this file runs with IFS=$'\n\t', so a `for` over a
  # space-separated string reads the whole list as 1 word and every group then
  # looks unknown. Measured here on the first run against a real image.
  local -a groups=()
  IFS=' ' read -r -a groups <<< "${SMOKE_CHECKS:-}"
  for group in ${groups[@]+"${groups[@]}"}; do
    case "$group" in
      go-gate)        checks_go_gate ;;
      dockerfile-lint) checks_dockerfile_lint ;;
      compose)        checks_compose ;;
      debugger)       checks_debugger ;;
      protocols)      checks_protocols ;;
      content-base)   checks_content_base ;;
      content-cloud)  checks_content_cloud ;;
      content-runner) checks_content_runner ;;
      content-flutter) checks_content_flutter ;;
      content-zephyr) checks_content_zephyr ;;
      content-devbox) checks_content_devbox ;;
      content-hardware) checks_content_hardware ;;
      content-ui)     checks_content_ui ;;
      *) fail "unknown check group: '${group}' — .ci/smoke.sh named a group this file does not have" ;;
    esac
  done
}

# The content groups run BEFORE the functional ones: the cloud content group
# asserts that the Go caches are absent, and a Go build is what would create
# them. The groups are named in whatever order the driver sends, so the ordering
# lives here, in the 1 place that knows why.
function order_groups() {
  local name content="" functional=""
  local -a named=()
  IFS=' ' read -r -a named <<< "${SMOKE_CHECKS:-}"
  for name in ${named[@]+"${named[@]}"}; do
    case "$name" in
      content-*) content="${content:+${content} }${name}" ;;
      *)         functional="${functional:+${functional} }${name}" ;;
    esac
  done
  printf '%s' "${content}${content:+${functional:+ }}${functional}"
}
SMOKE_CHECKS="$(order_groups)"

run_comparator
run_devcontainer_marker
# Before the functional groups, and for the reason the content groups run before
# them: a Go build writes caches and a check group could install nothing, but the
# absence claim is about the image AS BUILT, and the earliest reading is the
# truest one.
run_absence_checks
run_functional_groups

if [[ "$FAILURES" -ne 0 ]]; then
  say "image-checks.sh: FAILED — ${FAILURES} of its checks"
  exit 1
fi
say "image-checks.sh: every check passed"
