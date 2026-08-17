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
# 09:00 UTC — 02:00 MST, the hour the nightly cron names — and nobody refreshes
# the Actions tab afterwards, so a red nightly is a red that reaches no human.
# The same is true of every clause below: a scan
# whose gate is `--exit-code 0` reports and passes, a waiver with no expiry
# never comes back for review, and a digest pin that nothing watches freezes the
# base OS at a snapshot that looks current forever.
#
# Every rule here is therefore about the property that makes the mechanism
# LOUD, and never about the presence of the mechanism.
#
# ============================================================================
# THE 7 RULES
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
#      each declaring that ARG above its FROM and VALUE-LESS, and versions.env —
#      the 1 home — holds a full sha256. A floating ubuntu:24.04 means 2 builds
#      of 1 commit can produce 2 different images, and this repository rests on
#      the opposite property: the commit decides the image. This rule held the
#      2 homes to 1 value until base/Dockerfile went value-less; it now holds
#      the second home shut instead.
#
#   5. base_image_digest_reports_a_move
#      The currency reader answers what the REGISTRY holds, and the check exits
#      non-zero when that differs from the pin. A pin nothing watches is the
#      cost of rule 4, so the 2 halves ship together.
#
#   6. the_notify_job_reduces_the_verdicts_it_needs
#      In a scheduled workflow of more than 1 job, the job that calls the
#      notifier runs on every outcome, needs EVERY other job, and reduces their
#      results to its own status BEFORE any step on the success path. Rule 1 is
#      about a step and is the whole rule for a workflow of 1 job; a job under
#      always() has no failure of its own, so without the reduction a red night
#      CLOSES the issue that reports it.
#
#   7. the_scan_matrix_equals_BUILD_ORDER
#      The image list of the scan matrix holds exactly the names BUILD_ORDER
#      declares in ctl.sh — order-insensitive, no duplicates. A hand-written
#      matrix is a second declaration of the published set, and narrowing it to
#      [base] drops 5 images out of the security gate with every other check in
#      this repository still green.
#
#   8. scheduled_matrix_is_bounded
#      A job of a scheduled workflow that fans out over a `strategy.matrix`
#      declares `max-parallel`. This is a RATCHET on the same key as rule 1 —
#      the TRIGGER — so a scheduled workflow added tomorrow is covered the day
#      it is added, and a job with no matrix is never asked for a bound it has
#      no use for.
#
#      The reason it is a rule now: these runs left the GitHub-hosted pool. On
#      a hosted runner an unbounded fan-out is somebody else's capacity, and
#      the only cost is money. On the homelab pool it is N pods placed on a
#      handful of nodes, each unpacking a multi-GB image onto the node's own
#      filesystem, and the node runs out of disk. The run then fails with "No
#      space left on device" — a red that says nothing about the images it was
#      asked to judge — and it takes every other pod on that node with it,
#      including the `validate` job of an unrelated repository. The blast
#      radius of a missing integer is the cluster.
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
# There IS a parser in the suite now, and it is deliberately not in this file.
# `_ctl/tests/workflow-yaml.test.sh` runs yq over every workflow file and asks 1
# question: does the document parse. It exists because a token reader cannot
# see a file that does not parse — the first version of the nightly reached a
# green gate carrying an unparseable `run:` line, and every rule in THIS file
# passed on it, correctly, because each token really was there. The 2 files
# answer 2 different questions, and only 1 of them needs a tool.
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
# Empty when the ARG is absent or value-less. Value-less is what BOTH root
# Dockerfiles must be: every pin of base and cloud arrives from versions.env as
# a generated --build-arg, so a value here is a SECOND home for a pin that has
# 1, and this reader is how rule 5 below sees one appear.
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

# ---------------------------------------------------------------------------
# The job readers, for the notify-job shape (rule 6).
#
# Rule 1 above is about a STEP: a call to the notifier under `if: failure()`.
# That is the whole rule for a workflow of 1 job, because `failure()` in a step
# means "a step of THIS job failed" and the scan is in the same job.
#
# It is not the whole rule for a workflow of several jobs, and the nightly is
# one. There the notifier lives in its own job that runs under `always()` — it
# must, or it could not close the issue on a green night — and a job under
# always() has no failure of its own to react to. Its steps all succeed
# whatever the scan did, so `failure()` is FALSE and `success()` is TRUE on the
# reddest possible night. The job therefore has to REDUCE the results of the
# jobs it needs to its own status first, and everything else in it reads that.
#
# 3 things can be deleted from that shape, and the suite this file belongs to
# stayed green on all 3 until these readers existed:
#
#   the reduction step   -> a red night CLOSES the issue that reports it
#   always()             -> the job is skipped exactly when it is needed
#   1 name from needs:   -> that job's result never reaches the reduction, and
#                           the notify job does not even wait for it
#
# The readers are awk and bash, like every other reader here. A YAML parser
# does now run over these files — _ctl/tests/workflow-yaml.test.sh — and it
# answers 1 question, whether the document parses. It is a sibling file so that
# this one keeps the property its header claims: it needs no tool the gate does
# not already have.
# ---------------------------------------------------------------------------

# job_key_lines <file> — `<line>:<job name>` for every top-level job key.
function job_key_lines() {
  awk '
    BEGIN { in_jobs = 0; job_indent = -1 }
    {
      stripped = $0
      sub(/^[[:space:]]+/, "", stripped)
      if (stripped == "" || substr(stripped, 1, 1) == "#") { next }
      match($0, /^[[:space:]]*/)
      indent = RLENGTH
      if (indent == 0) {
        in_jobs = (stripped ~ /^jobs:[[:space:]]*$/) ? 1 : 0
        job_indent = -1
        next
      }
      if (!in_jobs) { next }
      if (job_indent == -1) { job_indent = indent }
      if (indent != job_indent) { next }
      if (stripped ~ /^[A-Za-z0-9_.-]+:[[:space:]]*$/) {
        key = stripped
        sub(/:.*$/, "", key)
        print NR ":" key
      }
    }
  ' "$1"
}

# job_names <file> — every top-level job name, 1 per line, in file order.
function job_names() {
  local record
  while IFS= read -r record; do
    [[ -z "$record" ]] && continue
    printf '%s\n' "${record#*:}"
  done < <(job_key_lines "$1")
}

# job_span <file> <job name> — `<first line>:<last line>` of that job's block,
# and `0:0` when the file declares no such job.
#
# The block ends at the next job key, at the next top-level key, or at the end
# of the file — whichever comes first. The middle one matters: `jobs:` is the
# last top-level key of every workflow here, and a reader that assumed it always
# is would silently swallow whatever a future file puts after it.
function job_span() {
  local file="$1" want="$2"
  local record line name start=0 end=0 found=0 boundary total

  while IFS=: read -r line name; do
    [[ -z "$line" ]] && continue
    if [[ "$found" -eq 1 ]]; then
      end=$((line - 1))
      break
    fi
    [[ "$name" == "$want" ]] && { start="$line"; found=1; }
  done < <(job_key_lines "$file")

  if [[ "$found" -eq 0 ]]; then
    printf '0:0'
    return 0
  fi

  total="$(awk 'END { print NR + 0 }' "$file")"
  boundary="$(awk -v start="$start" 'NR > start && /^[^[:space:]#]/ { print NR - 1; exit }' "$file")"
  [[ -z "$boundary" ]] && boundary="$total"
  [[ "$end" -eq 0 || "$end" -gt "$boundary" ]] && end="$boundary"
  printf '%s:%s' "$start" "$end"
}

# job_property_lines <file> <first> <last> — `<line><TAB><text>` for every
# job-level property of that block: the lines at the SHALLOWEST indent the block
# holds. A step-level key sits deeper and is not one, which is the whole point —
# `if:` on a step and `if:` on a job are 2 different rules.
function job_property_lines() {
  awk -v first="$2" -v last="$3" '
    BEGIN { minimum = -1; count = 0 }
    NR <= first { next }
    NR > last { exit }
    {
      stripped = $0
      sub(/^[[:space:]]+/, "", stripped)
      if (stripped == "" || substr(stripped, 1, 1) == "#") { next }
      match($0, /^[[:space:]]*/)
      indent = RLENGTH
      count++
      number[count] = NR
      text[count] = stripped
      depth[count] = indent
      if (minimum == -1 || indent < minimum) { minimum = indent }
    }
    END {
      for (item = 1; item <= count; item++) {
        if (depth[item] == minimum) { print number[item] "\t" text[item] }
      }
    }
  ' "$1"
}

# job_property_record <file> <first> <last> <key> — `<line><TAB><value>` for
# that job-level key, empty when the job declares none. The value is the text
# after the colon, which is empty for a key that opens a block.
function job_property_record() {
  local file="$1" first="$2" last="$3" key="$4"
  local line text value
  while IFS=$'\t' read -r line text; do
    [[ -z "$text" ]] && continue
    case "$text" in
      "${key}:"*)
        value="${text#"${key}":}"
        value="${value%%#*}"
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"
        printf '%s\t%s' "$line" "$value"
        return 0
        ;;
    esac
  done < <(job_property_lines "$file" "$first" "$last")
  printf ''
}

# job_condition <file> <first> <last> — the job-level `if:` value, empty when
# the job carries none.
function job_condition() {
  local record
  record="$(job_property_record "$1" "$2" "$3" "if")"
  [[ -z "$record" ]] && return 0
  printf '%s' "${record#*$'\t'}"
}

# runs_on_every_outcome <condition> — 1 when that job-level condition runs the
# job whether the jobs it needs passed or failed.
#
# `always()` is the spelling this repository uses. `!cancelled()` is accepted as
# well: it also runs on both outcomes, it is the stricter of the 2 — it stops a
# cancelled run from filing an issue — and a rule that forbade it would forbid
# the better version of the same shape. An empty condition is NOT one of them: a
# job with no `if:` runs only when everything it needs succeeded, so it is
# skipped on exactly the night it exists for.
function runs_on_every_outcome() {
  if grep -qE 'always\(\)|![[:space:]]*cancelled\(\)' <<< "$1"; then
    printf '1'
  else
    printf '0'
  fi
}

# job_needs <file> <first> <last> — the job names in `needs:`, 1 per line, in
# both spellings YAML allows: `needs: [a, b]` and a block list of `- a` lines.
# Silent when the job declares no needs.
function job_needs() {
  local file="$1" first="$2" last="$3"
  local record line value

  record="$(job_property_record "$file" "$first" "$last" "needs")"
  [[ -z "$record" ]] && return 0
  line="${record%%$'\t'*}"
  value="${record#*$'\t'}"

  if [[ -n "$value" ]]; then
    value="${value#[}"
    value="${value%]}"
    awk 'BEGIN { RS = "," } { gsub(/^[[:space:]]+|[[:space:]]+$/, ""); gsub(/^["'"'"']|["'"'"']$/, ""); if ($0 != "") print }' <<< "$value"
    return 0
  fi

  # The block form. The items sit deeper than the key that opens them.
  awk -v start="$line" -v last="$last" '
    NR <= start { next }
    NR > last { exit }
    {
      stripped = $0
      sub(/^[[:space:]]+/, "", stripped)
      if (stripped == "" || substr(stripped, 1, 1) == "#") { next }
      if (substr(stripped, 1, 2) != "- ") { exit }
      value = substr(stripped, 3)
      sub(/[[:space:]]*#.*$/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      gsub(/^["'"'"']|["'"'"']$/, "", value)
      if (value != "") { print value }
    }
  ' "$file"
}

# job_step_lines <file> <first> <last> — the line of every step dash of that
# job, 1 per line.
#
# Anchored on the `steps:` key rather than on "a dash inside the job": a block
# `needs:` list carries dashes at the same indent, and counting those as steps
# would make the reader answer a question about a list of job names.
function job_step_lines() {
  local file="$1" first="$2" last="$3"
  local record start
  record="$(job_property_record "$file" "$first" "$last" "steps")"
  [[ -z "$record" ]] && return 0
  start="${record%%$'\t'*}"
  awk -v start="$start" -v last="$last" '
    BEGIN { dash_indent = -1 }
    NR <= start { next }
    NR > last { exit }
    {
      stripped = $0
      sub(/^[[:space:]]+/, "", stripped)
      if (stripped == "" || substr(stripped, 1, 1) == "#") { next }
      if (substr(stripped, 1, 2) != "- ") { next }
      match($0, /^[[:space:]]*/)
      indent = RLENGTH
      if (dash_indent == -1) { dash_indent = indent }
      if (indent == dash_indent) { print NR }
    }
  ' "$file"
}

# step_condition <step slice> — the `if:` line of a step, empty when it has
# none. awk and not grep: grep exits 1 on no match, and a step with no `if:` is
# an ANSWER here, not a failure.
function step_condition() {
  awk '/^[[:space:]]*(-[[:space:]]+)?if:/ { print; exit }' <<< "$1"
}

# verdict_step_line <file> <first> <last> — the line of the first step that
# reduces the results of the needed jobs to this job's status, and 0 when the
# job has none.
#
# 3 clauses, and the step has to satisfy all 3:
#
#   it reads needs.<job>.result   the only place a needed job's verdict is
#   it compares against success   a step that PRINTS the results and exits 0 is
#                                 a log line, not a reduction
#   it is not skippable           a step under `if: failure()` never fires in a
#                                 job that runs under always(), so a reduction
#                                 written there reduces nothing
function verdict_step_line() {
  local file="$1" first="$2" last="$3"
  local dash slice condition
  while IFS= read -r dash; do
    [[ -z "$dash" ]] && continue
    slice="$(step_slice "$file" "$dash")"
    grep -qE 'needs\.[A-Za-z0-9_.-]+\.result' <<< "$slice" || continue
    grep -qF -- "success" <<< "$slice" || continue
    condition="$(step_condition "$slice")"
    if [[ -n "$condition" ]] && [[ "$(runs_on_every_outcome "$condition")" != "1" ]]; then
      continue
    fi
    printf '%s' "$dash"
    return 0
  done < <(job_step_lines "$file" "$first" "$last")
  printf '0'
}

# success_path_step_line <file> <first> <last> — the line of the first step
# guarded by `success()`, and 0 when the job has none.
#
# Any such step is a success path, and the closing of the issue is the one this
# repository has. Steps run in file order, so a success() step that runs BEFORE
# the reduction runs on a night that is not green: until the reduction has run,
# nothing in an always() job has failed, and success() is true.
function success_path_step_line() {
  local file="$1" first="$2" last="$3"
  local dash slice condition
  while IFS= read -r dash; do
    [[ -z "$dash" ]] && continue
    slice="$(step_slice "$file" "$dash")"
    condition="$(step_condition "$slice")"
    [[ -z "$condition" ]] && continue
    if grep -qE 'success\(\)' <<< "$condition"; then
      printf '%s' "$dash"
      return 0
    fi
  done < <(job_step_lines "$file" "$first" "$last")
  printf '0'
}

# job_calls_the_notifier <file> <first> <last> — 1 when a non-comment line of
# that job names the notifier.
function job_calls_the_notifier() {
  local file="$1" first="$2" last="$3"
  local hit
  hit="$(awk -v first="$first" -v last="$last" -v needle="$NOTIFIER" '
    NR <= first { next }
    NR > last { exit }
    /^[[:space:]]*#/ { next }
    index($0, needle) { found = 1 }
    END { print found + 0 }
  ' "$file")"
  printf '%s' "$hit"
}

# ---------------------------------------------------------------------------
# The scan-matrix readers (rule 7).
#
# The image set is declared in ctl.sh, as BUILD_ORDER. The matrix of the nightly
# is a SECOND hand-written copy of it, in 2 files, and a copy is a thing that
# drifts: narrow the matrix to [base] and 5 images leave the security gate with
# every test in this repository still green. So the matrix is held to the
# declaration instead of to a list written here — a list written here would be a
# third copy, and the next narrowing would only have to edit 1 more file.
# ---------------------------------------------------------------------------

# matrix_images <file> — every image name under a `matrix:` -> `image:` key,
# 1 per line, in both spellings YAML allows.
#
# Under a `matrix:` key and not the bare word `image:`: an action input named
# `image:` is not a scan target, and a reader that took it would report the real
# workflow as declaring an image it never declares.
function matrix_images() {
  awk '
    BEGIN { in_matrix = 0; in_list = 0; matrix_indent = -1; image_indent = -1 }
    {
      stripped = $0
      sub(/^[[:space:]]+/, "", stripped)
      if (stripped == "" || substr(stripped, 1, 1) == "#") { next }
      match($0, /^[[:space:]]*/)
      indent = RLENGTH

      if (in_list) {
        if (indent > image_indent && substr(stripped, 1, 2) == "- ") {
          emit(substr(stripped, 3))
          next
        }
        in_list = 0
      }
      if (in_matrix && indent <= matrix_indent) { in_matrix = 0 }
      if (stripped ~ /^matrix:[[:space:]]*$/) {
        in_matrix = 1
        matrix_indent = indent
        next
      }
      if (!in_matrix) { next }
      if (stripped !~ /^image:/) { next }

      rest = substr(stripped, 7)
      sub(/[[:space:]]*#.*$/, "", rest)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", rest)
      if (rest == "") {
        in_list = 1
        image_indent = indent
        next
      }
      sub(/^\[/, "", rest)
      sub(/\]$/, "", rest)
      total = split(rest, parts, ",")
      for (item = 1; item <= total; item++) { emit(parts[item]) }
    }
    function emit(value) {
      sub(/[[:space:]]*#.*$/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      gsub(/^["'"'"']|["'"'"']$/, "", value)
      if (value != "") { print value }
    }
  ' "$1"
}

# ---------------------------------------------------------------------------
# The strategy readers (rule 8).
#
# `strategy:` is a job-level key, so job_property_record above finds it. What is
# needed beyond that is which keys sit INSIDE it, and only at its immediate
# child depth: `matrix:` and `max-parallel:` are siblings there, while an image
# name under `matrix:` sits deeper and is not a strategy key.
# ---------------------------------------------------------------------------

# strategy_keys <file> <first> <last> — `<line><TAB><key>` for every key at the
# immediate child indent of that job's `strategy:` block. Silent when the job
# declares no strategy at all, which is the common case and not a defect.
function strategy_keys() {
  local file="$1" first="$2" last="$3"
  local record start
  record="$(job_property_record "$file" "$first" "$last" "strategy")"
  [[ -z "$record" ]] && return 0
  start="${record%%$'\t'*}"
  awk -v start="$start" -v last="$last" '
    BEGIN { child_indent = -1 }
    NR < start { next }
    NR == start {
      match($0, /^[[:space:]]*/)
      strategy_indent = RLENGTH
      next
    }
    NR > last { exit }
    {
      stripped = $0
      sub(/^[[:space:]]+/, "", stripped)
      if (stripped == "" || substr(stripped, 1, 1) == "#") { next }
      match($0, /^[[:space:]]*/)
      indent = RLENGTH
      # The block ends at the first line back out at the strategy key depth or
      # shallower. Without this the walk would read the next job key as a
      # strategy key and report `runs-on` as a bound.
      if (indent <= strategy_indent) { exit }
      if (child_indent == -1) { child_indent = indent }
      if (indent != child_indent) { next }
      key = stripped
      sub(/:.*$/, "", key)
      print NR "\t" key
    }
  ' "$file"
}

# strategy_declares <file> <first> <last> <key> — 1 when that job's strategy
# block holds the key, else 0.
#
# A COMMENTED key is not one: the awk above drops a comment line before it reads
# anything else, and matrix-unbounded.yml carries `# max-parallel: 3` for
# exactly that reason. A reader keyed on the text calls that job bounded, and
# the rule then passes on the one file it exists for.
function strategy_declares() {
  local file="$1" first="$2" last="$3" want="$4"
  local line key
  while IFS=$'\t' read -r line key; do
    [[ -z "$key" ]] && continue
    if [[ "$key" == "$want" ]]; then
      printf '1'
      return 0
    fi
  done < <(strategy_keys "$file" "$first" "$last")
  printf '0'
}

# unbounded_matrix_jobs <file> — 1 line per job that fans out over a matrix and
# declares no ceiling on the fan. Silent when every matrix job is bounded, and
# silent on a workflow with no matrix at all.
function unbounded_matrix_jobs() {
  local file="$1"
  local job_name span first last out=""
  while IFS= read -r job_name; do
    [[ -z "$job_name" ]] && continue
    span="$(job_span "$file" "$job_name")"
    [[ "$span" == "0:0" ]] && continue
    first="${span%%:*}"
    last="${span##*:}"
    [[ "$(strategy_declares "$file" "$first" "$last" "matrix")" == "1" ]] || continue
    [[ "$(strategy_declares "$file" "$first" "$last" "max-parallel")" == "0" ]] || continue
    out="${out:+${out}
}${job_name}: strategy.matrix with no max-parallel"
  done <<< "$(job_names "$file")"
  printf '%s' "$out"
}

# matrix_jobs <file> — the name of every job that declares a strategy.matrix,
# 1 per line. The liveness reader for rule 8: the ratchet is keyed on this set,
# and over an empty one it is green on every repository.
function matrix_jobs() {
  local file="$1"
  local job_name span
  while IFS= read -r job_name; do
    [[ -z "$job_name" ]] && continue
    span="$(job_span "$file" "$job_name")"
    [[ "$span" == "0:0" ]] && continue
    if [[ "$(strategy_declares "$file" "${span%%:*}" "${span##*:}" "matrix")" == "1" ]]; then
      printf '%s\n' "$job_name"
    fi
  done <<< "$(job_names "$file")"
}

# image_set_defects <declared> <expected> — 1 line per disagreement between 2
# newline-separated sets, and silent when they hold the same names.
#
# Order-insensitive, because the matrix order is not the build order and never
# has to be. Duplicates ARE a defect: a matrix that names 1 image twice scans it
# twice and hides that it dropped another.
function image_set_defects() {
  local declared="$1" expected="$2"
  local name seen="" out=""

  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    if grep -qxF -- "$name" <<< "$seen"; then
      out="${out:+${out}
}named twice in the matrix: ${name}"
    else
      seen="${seen:+${seen}
}${name}"
    fi
    if ! grep -qxF -- "$name" <<< "$expected"; then
      out="${out:+${out}
}in the matrix and not in BUILD_ORDER: ${name}"
    fi
  done <<< "$declared"

  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    if ! grep -qxF -- "$name" <<< "$declared"; then
      out="${out:+${out}
}in BUILD_ORDER and NOT SCANNED: ${name}"
    fi
  done <<< "$expected"

  printf '%s' "$out"
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
# at 09:00 UTC with a 127, which is a notification nobody receives.
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
# 5. THE BASE-OS PIN — 1 home, and both Dockerfiles read it
# ===========================================================================
# The 2 Dockerfiles that FROM the base OS. The other 4 FROM an image of this
# repository, so they inherit the pin instead of repeating it.
PINNED_DOCKERFILES=(
  "base/Dockerfile"
  "cloud/Dockerfile"
)

# The ONE pin home. It was 2 — this row and the `ARG UBUNTU_BASE_REF=<digest>`
# block of base/Dockerfile — and a check here held the 2 to the same `sha256:`.
# base/Dockerfile went value-less with every other pin of the collapse, so the
# drift that check existed for is no longer expressible, and the rule that
# replaces it is the one that KEEPS it inexpressible: neither Dockerfile may
# declare a value for this pin. `${relative}_declares_the_pin_ARG_value_less`
# below is that rule, and it runs over BOTH of them.
ENV_PIN_HOME="versions.env"
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
# This stimulus is what keeps `${relative}_declares_the_pin_ARG_value_less`
# from passing vacuously below. That check passes on an EMPTY read, so a
# dockerfile_arg_value that had quietly stopped parsing would report every
# Dockerfile as value-less and never fire. Here the same reader is handed an
# ARG that DOES carry a default, and it has to come back with it.
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

  # The ARG is declared, and it declares NO VALUE. That pair of properties is
  # what makes the interpolation work off 1 home: the declaration above the
  # FROM is what lets `${UBUNTU_BASE_REF}` expand at all, and the absence of a
  # default is what keeps the expanded value the generated --build-arg out of
  # versions.env rather than a second digest spelled here.
  #
  # A default is not a harmless fallback, which is why this is a failure and
  # not a note. An `ARG UBUNTU_BASE_REF=sha256:...` re-added here builds
  # SUCCESSFULLY off its own value the moment the build arg is not passed — so
  # the base family and the cloud family would go on building, on 2 different
  # operating systems, with 1 number in versions.env saying otherwise and no
  # error anywhere. That drift had a test of its own until the collapse; this
  # is the check that makes the drift unreachable instead of watched.
  declared_value="$(dockerfile_arg_value "$file" "$PIN_NAME")"
  if [[ "$argument_line" != "0" && -z "$declared_value" ]]; then
    pass_check "${relative}_declares_the_pin_ARG_value_less"
  else
    fail_check "${relative}_declares_the_pin_ARG_value_less" \
      "want: 'ARG ${PIN_NAME}' with no '=' — the value arrives as a generated --build-arg" \
      "got:  '${declared_value:-<no ARG at all>}'" \
      "${ENV_PIN_HOME} is the ONE home of this digest. A default here is a second home that" \
      "the build silently prefers whenever the --build-arg is not passed, and a build that" \
      "succeeds on the wrong operating system reports nothing"
  fi
done

# -------- THE RULE, on the 1 pin home --------
env_pin="$(env_pin_value "$REPO_ROOT/$ENV_PIN_HOME" "$PIN_NAME")"

if [[ "$(digest_is_well_formed "$env_pin")" == "1" ]]; then
  pass_check "${ENV_PIN_HOME}_pins_a_full_sha256_digest"
else
  fail_check "${ENV_PIN_HOME}_pins_a_full_sha256_digest" \
    "want: ${PIN_NAME} matching ^sha256:[0-9a-f]{64}\$" \
    "got:  '${env_pin:-<no such pin>}'" \
    "a truncated digest reads as correct in a diff and dies at docker build, after the merge" \
    "— and this is the only home left, so nothing else holds the value up against it"
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
    "the reader of a 09:00 UTC failure needs both digests, or the next step is to run the read by hand"
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

# ===========================================================================
# 7. THE NOTIFY JOB — it reduces the verdict of every job it needs
# ===========================================================================
NOTIFY_GOOD="$WORKFLOW_FIXTURES/notify-job-good.yml"
NOTIFY_NO_VERDICT="$WORKFLOW_FIXTURES/notify-job-without-verdict.yml"
NOTIFY_NO_ALWAYS="$WORKFLOW_FIXTURES/notify-job-without-always.yml"
NOTIFY_PARTIAL_NEEDS="$WORKFLOW_FIXTURES/notify-job-partial-needs.yml"
NOTIFY_LATE_VERDICT="$WORKFLOW_FIXTURES/notify-job-verdict-after-close.yml"

# set_difference <a> <b> — the names of a that b does not hold, 1 per line.
function set_difference() {
  local name
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    grep -qxF -- "$name" <<< "$2" || printf '%s\n' "$name"
  done <<< "$1"
}

missing_fixtures=""
for fixture in "$NOTIFY_GOOD" "$NOTIFY_NO_VERDICT" "$NOTIFY_NO_ALWAYS" \
  "$NOTIFY_PARTIAL_NEEDS" "$NOTIFY_LATE_VERDICT"; do
  [[ -f "$fixture" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${fixture}"
done

if [[ -n "$missing_fixtures" ]]; then
  fail_check "counter_stimulus_notify_job_fixtures_exist" \
    "the fixtures this test proves its job readers with are absent:" \
    "$missing_fixtures"
else
  pass_check "counter_stimulus_notify_job_fixtures_exist"

  # -- the block reader: it finds the jobs, and it finds their edges --
  assert_equal "counter_stimulus_reads_the_3_jobs_of_the_fixture" \
    "scan base-currency notify" "$(job_names "$NOTIFY_GOOD" | tr '\n' ' ' | sed -e 's/ $//')" \
    "a reader that missed a job would report a needs: set as complete while it misses that job"

  good_span="$(job_span "$NOTIFY_GOOD" "notify")"
  good_first="${good_span%%:*}"
  good_last="${good_span##*:}"
  assert_equal "counter_stimulus_reports_no_span_for_a_job_that_does_not_exist" \
    "0:0" "$(job_span "$NOTIFY_GOOD" "no-such-job")"

  # -- the notifier-job detector, both directions --
  assert_equal "counter_stimulus_finds_the_job_that_calls_the_notifier" \
    "1" "$(job_calls_the_notifier "$NOTIFY_GOOD" "$good_first" "$good_last")"
  scan_span="$(job_span "$NOTIFY_GOOD" "scan")"
  assert_equal "counter_stimulus_does_not_read_the_scan_job_as_a_notify_job" \
    "0" "$(job_calls_the_notifier "$NOTIFY_GOOD" "${scan_span%%:*}" "${scan_span##*:}")" \
    "the span reader would otherwise be reading past the end of the job"

  # -- the condition detector, both directions --
  assert_equal "counter_stimulus_finds_the_always_condition_on_the_job" \
    "1" "$(runs_on_every_outcome "$(job_condition "$NOTIFY_GOOD" "$good_first" "$good_last")")"
  late_span="$(job_span "$NOTIFY_NO_ALWAYS" "notify")"
  assert_equal "counter_stimulus_reports_the_notify_job_with_no_condition" \
    "0" "$(runs_on_every_outcome "$(job_condition "$NOTIFY_NO_ALWAYS" "${late_span%%:*}" "${late_span##*:}")")" \
    "a job with no if: runs only when every job it needs succeeded, so it is skipped on the red night" \
    "and a step-level if: further down does not change that"
  # The single quotes are the point: this is a literal line of YAML, and the
  # ${{ }} inside it belongs to GitHub rather than to bash.
  # shellcheck disable=SC2016
  assert_equal "counter_stimulus_accepts_the_stricter_not_cancelled_spelling" \
    "1" "$(runs_on_every_outcome 'if: ${{ !cancelled() }}')" \
    "it runs on both outcomes as well, and it is the version that does not file an issue for a cancelled run"

  # -- the needs reader, both directions --
  assert_equal "counter_stimulus_reads_the_complete_needs_set" \
    "scan base-currency" "$(job_needs "$NOTIFY_GOOD" "$good_first" "$good_last" | tr '\n' ' ' | sed -e 's/ $//')"
  partial_span="$(job_span "$NOTIFY_PARTIAL_NEEDS" "notify")"
  assert_equal "counter_stimulus_reports_the_job_missing_from_needs" \
    "base-currency" \
    "$(set_difference "$(job_names "$NOTIFY_PARTIAL_NEEDS" | grep -vxF 'notify')" \
      "$(job_needs "$NOTIFY_PARTIAL_NEEDS" "${partial_span%%:*}" "${partial_span##*:}")")" \
    "that fixture needs scan only, so the currency job's result never reaches the reduction"

  # -- the verdict-step detector, all 3 directions --
  good_verdict="$(verdict_step_line "$NOTIFY_GOOD" "$good_first" "$good_last")"
  good_close="$(success_path_step_line "$NOTIFY_GOOD" "$good_first" "$good_last")"
  if [[ "$good_verdict" -ne 0 ]]; then
    pass_check "counter_stimulus_finds_the_verdict_reduction_step"
  else
    fail_check "counter_stimulus_finds_the_verdict_reduction_step" \
      "the fixture reduces needs.scan.result and needs.base-currency.result to this job's status," \
      "and the reader found no such step" \
      "a reader that cannot find a reduction that IS there reports every workflow as broken"
  fi
  if [[ "$good_close" -ne 0 ]]; then
    pass_check "counter_stimulus_finds_the_success_path_step"
  else
    fail_check "counter_stimulus_finds_the_success_path_step" \
      "the fixture closes the issue from a step guarded by success(), and the reader found none" \
      "the ordering clause below is vacuous while this reader answers 0"
  fi
  if [[ "$good_verdict" -ne 0 && "$good_close" -ne 0 && "$good_verdict" -lt "$good_close" ]]; then
    pass_check "counter_stimulus_reads_the_verdict_step_as_the_earlier_one"
  else
    fail_check "counter_stimulus_reads_the_verdict_step_as_the_earlier_one" \
      "want: the reduction at a line before the success-path step" \
      "got:  reduction at ${good_verdict}, success path at ${good_close}"
  fi

  no_verdict_span="$(job_span "$NOTIFY_NO_VERDICT" "notify")"
  assert_equal "counter_stimulus_reports_the_notify_job_with_no_verdict_step" \
    "0" "$(verdict_step_line "$NOTIFY_NO_VERDICT" "${no_verdict_span%%:*}" "${no_verdict_span##*:}")" \
    "that fixture carries the deleted step's text in a COMMENT, so a reader of prose calls it correct" \
    "without the step a red night closes the issue that reports it"

  late_verdict_span="$(job_span "$NOTIFY_LATE_VERDICT" "notify")"
  late_verdict="$(verdict_step_line "$NOTIFY_LATE_VERDICT" "${late_verdict_span%%:*}" "${late_verdict_span##*:}")"
  late_close="$(success_path_step_line "$NOTIFY_LATE_VERDICT" "${late_verdict_span%%:*}" "${late_verdict_span##*:}")"
  if [[ "$late_verdict" -ne 0 && "$late_close" -ne 0 && "$late_verdict" -gt "$late_close" ]]; then
    pass_check "counter_stimulus_reports_the_verdict_step_that_runs_after_the_close"
  else
    fail_check "counter_stimulus_reports_the_verdict_step_that_runs_after_the_close" \
      "want: the reduction at a line AFTER the success-path step, which is that fixture's defect" \
      "got:  reduction at ${late_verdict}, success path at ${late_close}" \
      "steps run in file order, so a close guarded by success() before the reduction closes on a red night"
  fi
fi

# THE LIVENESS CLAUSE. The ratchet below is keyed on "a scheduled workflow of
# more than 1 job", so it covers a workflow added tomorrow — and it is vacuous
# on a repository where the nightly lost its notify job.
for directory in "${WORKFLOW_DIRECTORIES[@]}"; do
  expected="${directory}/${NIGHTLY_WORKFLOW}"
  notify_jobs=""
  if [[ -f "$REPO_ROOT/$expected" ]]; then
    while IFS= read -r job_name; do
      [[ -z "$job_name" ]] && continue
      span="$(job_span "$REPO_ROOT/$expected" "$job_name")"
      [[ "$span" == "0:0" ]] && continue
      if [[ "$(job_calls_the_notifier "$REPO_ROOT/$expected" "${span%%:*}" "${span##*:}")" == "1" ]]; then
        notify_jobs="${notify_jobs:+${notify_jobs}
}${job_name}"
      fi
    done <<< "$(job_names "$REPO_ROOT/$expected")"
  fi
  if [[ -n "$notify_jobs" ]]; then
    pass_check "${expected}_declares_a_job_that_notifies"
  else
    fail_check "${expected}_declares_a_job_that_notifies" \
      "no job of this file names ${NOTIFIER}, or the file is absent" \
      "the jobs found were:" "$(job_names "$REPO_ROOT/$expected" 2>&1 | tr '\n' ' ')" \
      "every clause below is keyed on that job, so with none they all pass over an empty set"
  fi
done

# THE RATCHET.
while IFS= read -r relative; do
  [[ -z "$relative" ]] && continue
  file="$REPO_ROOT/$relative"

  all_jobs="$(job_names "$file")"
  job_total="$(grep -c . <<< "$all_jobs")" || job_total=0

  # A workflow of 1 job is the other correct shape: the notifier step sits in
  # the job that does the work, guarded by if: failure(), and rule 1 above is
  # the whole rule for it. There is no verdict to reduce, because there is no
  # other job.
  [[ "$job_total" -lt 2 ]] && continue

  while IFS= read -r job_name; do
    [[ -z "$job_name" ]] && continue
    span="$(job_span "$file" "$job_name")"
    [[ "$span" == "0:0" ]] && continue
    first="${span%%:*}"
    last="${span##*:}"
    [[ "$(job_calls_the_notifier "$file" "$first" "$last")" == "1" ]] || continue

    condition="$(job_condition "$file" "$first" "$last")"
    if [[ "$(runs_on_every_outcome "$condition")" == "1" ]]; then
      pass_check "${relative}_${job_name}_runs_on_every_outcome"
    else
      fail_check "${relative}_${job_name}_runs_on_every_outcome" \
        "the job-level condition is: ${condition:-<none>}" \
        "want: always(), or the stricter !cancelled()" \
        "a notify job with any other condition is SKIPPED on the night it exists for," \
        "and a skipped job files nothing and closes nothing"
    fi

    declared_needs="$(job_needs "$file" "$first" "$last")"
    other_jobs="$(grep -vxF -- "$job_name" <<< "$all_jobs")" || other_jobs=""
    not_needed="$(set_difference "$other_jobs" "$declared_needs")"
    needed_ghosts="$(set_difference "$declared_needs" "$other_jobs")"
    if [[ -z "$not_needed" && -z "$needed_ghosts" ]]; then
      pass_check "${relative}_${job_name}_needs_every_other_job"
    else
      fail_check "${relative}_${job_name}_needs_every_other_job" \
        "jobs of this workflow that the notify job does not need:" "${not_needed:-<none>}" \
        "names in needs: that are not jobs of this workflow:" "${needed_ghosts:-<none>}" \
        "needs: is:" "$(tr '\n' ' ' <<< "$declared_needs")" \
        "a job it does not need cannot fail it, its result never reaches the reduction step," \
        "and the notify job does not even wait for it to finish"
    fi

    verdict_line="$(verdict_step_line "$file" "$first" "$last")"
    close_line="$(success_path_step_line "$file" "$first" "$last")"
    if [[ "$verdict_line" -ne 0 ]]; then
      pass_check "${relative}_${job_name}_reduces_the_needed_verdicts"
    else
      fail_check "${relative}_${job_name}_reduces_the_needed_verdicts" \
        "no step of this job reads needs.<job>.result, compares it against success," \
        "and can fail the job — the 3 clauses together" \
        "the job runs under a condition that runs it on every outcome, so its own steps all" \
        "succeed whatever the jobs above did: failure() is false and success() is TRUE on the" \
        "reddest possible night, and the step that CLOSES the issue is the one that fires"
    fi

    if [[ "$verdict_line" -eq 0 ]]; then
      fail_check "${relative}_${job_name}_reduces_before_the_success_path" \
        "there is no reduction step to place, so nothing guards the success path"
    elif [[ "$close_line" -eq 0 ]]; then
      pass_check "${relative}_${job_name}_reduces_before_the_success_path"
    elif [[ "$verdict_line" -lt "$close_line" ]]; then
      pass_check "${relative}_${job_name}_reduces_before_the_success_path"
    else
      fail_check "${relative}_${job_name}_reduces_before_the_success_path" \
        "the reduction is at line ${verdict_line} and a step guarded by success() is at line ${close_line}" \
        "steps run in file order, and until the reduction has run nothing in this job has failed," \
        "so success() is true and the issue is closed on a red night"
    fi
  done <<< "$all_jobs"
done <<< "$scheduled"

# ===========================================================================
# 8. THE SCAN MATRIX — it is BUILD_ORDER, and not a 5th copy of it
# ===========================================================================
MATRIX_FLOW_FIXTURE="$WORKFLOW_FIXTURES/matrix-flow.yml"
MATRIX_BLOCK_FIXTURE="$WORKFLOW_FIXTURES/matrix-block.yml"

missing_fixtures=""
for fixture in "$MATRIX_FLOW_FIXTURE" "$MATRIX_BLOCK_FIXTURE"; do
  [[ -f "$fixture" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${fixture}"
done

if [[ -n "$missing_fixtures" ]]; then
  fail_check "counter_stimulus_matrix_fixtures_exist" \
    "the fixtures this test proves its matrix reader with are absent:" \
    "$missing_fixtures"
else
  pass_check "counter_stimulus_matrix_fixtures_exist"

  assert_equal "counter_stimulus_reads_the_flow_form_matrix" \
    "alpha beta gamma" "$(matrix_images "$MATRIX_FLOW_FIXTURE" | tr '\n' ' ' | sed -e 's/ $//')" \
    "the quotes come off, the trailing comment comes off, and the image: input of the second job" \
    "is not under a matrix: key and is not a scan target"
  assert_equal "counter_stimulus_reads_the_block_form_matrix_and_skips_the_commented_entry" \
    "alpha beta gamma" "$(matrix_images "$MATRIX_BLOCK_FIXTURE" | tr '\n' ' ' | sed -e 's/ $//')" \
    "YAML spells 1 list 2 ways, and a rewrite into the other form is a change no reviewer stops" \
    "a reader that saw 1 form would report an empty matrix on the day of that rewrite"

  assert_equal "counter_stimulus_leaves_2_equal_image_sets_alone" \
    "" "$(image_set_defects "$(printf 'beta\nalpha\n')" "$(printf 'alpha\nbeta\n')")" \
    "the comparison is order-insensitive: the matrix order is not the build order and never has to be"
  assert_contains "counter_stimulus_reports_the_image_that_is_not_scanned" \
    "$(image_set_defects "$(printf 'alpha\n')" "$(printf 'alpha\nbeta\n')")" \
    "in BUILD_ORDER and NOT SCANNED: beta" \
    "this is the drill: narrow the matrix, and 1 image leaves the security gate"
  assert_contains "counter_stimulus_reports_the_image_the_matrix_invents" \
    "$(image_set_defects "$(printf 'alpha\ndelta\n')" "$(printf 'alpha\n')")" \
    "in the matrix and not in BUILD_ORDER: delta" \
    "an image this repository does not build cannot be scanned at :latest, so the job is red every night"
  assert_contains "counter_stimulus_reports_the_image_named_twice" \
    "$(image_set_defects "$(printf 'alpha\nalpha\n')" "$(printf 'alpha\nbeta\n')")" \
    "named twice in the matrix: alpha" \
    "a duplicate scans 1 image twice and hides that the count still looks right"
fi

# THE DECLARATION. Read out of a running shell rather than out of the text of a
# line: the value the shell ends up holding is the value ctl.sh builds with, and
# a line-reader agrees with a BUILD_ORDER that a later line rewrites.
#
# This is not a test reading its own expectation. The property is AGREEMENT
# between 2 declarations of 1 set, and the second declaration is the matrix. A
# literal list written here would be a THIRD copy, and the next narrowing would
# need 1 more file edited rather than being impossible.
build_order_errors="$(mktemp)"
build_order_status=0
build_order=""
build_order="$(CTL_SCRIPT="$REPO_ROOT/ctl.sh" bash -c '
  # No argv, so the dispatcher at the foot of ctl.sh takes its help path and
  # returns 0 instead of exiting 1 on an unknown command.
  set --
  source "$CTL_SCRIPT" > /dev/null
  printf "%s\n" "${BUILD_ORDER[@]}"
' 2> "$build_order_errors")" || build_order_status=$?
build_order_stderr="$(cat "$build_order_errors")"
rm -f "$build_order_errors"

if [[ "$build_order_status" -eq 0 && -n "$build_order" ]]; then
  pass_check "the_BUILD_ORDER_declaration_is_readable"
else
  fail_check "the_BUILD_ORDER_declaration_is_readable" \
    "sourcing ctl.sh and reading BUILD_ORDER exited ${build_order_status}" \
    "it printed:" "${build_order:-<nothing>}" \
    "stderr was:" "${build_order_stderr:-<nothing>}" \
    "with no declaration to compare against, every clause below passes over an empty set"
fi

# THE LIVENESS CLAUSE: the 2 copies of the nightly each declare a matrix. The
# ratchet is keyed on "a scanning workflow that declares a matrix", so a scan of
# 1 image is not forced to grow one — and a nightly that lost its matrix would
# otherwise leave the rule with nothing to judge.
for directory in "${WORKFLOW_DIRECTORIES[@]}"; do
  expected="${directory}/${NIGHTLY_WORKFLOW}"
  declared_images=""
  [[ -f "$REPO_ROOT/$expected" ]] && declared_images="$(matrix_images "$REPO_ROOT/$expected")"
  if [[ -n "$declared_images" ]]; then
    pass_check "${expected}_declares_a_scan_matrix"
  else
    fail_check "${expected}_declares_a_scan_matrix" \
      "this file is absent, or it declares no matrix: -> image: list" \
      "the whole point of the nightly is that it scans EVERY published image"
  fi
done

# THE RATCHET.
while IFS= read -r relative; do
  [[ -z "$relative" ]] && continue
  file="$REPO_ROOT/$relative"
  declared_images="$(matrix_images "$file")"
  [[ -z "$declared_images" ]] && continue
  [[ -z "$build_order" ]] && continue

  matrix_report="$(image_set_defects "$declared_images" "$build_order")"
  if [[ -z "$matrix_report" ]]; then
    pass_check "${relative}_scan_matrix_equals_BUILD_ORDER"
  else
    fail_check "${relative}_scan_matrix_equals_BUILD_ORDER" \
      "$matrix_report" \
      "the matrix is:      $(tr '\n' ' ' <<< "$declared_images")" \
      "BUILD_ORDER is:     $(tr '\n' ' ' <<< "$build_order")" \
      "BUILD_ORDER in ctl.sh is the 1 declaration of the published set. A matrix that says" \
      "anything else is a second declaration, and an image dropped from it leaves the security" \
      "gate with every other check in this repository still green"
  fi
done <<< "$scanning"

# ===========================================================================
# 9. THE MATRIX FAN-OUT — a scheduled matrix declares its ceiling
# ===========================================================================
BOUNDED_FIXTURE="$WORKFLOW_FIXTURES/matrix-bounded.yml"
UNBOUNDED_FIXTURE="$WORKFLOW_FIXTURES/matrix-unbounded.yml"

missing_fixtures=""
for fixture in "$BOUNDED_FIXTURE" "$UNBOUNDED_FIXTURE"; do
  [[ -f "$fixture" ]] || missing_fixtures="${missing_fixtures:+${missing_fixtures}
}${fixture}"
done

if [[ -n "$missing_fixtures" ]]; then
  fail_check "counter_stimulus_bounded_matrix_fixtures_exist" \
    "the fixtures this test proves its strategy reader with are absent:" \
    "$missing_fixtures"
else
  pass_check "counter_stimulus_bounded_matrix_fixtures_exist"

  # -- the reader finds the shape it claims to read --
  bounded_span="$(job_span "$BOUNDED_FIXTURE" "scan")"
  assert_equal "counter_stimulus_reads_the_3_strategy_keys_and_not_the_matrix_entries" \
    "fail-fast max-parallel matrix" \
    "$(strategy_keys "$BOUNDED_FIXTURE" "${bounded_span%%:*}" "${bounded_span##*:}" | cut -f2 | tr '\n' ' ' | sed -e 's/ $//')" \
    "the image list under matrix: sits deeper and is not a strategy key" \
    "a reader that returned it would report 'image' as a bound and pass every file"

  notify_span="$(job_span "$BOUNDED_FIXTURE" "notify")"
  assert_equal "counter_stimulus_reads_no_strategy_key_for_a_job_that_has_none" \
    "" "$(strategy_keys "$BOUNDED_FIXTURE" "${notify_span%%:*}" "${notify_span##*:}")" \
    "the walk must stop at the end of the job it was given, not run on into the next one"

  # -- the matrix detector, both directions --
  assert_equal "counter_stimulus_finds_the_job_that_fans_out" \
    "scan" "$(matrix_jobs "$BOUNDED_FIXTURE" | tr '\n' ' ' | sed -e 's/ $//')" \
    "the notify job declares no matrix, and the rule must never demand a bound of it"

  # -- THE RULE's detector, both directions --
  assert_equal "counter_stimulus_leaves_the_bounded_matrix_alone" \
    "" "$(unbounded_matrix_jobs "$BOUNDED_FIXTURE")" \
    "that job declares max-parallel; a detector that reports it forbids its own fix"

  unbounded_report="$(unbounded_matrix_jobs "$UNBOUNDED_FIXTURE")"
  assert_contains "counter_stimulus_reports_the_matrix_with_no_ceiling" \
    "$unbounded_report" "scan: strategy.matrix with no max-parallel" \
    "that fixture carries the deleted bound in a COMMENT, so a reader of prose calls it bounded"
  assert_not_contains "counter_stimulus_does_not_report_the_bounded_job_beside_it" \
    "$unbounded_report" "bounded-sibling" \
    "that job has the same matrix WITH its ceiling; a detector that reports both names neither"
fi

# THE LIVENESS CLAUSE. The ratchet below is keyed on "a scheduled job that fans
# out over a matrix", so it covers a scheduled workflow added tomorrow — and it
# is vacuous on a repository where the nightly lost its matrix. That set is
# non-empty because both copies of the nightly scan every published image.
for directory in "${WORKFLOW_DIRECTORIES[@]}"; do
  expected="${directory}/${NIGHTLY_WORKFLOW}"
  fanning_jobs=""
  [[ -f "$REPO_ROOT/$expected" ]] && fanning_jobs="$(matrix_jobs "$REPO_ROOT/$expected")"
  if [[ -n "$fanning_jobs" ]]; then
    pass_check "${expected}_declares_a_job_that_fans_out_over_a_matrix"
  else
    fail_check "${expected}_declares_a_job_that_fans_out_over_a_matrix" \
      "this file is absent, or no job of it declares a strategy.matrix" \
      "the jobs found were:" "$(job_names "$REPO_ROOT/$expected" 2>&1 | tr '\n' ' ')" \
      "the rule below is keyed on that set, so with none it passes over nothing"
  fi
done

# THE RATCHET. Keyed on the schedule trigger, like rule 1.
while IFS= read -r relative; do
  [[ -z "$relative" ]] && continue
  file="$REPO_ROOT/$relative"

  unbounded="$(unbounded_matrix_jobs "$file")"
  if [[ -z "$unbounded" ]]; then
    pass_check "${relative}_every_scheduled_matrix_is_bounded"
  else
    fail_check "${relative}_every_scheduled_matrix_is_bounded" \
      "$unbounded" \
      "these runs are on the homelab pool now, and a matrix with no ceiling starts every leg at once" \
      "each leg unpacks a multi-GB image onto the node's own filesystem, so the fan-out ends in" \
      "'No space left on device' — a red that says nothing about the image it was asked to judge —" \
      "and it takes every other pod on that node with it, including another repository's validate" \
      "fix: declare 'max-parallel: <n>' beside 'matrix:' under this job's strategy" \
      "a scheduled run has no author watching it, so nobody is there to cancel the fan-out"
  fi
done <<< "$scheduled"

test_summary "$TEST_NAME"
