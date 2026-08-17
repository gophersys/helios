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
#   SMOKE_CHECKS   space-separated names of the functional groups to run. An
#                  unknown name FAILS naming it. Empty means the comparator
#                  alone, which is how the pull request gate runs this file; the
#                  host driver always names its groups, and refuses an image it
#                  has no group list for.
#   SMOKE_FIXTURE_DIR  where the driver wrote the embedded fixtures. A group that
#                  needs them FAILS naming the file it could not find.
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
  if [[ "${GOPHERSYS_DEVCONTAINER:-}" != "cloud" ]]; then
    fail "GOPHERSYS_DEVCONTAINER is '${GOPHERSYS_DEVCONTAINER:-}', want 'cloud'"
  else
    say "ok   GOPHERSYS_DEVCONTAINER = cloud"
  fi
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
  local toolchain
  for toolchain in xtensa-espressif_esp32_zephyr-elf xtensa-espressif_esp32s2_zephyr-elf xtensa-espressif_esp32s3_zephyr-elf riscv64-zephyr-elf; do
    if [[ -x "${ZEPHYR_SDK_INSTALL_DIR}/${toolchain}/bin/${toolchain}-gcc" ]]; then
      say "ok   sdk toolchain ${toolchain}"
    else
      fail "sdk toolchain ${toolchain}: no gcc at ${ZEPHYR_SDK_INSTALL_DIR}/${toolchain}/bin"
    fi
  done
  # Throwaway host keys, so `sshd -t` validates the full effective config,
  # HostKey paths included.
  run_step "sshd host keys" sudo mkdir -p /etc/ssh/hostkeys
  run_step "sshd host key ed25519" sudo ssh-keygen -q -N '' -t ed25519 -f /etc/ssh/hostkeys/ssh_host_ed25519_key
  run_step "sshd host key rsa" sudo ssh-keygen -q -N '' -t rsa -f /etc/ssh/hostkeys/ssh_host_rsa_key
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
run_functional_groups

if [[ "$FAILURES" -ne 0 ]]; then
  say "image-checks.sh: FAILED — ${FAILURES} of its checks"
  exit 1
fi
say "image-checks.sh: every check passed"
