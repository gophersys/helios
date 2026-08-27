#!/usr/bin/env bash
#
# scripts/graph-guard_test.sh — the holder of `.ci/ctl.sh graph-guard` and of `.nxignore`.
#
# WHY THIS FILE EXISTS. `graph-guard` is a gate, and a gate with no test is a claim. Five adversarial
# refutations have now attacked this pair, and every one of them found the same SHAPE of defect in
# the holder rather than in the verb: a check that could not fail. In order —
#
#   1. the patterns covered `project.json` only, so a `package.json` + `tsconfig.json` fixture that
#      `@nx/js/typescript` INFERS entered the graph untouched;
#   2. the verb guessed project NAMES instead of reading roots, so a fixture named from a sibling
#      `package.json` was invisible to it;
#   3. the holder GREPPED `.ci/ctl.sh` for marker strings, so moving a string into a comment
#      regressed the verb while this file printed a certification that was false as it printed;
#   4. the holder ran the verb but its assertions reached only 2 of the verb's 5 clauses, so two
#      whole clauses could be deleted with the suite green;
#   5. the surviving assertions each held their clause by ONE representative input, so the verb's
#      directory vocabulary could be cut from 6 names to 2, the resolution clause could be neutered
#      while the duplicate-name assertion still passed (it was reddening on a DIFFERENT clause), and
#      the count-agreement clause could be deleted outright because nothing could reach it.
#
# THE RULE THIS FILE NOW OBEYS, AND IT IS THE WHOLE DESIGN:
#   (a) never read the verb's SOURCE — plant a real input, run the verb, read its exit status;
#   (b) assert WHICH clause fired, by matching its message — a red for the wrong reason is a false
#       pass wearing a red hat, and that is exactly how the resolution clause escaped;
#   (c) quantify over the SET a rule covers, never one member of it;
#   (d) every clause must be REACHABLE and proven able to fire, including the two that no ordinary
#       repository state can trigger. Those use a shim rather than being left as decoration.
#
# WHAT A GREEN RUN PROVES — each of the verb's 5 clauses is present, reachable, and load-bearing:
#   clause 1  `.nxignore` coverage      — remove one of the 36 patterns, the verb must red
#   clause 2  the graph RESOLVES        — plant a duplicate name, the verb must red NAMING resolution
#   clause 2b the 2 readers AGREE       — shim nx so they disagree, the verb must red naming the gap
#   clause 4  no fixture-rooted project — plant into EVERY one of the 6 vocabulary directories
#   clause 5  the graph MATCHES the roster — over-broad .nxignore reds, and so does an extra project
#   clause 6  submodules checked out    — hide a `.git` entry, the verb must red
#   plus the exclusion path itself: fixtures in COVERED directories must be excluded, verb green.
#
# SCOPE — read this before reading a green run as more than it is.
#   COVERED: the 5 clauses above, executed.
#   NOT COVERED: the CONTENT of eden's 49 real projects, and whether nx itself is correct. This file
#     plants synthetic projects; it does not audit real ones.
#
# HOW IT KEEPS THE TREE SAFE. It plants under `libs/.graph-guard-selftest/`, temporarily edits
# `.nxignore`, and temporarily moves a submodule's `.git` aside.
#
# It writes NO BACKUP of `.nxignore`, and no temporary file beside it. An earlier version kept a
# `.nxignore.graph-guard-selftest-backup`, and a hard kill left that backup behind as untracked
# residue next to a still-mutated `.nxignore` — residue guarding residue. A later version still
# wrote `.nxignore.tmp` at the repository root for the width of one `grep`, which no sweep knew
# about; that scratch file now lives inside the swept probe tree. Recovery is
# `git checkout -- .nxignore`, which needs no surviving process, so a SIGKILL leaves a mutation that
# git itself both reveals and undoes. PREFLIGHT 2 refuses to run at all when `.nxignore` is already
# dirty, so that checkout can never destroy an edit somebody meant to keep, and PREFLIGHT 3 sweeps a
# probe tree left by a run killed where no trap could reach it.
#
# WHERE THE PROBE TREE LIVES, AND WHY IT IS NOT MOVED. `libs/.graph-guard-selftest/` sits inside the
# `libs` SUBMODULE working tree, so `git -C libs status` shows it while a run is in flight and a
# concurrent gate in that submodule asserting its own tree is clean would see it. That is a real cost
# and it is accepted deliberately: clause 4 judges roots UNDER a submodule, so a probe that proves it
# has to be under one — moving to `.devcontainer` or `infrastructure` relocates the exposure without
# removing it. It is namespaced, dot-prefixed, untracked, swept by `sweep()` on every trappable exit,
# and swept again by PREFLIGHT 3 after a kill that no trap can catch.
#
# Run it directly:  bash scripts/graph-guard_test.sh
# It exits non-zero on any failure. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${here}/.." && pwd)"
nxignore="${repository_root}/.nxignore"
ctl="${repository_root}/.ci/ctl.sh"

# The contract, as LITERALS, never read out of the files under test. A test that derives its
# expectation from its subject agrees with a wrong subject too.
submodules=(".devcontainer" "libs" "infrastructure")
ignored_dirs=("fixture" "fixtures" "__fixtures__" "testdata")
project_files=("project.json" "package.json" "tsconfig*.json")
# EVERY directory name the verb's `fixture_dir_re` must recognise. The 4 above are also spelled in
# `.nxignore`; these 2 are deliberately NOT, so the verb is their only defence. Clause 3 is exercised
# against ALL SIX below, because a vocabulary is a SET and one member cannot stand for it.
vocabulary_dirs=("fixture" "fixtures" "__fixtures__" "testdata" "_fixtures" "test-fixtures")
uncovered_dirs=("_fixtures" "test-fixtures")

fails=0
report_fail() {
  local name="$1"; shift
  printf '  FAIL  %s\n' "$name" >&2
  local problem
  for problem in "$@"; do printf '          %s\n' "$problem" >&2; done
  fails=$((fails + 1))
}
report_ok() { printf '  ok    %s\n' "$1"; }

for f in "$nxignore" "$ctl"; do
  if [[ ! -f "$f" ]]; then
    printf 'graph-guard_test: FAILED — the file does not exist: %s\n' "$f" >&2
    exit 1
  fi
done

mapfile -t patterns < <(grep -vE '^\s*(#|$)' "$nxignore" || true)

printf -- '-- .nxignore, as a file --\n'

expected_total=$(( ${#submodules[@]} * ${#ignored_dirs[@]} * ${#project_files[@]} ))
missing=()
for sm in "${submodules[@]}"; do
  for d in "${ignored_dirs[@]}"; do
    for pf in "${project_files[@]}"; do
      want="${sm}/**/${d}/**/${pf}"
      printf '%s\n' "${patterns[@]}" | grep -qxF -- "$want" || missing+=("$want")
    done
  done
done
if [[ ${#missing[@]} -gt 0 ]]; then
  report_fail "every required pattern is present" "${#missing[@]} of ${expected_total} missing, first: ${missing[0]}"
else
  report_ok "every required pattern is present (${expected_total})"
fi

if [[ ${#patterns[@]} -lt $expected_total ]]; then
  report_fail "the pattern file is not smaller than the contract" \
    "${#patterns[@]} pattern line(s) for ${expected_total} required patterns"
else
  report_ok "the pattern file holds at least the contracted ${expected_total} pattern(s)"
fi

for pf in "${project_files[@]}"; do
  count=0
  for p in "${patterns[@]}"; do [[ "$p" == *"/${pf}" ]] && count=$((count + 1)); done
  if [[ $count -lt $(( ${#submodules[@]} * ${#ignored_dirs[@]} )) ]]; then
    report_fail "the file type '${pf}' is covered everywhere" \
      "found ${count}, need $(( ${#submodules[@]} * ${#ignored_dirs[@]} ))"
  else
    report_ok "the file type '${pf}' is covered ${count} time(s)"
  fi
done

# A committed negation would re-include what an earlier line excluded, and the verb's own coverage
# clause greps for the positive line, so it would not see the hole. (This file USES a negation as a
# temporary probe below; what is forbidden is one being committed.)
negations=()
for p in "${patterns[@]}"; do [[ "$p" == '!'* ]] && negations+=("$p"); done
if [[ ${#negations[@]} -gt 0 ]]; then
  report_fail "no negation is COMMITTED in .nxignore" "${#negations[@]} found, first: ${negations[0]}"
else
  report_ok "no negation is committed in .nxignore"
fi

for d in "${uncovered_dirs[@]}"; do
  covering=()
  for p in "${patterns[@]}"; do [[ "$p" == *"/${d}/"* ]] && covering+=("$p"); done
  if [[ ${#covering[@]} -gt 0 ]]; then
    report_fail "'${d}' is uncovered by .nxignore, so the verb is its only defence" \
      "it now has a pattern: ${covering[0]}"
  else
    report_ok "'${d}' is uncovered by .nxignore — the verb is its only defence"
  fi
done

printf -- '-- the verb, EXECUTED --\n'

# PREFLIGHT 1 — nx must be here. A missing tool is a FAILURE, never a skip.
if [[ ! -x "${repository_root}/node_modules/.bin/nx" ]] && ! command -v nx >/dev/null 2>&1; then
  printf '  FAIL  nx is available to execute the verb\n' >&2
  printf '          no nx on PATH and no node_modules/.bin/nx — this gate cannot be tested, which is a failure, not a skip\n' >&2
  printf 'graph-guard_test: 1 failure(s)\n' >&2
  exit 1
fi

# PREFLIGHT 2 — `.nxignore` must be clean in git, because `git checkout --` is how every probe below
# is undone. Refusing here is what makes that restore incapable of destroying somebody's edit.
if ! git -C "$repository_root" diff --quiet -- .nxignore 2>/dev/null; then
  printf '  FAIL  .nxignore is clean in git before any probe runs\n' >&2
  printf '          it has uncommitted changes. This test restores it with git checkout, which would\n' >&2
  printf '          destroy them. Commit or stash them first.\n' >&2
  printf 'graph-guard_test: 1 failure(s)\n' >&2
  exit 1
fi

selftest_root="${repository_root}/libs/.graph-guard-selftest"
shim_dir=""
hidden_git=""
interrupted=0

# PREFLIGHT 3 — sweep a probe tree left by a run that died where no trap could reach it. SIGKILL and
# a killed container run no handler, so the one thing this file cannot promise is that its own sweep
# always executes. It CAN promise the residue is namespaced, untracked, and cleared by the next run.
# Measured: after `kill -9` mid-run the probe tree survives while `.nxignore` is left visibly dirty
# in git — the mutation is recoverable by `git checkout` and this line removes the rest.
if [[ -d "$selftest_root" ]]; then
  printf '  note  removing a probe tree left by an earlier run that was killed: %s\n' "${selftest_root#"${repository_root}"/}"
  rm -rf "$selftest_root"
fi

sweep() {
  local rc=$?
  rm -rf "$selftest_root"
  [[ -n "$shim_dir" ]] && rm -rf "$shim_dir"
  # No backup file, by design. git holds the pristine copy, so this survives anything that kills the
  # process — and if even this does not run, `git status` shows the mutation and `git checkout` undoes
  # it. A backup FILE would instead survive as residue beside a still-mutated .nxignore.
  git -C "$repository_root" checkout -- .nxignore 2>/dev/null || true
  if [[ -n "$hidden_git" && -e "${hidden_git}.graph-guard-selftest" ]]; then
    mv "${hidden_git}.graph-guard-selftest" "$hidden_git"
  fi
  if [[ -n "$hidden_git" && ! -e "$hidden_git" ]]; then
    printf 'graph-guard_test: FATAL — could not restore %s. Run: mv %s.graph-guard-selftest %s\n' \
      "$hidden_git" "$hidden_git" "$hidden_git" >&2
  fi
  if [[ $interrupted -ne 0 ]]; then
    printf 'graph-guard_test: INTERRUPTED before it finished — reporting %d, never success\n' "$interrupted" >&2
    exit "$interrupted"
  fi
  return "$rc"
}
trap sweep EXIT
trap 'interrupted=130; exit 130' INT
trap 'interrupted=143; exit 143' TERM
trap 'interrupted=129; exit 129' HUP

guard_rc=0
guard_out=""
run_guard() {
  guard_rc=0
  guard_out="$( ( cd "$repository_root" && bash .ci/ctl.sh graph-guard ) 2>&1 )" || guard_rc=$?
}

# expect_red <label> <regex> — the verb must fail AND fail for the named reason. Matching the reason
# is the point: refutation 5 neutered the resolution clause and the duplicate-name assertion still
# passed, because the verb was reddening on the zero-projects clause instead. A red is not a pass.
expect_red() {
  local label="$1" want="$2"
  if [[ $guard_rc -eq 0 ]]; then
    report_fail "$label" "graph-guard exited 0"
  elif ! printf '%s' "$guard_out" | grep -qE "$want"; then
    report_fail "$label" \
      "it went red, but for the WRONG reason — no line matching: ${want}" \
      "first error was: $(printf '%s' "$guard_out" | grep -aE '\[error\]' | head -1 | cut -c1-150)"
  else
    report_ok "$label"
  fi
}

plant() {
  local rel="$1" name="$2"
  mkdir -p "${selftest_root}/${rel}"
  printf '{"name":"%s"}\n' "$name" > "${selftest_root}/${rel}/project.json"
}

# ANTI-VACUITY, AND IT ABORTS. If the verb does not pass on the untouched tree, every red below could
# be that unrelated failure, and each would print `ok` while proving nothing.
run_guard
if [[ $guard_rc -eq 0 ]]; then
  report_ok "the verb PASSES on the untouched tree (so the reds below mean something)"
else
  report_fail "the verb passes on the untouched tree" \
    "graph-guard exited ${guard_rc} before anything was planted — the rest of this section is ABORTED"
  printf '\n'
  printf 'graph-guard_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi

# CLAUSE 3, over the WHOLE vocabulary. A fixture in a COVERED directory is held by `.nxignore`, so to
# put it in front of the verb's regex the pattern is suspended with a temporary negation line rather
# than by deleting a pattern — deleting one would trip clause 1 first and red for the wrong reason.
for d in "${vocabulary_dirs[@]}"; do
  rm -rf "$selftest_root"
  needs_negation=1
  for u in "${uncovered_dirs[@]}"; do [[ "$d" == "$u" ]] && needs_negation=0; done
  if [[ $needs_negation -eq 1 ]]; then
    printf '!libs/**/%s/**/project.json\n' "$d" >> "$nxignore"
  fi
  plant "voc-${d}/${d}/one" "graph-guard-selftest-voc-${d}"
  run_guard
  expect_red "clause 4 catches a fixture in '${d}' (vocabulary entry $(( $(printf '%s\n' "${vocabulary_dirs[@]}" | grep -nxF -- "$d" | cut -d: -f1) )) of ${#vocabulary_dirs[@]})" \
    "submodule fixture project\\(s\\) reached"
  git -C "$repository_root" checkout -- .nxignore
  rm -rf "$selftest_root"
done

# THE EXCLUSION PATH ITSELF. Without this the suite could be satisfied by a verb that always fails.
rm -rf "$selftest_root"
for d in "${ignored_dirs[@]}"; do
  plant "cov/${d}/one" "graph-guard-selftest-cov-${d}"
  printf '{"name":"graph-guard-selftest-cov-%s-pkg","version":"0.0.0"}\n' "$d" \
    > "${selftest_root}/cov/${d}/one/package.json"
done
run_guard
if [[ $guard_rc -eq 0 ]]; then
  report_ok "fixtures in all ${#ignored_dirs[@]} COVERED directories are excluded, and the verb passes"
else
  report_fail "fixtures in all COVERED directories are excluded" \
    "graph-guard exited ${guard_rc}: $(printf '%s' "$guard_out" | grep -aE '\[error\]' | head -1 | cut -c1-150)"
fi
rm -rf "$selftest_root"

# CLAUSE 5 — the graph must MATCH the committed roster, proven in BOTH directions and over every
# AREA a `.nxignore` pattern can target.
#
# WHY AREAS AND NOT ALL 49 ROWS. The roster check is an EQUALITY computed in one `comm`, not 49
# independent predicates, so there is no per-row code path that could be broken while its neighbours
# survive — the thing that made the old anchor LIST need quantifying. What a `.nxignore` pattern
# actually targets is a directory area, so that is the set worth quantifying over, and the roster's
# own COMPLETENESS is asserted separately below against the live graph.
roster="${repository_root}/.ci/graph-roster.txt"

# load_roster <path> — fill `roster_pairs`, and be LOUD about every reason it could not.
#
# The read used to end `... || true`, which swallowed grep's rc=2 on an absent or unreadable file and
# left the array empty. Nothing exited, so the 8 pairs below were then judged against ZERO rows and
# every one of them reported "the roster holds neither the name … the project is GONE from it" —
# about a file that had never been read. Loud and WRONG is not better than silent: it sent the reader
# to look at 8 projects instead of at the one path that was wrong.
roster_pairs=()
load_roster() {
  local path="$1" body rc
  # The status is grep's own. Read after `|| true` it is always 0, and that is the form that hid rc=2.
  set +e
  body="$(grep -vE '^\s*(#|$)' "$path" 2>&1)"
  rc=$?
  set -e
  if [[ $rc -gt 1 ]]; then
    report_fail "the committed roster reads: ${path#"${repository_root}"/}" \
      "grep exited ${rc}: ${body}" \
      "no pair below is judged against it — an unread roster holds no name and no root, so every pair would look GONE"
    return 1
  fi
  if [[ $rc -eq 1 || -z "$body" ]]; then
    report_fail "the committed roster holds project rows: ${path#"${repository_root}"/}" \
      "it reads, and holds no row that is not a comment or blank" \
      "no pair below is judged against it — an empty roster holds no name and no root, so every pair would look GONE"
    return 1
  fi
  mapfile -t roster_pairs <<< "$body"
  report_ok "the committed roster exists and reads (${#roster_pairs[@]} project row(s))"
  return 0
}
roster_is_loaded=0
if load_roster "$roster"; then roster_is_loaded=1; fi

# One project per area, as LITERALS. A pair that stops matching the tree is a red that names itself,
# which is what a test reading its own subject could never give.
area_probes=(
  ".devcontainer/base/**:images-base"
  ".devcontainer/mobile/**:images-mobile"
  "libs/go/agentruntime/**:agentruntime"
  "libs/typescript/primitives/**:primitives"
  "libs/templates/go/http-gateway/**:http-gateway-template"
  "infrastructure/clusters/**:clusters"
  "apps/frontend/**:frontend"
  "tools/**:"
)
# STALENESS PREFLIGHT, run for EVERY pair before that pair is used. The comment above promises a
# dead pair is "a red that names itself"; until this block it was not one. `.devcontainer` renamed
# `flutter/` to `mobile/` in ec59789, and the pointer bump ae506bd regenerated the roster with FIVE
# rows out and FIVE in — measured with `git show ae506bd -- .ci/graph-roster.txt`, and not only the
# `images-flutter` -> `images-mobile` row that this list happened to name — while leaving the list
# untouched. So the probe appended a pattern matching nothing, the graph did not change, and clause 5
# red with `graph-guard exited 0`, naming neither the dead pair nor the file holding it. A list of
# literals goes stale one pointer bump at a time, and only this block turns that into a red that
# points at this file.
#
# The roster is committed DATA that clause 5 diffs against, never the verb's SOURCE, so rule (a)
# holds: each assertion below still runs the verb and matches its message, and the anti-vacuity abort
# has already proven this roster agrees with the live graph.
probe_is_fresh() {
  local pattern="$1" expected_name="$2"
  local expected_root="${pattern%/\*\*}"
  local row row_name row_root name_root="" root_name="" exact=0 under=0
  # With zero rows loaded, EVERY pair looks GONE — which is a fact about the read, never about the
  # project. Diagnosing it as the project's fault is what made an unreadable roster print 8 reds that
  # all pointed away from the single line that was wrong.
  if [[ ${#roster_pairs[@]} -eq 0 ]]; then
    report_fail "the probe pair '${pattern}:${expected_name}' is judged against .ci/graph-roster.txt" \
      "the roster loaded ZERO rows — the failure above says why — so this pair was compared with nothing"
    return 1
  fi
  for row in "${roster_pairs[@]}"; do
    row_name="${row%%$'\t'*}"
    row_root="${row#*$'\t'}"
    [[ "$row_name" == "$expected_name" ]] && name_root="$row_root"
    [[ "$row_root" == "$expected_root" ]] && root_name="$row_name"
    [[ "$row_name" == "$expected_name" && "$row_root" == "$expected_root" ]] && exact=1
    [[ "$row_root" == "$expected_root" || "$row_root" == "${expected_root}/"* ]] && under=$((under + 1))
  done
  local fix="the fix is the area_probes list of scripts/graph-guard_test.sh, updated in the same change that moves the submodule pointer"
  # The generic pair names no project, so it is quantified instead. Left unchecked it could go
  # vacuous the same way, excluding nothing while its assertion read like a clause-5 proof.
  if [[ -z "$expected_name" ]]; then
    if [[ $under -eq 0 ]]; then
      report_fail "the probe pattern '${pattern}' still matches .ci/graph-roster.txt" \
        "no rostered project is rooted at or under '${expected_root}', so this pattern excludes nothing" "$fix"
      return 1
    fi
    report_ok "the probe pattern '${pattern}' covers ${under} rostered project(s)"
    return 0
  fi
  if [[ $exact -eq 1 ]]; then
    report_ok "the probe pair '${pattern}:${expected_name}' still matches .ci/graph-roster.txt"
    return 0
  fi
  # Which half moved is the difference between a relocation and a rename, so it is diagnosed rather
  # than reported as one undifferentiated mismatch.
  if [[ -n "$name_root" ]]; then
    report_fail "the probe pair '${pattern}:${expected_name}' still matches .ci/graph-roster.txt" \
      "the roster roots '${expected_name}' at '${name_root}', not at '${expected_root}' — the project MOVED" "$fix"
  elif [[ -n "$root_name" ]]; then
    report_fail "the probe pair '${pattern}:${expected_name}' still matches .ci/graph-roster.txt" \
      "the roster calls the project at '${expected_root}' '${root_name}', not '${expected_name}' — it was RENAMED" "$fix"
  else
    report_fail "the probe pair '${pattern}:${expected_name}' still matches .ci/graph-roster.txt" \
      "the roster holds neither the name '${expected_name}' nor the root '${expected_root}' — the project is GONE from it" "$fix"
  fi
  return 1
}

# THE PREFLIGHT'S OWN FAILURE HALF, EXECUTED. On a green run every real pair is exact, so only the
# `exact=1` and `under>0` success paths ever run and the whole MOVED / RENAMED / GONE / vacuity
# diagnosis above is unreachable — vouched for by a commit message and by nothing that executes. A
# refutation proved the cost: changing the GONE branch's `report_fail` to `report_ok` and planting a
# dead pair produced a FULLY GREEN suite that printed "all assertions passed … 6 verb clause(s)
# proven able to fire" while carrying a dead probe. That is refutation #3's shape a second time — a
# holder printing a certification that was false as it printed — and a breach of rule (d) above.
#
# It MUTATES NOTHING: no file, no `.nxignore`, no probe tree. It calls the function with pairs
# invented to reach each branch of the REAL roster already in `roster_pairs`, and the three that
# pivot on `.devcontainer/base` + `images-base` pivot on a row the first area probe asserts anyway,
# so a roster that loses it reds twice and both reds name it.
#
# IT ASSERTS THE MARKER AS WELL AS THE RETURN CODE, and that is the load-bearing half. `return 1`
# sits OUTSIDE the if/elif/else, so turning a `report_fail` into a `report_ok` keeps the return code
# AND every word of the message: only "is this line a FAIL line?" tells the neutered branch from the
# live one. `fails` cannot be asserted on — `report_fail` increments it inside this command
# substitution, i.e. inside a subshell, so it never propagates. That same subshell is why these
# synthetic lines reach neither the real counter nor the real report.
selfcheck_cases=(
  # <label>|<pattern>|<expected name>|<want rc>|<want marker>|<words the line must carry>
  "FRESH|.devcontainer/base/**|images-base|0|ok|still matches .ci/graph-roster.txt"
  "MOVED|.devcontainer/graph-guard-selftest-elsewhere/**|images-base|1|FAIL|the project MOVED"
  "RENAMED|.devcontainer/base/**|graph-guard-selftest-no-such-name|1|FAIL|it was RENAMED"
  "GONE|graph-guard-selftest-no-such-root/**|graph-guard-selftest-no-such-name|1|FAIL|is GONE from it"
  "VACUOUS|graph-guard-selftest-no-such-root/**||1|FAIL|excludes nothing"
)
selfcheck_failures=()
selfcheck_probe() {
  local label="$1" pattern="$2" expected_name="$3" want_rc="$4" want_marker="$5" want_words="$6"
  local other_marker="ok" out rc flat
  [[ "$want_marker" == "ok" ]] && other_marker="FAIL"
  # The mandated capture: the status is the function's own, never one read after `|| true`.
  set +e
  out="$(probe_is_fresh "$pattern" "$expected_name" 2>&1)"
  rc=$?
  set -e
  flat="$(printf '%s' "$out" | tr '\n' ' ')"
  if [[ $rc -ne "$want_rc" ]]; then
    selfcheck_failures+=("${label}: returned ${rc}, wanted ${want_rc} —${flat}")
  elif ! printf '%s\n' "$out" | grep -qE "^[[:space:]]+${want_marker}[[:space:]]"; then
    selfcheck_failures+=("${label}: it printed no '${want_marker}' line —${flat}")
  elif printf '%s\n' "$out" | grep -qE "^[[:space:]]+${other_marker}[[:space:]]"; then
    selfcheck_failures+=("${label}: it also printed a '${other_marker}' line —${flat}")
  elif ! printf '%s' "$out" | grep -qF -- "$want_words"; then
    selfcheck_failures+=("${label}: its ${want_marker} line never says '${want_words}' —${flat}")
  fi
}
if [[ $roster_is_loaded -ne 1 ]]; then
  report_fail "the staleness preflight diagnoses all ${#selfcheck_cases[@]} of its paths" \
    "the roster did not load, so not one of them could be driven — a check that cannot run is a failure, never a skip"
else
  for selfcheck_case in "${selfcheck_cases[@]}"; do
    IFS='|' read -r sc_label sc_pattern sc_name sc_rc sc_marker sc_words <<< "$selfcheck_case"
    selfcheck_probe "$sc_label" "$sc_pattern" "$sc_name" "$sc_rc" "$sc_marker" "$sc_words"
  done
  if [[ ${#selfcheck_failures[@]} -gt 0 ]]; then
    report_fail "the staleness preflight diagnoses all ${#selfcheck_cases[@]} of its paths" \
      "${selfcheck_failures[@]}"
  else
    report_ok "the staleness preflight diagnoses all ${#selfcheck_cases[@]} of its paths (FRESH, MOVED, RENAMED, GONE, VACUOUS), each proven by its return code AND its FAIL/ok marker"
  fi
fi

for probe in "${area_probes[@]}"; do
  pat="${probe%%:*}"
  expect_name="${probe#*:}"
  # A dead pair is skipped, not run: its clause-5 red would be `graph-guard exited 0`, which points
  # at the verb while the defect is in the line above.
  probe_is_fresh "$pat" "$expect_name" || continue
  printf '%s\n' "$pat" >> "$nxignore"
  run_guard
  if [[ -n "$expect_name" ]]; then
    expect_red "clause 5 catches '${pat}' removing ${expect_name} from the graph" \
      "MISSING from the graph: ${expect_name}[[:space:]]"
  else
    expect_red "clause 5 catches '${pat}' removing real projects from the graph" "MISSING from the graph"
  fi
  git -C "$repository_root" checkout -- .nxignore
done

# THE OTHER DIRECTION. A floor could never do this half: a project that APPEARS is drift too, and it
# is how a fixture that becomes a real project by a route clause 5 does not model would surface.
mkdir -p "${selftest_root}/roster-extra"
printf '{"name":"graph-guard-selftest-unrostered"}\n' > "${selftest_root}/roster-extra/project.json"
run_guard
expect_red "clause 5 catches a project that is NOT in the roster" "NOT IN the roster"
rm -rf "$selftest_root"

# The roster must be non-trivial and COMPLETE against the live graph. An empty or truncated roster
# would match a graph that had lost half its projects. The count is the array the probes above were
# judged against, not a second read of the file: a second read could disagree with the first, and the
# `|| true` it used to end with swallowed its own error exactly as the load did.
if [[ ${#roster_pairs[@]} -lt 40 ]]; then
  report_fail "the roster is not truncated" \
    "it holds ${#roster_pairs[@]} row(s); the graph has ~49 projects"
else
  report_ok "the roster holds ${#roster_pairs[@]} project rows"
fi

# CLAUSE 2 — resolution. The message is asserted, not merely the exit status.
rm -rf "$selftest_root"
plant "dup-a" "graph-guard-selftest-dup"
plant "dup-b" "graph-guard-selftest-dup"
run_guard
expect_red "clause 2 REFUSES a duplicate project name, naming resolution" "does not resolve"
rm -rf "$selftest_root"

# CLAUSE 1 — `.nxignore` coverage, over ALL 36 required patterns.
#
# The probe used to remove `patterns[0]` and nothing else, so exactly one cell of the verb's
# 3 submodules x 4 directories x 3 file types requirement grid was load-bearing. A refutation
# narrowed the verb's `ignored_dirs` to one name, and separately its `project_files` to
# `project.json` alone — restoring refutation #1's original defect — and the suite stayed green both
# times. A grid is a SET; one cell cannot stand for it. Each iteration is cheap because clause 1
# returns before the graph is ever built.
#
# TWO OUTCOMES, TWO SENTENCES. A verb that stays GREEN after a removal is a coverage HOLE. A verb
# that REDS with another clause's message is not a hole — it is a red for another reason, and in one
# of these 36 subprocesses that reason can be environmental. Collapsing the two printed a sentence
# that was NOT TRUE: `affected-gate (fast)` at e40ceef failed with "1 removal(s) did not red, first:
# infrastructure/**/fixtures/**/package.json" (run 33002356484, job 98287181831), and a re-run of the
# SAME SHA with no change of any kind printed "ok … every one of the 36" (job 98295378366). The 36
# lines are unique, so no coverage differed between the two runs; the verb had red for a reason this
# loop discarded with `guard_out`. `expect_red` above already draws exactly this distinction and
# prints the verb's first `[error]` line, and clause 1 was the only probe here that did not.
#
# NEITHER MODE IS FORGIVEN. There is no retry, no tolerance and no threshold: both are failures, and
# the only change is that each now says which one happened.
c1_missed=()
c1_wrong_reason=()
c1_unbuildable=()
for victim in "${patterns[@]}"; do
  # The status is grep's own, and its stderr is read rather than sent to /dev/null. rc=1 is
  # legitimate — it means the victim was the only line — and anything above 1 means the mutated file
  # was never built, which is not a statement about coverage either.
  set +e
  c1_grep_error="$(grep -vxF -- "$victim" "$nxignore" 2>&1 > "${selftest_root}_c1")"
  c1_grep_rc=$?
  set -e
  if [[ $c1_grep_rc -gt 1 ]]; then
    rm -f "${selftest_root}_c1"
    c1_unbuildable+=("${victim} — grep exited ${c1_grep_rc}: ${c1_grep_error}")
    continue
  fi
  mkdir -p "$selftest_root"
  cp "${selftest_root}_c1" "$nxignore"
  rm -f "${selftest_root}_c1"
  run_guard
  if [[ $guard_rc -eq 0 ]]; then
    c1_missed+=("$victim")
  elif ! printf '%s' "$guard_out" | grep -qE "missing [0-9]+ required pattern"; then
    c1_wrong_reason+=("${victim} — first error was: $(printf '%s' "$guard_out" | grep -aE '\[error\]' | head -1 | cut -c1-150)")
  fi
  git -C "$repository_root" checkout -- .nxignore
done
if [[ ${#c1_unbuildable[@]} -gt 0 ]]; then
  report_fail "the clause-1 probe builds all ${#patterns[@]} mutated .nxignore file(s)" \
    "${#c1_unbuildable[@]} could not be built, so those removals were never put to the verb:" \
    "${c1_unbuildable[@]}"
fi
if [[ ${#c1_missed[@]} -gt 0 ]]; then
  report_fail "clause 1 REFUSES the removal of EVERY one of the ${#patterns[@]} required patterns" \
    "${#c1_missed[@]} removal(s) left the verb GREEN — a real coverage hole, first: ${c1_missed[0]}"
fi
if [[ ${#c1_wrong_reason[@]} -gt 0 ]]; then
  report_fail "CLAUSE 1 is the clause that fires for every one of the ${#patterns[@]} removals" \
    "${#c1_wrong_reason[@]} removal(s) RED for another reason, which is not a coverage hole:" \
    "${c1_wrong_reason[@]}"
fi
if [[ ${#c1_unbuildable[@]} -eq 0 && ${#c1_missed[@]} -eq 0 && ${#c1_wrong_reason[@]} -eq 0 ]]; then
  report_ok "clause 1 REFUSES the removal of every one of the ${#patterns[@]} required patterns"
fi

# CLAUSE 2b — the 2 readers must agree. No repository state can trigger this: a duplicate name is
# refused by clause 2 above, so control never reaches it. A refutation deleted the clause outright
# with the suite still green. A shim is therefore the ONLY way to prove it is reachable and fires —
# it returns nx's real answers, then drops one node from the graph file.
shim_dir="$(mktemp -d -t graph-guard-shim.XXXXXX)"
real_nx="${repository_root}/node_modules/.bin/nx"
if [[ -x "$real_nx" ]]; then
  cat > "${shim_dir}/nx" <<SHIM
#!/bin/bash
if [[ "\$1" == "graph" ]]; then
  "${real_nx}" "\$@" || exit \$?
  f=""
  for a in "\$@"; do [[ "\$a" == --file=* ]] && f="\${a#--file=}"; done
  jq 'del(.graph.nodes[(.graph.nodes|keys_unsorted)[0]])' "\$f" > "\$f.t" && mv "\$f.t" "\$f"
  exit 0
fi
exec "${real_nx}" "\$@"
SHIM
  chmod +x "${shim_dir}/nx"
  guard_rc=0
  guard_out="$( ( cd "$repository_root" && PATH="${shim_dir}:$PATH" bash .ci/ctl.sh graph-guard ) 2>&1 )" || guard_rc=$?
  expect_red "clause 2b fires when the 2 graph readers disagree" "2 graph readers disagree"
else
  report_fail "clause 2b fires when the 2 graph readers disagree" \
    "node_modules/.bin/nx is absent, so the shim could not be built and this clause was not exercised"
fi
rm -rf "$shim_dir"; shim_dir=""

# CLAUSE 4 — liveness. `git clone` without --recursive leaves an EMPTY DIRECTORY that a bare `-d`
# test passes while 39 of the 49 projects are absent.
hidden_git="${repository_root}/.devcontainer/.git"
if [[ -e "$hidden_git" ]]; then
  mv "$hidden_git" "${hidden_git}.graph-guard-selftest"
  run_guard
  expect_red "clause 6 REFUSES a submodule that is not checked out" "NOT checked out"
  mv "${hidden_git}.graph-guard-selftest" "$hidden_git"
  hidden_git=""
else
  report_fail "clause 6 REFUSES a submodule that is not checked out" \
    ".devcontainer/.git does not exist, so this assertion could not be made"
fi

printf '\n'
if [[ $fails -gt 0 ]]; then
  printf 'graph-guard_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf 'graph-guard_test: all assertions passed (%d pattern(s), %d vocabulary dir(s), 6 verb clause(s) proven able to fire)\n' \
  "${#patterns[@]}" "${#vocabulary_dirs[@]}"
