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

# ============================================================================
# THE SECOND IMAGE, AND WHY 1 WAS NOT ENOUGH
# ============================================================================
#
# Every rule above ran against `cloud` alone, so each one held for the ARM of
# the driver that `cloud` takes and for no other. That was invisible while the
# driver's per-image work was 1 `case` arm and a shared tail — and it stopped
# being true when a second SHAPE arrived.
#
# `hardware` is that shape: a CHILD that reads versions.env. Its pins arrive as
# generated --build-args like cloud's, so it takes a class table of its OWN over
# the SAME home while the other 3 children read a table over their own
# Dockerfile; it declares a size budget, which 2 of the 6 images do not; and its
# whole reason to exist — the KiCad rows — is `asserted` in ITS table and
# `not-in-this-image` in the 3 others that read that home. A driver that selected
# the wrong table would produce a payload that is entirely well-formed and
# asserts the wrong image, and every check above would still pass, because they
# read cloud.
#
# Read on 2026-08-19 rather than incremented — and it had been incremented, by
# a paragraph written before the embedded fold made 2 images 1: `.ci/smoke.sh`
# declares 6 class tables, 4 of them over versions.env (CLOUD, BASE, HARDWARE,
# UI) and 2 over a child Dockerfile (MOBILE, EMBEDDED); images.yaml declares 6
# images and 4 of them carry
# `size_budget_gb` (cloud, embedded, hardware, ui), so 2 do not; and
# KICAD_PPA_VERSION is
# `asserted` in PIN_CLASSES_HARDWARE and `not-in-this-image:kicad-cli` in the
# other 3 tables over that home.
#
# `embedded` joined the budgeted set on 2026-08-19 at 8.98 GB, the first row of
# the 4 measured off a PUBLISHED image rather than a rehearsal job — its
# measurement and the proxy drift that qualifies it are beside the key in
# images.yaml. It is also the 1 budgeted image with no hand-kept literal in
# this file: the gate is 1 shared data-driven path whose 2 boundaries are held
# below for 3 images and whose BASIS is held by size-gate.test.sh, so a 4th
# copy would discriminate nothing. Stated rather than left to be noticed.
#
# The names below carry the image for the reason version-coverage.test.sh gives
# at its child loop: a reader finds the broken one in the list of names, and not
# only in the evidence.
HARDWARE_IMAGE="hardware"
HARDWARE_SMOKE_REF="hardware:smoke"
HARDWARE_CLASS_TABLE="PIN_CLASSES_HARDWARE"

# The 5 pins the hardware table flips from `not-in-this-image` to `asserted`,
# each written as the COMPARATOR ROW it has to arrive as: `<PIN>|<version>|` and
# then the command that prints the version, which is the shape
# .ci/image-checks.sh reads.
#
# THE ROW, AND NOT THE TOOL NAME, AND THAT IS THE WHOLE POINT OF THESE 5.
# Measured on 2026-08-18 by pointing the driver's hardware arm at
# PIN_CLASSES_CLOUD: a bare `assert_contains "$RUN_PAYLOAD" "pytest"` still
# passed, because the cloud table classifies the same pin
# `not-in-this-image:pytest` and the binary NAME then reaches the guest inside
# an ABSENT_TABLE row. 3 of the 5 tool names survived the wrong table that way,
# and the check that was supposed to catch it reported the payload as correct.
# An absence row is 2 fields and a comparator row is 3, so the pattern below
# separates them and a name alone cannot answer.
#
# The VERSION field is deliberately not stated: versions.env is the pin home,
# this is a contract test, and a value here would go red on every bump for a
# reason that has nothing to do with the contract. So each entry is
# `<PIN>|<the command that prints the version>` and the reader below compares
# FIELDS.
#
# FIELDS, AND NOT A REGULAR EXPRESSION, and that is not a style preference. The
# first version of this check was `grep -E "^${pin}|[^|]*|${command}"`, and `|`
# is ALTERNATION in an ERE: the pattern read as "^PIN or [^|]* or command", the
# middle branch matches every line ever written, and all 5 checks passed on a
# payload that carried none of the 5 rows. It was caught by breaking the driver
# on purpose and watching the check stay green — which is the only way that
# class of defect is ever caught. awk comparing $1 and $3 has no metacharacters
# to escape, and the commands here hold `(`, `)`, `'` and `-`.
HARDWARE_ASSERTED_ROWS=(
  'KICAD_PPA_VERSION|kicad-cli version'
  'KIUTILS_VERSION|python3 -c "import importlib.metadata as m; print(m.version('"'"'kiutils'"'"'))"'
  'SEXPDATA_VERSION|python3 -c "import importlib.metadata as m; print(m.version('"'"'sexpdata'"'"'))"'
  'PYTEST_VERSION|pytest --version'
  'RUFF_VERSION|ruff --version'
)

# The budget images.yaml declares for it, in the decimal bytes
# image_size_budget_bytes computes. It was 11.0 GB and PROVISIONAL — an estimate
# computed from 2 measured images, to be reset to the first green build's real
# size — and that reset has now happened: 10,013,827,072 unpacked bytes measured
# in rehearsal run 32202500436, x 1.05. This literal moves when that number
# does, and the pair of cases below is what makes the move visible instead of
# silent.
HARDWARE_SIZE_BUDGET="10520000000"

# ============================================================================
# THE THIRD IMAGE, WHICH IS THE SECOND OF ITS SHAPE
# ============================================================================
#
# `ui` is a CHILD that reads versions.env, the shape `hardware` introduced, and
# that is exactly why it is here: a shape with 1 member is a shape whose driver
# arm could be hardcoded to that member and nobody would know. Its 4th class
# table over the same home, its own content group and its own budget are each a
# thing the driver has to SELECT rather than assume.
#
# What is different from hardware, and what these checks are pinned on: this
# image asserts exactly 1 pin nothing else does, and that pin is not compared by
# running the tool's own name. `google-chrome-stable` is installed UNPINNED by
# Google's design — the docker-ce-cli precedent — so the row that MEANS anything
# is CHROME_MAJOR_VERSION, and it reaches the guest as a probe through the baked
# ${DENSUI_CHROME} rather than through a binary name on PATH. A payload that
# carried the pin with any other command would assert a browser this image did
# not bake.
UI_IMAGE="ui"
UI_SMOKE_REF="ui:smoke"
UI_CLASS_TABLE="PIN_CLASSES_UI"

# The 1 pin the ui table flips to `asserted`, written as the COMPARATOR ROW it
# has to arrive as, for the reason HARDWARE_ASSERTED_ROWS gives: a bare
# `assert_contains "$RUN_PAYLOAD" "chrome"` would pass on a payload built from
# another table, and the tool NAME is not the contract here at all.
#
# The command is `sh -c "..."` and the ${DENSUI_CHROME} inside it is UNEXPANDED
# on purpose. The row travels to the guest as text and the expansion happens
# THERE, inside the image, which is the whole point: the probe reads the entry
# point the image baked, and a row that named /usr/bin/google-chrome-stable
# directly would keep passing on an image whose DENSUI_CHROME points somewhere
# else — the one variable every gate of the consumer resolves through.
#
# The ${} must NOT expand here, for that reason, and the same disable as the
# GitHub-expression literal in _ctl/tests/images-manifest.test.sh says so.
# shellcheck disable=SC2016
UI_ASSERTED_ROWS=(
  'CHROME_MAJOR_VERSION|sh -c "${DENSUI_CHROME} --version"'
)

# The budget images.yaml declares for it, in the decimal bytes
# image_size_budget_bytes computes. It moved twice: 6.3 to 6.5 BEFORE this image
# was ever built, which is what a provisional number is for, and 6.5 to 6.33 on
# the first build ever measured in the unit the budget is written in —
# 6,027,251,712 unpacked bytes in rehearsal run 32202500436, x 1.05.
#
# The estimate it replaces was good: 6.32 from the dependency-closure reasoning
# lands 0.005 GB from the truth, while 6.47 from converting a compressed delta
# at one layer's ratio is 7.3% high. The full account with its measurements is
# beside the key in images.yaml; read it before moving this literal.
UI_SIZE_BUDGET="6330000000"

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

# asserted_pins <image> — the pins .ci/smoke.sh says it compares for that image.
#
# Read from the same SMOKE_LIST_PINS seam version-coverage.test.sh checks. The
# 2 files then cannot disagree: 1 says every pin carries a class, this one says
# every pin classified `asserted` really reaches the guest.
# stderr is kept and not sent to /dev/null: an error nobody reads is how a
# listing that failed becomes an empty list that looks like an answer. The awk
# filter accepts only `<NAME>|asserted` lines, so the log noise around the
# records cannot be read as data, and an empty result is reported below.
#
# The image is an ARGUMENT and not the file-level IMAGE it once read. A reader
# fixed to 1 image answers for 1 arm of the driver's case, and the rule that
# consumes it would then report the same image twice while naming 2.
function asserted_pins() {
  local image="$1"
  local text status=0
  text="$(env PATH="${STUB_BIN}:${PATH}" SMOKE_LIST_PINS=1 \
    bash "$SMOKE" "$image" < /dev/null 2>&1)" || status=$?
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

# named_check_groups <payload> — the SMOKE_CHECKS assignment the driver wrote
# into the payload, or the empty string when it wrote none.
#
# A CHECK THAT COULD NOT FAIL IS WHY THIS EXISTS. The rule below asked whether
# the payload NAMES the image's own group, and it asked it of the whole payload —
# which IS .ci/image-checks.sh, and that file spells every group name itself, in
# the `case` arm that dispatches it. So `content-hardware` was found in the
# guest's own source whatever the driver decided, and the check passed on a
# payload built for another image entirely. Measured 2026-08-18 by deleting
# `content-ui` from the ui entry of images.yaml: the driver wrote
# `SMOKE_CHECKS=content-cloud\ go-gate\ dockerfile-lint\ compose`, the group was
# never dispatched, and the check stayed GREEN.
#
# The assignment line is the only place in the payload where the DRIVER speaks.
# The reader takes the first line that starts with it and nothing else, so the
# 2 later references to ${SMOKE_CHECKS} inside the guest's own code cannot answer
# for it either.
#
# awk and not grep: grep exits 1 when it matches nothing, and this file runs
# under `set -Eeuo pipefail` — a payload with no assignment at all is the defect
# this reader has to REPORT, so it must survive reading one.
function named_check_groups() {
  awk '/^SMOKE_CHECKS=/ { print; exit }' <<< "$1"
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

# docker_run_argv <argv log> — the `docker run` invocations themselves, and no
# other docker call.
#
# THE SECOND CHECK THAT COULD NOT FAIL, and the rule it repairs is "the driver
# smokes the ref it was given". That rule read the WHOLE argv log, and the driver
# reads the same ref twice before it runs anything — `docker image inspect` for
# the platform and `docker history` for the size. So the ref was always in the
# log, whatever container was started. Measured 2026-08-18 by rewriting the last line of
# .ci/smoke.sh to `docker run ... "cloud:latest"`: all 3 ref checks stayed GREEN
# while every smoke in this file asserted about an image nobody built.
#
# A ref that is inspected and not run is exactly the failure the rule names: the
# gate reports an image as smoked and the container it smoked was another one.
function docker_run_argv() {
  awk '/^docker run /' <<< "$1"
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
  "$(docker_run_argv "$RUN_ARGV")" "$SMOKE_REF" \
  "the CI job builds a local ref with push:false + load:true and smokes THAT ref" \
  "a run against another ref would assert about an image nobody built here" \
  "the docker run line is what is read here; the size and platform gates inspect the ref too"

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
pins="$(asserted_pins "$IMAGE")"
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
# The stub answers `docker history` with STUB_IMAGE_SIZE, so no image of any
# size is ever built.
#
# THE 3 PAIRS BELOW ARE THE COMPARISON AND NOT THE BASIS, and each one stayed
# correctly green while the gate compared the wrong number entirely. What the
# driver ASKS THE DAEMON FOR is held in _ctl/tests/size-gate.test.sh (ledger
# #119); a stub that answers one number to every question cannot express that
# difference, which is why the file is a second one and not 3 more cases here.
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

# ===========================================================================
# 7. THE SAME CONTRACT, FOR THE SECOND IMAGE SHAPE
# ===========================================================================
# See the note beside HARDWARE_IMAGE above for why 1 image was not enough. This
# section asks the rules that are IMAGE-SPECIFIC — which ref, which table,
# which tools, which budget — and does not repeat the ones that are properties
# of the driver itself and already answered above.
run_smoke "$SMOKE" "$HARDWARE_IMAGE" "$HARDWARE_SMOKE_REF"

assert_equal "the_hardware_smoke_starts_exactly_one_container" \
  "1" "$(docker_run_lines "$RUN_ARGV")" \
  "docker was called with:" "${RUN_ARGV:-<no docker invocation>}" \
  "output was:" "$RUN_OUTPUT"
assert_contains "the_hardware_smoke_runs_the_ref_it_was_given" \
  "$(docker_run_argv "$RUN_ARGV")" "$HARDWARE_SMOKE_REF" \
  "the CI job builds a local ref with push:false + load:true and smokes THAT ref" \
  "a run against another ref would assert about an image nobody built here" \
  "the docker run line is what is read here; the size and platform gates inspect the ref too"

# The marker's DRIVER half. The guest holds GOPHERSYS_DEVCONTAINER against
# SMOKE_IMAGE — guest-checks.test.sh drives that comparison from both sides —
# and this is the only place that can say the driver SENDS the name at all. It
# travels in the payload rather than the argv, like every other table here, and
# an unexported one is an empty one on the far side: the guest then takes its
# "no image was named" branch and the whole marker check silently does nothing.
assert_contains "the_payload_names_the_image_for_the_marker" \
  "$RUN_PAYLOAD" "SMOKE_IMAGE=${HARDWARE_IMAGE}" \
  "the guest compares GOPHERSYS_DEVCONTAINER against this name, and a payload that omits it" \
  "turns the marker check off for every image at once"
assert_contains "the_payload_exports_the_image_for_the_marker" \
  "$RUN_PAYLOAD" "export SMOKE_IMAGE" \
  "the guest reads SMOKE_IMAGE out of its environment, and an unexported name is an absent one there"

# The functional group that only this image runs. It reaches the guest the same
# way the tables do, and a group that never arrives is a content check that
# silently did not happen.
#
# It is asked of the SMOKE_CHECKS assignment and not of the payload, for the
# reason named_check_groups gives: the guest names every group in its own case
# arm, so the whole-payload form was a check that could not fail.
assert_contains "the_hardware_payload_names_its_own_check_group" \
  "$(named_check_groups "$RUN_PAYLOAD")" "content-hardware" \
  "images.yaml declares this group for this image, and .ci/image-checks.sh runs the KiCad" \
  "library floors from it — a payload without it smokes an ECAD image and checks no ECAD tool" \
  "the driver's own line is what is read here; the guest's case arm names the group too"

# Section 3, asked of the other table. The KiCad rows are `asserted` here and
# `not-in-this-image` in the 2 tables over the same home, so a driver that chose
# the wrong table produces a payload that is well-formed and asserts cloud.
hardware_pins="$(asserted_pins "$HARDWARE_IMAGE")"
hardware_pin_total=0
hardware_missing_rows=""
while IFS= read -r pin; do
  [[ -z "$pin" ]] && continue
  hardware_pin_total=$((hardware_pin_total + 1))
  if ! grep -qE "^${pin}\|" <<< "$RUN_PAYLOAD"; then
    hardware_missing_rows="${hardware_missing_rows:+${hardware_missing_rows}
}${pin}"
  fi
done <<< "$hardware_pins"

if [[ "$hardware_pin_total" -eq 0 ]]; then
  fail_check "every_asserted_pin_reaches_the_guest_for_hardware" \
    "SMOKE_LIST_PINS=1 named no pin as asserted for ${HARDWARE_IMAGE}, so this rule compared nothing" \
    "a rule with no input reports a clean result it never read"
elif [[ -n "$hardware_missing_rows" ]]; then
  fail_check "every_asserted_pin_reaches_the_guest_for_hardware" \
    "these pins are classified asserted and carry no comparator row in the payload:" \
    "$hardware_missing_rows" \
    "a row is <PIN>|<expected version>|<command>, which is what .ci/image-checks.sh reads" \
    "a classification that never reaches the guest is a claim of coverage, not coverage"
else
  pass_check "every_asserted_pin_reaches_the_guest_for_hardware"
fi

# Section 3b, asked of the other table.
hardware_absent_rows="$(absence_rows "$HARDWARE_CLASS_TABLE")"
hardware_absent_total=0
hardware_missing_absent=""
while IFS= read -r absent_row; do
  [[ -z "$absent_row" ]] && continue
  hardware_absent_total=$((hardware_absent_total + 1))
  if ! grep -qxF -- "$absent_row" <<< "$RUN_PAYLOAD"; then
    hardware_missing_absent="${hardware_missing_absent:+${hardware_missing_absent}
}${absent_row}"
  fi
done <<< "$hardware_absent_rows"

if [[ "$hardware_absent_total" -eq 0 ]]; then
  fail_check "every_absence_probe_reaches_the_guest_for_hardware" \
    "the ${HARDWARE_IMAGE} class table names no absence probe at all, so this rule compared nothing" \
    "the driver refuses such an image, and a rule with no input reports a clean result it never read"
elif [[ -n "$hardware_missing_absent" ]]; then
  fail_check "every_absence_probe_reaches_the_guest_for_hardware" \
    "these absence probes are named in the class table and carry no ABSENT_TABLE row in the payload:" \
    "$hardware_missing_absent" \
    "a row is <PIN>|<binary>, which is what run_absence_checks in .ci/image-checks.sh reads" \
    "a probe that never reaches the guest is the unchecked claim not-in-this-image used to be"
else
  pass_check "every_absence_probe_reaches_the_guest_for_hardware"
fi

# Section 4, asked of the tools this image exists for. The floors in
# .ci/image-checks.sh are what catch an EMPTY /usr/share/kicad; this is what
# catches a payload that never asks about KiCad at all.
#
# These 5 are the literal half of this section, and they are what stands when
# the 2 rules above agree with each other: `asserted_pins` and the payload both
# come out of the driver, so a driver reading the wrong class table moves both
# sides at once and neither can report it. A row written here by hand cannot
# move with it.
# The rows the payload really carries, for the evidence of a failure below. It
# is read once, with its own status, because this file never writes `|| true`
# and a `grep` that matches nothing exits 1 under pipefail.
payload_rows_status=0
payload_rows=""
payload_rows="$(grep -E '^[A-Z][A-Z0-9_]*\|' <<< "$RUN_PAYLOAD")" || payload_rows_status=$?
if [[ "$payload_rows_status" -ne 0 ]]; then
  payload_rows="<the payload carries no <NAME>| row at all>"
fi

for asserted_row in "${HARDWARE_ASSERTED_ROWS[@]}"; do
  asserted_pin="${asserted_row%%|*}"
  asserted_command="${asserted_row#*|}"
  # The check name carries the pin, so a reader finds the missing one in the
  # list of names and not only in the evidence.
  check_name="the_hardware_payload_asserts_${asserted_pin}"
  # $3 and not $2: field 2 is the expected VERSION, which this file does not
  # state. A row is only a comparator row if it has a command in field 3 — an
  # absence row has 2 fields and would leave $3 empty.
  matched_row=""
  matched_row="$(awk -F'|' -v pin="$asserted_pin" -v want="$asserted_command" \
    '$1 == pin && $3 == want { print; exit }' <<< "$RUN_PAYLOAD")"
  if [[ -n "$matched_row" ]]; then
    pass_check "$check_name"
  else
    fail_check "$check_name" \
      "no row of the payload has field 1 = ${asserted_pin} and field 3 = ${asserted_command}" \
      "this pin is asserted in the hardware class table and in no other, so a payload without" \
      "its 3-field row was built from another image's table — the tool NAME is not enough here," \
      "because the cloud table carries the same binary inside a 2-field absence row" \
      "the payload's own pin rows were:" \
      "$payload_rows"
  fi
done

# Section 6, at the other budget. The 2 cases are 1 byte apart for the reason
# the cloud pair gives, and the number is this image's own: a size gate that
# read the cloud budget for every image would pass an 11 GB image at 5.75 GB
# only by refusing it, and would pass a 20 GB one by reading nothing at all.
run_smoke "$SMOKE" "$HARDWARE_IMAGE" "$HARDWARE_SMOKE_REF" "STUB_IMAGE_SIZE=$((HARDWARE_SIZE_BUDGET + 1))"
assert_refused_without_running "a_hardware_image_one_byte_over_its_budget_fails_and_starts_no_container" \
  "$HARDWARE_SIZE_BUDGET" \
  "the image measured $((HARDWARE_SIZE_BUDGET + 1)) unpacked bytes, which is 1 byte over the 10.52 GB budget" \
  "that budget was reset in this change to the first measured size + 5%, so it sits 5% above a real" \
  "image rather than above an estimate — a gate that does not bite cannot report the growth it exists to catch"

run_smoke "$SMOKE" "$HARDWARE_IMAGE" "$HARDWARE_SMOKE_REF" "STUB_IMAGE_SIZE=${HARDWARE_SIZE_BUDGET}"
if [[ "$RUN_STATUS" -ne 0 ]]; then
  fail_check "a_hardware_image_exactly_at_its_budget_passes_the_gate_and_is_smoked" \
    "want: exit 0 — ${HARDWARE_SIZE_BUDGET} bytes is the budget, and the budget is inclusive" \
    "got:  ${RUN_STATUS}" \
    "a gate that refuses its own limit hands back a budget nobody can meet" \
    "output was:" "$RUN_OUTPUT"
elif [[ "$(docker_run_lines "$RUN_ARGV")" -ne 1 ]]; then
  fail_check "a_hardware_image_exactly_at_its_budget_passes_the_gate_and_is_smoked" \
    "the run exited 0 and started $(docker_run_lines "$RUN_ARGV") containers, want exactly 1" \
    "an exit 0 with no container is a size gate that ate the whole smoke" \
    "docker was called with:" "${RUN_ARGV:-<no docker invocation>}"
else
  pass_check "a_hardware_image_exactly_at_its_budget_passes_the_gate_and_is_smoked"
fi

# ===========================================================================
# 8. THE SAME CONTRACT, FOR THE SECOND IMAGE OF THAT SHAPE
# ===========================================================================
# See the note beside UI_IMAGE above. Section 7 asks the image-specific rules of
# `hardware`; this asks them of `ui`, and the point of asking twice is that the
# 2 images differ in every answer — a different table, a different group, a
# different budget, a different asserted pin — while taking the same arm of the
# driver. An arm that answered `hardware` for both would pass section 7 alone.
run_smoke "$SMOKE" "$UI_IMAGE" "$UI_SMOKE_REF"

assert_equal "the_ui_smoke_starts_exactly_one_container" \
  "1" "$(docker_run_lines "$RUN_ARGV")" \
  "docker was called with:" "${RUN_ARGV:-<no docker invocation>}" \
  "output was:" "$RUN_OUTPUT"
assert_contains "the_ui_smoke_runs_the_ref_it_was_given" \
  "$(docker_run_argv "$RUN_ARGV")" "$UI_SMOKE_REF" \
  "the CI job builds a local ref with push:false + load:true and smokes THAT ref" \
  "a run against another ref would assert about an image nobody built here" \
  "the docker run line is what is read here; the size and platform gates inspect the ref too"

# The functional group that only this image runs. Every branch of it is driven by
# functional-groups.test.sh — the browser, the font, PYTHONUNBUFFERED and the
# root-vs-dev pair — and not one of them happens if the group name never reaches
# the guest.
assert_contains "the_ui_payload_names_its_own_check_group" \
  "$(named_check_groups "$RUN_PAYLOAD")" "content-ui" \
  "images.yaml declares this group for this image, and it is the only check that can see" \
  "the /usr/local/bin exposure at all — no version comparison resolves a tool twice" \
  "the driver's own line is what is read here; the guest's case arm names the group too"

# Section 3, asked of the 4th table.
ui_pins="$(asserted_pins "$UI_IMAGE")"
ui_pin_total=0
ui_missing_rows=""
while IFS= read -r pin; do
  [[ -z "$pin" ]] && continue
  ui_pin_total=$((ui_pin_total + 1))
  if ! grep -qE "^${pin}\|" <<< "$RUN_PAYLOAD"; then
    ui_missing_rows="${ui_missing_rows:+${ui_missing_rows}
}${pin}"
  fi
done <<< "$ui_pins"

if [[ "$ui_pin_total" -eq 0 ]]; then
  fail_check "every_asserted_pin_reaches_the_guest_for_ui" \
    "SMOKE_LIST_PINS=1 named no pin as asserted for ${UI_IMAGE}, so this rule compared nothing" \
    "a rule with no input reports a clean result it never read"
elif [[ -n "$ui_missing_rows" ]]; then
  fail_check "every_asserted_pin_reaches_the_guest_for_ui" \
    "these pins are classified asserted and carry no comparator row in the payload:" \
    "$ui_missing_rows" \
    "a row is <PIN>|<expected version>|<command>, which is what .ci/image-checks.sh reads" \
    "a classification that never reaches the guest is a claim of coverage, not coverage"
else
  pass_check "every_asserted_pin_reaches_the_guest_for_ui"
fi

# Section 3b, asked of the 4th table.
ui_absent_rows="$(absence_rows "$UI_CLASS_TABLE")"
ui_absent_total=0
ui_missing_absent=""
while IFS= read -r absent_row; do
  [[ -z "$absent_row" ]] && continue
  ui_absent_total=$((ui_absent_total + 1))
  if ! grep -qxF -- "$absent_row" <<< "$RUN_PAYLOAD"; then
    ui_missing_absent="${ui_missing_absent:+${ui_missing_absent}
}${absent_row}"
  fi
done <<< "$ui_absent_rows"

if [[ "$ui_absent_total" -eq 0 ]]; then
  fail_check "every_absence_probe_reaches_the_guest_for_ui" \
    "the ${UI_IMAGE} class table names no absence probe at all, so this rule compared nothing" \
    "the driver refuses such an image, and a rule with no input reports a clean result it never read"
elif [[ -n "$ui_missing_absent" ]]; then
  fail_check "every_absence_probe_reaches_the_guest_for_ui" \
    "these absence probes are named in the class table and carry no ABSENT_TABLE row in the payload:" \
    "$ui_missing_absent" \
    "a row is <PIN>|<binary>, which is what run_absence_checks in .ci/image-checks.sh reads" \
    "a probe that never reaches the guest is the unchecked claim not-in-this-image used to be"
else
  pass_check "every_absence_probe_reaches_the_guest_for_ui"
fi

# Section 4, asked of the 1 pin this image exists for. The row is compared by
# FIELDS for the reason HARDWARE_ASSERTED_ROWS states — `|` is alternation in an
# ERE, and a regular expression here passed on a payload carrying none of the
# rows it claimed to check.
ui_payload_rows_status=0
ui_payload_rows=""
ui_payload_rows="$(grep -E '^[A-Z][A-Z0-9_]*\|' <<< "$RUN_PAYLOAD")" || ui_payload_rows_status=$?
if [[ "$ui_payload_rows_status" -ne 0 ]]; then
  ui_payload_rows="<the payload carries no <NAME>| row at all>"
fi

for asserted_row in "${UI_ASSERTED_ROWS[@]}"; do
  asserted_pin="${asserted_row%%|*}"
  asserted_command="${asserted_row#*|}"
  check_name="the_ui_payload_asserts_${asserted_pin}"
  # $3 and not $2: field 2 is the expected VERSION, which this file does not
  # state, and field 4 is the `prefix` extractor this pin needs because the row
  # holds a MAJOR line while the browser reports 151.0.7922.137.
  matched_row=""
  matched_row="$(awk -F'|' -v pin="$asserted_pin" -v want="$asserted_command" \
    '$1 == pin && $3 == want { print; exit }' <<< "$RUN_PAYLOAD")"
  if [[ -n "$matched_row" ]]; then
    pass_check "$check_name"
  else
    fail_check "$check_name" \
      "no row of the payload has field 1 = ${asserted_pin} and field 3 = ${asserted_command}" \
      "this pin is asserted in the ui class table and in no other, and its probe reads the" \
      "browser through the baked \${DENSUI_CHROME} — a row naming the binary directly would" \
      "keep passing on an image whose entry point points somewhere else" \
      "the payload's own pin rows were:" \
      "$ui_payload_rows"
  fi
done

# Section 6, at the third budget. 1 byte apart for the reason the cloud pair
# gives.
#
# WHAT THE PAIR PROVES, MEASURED RATHER THAN ARGUED. An earlier version of this
# note said "this image's budget is the smallest of the 3 declared, so a gate
# reading any other image's number would let an overrun through". Both halves
# were wrong: cloud's 5.75 GB is smaller than this image's 6.5, and the ordering
# is not what makes a wrong budget red anyway. The 2 cases were run against a
# driver pointed at each of the other 2 budgets on 2026-08-18:
#
#   the driver reads cloud's 5.75 GB   BOTH cases red — the refusal names
#                                      5750000000 and not this image's number,
#                                      and the at-budget case is refused its
#                                      own limit
#   the driver reads hardware's 11 GB  the over-budget case red — budget+1 was
#                                      accepted and the container started
#
# So the pair bites in BOTH directions, and what makes the smaller-budget
# direction bite is not arithmetic: `assert_refused_without_running` takes this
# image's own number as its needle, so a refusal that names another image's
# budget is a failure even though a refusal happened. A check that only asked
# for a non-zero status would have passed that case.
run_smoke "$SMOKE" "$UI_IMAGE" "$UI_SMOKE_REF" "STUB_IMAGE_SIZE=$((UI_SIZE_BUDGET + 1))"
assert_refused_without_running "a_ui_image_one_byte_over_its_budget_fails_and_starts_no_container" \
  "$UI_SIZE_BUDGET" \
  "the image measured $((UI_SIZE_BUDGET + 1)) unpacked bytes, which is 1 byte over the 6.33 GB budget" \
  "that budget was reset in this change to the first measured size + 5%, so it sits 5% above a real" \
  "image rather than above an estimate — a gate that does not bite cannot report the growth it exists to catch"

run_smoke "$SMOKE" "$UI_IMAGE" "$UI_SMOKE_REF" "STUB_IMAGE_SIZE=${UI_SIZE_BUDGET}"
if [[ "$RUN_STATUS" -ne 0 ]]; then
  fail_check "a_ui_image_exactly_at_its_budget_passes_the_gate_and_is_smoked" \
    "want: exit 0 — ${UI_SIZE_BUDGET} bytes is the budget, and the budget is inclusive" \
    "got:  ${RUN_STATUS}" \
    "a gate that refuses its own limit hands back a budget nobody can meet" \
    "output was:" "$RUN_OUTPUT"
elif [[ "$(docker_run_lines "$RUN_ARGV")" -ne 1 ]]; then
  fail_check "a_ui_image_exactly_at_its_budget_passes_the_gate_and_is_smoked" \
    "the run exited 0 and started $(docker_run_lines "$RUN_ARGV") containers, want exactly 1" \
    "an exit 0 with no container is a size gate that ate the whole smoke" \
    "docker was called with:" "${RUN_ARGV:-<no docker invocation>}"
else
  pass_check "a_ui_image_exactly_at_its_budget_passes_the_gate_and_is_smoked"
fi

test_summary "$TEST_NAME"
