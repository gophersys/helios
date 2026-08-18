#!/usr/bin/env bash
#
# _ctl/tests/smoke-contract.test.sh — what the host driver tells the guest.
#
# Hermetic: a stub `docker` first on PATH, and every argv it receives is
# recorded. The stub also keeps the STDIN of `docker run`, which is where the
# guest script travels, so this file asserts the PAYLOAD and not only the argv.
# No daemon, no network, no image.
#
# ============================================================================
# THE DEFECT
# ============================================================================
#
# .ci/smoke.sh runs ~40 `<tool> --version` lines inside the image and reads the
# exit status of each. An exit status of 0 says the binary RUNS. It says nothing
# about WHICH version runs, so `gh --version` is green on gh 2.40 while
# versions.env pins 2.90. 1 tool is compared against its pin today — buildx —
# and the other 43 pins are numbers in a file.
#
# 7 tools are named in the checks below because each one is a hole the gate can
# feel, and none of them is asserted today:
#
#   hnslint          the HNS-1 naming gate. Absent, the eden gate cannot run.
#   hadolint         .claude/rules/00-identity.md says the PIN governs the
#                    verdict: 2.15.1 raises DL3064 on a file 2.14.0 passes. A
#                    drifted hadolint makes `ctl.sh validate` disagree with CI.
#   docker compose   the cli-plugin. base-runner measurably shipped without the
#                    buildx plugin once, and nothing said so.
#   npm, nvm, node   npm and nvm are installed through nvm, so a drifted nvm
#                    silently changes the node the image runs.
#   zsh              the default shell of every image, and the shell the smoke
#                    itself runs in.
#   pnpm             corepack takes `pnpm@latest` today, so the image installs
#                    whatever the day gives it. That is not a pin at all.
#
# ============================================================================
# THE CONTRACT THIS FILE ENCODES
# ============================================================================
#
#   1. the host driver feeds the guest script (.ci/image-checks.sh) to the
#      container on STDIN. It travels there and not in the argv because the
#      guest also receives embedded fixtures, and an argv is not a place to put
#      a file.
#   2. the payload carries 1 comparator row per pin the driver classifies
#      `asserted`, in the `<PIN>|<expected>|<command>` shape .ci/image-checks.sh
#      reads. A pin classified `asserted` and absent from the payload is a
#      classification that lies.
#   2b. the payload carries 1 ABSENT_TABLE row per absence probe the class table
#      names, in the `<PIN>|<binary>` shape, and it EXPORTS that table. This is
#      rule 2 for the negative half of a classification (ledger #103): a
#      `not-in-this-image:terraform` row whose binary never reaches the guest is
#      the unchecked claim the probe exists to end, and it reads exactly like a
#      probe that ran. The export is part of the rule because the rows travel
#      inside the payload TEXT either way — without it every row is present and
#      the guest still sees nothing.
#   3. a pin that resolves to the EMPTY string fails the run, names the pin, and
#      starts NO container. An empty expected version compares against nothing,
#      so a container that ran anyway would report a green image that was never
#      checked — the exact result this repository has already published once.
#
# Rule 3 is asserted with the `refused without building` shape of
# build.test.sh:75, and for the same reason: a non-zero status alone also comes
# out of an unrelated abort, and only "no container was started" cannot be faked.
#
# Usage: bash _ctl/tests/smoke-contract.test.sh
#
set -Eeuo pipefail
IFS=$'\n\t'

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
PROJECT_ROOT="$REPO_ROOT"

# The logging lives in _ctl/lib.sh, 1 time only — the same source line every
# other script in this repository uses.
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../lib.sh
source "$REPO_ROOT/_ctl/lib.sh"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=harness.sh
source "$TESTS_DIR/harness.sh"

TEST_NAME="smoke-contract.test.sh"

STUB_BIN="$TESTS_DIR/stubs"
SMOKE="$REPO_ROOT/.ci/smoke.sh"
GUEST_SCRIPT="image-checks.sh"

# The image and the local ref the CI job smokes before it publishes. Written as
# literals: they are the shape build-and-push.yml uses, and a test that read
# them out of the workflow would agree with a wrong workflow.
IMAGE="cloud"
SMOKE_REF="cloud:smoke"

# The tools the payload must name. Each one is a gate-critical hole today.
# `docker compose` carries a space on purpose — the plugin is invoked that way,
# and `docker-compose` is the retired v1 binary.
NAMED_TOOLS=(
  "hnslint"
  "hadolint"
  "docker compose"
  "npm"
  "nvm"
  "zsh"
  "pnpm"
)

# The pin that the empty-resolution case removes. It is gate-critical, so a
# reader of the failure sees a real consequence and not a synthetic one.
EMPTY_PIN="HNSLINT_VERSION"

RUN_OUTPUT=""
RUN_STATUS=0
RUN_ARGV=""
RUN_PAYLOAD=""

# run_smoke <smoke.sh> <image> <ref> [KEY=VALUE ...] — a real smoke run against
# the stub docker.
#
# RUN_ARGV holds every docker invocation, 1 per line, which is how a check tells
# "it refused" apart from "it ran the container quietly". RUN_PAYLOAD holds the
# stdin of `docker run`, which is the guest script.
#
# The trailing KEY=VALUE arguments are the stub's own knobs — STUB_IMAGE_SIZE is
# the one the size-gate cases below set. They are passed here rather than
# exported by the caller, so a knob cannot leak from 1 case into the next.
#
# The run reads /dev/null on stdin. Without that, `docker run` inherits the
# stdin of this test file, and the stub would sit and wait on a terminal.
function run_smoke() {
  local smoke="$1" image="$2" reference="$3"
  shift 3
  local log payload
  log="$(mktemp)"
  payload="$(mktemp)"
  RUN_STATUS=0
  RUN_OUTPUT="$(env PATH="${STUB_BIN}:${PATH}" STUB_DOCKER_LOG="$log" STUB_DOCKER_STDIN="$payload" \
    "$@" bash "$smoke" "$image" "$reference" < /dev/null 2>&1)" || RUN_STATUS=$?
  RUN_ARGV="$(cat "$log")"
  RUN_PAYLOAD="$(cat "$payload")"
  rm -f "$log" "$payload"
}

# stage_repository_without_pin <pin name> — a repository root whose versions.env
# lost 1 row, built out of symlinks to the real tree.
#
# No seam is added to .ci/smoke.sh for this. The script already reads its
# repository root out of its own location, so a copy of the file tree with a
# mutated versions.env is all a test needs to state the world it wants.
#
# EVERY file the driver reads has to be in the tree, and images.yaml joined that
# set when the image graph became data. Without its symlink the staged run died
# in _ctl/lib.sh — "the image manifest is absent" — before it read a single pin,
# so the case reported rule 3 as broken while the pin guard it names was
# untouched. A staging function that omits an input does not weaken the case it
# stages; it replaces it with a different one.
function stage_repository_without_pin() {
  local pin="$1"
  local root
  root="$(mktemp -d)"
  ln -s "$REPO_ROOT/_ctl" "${root}/_ctl"
  ln -s "$REPO_ROOT/base" "${root}/base"
  ln -s "$REPO_ROOT/.ci" "${root}/.ci"
  ln -s "$REPO_ROOT/images.yaml" "${root}/images.yaml"
  grep -v "^${pin}=" "$REPO_ROOT/versions.env" > "${root}/versions.env"
  printf '%s' "$root"
}

# asserted_pins — the pins .ci/smoke.sh says it compares for this image.
#
# Read from the same SMOKE_LIST_PINS seam version-coverage.test.sh checks. The
# 2 files then cannot disagree: 1 says every pin carries a class, this one says
# every pin classified `asserted` really reaches the guest.
# stderr is kept and not sent to /dev/null: an error nobody reads is how a
# listing that failed becomes an empty list that looks like an answer. The awk
# filter accepts only `<NAME>|asserted` lines, so the log noise around the
# records cannot be read as data, and an empty result is reported below.
function asserted_pins() {
  local text status=0
  text="$(env PATH="${STUB_BIN}:${PATH}" SMOKE_LIST_PINS=1 \
    bash "$SMOKE" "$IMAGE" < /dev/null 2>&1)" || status=$?
  if [[ "$status" -ne 0 ]]; then
    printf ''
    return 0
  fi
  printf '%s\n' "$text" | awk -F'|' '/^[A-Za-z_][A-Za-z0-9_]*\|asserted/ { print $1 }'
}

# absence_rows <table variable name> — the `<PIN>|<binary>` rows the class table
# of this image asks the guest to probe, 1 per line, 1 per BINARY: a row that
# names 2 (`RUST_CHANNEL|not-in-this-image:rustc,cargo`) is 2 rows in
# ABSENT_TABLE, because the guest runs 1 `command -v` per binary.
#
# THIS READS THE TABLE TEXT, and the file already offers a seam, so the reason
# has to be stated. SMOKE_LIST_PINS=1 prints the BARE class — that is the seam's
# contract, and version-coverage.test.sh holds it — so the listing cannot say
# which rows carry a probe or what binary they name. The probe is visible only in
# the table. Widening the seam is a change to .ci/smoke.sh and is open work;
# until then this reader is the only way this direction can fail at all.
#
# A `not-in-this-image` row with NO probe is deliberately not a row here.
# RUNNER_VERSION and ANSIBLE_VERSION are the 2, and each says beside itself why a
# probe would prove nothing: the Actions runner is on no image's PATH, and the
# ansible metapackage ships no binary of its own.
function absence_rows() {
  awk -v want="$1" '
    $0 ~ ("^read -r -d .. " want " <<") { inside = 1; next }
    /^PIN_CLASS_TABLE$/ { inside = 0; next }
    inside && /^[A-Za-z_][A-Za-z0-9_]*\|not-in-this-image:/ {
      position = index($0, "|")
      pin = substr($0, 1, position - 1)
      rest = substr($0, position + 1)
      second = index(rest, "|")
      class = (second == 0) ? rest : substr(rest, 1, second - 1)
      total = split(substr(class, index(class, ":") + 1), binaries, ",")
      for (index_of_binary = 1; index_of_binary <= total; index_of_binary++) {
        print pin "|" binaries[index_of_binary]
      }
    }
  ' "$SMOKE"
}

# docker_run_lines <argv log> — how many `docker run` invocations a log holds.
# The payload the driver sends can hold the word "run" itself, so the match is
# anchored at the start of a logged line.
#
# awk and not `grep -c`: grep exits 1 when it counts 0, and `grep -c ... || true`
# would throw a status away to keep the function quiet. This file never writes
# `|| true`.
function docker_run_lines() {
  printf '%s\n' "$1" | awk '/^docker run / { total++ } END { print total + 0 }'
}

# assert_refused_without_running <check name> <needle> [evidence...]
#
# 3 conditions, 1 check, on purpose — the shape build.test.sh:75 uses. A
# non-zero status and a named pin each pass on runs that have nothing to do with
# the rule; only "no container was started" cannot be faked, because a container
# that ran has already reported an image as smoked.
function assert_refused_without_running() {
  local name="$1" needle="$2"
  shift 2
  local runs
  runs="$(docker_run_lines "$RUN_ARGV")"
  if [[ "$RUN_STATUS" -eq 0 ]]; then
    fail_check "$name" \
      "want: a non-zero exit status, with a message naming ${needle}" \
      "got:  0 — the smoke was accepted" "$@" \
      "docker was called with:" "${RUN_ARGV:-<no docker invocation>}" \
      "output was:" "$RUN_OUTPUT"
  elif ! grep -qF -- "$needle" <<< "$RUN_OUTPUT"; then
    fail_check "$name" \
      "the smoke exited ${RUN_STATUS}, and the message never names ${needle}" "$@" \
      "docker was called with:" "${RUN_ARGV:-<no docker invocation>}" \
      "output was:" "$RUN_OUTPUT"
  elif [[ "$runs" -ne 0 ]]; then
    fail_check "$name" \
      "the smoke exited ${RUN_STATUS} and said the right thing, and it had ALREADY started a container:" \
      "$RUN_ARGV" "$@" \
      "a run that starts the container first has reported an image as smoked against an empty pin"
  else
    pass_check "$name"
  fi
}

printf '=== RUN  %s\n' "$TEST_NAME"

if [[ -x "$STUB_BIN/docker" ]]; then
  pass_check "the_docker_stub_is_executable"
else
  fail_check "the_docker_stub_is_executable" \
    "not executable: ${STUB_BIN}/docker" \
    "without it the real docker answers, and nothing below is hermetic"
fi

# -------- 1. the driver runs 1 container, and it is the ref it was given ------
run_smoke "$SMOKE" "$IMAGE" "$SMOKE_REF"
assert_equal "the_smoke_starts_exactly_one_container" \
  "1" "$(docker_run_lines "$RUN_ARGV")" \
  "docker was called with:" "${RUN_ARGV:-<no docker invocation>}" \
  "output was:" "$RUN_OUTPUT"
assert_contains "the_smoke_runs_the_ref_it_was_given" \
  "$RUN_ARGV" "$SMOKE_REF" \
  "the CI job builds a local ref with push:false + load:true and smokes THAT ref" \
  "a run against another ref would assert about an image nobody built here"

# -------- 2. the guest script travels on stdin --------
# Every rule below reads the payload, so a payload that is empty makes each of
# them vacuous. That is why this is a check of its own and it comes first.
if [[ -n "$RUN_PAYLOAD" ]]; then
  pass_check "the_guest_script_travels_on_stdin"
else
  fail_check "the_guest_script_travels_on_stdin" \
    "docker run received nothing on stdin" \
    "the guest also receives embedded fixtures, and an argv is not a place to put a file" \
    "docker was called with:" "${RUN_ARGV:-<no docker invocation>}"
fi
assert_contains "the_payload_is_the_guest_checker" \
  "$RUN_PAYLOAD" "$GUEST_SCRIPT" \
  "the payload has to BE .ci/image-checks.sh, which names itself in its header" \
  "a payload written inline in .ci/smoke.sh cannot be run on the host, and then nothing tests it"

# -------- 3. 1 comparator row per pin the driver calls `asserted` --------
pins="$(asserted_pins)"
pin_total=0
missing_rows=""
while IFS= read -r pin; do
  [[ -z "$pin" ]] && continue
  pin_total=$((pin_total + 1))
  if ! grep -qE "^${pin}\|" <<< "$RUN_PAYLOAD"; then
    missing_rows="${missing_rows:+${missing_rows}
}${pin}"
  fi
done <<< "$pins"

if [[ "$pin_total" -eq 0 ]]; then
  fail_check "every_asserted_pin_reaches_the_guest" \
    "SMOKE_LIST_PINS=1 named no pin as asserted, so this rule compared nothing" \
    "a rule with no input reports a clean result it never read"
elif [[ -n "$missing_rows" ]]; then
  fail_check "every_asserted_pin_reaches_the_guest" \
    "these pins are classified asserted and carry no comparator row in the payload:" \
    "$missing_rows" \
    "a row is <PIN>|<expected version>|<command>, which is what .ci/image-checks.sh reads" \
    "a classification that never reaches the guest is a claim of coverage, not coverage"
else
  pass_check "every_asserted_pin_reaches_the_guest"
fi

# -------- 3b. 1 ABSENT_TABLE row per absence probe the table names --------
#
# The mirror of section 3, for the negative half of a classification. The
# measured defect: on 2026-08-17 ghcr.io/gophersys/base:latest carried
# /usr/local/bin/terraform and /usr/local/bin/aws while 2 rows classified them
# not-in-this-image, and nothing here could report it. A probe that does not
# reach the guest restores exactly that silence, and the run stays green.
absent_rows="$(absence_rows "PIN_CLASSES_CLOUD")"
absent_row_total=0
missing_absent_rows=""
while IFS= read -r absent_row; do
  [[ -z "$absent_row" ]] && continue
  absent_row_total=$((absent_row_total + 1))
  if ! grep -qxF -- "$absent_row" <<< "$RUN_PAYLOAD"; then
    missing_absent_rows="${missing_absent_rows:+${missing_absent_rows}
}${absent_row}"
  fi
done <<< "$absent_rows"

if [[ "$absent_row_total" -eq 0 ]]; then
  fail_check "every_absence_probe_reaches_the_guest" \
    "the ${IMAGE} class table names no absence probe at all, so this rule compared nothing" \
    "the driver refuses such an image, and a rule with no input reports a clean result it never read"
elif [[ -n "$missing_absent_rows" ]]; then
  fail_check "every_absence_probe_reaches_the_guest" \
    "these absence probes are named in the class table and carry no ABSENT_TABLE row in the payload:" \
    "$missing_absent_rows" \
    "a row is <PIN>|<binary>, which is what run_absence_checks in .ci/image-checks.sh reads" \
    "a probe that never reaches the guest is the unchecked claim not-in-this-image used to be"
else
  pass_check "every_absence_probe_reaches_the_guest"
fi

# The rows travel inside the payload TEXT whether or not the guest can see them.
# Without the export they are a heredoc the guest writes to a variable of its own
# stdin shell and never passes on, every row above is still found, and
# run_absence_checks reads an empty ABSENT_TABLE and returns 0 — a green run with
# every probe silently dropped.
assert_contains "the_payload_exports_the_absence_table" \
  "$RUN_PAYLOAD" "export ABSENT_TABLE" \
  "the guest reads ABSENT_TABLE out of its environment, and an unexported table is an empty one there"

# -------- 4. the 7 gate-critical tools are named --------
for tool in "${NAMED_TOOLS[@]}"; do
  # The check name carries the tool, so a reader finds the missing one in the
  # list of names and not only in the evidence.
  check_name="the_payload_asserts_$(printf '%s' "$tool" | tr ' -' '__')"
  assert_contains "$check_name" "$RUN_PAYLOAD" "$tool" \
    "this tool is gate-critical and no version of it is compared today"
done

# pnpm is pinned by NO row of versions.env today: cloud/Dockerfile takes
# `corepack prepare pnpm@latest`, so the image installs whatever the day gives
# it. The tool name alone is not enough here — the PIN has to exist.
assert_contains "the_payload_asserts_the_pnpm_pin" \
  "$RUN_PAYLOAD" "PNPM_VERSION" \
  "pnpm@latest is not a pin; the image content then changes with no diff at all"

# -------- 5. an empty pin fails the run, and starts no container --------
staged_root="$(stage_repository_without_pin "$EMPTY_PIN")"
run_smoke "${staged_root}/.ci/smoke.sh" "$IMAGE" "$SMOKE_REF"
rm -rf "$staged_root"
assert_refused_without_running "an_empty_pin_fails_the_run_and_starts_no_container" \
  "$EMPTY_PIN" \
  "versions.env in this run holds no ${EMPTY_PIN} row, so the pin resolves to the empty string" \
  "an empty expected version compares against nothing, and a green run would bless any image"

# -------- 6. the R4 size budget, at its 2 sides --------
#
# The cloud budget is acceptance metric 2 of the image program (risk R4), and
# Mateo set the number at 5.75 GB on 2026-08-16 after the levers were measured
# one by one. Until now the gate ran only against a real image on the publish
# path, so nothing on the pull request path could tell a working gate from a
# gate that reads the size and never compares it.
#
# The 2 cases are 1 byte apart on purpose. A budget checked far from its edge
# passes with `>` written as `>=`, with the wrong constant, and with a
# comparison the shell reads as a string — 5750000001 vs 5750000000 as strings
# still orders correctly, so the pair below is chosen so that ONLY the boundary
# itself separates them.
#
# The stub answers `docker image inspect --format '{{.Size}}'` with
# STUB_IMAGE_SIZE, so no image of any size is ever built.
CLOUD_SIZE_BUDGET="5750000000"

run_smoke "$SMOKE" "$IMAGE" "$SMOKE_REF" "STUB_IMAGE_SIZE=$((CLOUD_SIZE_BUDGET + 1))"
assert_refused_without_running "an_image_one_byte_over_the_budget_fails_and_starts_no_container" \
  "$CLOUD_SIZE_BUDGET" \
  "the image measured $((CLOUD_SIZE_BUDGET + 1)) bytes, which is 1 byte over the 5.75 GB budget" \
  "the gate runs before the push, so an oversize image that smokes green reaches every consumer"

run_smoke "$SMOKE" "$IMAGE" "$SMOKE_REF" "STUB_IMAGE_SIZE=${CLOUD_SIZE_BUDGET}"
if [[ "$RUN_STATUS" -ne 0 ]]; then
  fail_check "an_image_exactly_at_the_budget_passes_the_gate_and_is_smoked" \
    "want: exit 0 — ${CLOUD_SIZE_BUDGET} bytes is the budget, and the budget is inclusive" \
    "got:  ${RUN_STATUS}" \
    "a gate that refuses its own limit hands back a budget nobody can meet" \
    "output was:" "$RUN_OUTPUT"
elif [[ "$(docker_run_lines "$RUN_ARGV")" -ne 1 ]]; then
  fail_check "an_image_exactly_at_the_budget_passes_the_gate_and_is_smoked" \
    "the run exited 0 and started $(docker_run_lines "$RUN_ARGV") containers, want exactly 1" \
    "an exit 0 with no container is a size gate that ate the whole smoke" \
    "docker was called with:" "${RUN_ARGV:-<no docker invocation>}"
else
  pass_check "an_image_exactly_at_the_budget_passes_the_gate_and_is_smoked"
fi

test_summary "$TEST_NAME"
