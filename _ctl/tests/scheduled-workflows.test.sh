#!/usr/bin/env bash
#
# _ctl/tests/scheduled-workflows.test.sh — the nightly security scan, and the
# base-OS pin it watches.
#
# Static means static: this file reads files. It starts no container, it calls
# no daemon and it reaches no network, so it runs identically on a laptop and on
# a CI runner — and, unlike the nightly itself, it runs in the PULL REQUEST
# gate. There is no image to build to check the FLAGS in a YAML file, and a test
# that built one would be checking something else. The 1 clause that needs a
# docker client drives the stub in _ctl/tests/stubs/docker.
#
# ============================================================================
# THE DEFECT THIS FILE EXISTS FOR
# ============================================================================
#
# A scheduled run has no author watching it. Nobody opened a pull request at
# 03:00 and nobody refreshes the Actions tab afterwards, so a red nightly is a
# red that reaches no human. The same is true of every clause below: a scan
# whose gate is `--exit-code 0` reports and passes, a waiver with no expiry
# never comes back for review, and a digest pin that nothing watches freezes the
# base OS at a snapshot that looks current forever.
#
# Every rule here is therefore about the property that makes the mechanism
# LOUD, and never about the presence of the mechanism.
#
# ============================================================================
# THE 5 RULES
# ============================================================================
#
#   1. scheduled_workflow_declares_a_failure_notification
#      Every workflow that runs `on: schedule` calls .ci/notify-failure.sh from
#      a step guarded by `if: failure()`, and declares `issues: write`. This is
#      a RATCHET: it is keyed on the trigger, so a scheduled workflow added
#      tomorrow is covered the day it is added, with no edit here.
#
#   2. the_trivy_gate_cannot_pass_an_unpatched_critical
#      The scan names CRITICAL, fails the step with `--exit-code 1`, does NOT
#      set --ignore-unfixed, and names the waiver file. An unfixed CRITICAL has
#      to become a waiver with an expiry — a visible line in a diff — and never
#      a silent skip.
#
#   3. every_waiver_carries_an_expiry_and_a_reason
#      Each entry of .ci/trivyignore.yaml carries an id, a `statement` and an
#      `expired_at`. A waiver with no expiry is a permanent exception written
#      as a temporary one.
#
#   4. both_dockerfiles_build_from_the_pinned_digest
#      base/Dockerfile and cloud/Dockerfile FROM the digest in UBUNTU_BASE_REF,
#      and the 2 pin homes hold the same sha256. A floating ubuntu:24.04 means
#      2 builds of 1 commit can produce 2 different images, and this repository
#      rests on the opposite property: the commit decides the image.
#
#   5. base_image_digest_reports_a_move
#      The currency reader answers what the REGISTRY holds, and the check exits
#      non-zero when that differs from the pin. A pin nothing watches is the
#      cost of rule 4, so the 2 halves ship together.
#
# ============================================================================
# WHY THE FIELD NAMES IN RULE 3 ARE THESE FIELD NAMES
# ============================================================================
#
# `id`, `statement` and `expired_at` are trivy's own field names for a YAML
# ignore file, read from the upstream documentation on 2026-08-16
# (https://trivy.dev/latest/docs/configuration/filtering/, "By Finding IDs").
# `id` is the only required field; `statement` is the reason and `expired_at`
# is the expiry date in yyyy-mm-dd. Trivy enforces the expiry itself — an entry
# past its date stops ignoring — so no clause here compares a date to today,
# and the pull request gate carries no time bomb.
#
# The same page states that the YAML ignore file is EXPERIMENTAL and is loaded
# only when its path is given with --ignorefile. That is why rule 2 checks that
# the path is named: without it every waiver in the file is dead text, and the
# waiver rule below would be checking a file that nothing reads.
#
# ============================================================================
# NO YAML LIBRARY
# ============================================================================
#
# The readers below are awk and bash, for the reason publish-order.test.sh
# gives: this repository ships no YAML parser on the path that runs
# `ctl.sh test`, and a hermetic test that needs a tool the gate does not
# install is a test that skips. Every assumption a reader makes is checked — a
# fixture that must parse into a known shape, and a liveness clause on the real
# files — so a shape it cannot read fails loudly instead of reporting a clean
# file it never read.
#
# Usage: bash _ctl/tests/scheduled-workflows.test.sh
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

TEST_NAME="scheduled-workflows.test.sh"

# The 2 directories that hold a workflow. The provider directory is the source
# of truth and .github/workflows/ holds a copy of each file
# (.ci/providers/README.md), and platform-policy.test.sh compares the 2 with
# `cmp`. Both are read here anyway, for the reason publish-order.test.sh reads
# both: a test that only holds while another test file is healthy is a test with
# an undeclared dependency, and this pair has already drifted twice.
WORKFLOW_DIRECTORIES=(
  ".github/workflows"
  ".ci/providers/github"
)

# The scheduled workflow this feature adds, named as a literal. The rules above
# are keyed on the trigger, so they cover a future scheduled workflow with no
# edit here — but a ratchet over an EMPTY set is green on every repository,
# including one where the nightly was deleted. This name is what makes the set
# non-empty, and it is the 1 line to edit when the nightly is renamed.
NIGHTLY_WORKFLOW="security-nightly.yml"

# The notifier both scheduled workflows call. 1 home for the notification, so a
# second scheduled workflow inherits it instead of inventing a second shape.
NOTIFIER=".ci/notify-failure.sh"

# The waiver file, and the 4 sections trivy allows in it.
WAIVER_FILE=".ci/trivyignore.yaml"

# The counter-stimulus. A detector that has only ever seen correct input has
# never been observed to fire.
WORKFLOW_FIXTURES="$TESTS_DIR/fixtures/scheduled-workflows"

# ---------------------------------------------------------------------------
# The readers.
#
# Every one of them drops comment lines FIRST. A comment is prose, not an
# instruction — the same rule dockerfile-args.test.sh and publish-order.test.sh
# apply — and 2 of the fixtures carry the exact token their detector keys on
# inside a comment, so this is watched rather than assumed.
# ---------------------------------------------------------------------------

# uncommented <file> — the file with every whole-line comment removed.
function uncommented() {
  sed -e '/^[[:space:]]*#/d' "$1"
}

# declares_a_schedule <file> — 1 when the workflow runs on a schedule, else 0.
#
# The key, and not the string: `schedule:` at an indent inside `on:`. A trailing
# `# comment` on the key line is left alone, because the key is what matters.
function declares_a_schedule() {
  if uncommented "$1" | grep -qE '^[[:space:]]+schedule:[[:space:]]*$'; then
    printf '1'
  else
    printf '0'
  fi
}

# declares_a_cron <file> — 1 when the schedule carries at least 1 cron entry.
# A `schedule:` key with no cron under it parses and never fires.
function declares_a_cron() {
  if uncommented "$1" | grep -qE '^[[:space:]]+-[[:space:]]+cron:'; then
    printf '1'
  else
    printf '0'
  fi
}

# declares_issues_write <file> — 1 when a permissions block grants `issues:
# write`. Which block holds it is not constrained here: a job-level grant is
# narrower than a workflow-level one and both are correct.
function declares_issues_write() {
  if uncommented "$1" | grep -qE '^[[:space:]]+issues:[[:space:]]+write[[:space:]]*$'; then
    printf '1'
  else
    printf '0'
  fi
}

# step_slice <file> <line number> — the step block that holds that line.
#
# A step starts at a `- ` dash and ends at the line before the next dash at the
# SAME indent, or at the next line indented less than the dash. That is enough
# structure to answer "what `if:` guards this step", and it needs no state
# machine over the whole file: the walk starts at the line that matched and goes
# outward, so a shape it cannot read produces a short slice and a loud failure
# rather than a silent pass.
function step_slice() {
  local file="$1" line_number="$2"
  local lines=() text stripped indent
  local start=0 dash_indent=0 index

  while IFS= read -r text || [[ -n "$text" ]]; do
    lines+=("$text")
  done < "$file"

  # Backward to the dash that opens the step.
  for ((index = line_number; index >= 1; index--)); do
    text="${lines[index - 1]}"
    stripped="${text#"${text%%[![:space:]]*}"}"
    case "$stripped" in '#'*) continue ;; esac
    if [[ "$stripped" == "- "* ]]; then
      start="$index"
      dash_indent=$(( ${#text} - ${#stripped} ))
      break
    fi
  done
  if [[ "$start" -eq 0 ]]; then
    return 0
  fi

  printf '%s\n' "${lines[start - 1]}"
  # Forward to the next boundary at that indent or shallower.
  for ((index = start + 1; index <= ${#lines[@]}; index++)); do
    text="${lines[index - 1]}"
    stripped="${text#"${text%%[![:space:]]*}"}"
    [[ -z "$stripped" ]] && continue
    case "$stripped" in '#'*) continue ;; esac
    indent=$(( ${#text} - ${#stripped} ))
    if [[ "$indent" -le "$dash_indent" ]]; then
      break
    fi
    printf '%s\n' "$text"
  done
}

# notifier_steps <file> — `line:guarded` for every step that calls the notifier,
# where guarded is 1 when the step carries an `if:` naming failure(). Silent
# when the file never calls the notifier at all.
#
# `failure()` and not `always()`: a notifier under always() runs on a green run
# too, so the step that files the issue would have to decide for itself whether
# there is anything to file — and a notifier that silently decides "nothing to
# report" is the exact shape this whole file exists to forbid. A SECOND step
# that resolves the issue on a green run is free to carry any condition; the
# rule below asks that AT LEAST 1 call is guarded by failure().
function notifier_steps() {
  local file="$1"
  local hits="" line_number slice guarded
  while IFS=: read -r line_number _; do
    [[ -z "$line_number" ]] && continue
    slice="$(step_slice "$file" "$line_number")"
    guarded=0
    if grep -qE '^[[:space:]]+if:.*failure\(\)' <<< "$slice"; then
      guarded=1
    fi
    hits="${hits:+${hits}
}${line_number}:${guarded}"
  done < <(uncommented_line_numbers "$file" "$NOTIFIER")
  printf '%s' "$hits"
}

# uncommented_line_numbers <file> <fixed needle> — `<line>:` for every
# NON-COMMENT line of the file that holds the needle. Silent when there is none,
# and never a failure: grep exits 1 on no match, and under `set -e` with
# pipefail that would kill the run instead of reporting an absent notifier,
# which is a defect this file has to REPORT.
function uncommented_line_numbers() {
  local file="$1" needle="$2"
  awk -v needle="$needle" '
    /^[[:space:]]*#/ { next }
    index($0, needle) { print NR ":" }
  ' "$file"
}

# guarded_notifier_total <file> — how many notifier calls are guarded by
# failure(). 0 covers both "no call at all" and "a call that never runs".
function guarded_notifier_total() {
  local file="$1" record total=0
  while IFS= read -r record; do
    [[ -z "$record" ]] && continue
    [[ "${record#*:}" == "1" ]] && total=$((total + 1))
  done <<< "$(notifier_steps "$file")"
  printf '%s' "$total"
}

# ---------------------------------------------------------------------------
# The trivy readers.
#
# Each one is a property of the POLICY, spelled in the 2 forms the same policy
# can take: the CLI flag (`--severity CRITICAL`) and the action input
# (`severity: CRITICAL`). Naming both is not the same as agreeing with any
# value — the value is still written here as a literal, and a third spelling
# that means something else does not match.
# ---------------------------------------------------------------------------

# invokes_trivy <file> — 1 when the workflow really runs a scan.
#
# The binary with a subcommand, or the action. Not the bare word: the waiver
# path .ci/trivyignore.yaml holds the string "trivy", so a looser detector reads
# a workflow that merely mentions the waiver file as a workflow that scans, and
# every clause below then passes over a scan that does not exist.
function invokes_trivy() {
  if uncommented "$1" | grep -qE '(aquasecurity/trivy-action|(^|[[:space:]])trivy[[:space:]]+(image|fs|filesystem|repo|repository|rootfs|config|sbom))'; then
    printf '1'
  else
    printf '0'
  fi
}

# gates_critical <file> — 1 when the severity list names CRITICAL.
function gates_critical() {
  if uncommented "$1" | grep -qE "(--severity[[:space:]=]|severity:[[:space:]]*)['\"]?[A-Z,]*CRITICAL"; then
    printf '1'
  else
    printf '0'
  fi
}

# fails_the_step <file> — 1 when a finding makes the step exit non-zero.
#
# `--exit-code 0` is the shape that turns a gate into a report: trivy prints the
# table, the step succeeds, the run is green, and nobody reads the log of a
# scheduled job.
function fails_the_step() {
  if uncommented "$1" | grep -qE "(--exit-code[[:space:]=]|exit-code:[[:space:]]*)['\"]?1"; then
    printf '1'
  else
    printf '0'
  fi
}

# unfixed_skip_lines <file> — `line: text` for every line that turns
# ignore-unfixed ON. Silent when the file leaves it off or sets it to false.
#
# An explicit `ignore-unfixed: false` is CORRECT and must never be reported: it
# states the policy rather than relying on the default, and a detector keyed on
# the mere presence of the token would report the file that says the right thing
# most loudly.
function unfixed_skip_lines() {
  local file="$1"
  awk '
    /^[[:space:]]*#/ { next }
    /ignore-unfixed/ {
      if ($0 ~ /ignore-unfixed[=:][[:space:]]*["'"'"']?false/) { next }
      line = $0
      sub(/^[[:space:]]+/, "", line)
      print NR ": " line
    }
  ' "$file"
}

# names_the_waiver_file <file> — 1 when the scan is told where the waivers are.
#
# The YAML ignore file is EXPERIMENTAL in trivy and is loaded ONLY when its path
# is given (--ignorefile, or the trivyignores input of the action). Without it
# .ci/trivyignore.yaml is a file the scanner never opens, every waiver in it is
# dead text, and the waiver rule further down would be checking a document with
# no effect on anything.
function names_the_waiver_file() {
  if uncommented "$1" | grep -qF -- "$WAIVER_FILE"; then
    printf '1'
  else
    printf '0'
  fi
}

# ---------------------------------------------------------------------------
# The waiver reader.
#
# waiver_entries <file> — 1 record per waiver entry:
#
#   <section>|<line>|<id>|<has statement>|<has expired_at>
#
# An entry opens at a `- ` dash whose indent is the indent of the FIRST dash of
# its section, and it runs to the next such dash or to the next section. The
# nested list under `paths:` sits deeper, so its items are part of the entry and
# never an entry of their own — which is checked, because good.yaml carries one
# and the test asserts that file holds exactly 3 entries.
#
# An id that is absent is reported as <no-id> rather than as an empty field, so
# the failure line reads as a sentence.
# ---------------------------------------------------------------------------
function waiver_entries() {
  awk '
    function flush() {
      if (open) {
        printf "%s|%d|%s|%d|%d\n", section, start, (id == "" ? "<no-id>" : id), has_statement, has_expiry
        open = 0
      }
    }
    /^[[:space:]]*#/  { next }
    /^[[:space:]]*$/  { next }
    /^(vulnerabilities|misconfigurations|secrets|licenses):[[:space:]]*$/ {
      flush()
      section = $0
      sub(/:.*$/, "", section)
      dash_indent = -1
      next
    }
    {
      match($0, /^[[:space:]]*/)
      indent = RLENGTH
      body = substr($0, indent + 1)
      if (substr(body, 1, 2) == "- ") {
        if (dash_indent == -1) { dash_indent = indent }
        if (indent == dash_indent) {
          flush()
          open = 1; start = NR; id = ""; has_statement = 0; has_expiry = 0
          body = substr(body, 3)
        }
      }
      if (open) {
        if (body ~ /^id:/) {
          id = substr(body, 4)
          sub(/[[:space:]]*#.*$/, "", id)
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", id)
        } else if (body ~ /^statement:/)  { has_statement = 1 }
        else if   (body ~ /^expired_at:/) { has_expiry = 1 }
      }
    }
    END { flush() }
  ' "$1"
}

# waiver_defects <file> — 1 line per incomplete entry, naming the line, the
# entry and every field it is missing. Silent when every entry is complete, and
# silent on a file with no entries at all: an empty waiver file is the correct
# state, and the rule is about what a waiver MUST carry, not about having one.
function waiver_defects() {
  local file="$1"
  local record section line id has_statement has_expiry missing out=""
  while IFS='|' read -r section line id has_statement has_expiry; do
    [[ -z "$section" ]] && continue
    missing=""
    [[ "$id" == "<no-id>" ]]     && missing="${missing:+${missing}, }id"
    [[ "$has_statement" == "0" ]] && missing="${missing:+${missing}, }statement (the reason)"
    [[ "$has_expiry" == "0" ]]    && missing="${missing:+${missing}, }expired_at (the expiry)"
    [[ -z "$missing" ]] && continue
    out="${out:+${out}
}line ${line}, ${section} entry ${id}: no ${missing}"
  done <<< "$(waiver_entries "$file")"
  printf '%s' "$out"
}

# waiver_entry_total <file> — how many entries the reader found.
function waiver_entry_total() {
  local record total=0
  while IFS= read -r record; do
    [[ -z "$record" ]] && continue
    total=$((total + 1))
  done <<< "$(waiver_entries "$1")"
  printf '%s' "$total"
}

# declares_a_waiver_section <file> — 1 when the file declares at least 1 of the
# 4 sections trivy reads. A waiver file with no section at all is not "empty",
# it is a file trivy cannot use.
function declares_a_waiver_section() {
  if grep -qE '^(vulnerabilities|misconfigurations|secrets|licenses):[[:space:]]*$' "$1"; then
    printf '1'
  else
    printf '0'
  fi
}

# ---------------------------------------------------------------------------
# The base-OS pin readers.
# ---------------------------------------------------------------------------

# digest_is_well_formed <value> — 1 when the value is a full sha256 digest.
#
# 64 hex characters, lower case, and the whole string. A truncated digest is the
# failure worth naming: it looks right in a diff, and it fails at `docker build`
# in a job that runs after the merge.
function digest_is_well_formed() {
  if [[ "$1" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    printf '1'
  else
    printf '0'
  fi
}

# from_lines <file> — `line: text` for every non-comment FROM.
function from_lines() {
  awk '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*FROM[[:space:]]/ {
      line = $0
      sub(/^[[:space:]]+/, "", line)
      print NR ": " line
    }
  ' "$1"
}

# floating_from_lines <file> — `line: text` for every FROM that names an ubuntu
# TAG and no digest. The tag is what upstream moves under us: 2 builds of 1
# commit then produce 2 different images, and this repository rests on the
# opposite property — the commit decides the image.
function floating_from_lines() {
  awk '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*FROM[[:space:]]/ {
      if ($0 ~ /ubuntu:/ && $0 !~ /@/) {
        line = $0
        sub(/^[[:space:]]+/, "", line)
        print NR ": " line
      }
    }
  ' "$1"
}

# pin_reference_line <file> <name> — the line of the first non-comment FROM that
# reads ${NAME}, 0 when no FROM reads it.
function pin_reference_line() {
  awk -v name="$2" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*FROM[[:space:]]/ {
      if (index($0, "${" name "}") > 0) { print NR; found = 1; exit }
    }
    END { if (!found) print 0 }
  ' "$1"
}

# arg_declaration_line <file> <name> — the line of the first `ARG NAME`, 0 when
# the file declares none. An ARG that a FROM interpolates has to be declared
# ABOVE that FROM: below it, the expansion is the empty string, the FROM becomes
# `ubuntu:24.04@`, and the build dies — after the merge, in the publish job.
function arg_declaration_line() {
  awk -v name="$2" '
    /^[[:space:]]*ARG[[:space:]]+/ {
      split($2, parts, "=")
      if (parts[1] == name) { print NR; found = 1; exit }
    }
    END { if (!found) print 0 }
  ' "$1"
}

# env_pin_value <file> <name> — the value of a `NAME=value` row, comment
# stripped. Empty when the file holds no such row.
function env_pin_value() {
  awk -v name="$2" '
    index($0, name "=") == 1 {
      value = substr($0, length(name) + 2)
      sub(/[[:space:]]*#.*$/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      print value
      exit
    }
  ' "$1"
}

# dockerfile_arg_value <file> <name> — the DEFAULT value of `ARG NAME=value`.
# Empty when the ARG is absent or value-less. Value-less is correct in
# cloud/Dockerfile, where every pin arrives from versions.env as a generated
# --build-arg, and it is a defect in base/Dockerfile, which is a pin home.
function dockerfile_arg_value() {
  awk -v name="$2" '
    /^[[:space:]]*ARG[[:space:]]+/ {
      split($2, parts, "=")
      if (parts[1] != name) { next }
      if (index($2, "=") == 0) { print ""; exit }
      value = substr($0, index($0, "=") + 1)
      sub(/[[:space:]]*#.*$/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      print value
      exit
    }
  ' "$1"
}

# workflow_files — `<relative path>` for every workflow file of both
# directories, 1 per line. Both .yml and .yaml, because GitHub reads both and a
# rule that saw only 1 of them would be walked around by a rename.
function workflow_files() {
  local directory file
  for directory in "${WORKFLOW_DIRECTORIES[@]}"; do
    [[ -d "$REPO_ROOT/$directory" ]] || continue
    for file in "$REPO_ROOT/$directory"/*.yml "$REPO_ROOT/$directory"/*.yaml; do
      [[ -f "$file" ]] || continue
      printf '%s\n' "${file#"$REPO_ROOT"/}"
    done
  done
}

printf '=== RUN  %s\n' "$TEST_NAME"

# ===========================================================================
# 1. THE COUNTER-STIMULUS — every notification detector FIRES, and stays quiet
# ===========================================================================
# This runs before the real files on purpose. A verdict on the real workflows
# means nothing until the same functions have been watched to report a file that
# is broken AND to leave the correct shape alone.
GOOD_FIXTURE="$WORKFLOW_FIXTURES/good-nightly.yml"
UNNOTIFIED_FIXTURE="$WORKFLOW_FIXTURES/unnotified-nightly.yml"
UNGUARDED_FIXTURE="$WORKFLOW_FIXTURES/notify-without-failure.yml"
UNSCHEDULED_FIXTURE="$WORKFLOW_FIXTURES/unscheduled-workflow.yml"

missing_fixtures=""
for fixture in "$GOOD_FIXTURE" "$UNNOTIFIED_FIXTURE" "$UNGUARDED_FIXTURE" "$UNSCHEDULED_FIXTURE"; do
  [[ -f "$fixture" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${fixture}"
done

if [[ -n "$missing_fixtures" ]]; then
  fail_check "counter_stimulus_workflow_fixtures_exist" \
    "the fixtures this test proves its detectors with are absent:" \
    "$missing_fixtures"
else
  pass_check "counter_stimulus_workflow_fixtures_exist"

  # -- the trigger detector, both directions --
  assert_equal "counter_stimulus_finds_the_schedule_key" \
    "1" "$(declares_a_schedule "$GOOD_FIXTURE")" \
    "the fixture runs on a cron schedule; a detector that misses it makes every rule below vacuous"
  assert_equal "counter_stimulus_does_not_read_a_commented_schedule_as_a_schedule" \
    "0" "$(declares_a_schedule "$UNSCHEDULED_FIXTURE")" \
    "that fixture names 'schedule:' inside a comment and runs on a push" \
    "a rule that reported it would demand issues: write on every workflow in the repository"
  assert_equal "counter_stimulus_finds_the_cron_entry" \
    "1" "$(declares_a_cron "$GOOD_FIXTURE")" \
    "a schedule: key with no cron under it parses and never fires"

  # -- the permission detector, both directions --
  assert_equal "counter_stimulus_finds_the_issues_write_grant" \
    "1" "$(declares_issues_write "$GOOD_FIXTURE")"
  assert_equal "counter_stimulus_reports_the_missing_issues_write_grant" \
    "0" "$(declares_issues_write "$UNNOTIFIED_FIXTURE")" \
    "without issues: write the filer step fails, and a run that is already red gets a second red"

  # -- the notification detector, all 3 directions --
  assert_equal "counter_stimulus_finds_the_guarded_notifier_call" \
    "1" "$(guarded_notifier_total "$GOOD_FIXTURE")" \
    "the fixture calls the notifier from a step guarded by if: failure()" \
    "it calls it a second time under if: success() to close the issue, and that call is not this rule's business"
  assert_equal "counter_stimulus_reports_the_workflow_that_never_notifies" \
    "0" "$(guarded_notifier_total "$UNNOTIFIED_FIXTURE")" \
    "that fixture fails at 04:00 and tells nobody"
  assert_equal "counter_stimulus_reports_the_notifier_that_is_not_guarded_by_failure" \
    "0" "$(guarded_notifier_total "$UNGUARDED_FIXTURE")" \
    "that fixture calls the notifier from a step with no if:, so GitHub skips it exactly when it is needed" \
    "a rule keyed on the presence of the string reads that file as correct"
fi

# ===========================================================================
# 2. THE RULE — every scheduled workflow notifies, and the set is not empty
# ===========================================================================
workflows="$(workflow_files)"

if [[ -z "$workflows" ]]; then
  fail_check "the_workflow_directories_hold_at_least_one_file" \
    "no *.yml or *.yaml under: ${WORKFLOW_DIRECTORIES[*]}" \
    "either the directories moved, or the reader in this test stopped matching"
else
  pass_check "the_workflow_directories_hold_at_least_one_file"
fi

scheduled=""
while IFS= read -r relative; do
  [[ -z "$relative" ]] && continue
  if [[ "$(declares_a_schedule "$REPO_ROOT/$relative")" == "1" ]]; then
    scheduled="${scheduled:+${scheduled}
}${relative}"
  fi
done <<< "$workflows"

# The liveness clause. Everything below is keyed on the trigger, so it covers a
# scheduled workflow added tomorrow with no edit here — and it is all vacuous
# while no scheduled workflow exists. A rule over an empty set passes on a
# repository whose nightly was deleted.
for directory in "${WORKFLOW_DIRECTORIES[@]}"; do
  expected="${directory}/${NIGHTLY_WORKFLOW}"
  if grep -qxF -- "$expected" <<< "$scheduled"; then
    pass_check "${expected}_runs_on_a_schedule"
  else
    fail_check "${expected}_runs_on_a_schedule" \
      "this file is either absent or declares no 'schedule:' key" \
      "the scheduled workflows found were:" "${scheduled:-<none>}" \
      "every rule in this file is keyed on the schedule trigger, so with no scheduled" \
      "workflow they all pass over an empty set"
  fi
done

# THE RATCHET. Keyed on the trigger and not on a file list, so a scheduled
# workflow added tomorrow is covered the day it is added.
while IFS= read -r relative; do
  [[ -z "$relative" ]] && continue
  file="$REPO_ROOT/$relative"

  if [[ "$(declares_a_cron "$file")" == "1" ]]; then
    pass_check "${relative}_schedule_carries_a_cron_entry"
  else
    fail_check "${relative}_schedule_carries_a_cron_entry" \
      "the workflow declares 'schedule:' and no '- cron:' under it" \
      "it parses, and it never fires"
  fi

  guarded="$(guarded_notifier_total "$file")"
  if [[ "$guarded" -ge 1 ]]; then
    pass_check "${relative}_notifies_on_failure"
  else
    calls="$(notifier_steps "$file")"
    fail_check "${relative}_notifies_on_failure" \
      "no step of this scheduled workflow calls ${NOTIFIER} under 'if: failure()'" \
      "the notifier calls found were (line:guarded-by-failure):" "${calls:-<none>}" \
      "a scheduled run has no author watching it, so its red reaches nobody" \
      "fix: add a step that runs ${NOTIFIER} with 'if: \${{ failure() }}'"
  fi

  if [[ "$(declares_issues_write "$file")" == "1" ]]; then
    pass_check "${relative}_declares_issues_write"
  else
    fail_check "${relative}_declares_issues_write" \
      "no permissions block of this scheduled workflow grants 'issues: write'" \
      "the notifier opens and closes an issue, so without the grant it fails" \
      "and the run gets a second red instead of a notification"
  fi
done <<< "$scheduled"

# The notifier itself. A workflow that calls a script which is not there fails
# at 03:00 with a 127, which is a notification nobody receives.
if [[ -f "$REPO_ROOT/$NOTIFIER" ]]; then
  pass_check "the_notifier_script_exists"
  if [[ -x "$REPO_ROOT/$NOTIFIER" ]]; then
    pass_check "the_notifier_script_is_executable"
  else
    fail_check "the_notifier_script_is_executable" \
      "not executable: ${NOTIFIER}" \
      "every other script this repository invokes directly carries its execute bit"
  fi
else
  fail_check "the_notifier_script_exists" \
    "absent: ${NOTIFIER}" \
    "both scheduled workflows call it, so the notification has 1 home"
  fail_check "the_notifier_script_is_executable" \
    "absent: ${NOTIFIER}"
fi

# ===========================================================================
# 3. THE TRIVY GATE — it cannot pass an unpatched CRITICAL
# ===========================================================================
LAX_FIXTURE="$WORKFLOW_FIXTURES/lax-trivy.yml"

if [[ ! -f "$LAX_FIXTURE" || ! -f "$GOOD_FIXTURE" ]]; then
  fail_check "counter_stimulus_trivy_fixtures_exist" \
    "the fixtures this test proves its trivy detectors with are absent:" \
    "$LAX_FIXTURE" "$GOOD_FIXTURE"
else
  pass_check "counter_stimulus_trivy_fixtures_exist"

  assert_equal "counter_stimulus_finds_the_trivy_invocation" \
    "1" "$(invokes_trivy "$GOOD_FIXTURE")" \
    "a detector that misses the scan makes every clause below vacuous"
  assert_equal "counter_stimulus_does_not_read_a_workflow_without_a_scan_as_one_that_scans" \
    "0" "$(invokes_trivy "$UNSCHEDULED_FIXTURE")"

  assert_equal "counter_stimulus_finds_the_CRITICAL_severity" \
    "1" "$(gates_critical "$GOOD_FIXTURE")"
  assert_equal "counter_stimulus_reports_a_severity_list_without_CRITICAL" \
    "0" "$(gates_critical "$LAX_FIXTURE")" \
    "that fixture gates HIGH only, so a critical vulnerability passes its gate"

  assert_equal "counter_stimulus_finds_the_failing_exit_code" \
    "1" "$(fails_the_step "$GOOD_FIXTURE")"
  assert_equal "counter_stimulus_reports_the_exit_code_that_never_fails" \
    "0" "$(fails_the_step "$LAX_FIXTURE")" \
    "that fixture scans with --exit-code 0: it reports, and the run stays green"

  assert_equal "counter_stimulus_leaves_a_scan_without_ignore_unfixed_alone" \
    "" "$(unfixed_skip_lines "$GOOD_FIXTURE")"
  assert_contains "counter_stimulus_reports_the_ignore_unfixed_flag" \
    "$(unfixed_skip_lines "$LAX_FIXTURE")" "--ignore-unfixed" \
    "an unfixed CRITICAL must become a waiver with an expiry, which is a visible line in a diff"

  assert_equal "counter_stimulus_finds_the_named_waiver_file" \
    "1" "$(names_the_waiver_file "$GOOD_FIXTURE")"
  assert_equal "counter_stimulus_reports_the_scan_that_never_names_the_waiver_file" \
    "0" "$(names_the_waiver_file "$LAX_FIXTURE")" \
    "trivy loads the YAML ignore file only when its path is given, so an unnamed waiver file is dead text"
fi

# The scanning workflows, found by what they DO. A future scheduled workflow
# that runs no scan — a weekly version bump, for instance — must not be judged
# by a rule about trivy flags, so this set is not the scheduled set.
scanning=""
while IFS= read -r relative; do
  [[ -z "$relative" ]] && continue
  if [[ "$(invokes_trivy "$REPO_ROOT/$relative")" == "1" ]]; then
    scanning="${scanning:+${scanning}
}${relative}"
  fi
done <<< "$workflows"

# The liveness clause, for the reason section 2 has one: every rule below is
# keyed on "this workflow scans", and over an empty set they are all green.
for directory in "${WORKFLOW_DIRECTORIES[@]}"; do
  expected="${directory}/${NIGHTLY_WORKFLOW}"
  if grep -qxF -- "$expected" <<< "$scanning"; then
    pass_check "${expected}_runs_a_trivy_scan"
  else
    fail_check "${expected}_runs_a_trivy_scan" \
      "this file is either absent or runs no trivy scan" \
      "the scanning workflows found were:" "${scanning:-<none>}" \
      "with no scanning workflow, every severity-gate clause below passes over an empty set"
  fi
done

while IFS= read -r relative; do
  [[ -z "$relative" ]] && continue
  file="$REPO_ROOT/$relative"

  if [[ "$(gates_critical "$file")" == "1" ]]; then
    pass_check "${relative}_gates_CRITICAL"
  else
    fail_check "${relative}_gates_CRITICAL" \
      "the scan names no severity list holding CRITICAL" \
      "a gate that does not name CRITICAL passes an image that carries one"
  fi

  if [[ "$(fails_the_step "$file")" == "1" ]]; then
    pass_check "${relative}_fails_the_step_on_a_finding"
  else
    fail_check "${relative}_fails_the_step_on_a_finding" \
      "the scan does not set an exit code of 1" \
      "with --exit-code 0 trivy prints its table and the step succeeds," \
      "so the whole scan is a log line in a job nobody watches"
  fi

  unfixed="$(unfixed_skip_lines "$file")"
  if [[ -z "$unfixed" ]]; then
    pass_check "${relative}_does_not_skip_an_unfixed_finding"
  else
    fail_check "${relative}_does_not_skip_an_unfixed_finding" \
      "ignore-unfixed is turned on here:" \
      "$unfixed" \
      "an unfixed CRITICAL must become a waiver in ${WAIVER_FILE} carrying a reason and an expiry," \
      "which is a visible line in a diff — never a silent skip" \
      "an explicit 'ignore-unfixed: false' is fine and is not reported"
  fi

  if [[ "$(names_the_waiver_file "$file")" == "1" ]]; then
    pass_check "${relative}_names_the_waiver_file"
  else
    fail_check "${relative}_names_the_waiver_file" \
      "the scan never names ${WAIVER_FILE}" \
      "the YAML ignore file is experimental in trivy and is loaded only when its path is given," \
      "so an unnamed waiver file is a document with no effect on the scan"
  fi
done <<< "$scanning"

# ===========================================================================
# 4. THE WAIVERS — every one carries an expiry and a reason
# ===========================================================================
WAIVER_FIXTURES="$TESTS_DIR/fixtures/waivers"
GOOD_WAIVERS="$WAIVER_FIXTURES/good.yaml"
NO_EXPIRY_WAIVERS="$WAIVER_FIXTURES/no-expiry.yaml"
NO_REASON_WAIVERS="$WAIVER_FIXTURES/no-reason.yaml"
NO_ID_WAIVERS="$WAIVER_FIXTURES/no-id.yaml"

missing_fixtures=""
for fixture in "$GOOD_WAIVERS" "$NO_EXPIRY_WAIVERS" "$NO_REASON_WAIVERS" "$NO_ID_WAIVERS"; do
  [[ -f "$fixture" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${fixture}"
done

if [[ -n "$missing_fixtures" ]]; then
  fail_check "counter_stimulus_waiver_fixtures_exist" \
    "the fixtures this test proves its waiver detectors with are absent:" \
    "$missing_fixtures"
else
  pass_check "counter_stimulus_waiver_fixtures_exist"

  # The reader parses the shape it claims to read. 3 entries, and the nested
  # list under `paths:` is part of its entry rather than an entry of its own.
  assert_equal "counter_stimulus_reads_3_waiver_entries_and_not_the_nested_paths" \
    "3" "$(waiver_entry_total "$GOOD_WAIVERS")" \
    "the fixture holds 3 entries across 2 sections, and 1 of them carries a nested paths list" \
    "a parser that counted the path item would report 4, and one that stopped matching would report 0"

  # The quiet direction.
  assert_equal "counter_stimulus_leaves_the_complete_waiver_file_alone" \
    "" "$(waiver_defects "$GOOD_WAIVERS")" \
    "every entry of that fixture carries an id, a statement and an expired_at"

  # Each defect direction: the bad entry is named, and the complete entry that
  # sits beside it is not.
  no_expiry_report="$(waiver_defects "$NO_EXPIRY_WAIVERS")"
  assert_contains "counter_stimulus_reports_the_waiver_with_no_expiry" \
    "$no_expiry_report" "CVE-2026-00004" \
    "a waiver with no expired_at is a permanent exception written as a temporary one"
  assert_not_contains "counter_stimulus_does_not_report_the_complete_entry_beside_it" \
    "$no_expiry_report" "CVE-2026-00003" \
    "that entry is complete; a detector that reports it as well reports everything"

  no_reason_report="$(waiver_defects "$NO_REASON_WAIVERS")"
  assert_contains "counter_stimulus_reports_the_waiver_with_no_reason" \
    "$no_reason_report" "CVE-2026-00006" \
    "a waiver with no statement says what is ignored and never why"
  assert_not_contains "counter_stimulus_does_not_report_the_complete_entry_beside_the_reasonless_one" \
    "$no_reason_report" "CVE-2026-00005"

  no_id_report="$(waiver_defects "$NO_ID_WAIVERS")"
  assert_contains "counter_stimulus_reports_the_waiver_with_no_id" \
    "$no_id_report" "<no-id>" \
    "id is the only field trivy requires, and an entry without one waives nothing"
  assert_not_contains "counter_stimulus_does_not_report_the_complete_entry_beside_the_idless_one" \
    "$no_id_report" "CVE-2026-00007"
fi

# THE RULE, on the real file.
if [[ ! -f "$REPO_ROOT/$WAIVER_FILE" ]]; then
  fail_check "the_waiver_file_exists" \
    "absent: ${WAIVER_FILE}" \
    "the scan names this path, so without the file the scan fails or every waiver is lost" \
    "it is empty at merge: the section keys, and no entry under them"
  fail_check "the_waiver_file_declares_a_section_trivy_reads" \
    "absent: ${WAIVER_FILE}"
  fail_check "every_waiver_carries_an_expiry_and_a_reason" \
    "absent: ${WAIVER_FILE}"
else
  pass_check "the_waiver_file_exists"

  if [[ "$(declares_a_waiver_section "$REPO_ROOT/$WAIVER_FILE")" == "1" ]]; then
    pass_check "the_waiver_file_declares_a_section_trivy_reads"
  else
    fail_check "the_waiver_file_declares_a_section_trivy_reads" \
      "${WAIVER_FILE} declares none of: vulnerabilities, misconfigurations, secrets, licenses" \
      "a file with no section is not an empty waiver file, it is a file trivy cannot use"
  fi

  waiver_report="$(waiver_defects "$REPO_ROOT/$WAIVER_FILE")"
  if [[ -z "$waiver_report" ]]; then
    pass_check "every_waiver_carries_an_expiry_and_a_reason"
  else
    fail_check "every_waiver_carries_an_expiry_and_a_reason" \
      "these entries of ${WAIVER_FILE} are incomplete:" \
      "$waiver_report" \
      "id names the finding, statement is the reason it is accepted, expired_at is the date it" \
      "comes back for review — trivy enforces the expiry itself, so a dated waiver reopens on its own" \
      "a waiver with no expiry is a permanent exception written as a temporary one"
  fi
fi

# ===========================================================================
# 5. THE BASE-OS PIN — both Dockerfiles build from the digest
# ===========================================================================
# The 2 Dockerfiles that FROM the base OS. The other 4 FROM an image of this
# repository, so they inherit the pin instead of repeating it.
PINNED_DOCKERFILES=(
  "base/Dockerfile"
  "cloud/Dockerfile"
)

# The 2 pin homes. cloud/Dockerfile is deliberately NOT one: every pin of the
# cloud family arrives from versions.env as a generated --build-arg, and its
# ARGs are value-less on purpose.
ENV_PIN_HOME="versions.env"
DOCKERFILE_PIN_HOME="base/Dockerfile"
PIN_NAME="UBUNTU_BASE_REF"

# -------- the counter-stimulus: the digest shape detector, both ways --------
# The stimulus is written inline rather than as a fixture file, the way
# version-coverage.test.sh builds its appended and deleted pin files: the input
# is 3 strings, and a file on disk would only hide them.
assert_equal "counter_stimulus_accepts_a_full_sha256_digest" \
  "1" "$(digest_is_well_formed "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")"
assert_equal "counter_stimulus_reports_a_digest_that_is_1_character_short" \
  "0" "$(digest_is_well_formed "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcde")" \
  "a truncated digest reads as correct in a diff and fails at docker build, after the merge"
assert_equal "counter_stimulus_reports_a_floating_tag_in_the_pin_home" \
  "0" "$(digest_is_well_formed "24.04")" \
  "a tag in the pin home is the defect the pin exists to remove"

# -------- the counter-stimulus: the FROM detectors, both ways --------
stimulus_floating="$(mktemp)"
stimulus_pinned="$(mktemp)"
# Every `$` below belongs to the DOCKERFILE these 2 lines write, and the
# detectors under test read it as text. The single quotes are the point rather
# than an oversight: a `${UBUNTU_BASE_REF}` that this shell expanded would write
# a stimulus with no pin reference in it at all.
# shellcheck disable=SC2016
printf '# FROM ubuntu:24.04@${UBUNTU_BASE_REF} is what this line used to say\nFROM ubuntu:24.04\n' > "$stimulus_floating"
# shellcheck disable=SC2016
printf 'ARG UBUNTU_BASE_REF=sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\nFROM ubuntu:24.04@${UBUNTU_BASE_REF}\n' > "$stimulus_pinned"

assert_contains "counter_stimulus_reports_the_floating_FROM" \
  "$(floating_from_lines "$stimulus_floating")" "FROM ubuntu:24.04" \
  "that stimulus names the pinned form inside a comment and builds from the moving tag" \
  "a detector that reads prose calls it pinned"
assert_equal "counter_stimulus_leaves_the_pinned_FROM_alone" \
  "" "$(floating_from_lines "$stimulus_pinned")"
assert_equal "counter_stimulus_finds_no_pin_reference_in_the_floating_FROM" \
  "0" "$(pin_reference_line "$stimulus_floating" "$PIN_NAME")" \
  "the only mention there is a comment, and a comment builds nothing"
assert_equal "counter_stimulus_finds_the_pin_reference_on_the_FROM_line" \
  "2" "$(pin_reference_line "$stimulus_pinned" "$PIN_NAME")"
assert_equal "counter_stimulus_finds_the_ARG_above_the_FROM" \
  "1" "$(arg_declaration_line "$stimulus_pinned" "$PIN_NAME")" \
  "an ARG below its FROM expands to the empty string and the build dies at 'ubuntu:24.04@'"
assert_equal "counter_stimulus_reads_the_ARG_default_as_the_pin_value" \
  "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" \
  "$(dockerfile_arg_value "$stimulus_pinned" "$PIN_NAME")"
rm -f "$stimulus_floating" "$stimulus_pinned"

# -------- THE RULE, on both real Dockerfiles --------
for relative in "${PINNED_DOCKERFILES[@]}"; do
  file="$REPO_ROOT/$relative"
  if [[ ! -f "$file" ]]; then
    fail_check "${relative}_exists" \
      "the file list in this test is stale; this path is named but absent"
    continue
  fi

  reference_line="$(pin_reference_line "$file" "$PIN_NAME")"
  if [[ "$reference_line" != "0" ]]; then
    pass_check "${relative}_FROM_reads_the_pin"
  else
    fail_check "${relative}_FROM_reads_the_pin" \
      "no FROM line of ${relative} reads \${${PIN_NAME}}" \
      "its FROM lines are:" "$(from_lines "$file")" \
      "want: FROM ubuntu:24.04@\${${PIN_NAME}}"
  fi

  floating="$(floating_from_lines "$file")"
  if [[ -z "$floating" ]]; then
    pass_check "${relative}_FROM_carries_no_floating_ubuntu_tag"
  else
    fail_check "${relative}_FROM_carries_no_floating_ubuntu_tag" \
      "these FROM lines name an ubuntu tag and no digest:" \
      "$floating" \
      "the tag moves upstream, so 2 builds of 1 commit produce 2 different images" \
      "and verify-published cannot say which one it read"
  fi

  argument_line="$(arg_declaration_line "$file" "$PIN_NAME")"
  if [[ "$argument_line" == "0" ]]; then
    fail_check "${relative}_declares_the_pin_ARG_above_its_FROM" \
      "${relative} declares no 'ARG ${PIN_NAME}'" \
      "a FROM can interpolate only an ARG declared before it"
  elif [[ "$reference_line" != "0" && "$argument_line" -gt "$reference_line" ]]; then
    fail_check "${relative}_declares_the_pin_ARG_above_its_FROM" \
      "ARG ${PIN_NAME} is on line ${argument_line} and the FROM that reads it is on line ${reference_line}" \
      "below its FROM the ARG expands to the empty string, the FROM becomes 'ubuntu:24.04@'," \
      "and the build dies in the publish job, after the merge"
  else
    pass_check "${relative}_declares_the_pin_ARG_above_its_FROM"
  fi
done

# -------- THE RULE, on both pin homes --------
env_pin="$(env_pin_value "$REPO_ROOT/$ENV_PIN_HOME" "$PIN_NAME")"
dockerfile_pin="$(dockerfile_arg_value "$REPO_ROOT/$DOCKERFILE_PIN_HOME" "$PIN_NAME")"

if [[ "$(digest_is_well_formed "$env_pin")" == "1" ]]; then
  pass_check "${ENV_PIN_HOME}_pins_a_full_sha256_digest"
else
  fail_check "${ENV_PIN_HOME}_pins_a_full_sha256_digest" \
    "want: ${PIN_NAME} matching ^sha256:[0-9a-f]{64}\$" \
    "got:  '${env_pin:-<no such pin>}'"
fi

if [[ "$(digest_is_well_formed "$dockerfile_pin")" == "1" ]]; then
  pass_check "${DOCKERFILE_PIN_HOME}_pins_a_full_sha256_digest"
else
  fail_check "${DOCKERFILE_PIN_HOME}_pins_a_full_sha256_digest" \
    "want: ARG ${PIN_NAME}=<digest> matching ^sha256:[0-9a-f]{64}\$" \
    "got:  '${dockerfile_pin:-<no such ARG, or a value-less one>}'"
fi

# The 2 homes hold 1 value. This is the clause that a copy-paste bump breaks:
# each home is well formed, and the base family and the cloud family then build
# on 2 different operating systems.
if [[ -n "$env_pin" && "$env_pin" == "$dockerfile_pin" ]]; then
  pass_check "both_pin_homes_hold_the_same_digest"
else
  fail_check "both_pin_homes_hold_the_same_digest" \
    "${ENV_PIN_HOME}:      '${env_pin:-<no such pin>}'" \
    "${DOCKERFILE_PIN_HOME}: '${dockerfile_pin:-<no such ARG>}'" \
    "2 homes holding 2 values means the base family and the cloud family build on 2 different" \
    "operating systems while 1 number in a file says otherwise"
fi

# ===========================================================================
# 6. THE DRIFT PROBE — the currency check reports a move
# ===========================================================================
# A digest pin freezes the base OS until a bump merges, so a pull request that
# nobody opens means unpatched images that look current. This is the half that
# reports it, and the 2 halves ship together.
#
# THE SEAM, which _ctl/lib.sh must declare:
#
#   base_image_digest [reference]
#       Prints the digest the REGISTRY holds for the reference now, 1 line,
#       exit 0. The default reference is ubuntu:24.04. It reads the registry
#       through docker; it never answers out of a file, because a reader that
#       returns the pin agrees with the pin on every night including the ones
#       where upstream moved.
#
#   require_base_image_current [reference]
#       Exit 0 when that digest equals the ${PIN_NAME} pin, non-zero naming
#       BOTH digests when it differs. `require_` is the prefix this library
#       already uses for a guard that fails closed.
#
# Hermetic: the stub docker is first on PATH and every argv it receives is
# recorded, so a reader that answered without asking the registry is reported
# instead of believed.
STUB_BIN="$TESTS_DIR/stubs"

# A digest no file in this repository holds. It can only reach the output of a
# reader that really asked the stub registry.
DRIFTED_DIGEST="sha256:d1f7d1f7d1f7d1f7d1f7d1f7d1f7d1f7d1f7d1f7d1f7d1f7d1f7d1f7d1f7d1f7"

PROBE_OUTPUT=""
PROBE_STATUS=0
PROBE_ARGV=""

# run_library_probe <shell body> [KEY=VALUE ...] — source _ctl/lib.sh in a fresh
# shell and run the body against the stub docker. The same shape
# platform-policy.test.sh uses to read SANCTIONED_PLATFORMS out of a running
# shell rather than out of the text of a line.
function run_library_probe() {
  local body="$1"
  shift
  local log
  log="$(mktemp)"
  PROBE_STATUS=0
  # The `$1` and `$2` belong to the PROBE shell and must reach it unexpanded,
  # the same way .ci/smoke.sh writes its guest payload.
  # shellcheck disable=SC2016
  PROBE_OUTPUT="$(env PATH="${STUB_BIN}:${PATH}" STUB_DOCKER_LOG="$log" PROJECT_ROOT="$REPO_ROOT" "$@" \
    bash -c 'source "$1"; eval "$2"' probe "$REPO_ROOT/_ctl/lib.sh" "$body" 2>&1)" || PROBE_STATUS=$?
  PROBE_ARGV="$(cat "$log")"
  rm -f "$log"
}

# -------- the stub answers the currency question, in every shape --------
# A knob that answers nothing would make every clause below fail for a reason
# that has nothing to do with the library.
if [[ -x "$STUB_BIN/docker" ]]; then
  pass_check "the_docker_stub_is_executable"
else
  fail_check "the_docker_stub_is_executable" \
    "not executable: ${STUB_BIN}/docker" \
    "without it the real docker answers, and nothing below is hermetic"
fi

stub_answer="$(env PATH="${STUB_BIN}:${PATH}" STUB_REGISTRY_DIGEST="$DRIFTED_DIGEST" \
  docker buildx imagetools inspect ubuntu:24.04 --format '{{.Manifest.Digest}}' 2>&1)"
assert_equal "the_stub_answers_a_formatted_digest_read" "$DRIFTED_DIGEST" "$stub_answer"

stub_answer="$(env PATH="${STUB_BIN}:${PATH}" STUB_REGISTRY_DIGEST="$DRIFTED_DIGEST" \
  docker buildx imagetools inspect ubuntu:24.04 2>&1)"
assert_contains "the_stub_answers_an_unformatted_digest_read" "$stub_answer" "$DRIFTED_DIGEST"

stub_answer="$(env PATH="${STUB_BIN}:${PATH}" STUB_REGISTRY_DIGEST="$DRIFTED_DIGEST" \
  docker image inspect ubuntu:24.04 --format '{{index .RepoDigests 0}}' 2>&1)"
assert_contains "the_stub_answers_a_local_repo_digest_read" "$stub_answer" "$DRIFTED_DIGEST"

stub_status=0
stub_answer="$(env PATH="${STUB_BIN}:${PATH}" STUB_REGISTRY_DIGEST="$DRIFTED_DIGEST" \
  STUB_MANIFEST_STATUS=1 STUB_MANIFEST_ERROR="stub: the registry did not answer" \
  docker buildx imagetools inspect ubuntu:24.04 --format '{{.Manifest.Digest}}' 2>&1)" || stub_status=$?
assert_status_nonzero "the_stub_reports_a_failed_registry_read" "$stub_status" \
  "a stub that answered a digest on a failed read would let a reader call the base OS current" \
  "on a night when nothing could be read at all" \
  "output was:" "$stub_answer"

# -------- the seam is declared --------
run_library_probe 'declare -F base_image_digest > /dev/null'
if [[ "$PROBE_STATUS" -eq 0 ]]; then
  pass_check "the_library_declares_base_image_digest"
else
  fail_check "the_library_declares_base_image_digest" \
    "sourcing _ctl/lib.sh and asking for base_image_digest exited ${PROBE_STATUS}" \
    "output was:" "${PROBE_OUTPUT:-<none>}" \
    "want: a reader that prints the digest ubuntu:24.04 holds in the registry now"
fi

run_library_probe 'declare -F require_base_image_current > /dev/null'
if [[ "$PROBE_STATUS" -eq 0 ]]; then
  pass_check "the_library_declares_require_base_image_current"
else
  fail_check "the_library_declares_require_base_image_current" \
    "sourcing _ctl/lib.sh and asking for require_base_image_current exited ${PROBE_STATUS}" \
    "output was:" "${PROBE_OUTPUT:-<none>}" \
    "want: a guard that exits non-zero when the registry digest differs from the ${PIN_NAME} pin"
fi

# -------- the reader answers the REGISTRY --------
run_library_probe 'base_image_digest' STUB_REGISTRY_DIGEST="$DRIFTED_DIGEST"
if [[ "$PROBE_STATUS" -ne 0 ]]; then
  fail_check "base_image_digest_reports_what_the_registry_holds" \
    "the reader exited ${PROBE_STATUS}" \
    "docker was called with:" "${PROBE_ARGV:-<no docker invocation>}" \
    "output was:" "${PROBE_OUTPUT:-<none>}"
elif ! grep -qF -- "$DRIFTED_DIGEST" <<< "$PROBE_OUTPUT"; then
  fail_check "base_image_digest_reports_what_the_registry_holds" \
    "want: ${DRIFTED_DIGEST}, which is what the stub registry holds" \
    "got:  ${PROBE_OUTPUT:-<nothing>}" \
    "docker was called with:" "${PROBE_ARGV:-<no docker invocation>}" \
    "a reader that answers out of a file agrees with the pin on every night, including the ones" \
    "where upstream moved"
elif [[ -z "$PROBE_ARGV" ]]; then
  fail_check "base_image_digest_reports_what_the_registry_holds" \
    "the reader printed the right digest and it called docker not once:" \
    "${PROBE_ARGV:-<no docker invocation>}" \
    "a currency reader that contacts no registry reports the state of a file, not of the world"
else
  pass_check "base_image_digest_reports_what_the_registry_holds"
fi

# -------- the guard reports a move --------
run_library_probe 'require_base_image_current' STUB_REGISTRY_DIGEST="$DRIFTED_DIGEST"
if [[ "$PROBE_STATUS" -eq 0 ]]; then
  fail_check "the_currency_check_reports_a_move" \
    "want: a non-zero exit status — the stub registry holds ${DRIFTED_DIGEST}," \
    "which is not the pin in ${ENV_PIN_HOME}" \
    "got:  0" \
    "output was:" "${PROBE_OUTPUT:-<none>}"
elif ! grep -qF -- "$DRIFTED_DIGEST" <<< "$PROBE_OUTPUT"; then
  fail_check "the_currency_check_reports_a_move" \
    "the check exited ${PROBE_STATUS} and its message never names the digest the registry holds" \
    "output was:" "${PROBE_OUTPUT:-<none>}" \
    "the reader of a 03:00 failure needs both digests, or the next step is to run the read by hand"
else
  pass_check "the_currency_check_reports_a_move"
fi

# -------- and it is silent when the pin agrees --------
# The agreeing case is built from the pin the repository really holds. That is
# not a test reading its own expectation: the value under test here is the
# COMPARISON, and feeding it 2 equal digests is the only way to watch the guard
# stay quiet.
if [[ "$(digest_is_well_formed "$env_pin")" != "1" ]]; then
  fail_check "the_currency_check_is_silent_when_the_pin_agrees" \
    "${ENV_PIN_HOME} holds no well-formed ${PIN_NAME}, so the agreeing case cannot be built" \
    "got: '${env_pin:-<no such pin>}'"
else
  run_library_probe 'require_base_image_current' STUB_REGISTRY_DIGEST="$env_pin"
  if [[ "$PROBE_STATUS" -eq 0 ]]; then
    pass_check "the_currency_check_is_silent_when_the_pin_agrees"
  else
    fail_check "the_currency_check_is_silent_when_the_pin_agrees" \
      "the stub registry holds exactly the pin, and the check exited ${PROBE_STATUS}" \
      "docker was called with:" "${PROBE_ARGV:-<no docker invocation>}" \
      "output was:" "${PROBE_OUTPUT:-<none>}" \
      "a guard that fires on a match makes the nightly red every night, which teaches the reader to ignore red"
  fi
fi

test_summary "$TEST_NAME"
