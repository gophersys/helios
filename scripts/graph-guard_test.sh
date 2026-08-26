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
#   clause 4  the REAL projects remain  — over-broad .nxignore must red, both floor and anchors
#   clause 5  no fixture-rooted project — plant into EVERY one of the 6 vocabulary directories
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
  expect_red "clause 5 catches a fixture in '${d}' (vocabulary entry $(( $(printf '%s\n' "${vocabulary_dirs[@]}" | grep -nxF -- "$d" | cut -d: -f1) )) of ${#vocabulary_dirs[@]})" \
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

# CLAUSE 4 — the real projects must still be there, proven in BOTH directions. This is the hole
# round 6 found: `.nxignore` was checked one way only, so a pattern could be added that excluded 16
# REAL projects and every clause stayed green while `nx affected` quietly stopped selecting them.
#
# BROAD, caught by the COUNT floor: `libs/go/**` takes the graph 49 -> 33.
printf 'libs/go/**\n' >> "$nxignore"
run_guard
expect_red "clause 4 (count floor) REFUSES an .nxignore that excludes a whole subtree" "below the floor of"
git -C "$repository_root" checkout -- .nxignore

# NARROW, caught by the ANCHORS and invisible to the floor: excluding one project keeps the count at
# 48, comfortably above 45, so only a named anchor can see it. Without this the floor would look
# sufficient and the anchors would be decoration.
printf 'libs/typescript/primitives/**\n' >> "$nxignore"
run_guard
expect_red "clause 4 (anchors) REFUSES an .nxignore that excludes ONE real project the floor cannot see" "anchor project\(s\) missing or moved"
git -C "$repository_root" checkout -- .nxignore

# CLAUSE 2 — resolution. The message is asserted, not merely the exit status.
rm -rf "$selftest_root"
plant "dup-a" "graph-guard-selftest-dup"
plant "dup-b" "graph-guard-selftest-dup"
run_guard
expect_red "clause 2 REFUSES a duplicate project name, naming resolution" "does not resolve"
rm -rf "$selftest_root"

# CLAUSE 1 — `.nxignore` coverage. The only clause with anything to say on a tree carrying no fixture,
# which is the state of eden main. Restored by git, never by a backup file.
# Remove a real PATTERN line, named explicitly. An earlier probe used `head -n -1`, which stripped
# the file's trailing BLANK line, left all 36 patterns in place, and reported a false pass.
victim_pattern="${patterns[0]}"
# The scratch file goes INSIDE the probe tree, which sweep() and PREFLIGHT 3 both remove. Written
# beside `.nxignore` it was residue no sweep knew about, contradicting this file's own header.
mkdir -p "$selftest_root"
grep -vxF -- "$victim_pattern" "$nxignore" > "${selftest_root}/nxignore.mangled" \
  && cp "${selftest_root}/nxignore.mangled" "$nxignore"
run_guard
expect_red "clause 1 REFUSES a .nxignore missing the pattern ${victim_pattern}" "missing [0-9]+ required pattern"
git -C "$repository_root" checkout -- .nxignore

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
