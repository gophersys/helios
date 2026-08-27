# The `ctl.sh` standard

> **Class: CANONICAL.** This file states what the rule IS, not what somebody
> proposes it should be. Last judged true 2026-08-26. Owner: the eden rework
> program, blueprint §4.1 / §4.2, items P0-6 and P0-4.
>
> Every other file in `docs/` is a proposal. This one is not — see
> `docs/README.md`.

## Why this document exists at all

**The standard was already in force and written down nowhere.** Four
repositories — `eden`, `libs`, `infrastructure` and this one — each carried
their own copy of the same loggers and the same tool gate. Measured 2026-08-26:

| | loggers | `require_cmd` reads |
| --- | --- | --- |
| eden `.ci/ctl.sh:17-20` | 4, byte-identical | — |
| libs `.ci/ctl.sh:46-49` | 4, byte-identical | `type -t` (`:64-83`) |
| infrastructure `ctl.sh:26-28` | 3, byte-identical, no `log_success` | `command -v` (`:31-40`) |
| this repository, before this change | 3, byte-identical, no `log_success` | `command -v` |

A practice held in four copies is not a standard. It is four copies, and the
only thing they can do is drift — which two of the three rows above already
record. `libs` moved to `type -t` after measuring a real defect; the other two
stayed on `command -v` and nothing could report the difference.

So this document is **descriptive first**: it writes down what already runs,
names the file each rule lives in, and marks the two places where writing it
down forced a correction.

## What is CODE and what is PROSE

| | |
| --- | --- |
| `_ctl/standard.sh` | the PORTABLE core — C1, the four C4 loggers, the C5 tool gate, the I7 root finder. A consumer sources it and has them. |
| `_ctl/lib.sh` | this repository's own library. It SOURCES `_ctl/standard.sh` and adds the image verbs, the pin readers and the platform policy. |
| this file | every rule, including the ones no file can hand out — how a `main()` reads, where a section banner sits, what a target may be called. |

**Take the standard with one line, from a repository that has configured
nothing:**

```sh
source <path-to-submodule>/_ctl/standard.sh
require_cmd sqlc yq jq
ROOT="$(find_repository_root)" || exit 1
```

`_ctl/standard.sh` asserts NO input. That is the property the whole layer rests
on and it is why the core is a second file: `_ctl/lib.sh` opens with
`: "${PROJECT_ROOT:?…}"`, which is correct for a dispatcher of this repository
and fatal for a consumer that wants only the loggers —
`bash -c 'unset PROJECT_ROOT; source _ctl/lib.sh'` exits 1. C9 is not weakened
by the split: `lib.sh` keeps its assertion, because PROJECT_ROOT really is a
required input THERE.

**A home below is a FILE and a SYMBOL, deliberately not a line number.** A line
number in a document is a fact that goes stale on the next edit, and this
repository has paid for that class of error more than once. Where no symbol
exists to name — C1 is a pair of bare statements — the line is given and dated.

---

## C1–C10 — safety: how a script FAILS

Each rule was already in force in this repository when it was written down.

| # | Rule | Home |
| --- | --- | --- |
| C1 | `set -Eeuo pipefail` + `IFS=$'\n\t'` in **every** script — tests and fixtures included. Not only in the library: a sourced file that sets them does not protect a file that forgot. | `_ctl/standard.sh:28-29`, `_ctl/lib.sh:58-59`, `ctl.sh:15-16` (read 2026-08-26) |
| C2 | **No `EXIT` trap.** Measured: with the trap, a script that aborts on an unbound variable exits **0**; without it, 1. | `_ctl/lib.sh`, the "no EXIT trap, and that is deliberate" block |
| C3 | `main()` at the bottom, `case` dispatch, an unknown verb prints usage and exits 1, `main "$@"` is the last line, and `shift \|\| true` because `-u` makes a bare `shift` on an empty argv fatal. | `ctl.sh`, `main` |
| C4 | **Four `printf` loggers, never `echo`; defined once.** `log_info` and `log_success` to stdout, `log_warn` and `log_error` to stderr. A warning on stdout vanishes into a command substitution. | `_ctl/standard.sh`, `log_info` / `log_warn` / `log_error` / `log_success` |
| C5 | **FAIL-NOT-SKIP.** `require_cmd` exits **127** naming EVERY missing tool in one message. A check that opened zero files is a FAILURE, not a pass. | `_ctl/standard.sh`, `require_cmd`; zero-file failures at `ctl.sh:422` and in `cmd_test` / `cmd_validate`; `_ctl/tests/harness.sh`, `test_summary` |
| C6 | Guards fail **closed**, and every refusal names the offending VALUE and the REMEDY. `exit 1` with no value tells the operator nothing. | `_ctl/lib.sh`, `require_sanctioned_platforms` and `require_buildx_and_platforms` |
| C7 | Never let `errexit` + `pipefail` swallow a diagnostic. Capture the status explicitly and KEEP stderr. | `_ctl/lib.sh`, `require_buildx_and_platforms` — the `inspect_output="$(…)" \|\| bootstrap_status=$?` block, with the measurement beside it |
| C8 | Never pipe a haystack into `grep -q`. Use a herestring: `grep -q` closes the pipe on its first match, the writer takes EPIPE, and a TRUE assertion goes red at random. | `_ctl/tests/harness.sh`, `assert_contains` / `assert_not_contains` |
| C9 | A required input is asserted with `: "${VAR:?message}"` at the TOP, before any work. | `_ctl/lib.sh:72` and `image_main`; `_delta/components/agents.sh:21-23` |
| C10 | **Bodies live once**, in the library. A per-unit `ctl.sh` sets its data, sources, and dispatches. The dispatcher's executable bit is enforced. | `.claude/rules/00-identity.md` "A per-image `ctl.sh` is a thin dispatcher"; `ctl.sh`, `image_ctl`; `_ctl/tests/dispatcher-mode.test.sh` |

**C4 and C5 moved home in the change that wrote this document**, and both moves
are corrections rather than relocations:

- C4 was **three** loggers in `_ctl/lib.sh`. It is **four** in
  `_ctl/standard.sh`. `log_success` was the missing one — eden and libs both
  had it, this repository and infrastructure had neither, so a script moved
  between repositories gained or lost a logger silently.
- C5 read `command -v`, which reports a shell FUNCTION of the tool's name as a
  present tool. `gophersys/libs` `.ci/ctl.sh:64-83` measured what that costs: a
  `cictl()` injected by `export -f` made the affected tier print git's own
  `fatal:` and still exit **0** with "all 1 affected project(s) green". A gate
  reads the TOOL's exit status; a shell function has a BODY, and only its last
  command's status survives. `require_cmd` now accepts only what `type -t` calls
  kind `file` — an alias, a builtin, a keyword and a function are each refused.

**Two more rules belong here because they are the difference between a check and
a ritual:**

- **A comment carries a MEASUREMENT or a run id**, not a restatement of the
  line below it. `ctl.sh` cites "run 32111944450"; `images.yaml` carries the
  unpacked-byte measurement beside each `size_budget_gb`. A comment that says
  what the next line does is deleted, not written.
- **A test is hermetic by construction** — stub binaries first on `PATH`,
  `mktemp` trees of COPIES and never symlinks.
  `_ctl/tests/toolchain-parity.test.sh` and `_ctl/tests/stubs/` are the shape.

---

## I1–I7 — structure: how a script READS

These seven come from `iotea-archive`, whose 900-line operational scripts are
readable in a way this repository's are not yet. They are the half the safety
rules say nothing about.

| # | Rule | Home in iotea |
| --- | --- | --- |
| I1 | **`main()` reads as a table of contents** — each verb's body is a list of named function calls and nothing else. | `deploy/engine/production/ctl.sh:885-892` |
| I2 | **Section banners at a fixed ruler**, title right-aligned, each section opening with its own constants block. Nine of them carry 917 lines. | `deploy/engine/production/ctl.sh:164-166`; sections at `:14,:19,:43,:72,:164,:672,:724,:766,:869` |
| I3 | **Visibility sigils**: `lib_` exported · `_` file-private · `__` section-private. | `libs/bash/production.sh:6`; `deploy/engine/production/ctl.sh:407`, `:272` |
| I4 | **A three-line function header**: purpose / `Usage:` / `Returns:`. | `libs/bash/production.sh:20-23` |
| I5 | **Check-then-act idempotency in BOTH directions** — create and teardown mirror each other exactly, and a partially-applied release RESUMES rather than failing. | `deploy/engine/production/ctl.sh:50-59` vs `:61-70`; resume at `:564-572` |
| I6 | **Named timeout constants and a mandatory `--wait`** on every cluster call. No helm invocation in iotea omits it. | `deploy/engine/production/ctl.sh:27-29`, `:829-831` |
| I7 | **Root discovery by MARKER, never a counted `../../..`.** | `libs/bash/source.sh:3-25`, and see the correction below |

### I7 — what to take from iotea's finder, and what not to

`find_repository_root` in `_ctl/standard.sh` is the implementation. It walks up
from a start directory (default `$PWD`) to the nearest ancestor holding a `.git`
entry. On failure it prints NOTHING on stdout, writes a message to stderr, and
returns non-zero. All three halves are one contract: a finder that returns 0
having found nothing makes every `if [ $? -ne 0 ]` guard dead; one that prints a
path it never verified makes every path built from it wrong in silence; one that
refuses without a message leaves the operator a number and no next step.

Three properties are ours and not iotea's:

1. **The marker is `.git`, FILE or DIRECTORY.** `.git` is a directory in a normal
   clone and a FILE in a submodule and in a worktree, and this repository is
   checked out both ways at once. A reader written for one shape answers nothing
   in the other.
2. **The marker is never the monorepo.** iotea's finder looks for `nx.json`, and
   six of its nine `ctl.sh` hard-depend on it — an extracted script dies at
   "Could not find workspace root". A shared library must never require the
   monorepo (blueprint §4.2), which is the whole reason eden takes this one from
   a submodule that is present in a standalone clone by construction.
3. **The start directory is resolved with `cd -P` before the walk.** `$PWD` is
   the LOGICAL path, so under a symlinked ancestor `dirname` climbs a tree that
   does not exist.

**A REFUTED claim, kept because it changes what the rule says.** The blueprint
(§4.1, line 1064) states that `libs/bash/source.sh:18` "checks `$?` after an
assignment, so the guard can never fire". **That is wrong, and it was measured.**
On bash 5.2.21:

```
f() { return 3; }
V=$(f)        ; echo $?   # → 3   a PLAIN assignment DOES carry the status
g() { local W=$(f); echo $?; }
g                          # → 0   `local` reports its OWN status
```

Line 17 is `WORKSPACE_ROOT=$(find_workspace_root)` — a plain assignment — so the
guard at :18 fires correctly. The never-fires shape is `local V=$(false)`, and
that is the rule worth carrying: **never read `$?` after a `local`, a `declare`
or an `export` that assigns from a command substitution.** The bug class is
real; the cited line is not an instance of it.

The same rule in its other spelling: **never read `rc=$?` after `|| true` or
after a pipe.** `|| true` discards the status before `$?` reads it, `pipefail`
does not save that form, and no linter flags it. The correct shape is
`set +e; cmd; rc=$?; set -e`.

---

## V1–V5 — vocabulary: what a target is CALLED

C1–C10 and I1–I7 specify dispatch mechanics and say nothing about which verbs
exist. Two rules close that, and only the pair is sufficient: the first governs
a target's BODY, the second its NAME.

> **R-BODY — `ctl.sh` is the implementation; `nx` is a scheduler.** A
> `project.json` target contains exactly one command: `bash ./ctl.sh <verb>`.
> Logic in a `project.json` is a defect.

> **R-NAME — target names are drawn from ONE closed set**, and each project
> declares the subset its LANGUAGE CLASS owes. A project never invents a sixth
> name for an existing concept, and never declares a target it cannot really
> run.

| # | Verb | Means |
| --- | --- | --- |
| V1 | `validate` | the unit's own static gate. **Universal** — every class owes it, and it carries C5: an absent tool is exit 127, never a skip. |
| V2 | `build` | produce the unit's artifact |
| V3 | `test` | run the unit's own tests |
| V4 | `lint` | the language linter at the pinned version |
| V5 | `typecheck` | the type checker, where the language has one separate from the compiler |

| Class | Owes |
| --- | --- |
| Go module | `validate` · `build` · `test` · `lint` |
| TypeScript package | `validate` · `build` · `test` · `lint` · `typecheck` |
| bash / config unit | `validate` · `test` |

**Not all five everywhere, and the reason is FAIL-NOT-SKIP.** Requiring every
project to declare all five, exposing an inapplicable one as "a verb that exits
0 having said why", manufactures ~200 no-op targets whose steady-state output is
a green that ran nothing — the advisory-step pattern this whole standard bans.
It is also wrong as an nx mechanic: `nx affected -t <target>` SKIPS projects that
do not declare the target, so cross-project selection never needed universal
declaration. The property that matters — a lane knowing which projects OWE which
target — is carried by the class table alone.

Verbs outside the set are a unit's own business — `env`, `phase-gate`,
`lib-gate`, `release-check`, and this repository's `build`/`push`/
`verify-published`/`base-currency` — and nx may drive any of them. What R-NAME
forbids is a SECOND name for a concept the set already has.

**`ctl.sh` never calls `nx`.** iotea inverts this — `services/devenv/tests/ctl.sh:69-79`
calls `nx` from inside a script that `nx test devenv` invoked, with
`--skip-nx-cache` on every line. That is a cycle, and an admission that the
cache model does not fit a side-effecting target. nx owns cross-project
SEQUENCING; `ctl.sh` owns one unit's own work.

---

## What this document does NOT claim

- **It does not claim the three consumer repositories source the library.**
  `eden`, `libs` and `infrastructure` are separate repositories, and
  `.devcontainer` is a submodule OF eden rather than the other way round, so
  nothing here can reach them or check them. Each one taking
  `_ctl/standard.sh` is the rest of blueprint P0-6 and is not done.
- **It does not claim `ctl.sh verbs --check` exists.** The class table above is
  a rule with no enforcer yet; the enforcer walks eden's `project.json` set and
  belongs in eden.
- **A test cannot check prose.** `_ctl/tests/standard.test.sh` holds the CODE
  half — the five symbols, their streams, the 127, the marker walk, and the
  one-home rule in both directions — and deliberately checks nothing about this
  file. A test that grepped a document for its own headings would agree with a
  wrong document.
