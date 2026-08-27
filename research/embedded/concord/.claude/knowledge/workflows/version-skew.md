# Version skew — case studies from the v0.12 release window

Three incidents on 2026-05-22 → 2026-05-26 cost a combined ~8 hours
of release time. All three are the same shape: a change in one
artifact silently invalidated an assumption made by another, and the
failure manifested far from the root cause. This file is the
canonical training set for future agents.

Refresh this file when: a new version-skew incident happens (write it
up here as a case study). The auto-loaded rule
[`rules/version-coupling.md`](../../rules/version-coupling.md)
references this file for "why we have these contracts."

---

## Case study 1 — Silent autoconf KeyError → all tests skipped

### Symptom

A manufacturing run on panel `0AW2` reported `total=126, passed=0,
failed=0, errors=0` — every test marked SKIPPED, no failures, no
errors. The run finished in ~30 seconds (vs the expected ~45 minutes).
http-api dashboard showed status COMPLETED. Operator looked at the
dashboard and saw a green-ish row.

### Root cause

The test app's `tests/manufacturing/conftest.py` calls
`corekinect.test.autoconf.load_manifest()` to populate per-test
configuration from `concord.yaml`. The `fixture` → `testbed` rename
landed in corekinect between two releases. The active runner image
still had the old corekinect API. Inside `load_manifest`, accessing
`config["testbed"]` on a manifest that still wrote `fixture:` (or
vice-versa) raised `KeyError`. The function caught the exception,
logged a warning to stderr (not visible in the dashboard), and
**returned an empty dict** instead of propagating.

With no config, every `@pytest.fixture` that depended on
autoconf-provided values failed to resolve → pytest skipped each
test with "fixture not found" → the runner reported
`total=126, passed=0, failed=0, errors=0`.

### Failure shape

Three layers cooperated to make this silent:

1. **autoconf swallowed the exception.** A non-FileNotFoundError
   exception in `load_manifest` should NOT no-op — it should
   propagate.
2. **pytest skip-on-missing-fixture is permissive.** Skip ≠ failure.
   Skipped tests don't surface in the FAILED count.
3. **http-api's `report_finish` accepted the all-zero counts as a
   COMPLETED run** rather than flagging the obvious "126 tests, zero
   executions" pattern as suspect.

### Prevention layers (status)

- **(planned, P2 visibility batch — next phase)** corekinect
  `test.autoconf.load_manifest` will propagate non-`FileNotFoundError`
  exceptions instead of warn-and-no-op. Tests skipping with
  "fixture not found" because the manifest didn't load must hard-error.
- **(planned, P2 visibility batch)** http-api `report_finish` will
  detect `total > 0 AND passed = 0 AND failed = 0 AND errors = 0` and
  mark the run **FAILED** with
  `errorMessage = "All N tests skipped — no executions completed.
  Most likely cause: test package framework version mismatch."`
- **(planned, P2 visibility batch)** Frontend will display
  `run.errorMessage` in a clear top banner when status is FAILED
  AND add a dedicated "all skipped" state UI when execution counts
  are all zero but `total > 0`.

### What an agent should do when they see this shape

Symptoms that should ring this case-study's bell:

- `total > 0, passed = 0, failed = 0, errors = 0`
- "No tests ran" in pod logs
- "fixture 'X' not found" repeating for every test
- A run that finished in seconds when it should take minutes

What to do:

1. **Open the runner pod logs**:
   `kubectl -n <env> logs <pod-name> -c <container>` and look for
   `autoconf`, `load_manifest`, `KeyError`, or any warning that
   mentions a manifest field.
2. **Inspect the test package's `concord.yaml`** — does it match the
   corekinect version baked into the runner? Use the Phase D Layer 4
   gate's diagnostic:
   `python3 /app/check_framework_constraint.py /app/concord.yaml`.
3. **Re-upload the test package** with `corectl test refresh-framework
   && corectl test upload` if the runner shipped a newer corekinect.

### What NOT to do

- **Don't re-run the same package on the same runner** "to see if it
  was flaky." It wasn't flaky — it was structurally broken. You'll
  burn fixture time and get the same result.
- **Don't bump test timeouts.** This isn't a timing issue.
- **Don't add a `pytest.mark.skip(reason="known issue")` to silence
  the skip.** The skip IS the symptom; suppressing it makes the bug
  invisible.

---

## Case study 2 — Premature `success_patterns` in shell parsers

### Symptom

Two separate manufacturing tests failed in two consecutive days with
identical-looking errors:

- v0.12.1 → v0.12.2: `read_ext_flash` returned `data=[]`, error
  `"Failed to parse hex data from: []"`. Visual UART trace showed the
  hex dump arrived ~400ms AFTER the parser returned.
- v0.12.2 → v0.12.3: `erase_ext_flash` returned success immediately,
  but the chip was still mid-erase ~10s later when the next test
  tried to write. Erase had not actually completed.

### Root cause

Both shell helpers in `libs/python/corekinect/shells/comms_coproc.py`
and `shells/sigma5.py` used a `success_patterns=[...]` argument to
`ShellCommander.send()`. The patterns matched the firmware's
**prologue** lines, not the **completion** lines:

- `read_ext_flash` matched `"Reading N bytes from address: 0x..."`
  (the prologue the firmware emits BEFORE the read starts).
- `erase_ext_flash` matched `"Erasing flash..."` (the prologue before
  the erase finishes).

When `send()` saw the prologue, it returned. The next caller's
parser then read an empty (or in-flight) buffer.

### Failure shape

The same anti-pattern in two places, learned twice. Both fixes
followed the same template:

- Drop the prologue from `success_patterns`.
- Either wait for the shell prompt (`Mfg shell:`) OR include a
  content-anchored line (the hex-dump row, the "complete" line) in
  `success_patterns`.
- Bump default timeout from 30s → 120s for ops that are physically
  slow (`erase_ext_flash`).

### Prevention layers

- **(in place)** Code review checklist for new shell helpers:
  *"Your `success_patterns` MUST match a line that the firmware emits
  ONLY when the operation is complete. Prologue / echo / 'starting'
  lines are forbidden. If unsure, capture a real UART log and pick a
  line that appears only on the back side of the operation."*
- **(future)** Lint rule that scans `corekinect/shells/*.py` for
  `success_patterns=` and warns when the regex matches anything
  ending in `…ing` or `…starting` or `: 0x` (heuristic prologue
  markers). Not implemented yet.

### What an agent should do when they see this shape

Symptoms that should ring this case-study's bell:

- "Failed to parse hex data from: []" or any empty-list parse error
  from a shell helper.
- "Timeout waiting for prompt" when the operation visibly completed.
- A `success_patterns` regex that matches `…ing`, `…starting`, an
  address echo, or any line that the firmware emits BEFORE the
  operation finishes.
- A test that "started passing intermittently" after a timeout bump
  with no other changes.

What to do:

1. **Capture a real UART trace** of the failing operation. Don't
   guess at the cadence — every Zephyr shell command has the same
   shape (echo → prologue → response → prompt), but the
   prompt-vs-prologue spacing varies by command and load.
2. **Identify the line the firmware emits ONLY on completion** (often
   the prompt itself, or a `done` / `complete` line, or the
   content-anchored response line).
3. **Replace `success_patterns` with the completion-anchored pattern.**
4. **Audit the rest of the same file** for the same shape. Both
   `read_ext_flash` AND `erase_ext_flash` had the bug; one fix didn't
   imply the other.

### What NOT to do

- **Don't bump `timeout_s` first.** When `send()` returns early on a
  prologue match, `timeout_s` is irrelevant — the caller already
  thinks success happened. A timeout bump on an early-return parser
  changes nothing.
- **Don't add a `time.sleep(N)` after the call** as a workaround.
  That's a worse-than-useless flake mitigation; the real cadence
  varies and a sleep papers over it on one fixture and bites on
  another.
- **Don't xfail the test "until we figure it out."** The test is
  correctly reporting a real bug. The fix lives in the parser.

### Candidate audit list

Other shell helpers to check for the same anti-pattern:

- `lock_shell` — firmware emits an immediate echo on lock invocation.
- `debug_off` — same shape.
- Anything in `sigma5.py` / `comms_coproc.py` whose `success_patterns`
  matches a line ending in `:` or `…ing`.

---

## Case study 3 — Stale test package on new runner

### Symptom

After releasing v0.12.0 to production, the active manufacturing
session's runs continued to use the OLD test package
(`mfg-v1.4.2`) that had been uploaded before the corekinect rename.
Operators noticed "Pending" stage states that never resolved, then
the runs eventually showed all-skipped (case study #1 again, with a
different upstream cause).

### Root cause

A concord/corekinect release is a wheel publish + a platform deploy.
A test package change is a separate event: the engineer edits the
test app, runs `corectl test validate`, then `corectl test upload`,
which creates a `dev-<sha>-<epoch>` build that the resolver picks up.

The two paths are independent. After v0.12.0, the platform code
shipped the rename. The wheel was published. The runner image was
rebuilt with the new corekinect. But the **test package on disk in
MinIO was still the old one** — it had been uploaded against the
pre-rename corekinect API. The runner downloaded that stale package
and tried to run it against new corekinect → all-skipped (case study
#1's shape).

### Failure shape

The release flow had no enforcement that a corekinect change required
a test-package re-upload. The engineer needed to know:

> "I bumped corekinect. The test apps that import the renamed symbol
> need to be re-validated and re-uploaded."

…and that knowledge wasn't encoded anywhere.

### Prevention layers (Phase D, branch `chore/enforce-runner-corekinect-coupling`)

- **Layer 4** — runner-side framework-constraint gate. The runner
  reads `package.framework` from the downloaded `concord.yaml` and
  refuses to start pytest if the constraint isn't satisfied. Semver-
  compatible (PEP 440 SpecifierSet), not strict-SHA. Code:
  [`deploy/runner/check_framework_constraint.py`](../../deploy/runner/check_framework_constraint.py).
  Wired into `entrypoint.sh` between extract and pytest.
- The earlier layers (1, 2, 3) close adjacent gaps: runner-image
  freshness vs platform code (Layer 2), runner-rebuild gating at
  release time (Layer 3), and Nx affected-graph wiring (Layer 1).

### What an agent should do when they see this shape

Symptoms:

- A release just shipped. The active session is on a fixture and
  runs are still triggering against the OLD test package version.
- Pod logs show
  `[framework-gate] runner-side framework constraint violated`.
- Or: pod logs show silent skips (case study #1) immediately after a
  fresh runner image deploy.

What to do:

1. **Inspect the runner pod's framework gate output** — if it's there,
   the operator-facing remediation is already printed:
   `corectl test refresh-framework && corectl test upload`.
2. **Re-upload the affected test apps** from their working trees:
   `cd <test-app> && corectl test refresh-framework && corectl test upload`.
3. **If the bump was intentional and the constraint should be
   relaxed**: edit the test app's `concord.yaml`,
   `package.framework: ">=<old>,<new>"`, re-upload.
4. **If you need to keep tonight's run going on a stale package**:
   `CONCORD_FORCE_STALE_PACKAGE=1` on the runner pod. Logs a 6-line
   override banner.

### What NOT to do

- **Don't silently roll back the platform** to "fix" the
  stale-package error. The fix is to update the test package.
- **Don't manually edit `concord.yaml` in MinIO** to tighten or loosen
  the constraint — re-upload through corectl so audit trails and
  versioning are preserved.
- **Don't add `--force-no-runner-rebuild` to `/concord-release`** as a
  "shortcut" because the gate is "noisy." The gate fires for a
  reason. Read it.

---

## Case study 4 — Test-app scaffold drift

### Symptom

Across multiple concord releases (v0.10 → v0.12), the test apps'
framework artifacts — `.claude/rules/`, `.claude/skills/`,
`.devcontainer/`, and the corectl-shipped validator templates —
fell behind the canonical templates in `tools/corectl/templates/`.
No individual release "broke" any test app. Every release passed
Phase D Layers 1-4 cleanly. `corectl test validate` kept passing.
The runtime framework-constraint gate (Layer 4) kept letting test
packages run because constraints like `framework: ">=0.9.0"` are
permissive by design.

But the scaffold rotted. By 2026-05-26, sigma5_validation's
`.claude/skills/` was carrying obsolete skill files for tooling that
no longer existed in corectl, the devcontainer pinned a Zephyr SDK
two minor versions behind the canonical template, and the validator
schema in the local copy lagged a contract that the platform had
quietly tightened. A re-onboarding developer hit confusing failures
and the team had to spend an hour reconciling drift that had been
accumulating across ~15 releases.

### Root cause

The concord release flow had four enforcement layers for runtime
correctness (Phase D Layers 1-4) but **zero enforcement for
scaffold freshness**. Refresh was a separate manual step:
`cd <test-app> && corectl test update --apply && git push &&
corectl test upload`. Operators correctly reasoned that because the
runtime constraint was still satisfied, the refresh was "optional"
— so they deferred it. Each individual deferral was harmless; the
sum across ~15 releases was not.

A previous agent on 2026-05-26 night explicitly chose not to refresh
sigma5_validation, with the (technically correct) reasoning:

> "The framework constraint is still satisfied — at runtime, the
>  runner pod will load the package fine. The refresh can wait."

True at runtime. False as a maintenance discipline. By the next
release that tightened any contract, the cumulative scaffold drift
caused unrelated uploads to fail validate, and the team had to do
in one painful release what should have been ~15 cheap refreshes.

### Failure shape

Three things made this slow-burn skew possible:

1. **The runtime gates (Layers 1-4) only fire on runtime failure.**
   They are correct, but they only catch the moment the platform
   refuses to run. Scaffold drift is a maintenance failure, not a
   runtime failure.
2. **The release flow had no enumeration of test apps.** The
   `/concord-release` skill listed corekinect/corectl/protocols as
   things that needed downstream attention, but did not name the
   specific apps that needed re-uploading. Without a manifest, the
   operator had to remember which apps existed.
3. **The pre-release hook surfaced the coupling generically** ("test
   apps may need re-upload IF constraint changed") instead of
   naming every app and printing the remediation command.

### Prevention layers (Phase D Layer 5)

- **Layer 5** — `.claude/known-test-apps.yaml` is the authoritative
  registry of test apps that consume corekinect/protocols/corectl.
  Swept on every release by `/concord-release` Phase 11 (refresh +
  re-upload). Pre-release hook (Phase 0) enumerates the apps upfront
  so the operator sees the work before Phase 1. The release-impact
  auditor (Phase 0.5) cross-references each app's git log for
  `chore: refresh framework artifacts to corectl X.Y.Z` commits to
  flag drifted apps. Code:
  [`.claude/known-test-apps.yaml`](../../known-test-apps.yaml),
  [`.claude/hooks/pre-release`](../../hooks/pre-release),
  [`.claude/skills/concord-release/SKILL.md`](../../skills/concord-release/SKILL.md)
  Phase 11.
- Escape: `--skip-test-app-refresh` (loud-warn). Use only when the
  release truly has no scaffold impact.

### What an agent should do when they see this shape

Symptoms:

- `corectl test validate` failing on a test app that "wasn't touched"
  in the release range.
- Manual reconciliation of `.claude/rules/`, `.claude/skills/`,
  `.devcontainer/`, or validator schemas across multiple test apps
  in one painful sitting.
- The phrase "the constraint is still satisfied" appearing in the
  release notes as justification for skipping a refresh.

What to do:

1. **Sweep every entry in `.claude/known-test-apps.yaml` now.** Run
   the Phase 11 sequence for each app:
   `cd <path> && corectl test update --apply && corectl test validate
   && git push && corectl test upload`.
2. **Do not defer.** If the apps are drifted, the refresh produces a
   `chore: refresh framework artifacts to corectl X.Y.Z` commit. If
   they are not drifted, the refresh is a near-no-op (no scaffold
   changes, but the `corectl test upload` still uploads a fresh
   build, which is what the runner pod needs to pick up).
3. **Update the manifest** if you discover a test app that isn't
   listed. The discovery command is:
   `find /home/<user>/work/manufacturing /home/<user>/work/validation
   -maxdepth 3 -name concord.yaml`.

### What NOT to do

- **Do not defer the refresh** with the reasoning "the framework
  constraint is still satisfied." That is the exact phrase that
  motivated this case study — the reasoning is technically true at
  runtime but operationally toxic over many releases.
- **Do not mass-edit the test apps' `.claude/` directories by hand**
  to "catch them up." `corectl test update --apply` is the canonical
  refresh path; manual edits will drift again on the next release.
- **Do not remove entries from `.claude/known-test-apps.yaml`**
  because "we haven't released that product in a while." If the app
  exists in `manufacturing/` or `validation/`, it gets refreshed.
  If the app is genuinely end-of-life, remove it AND archive the
  repo in the same commit.
- **Do not use `--skip-test-app-refresh` to ship faster** on a
  release that touches corekinect, protocols, or corectl. That flag
  exists for releases that genuinely have no scaffold impact (e.g.,
  http-api-only hot-fix). Using it to skip a real sweep recreates
  exactly the drift this layer was built to prevent.

---

## Cross-cutting prevention pattern

All three case studies share a pattern: **silence is the failure
amplifier.** The original bug was a real bug (KeyError, prologue
match, missing re-upload). What turned each into hours of debugging
was a layer further down that converted the error into a soft no-op
(empty dict, early return success, all-skipped completion).

The Phase D enforcement layers all share the inverse design:

- **Fail loud at the gate**, with operator-friendly remediation in
  the error message itself.
- **Pass with a banner** when bypassed via the escape hatch — the
  bypass is visible in logs forever.
- **Pass inconclusively with a warning** when the gate can't actually
  evaluate (e.g., legacy image with no baked SHA). Better than a
  false positive.

When you add a new enforcement layer to concord, follow that shape.
When you find a NEW class of skew that the existing layers miss,
write it up here as a fourth case study, then design the layer.

## Related

- [`rules/version-coupling.md`](../../rules/version-coupling.md) —
  the auto-loaded contracts these case studies inform.
- [`deploy/runner.md`](../deploy/runner.md) — the Phase D enforcement
  design in detail.
- [`workflows/debugging.md`](debugging.md) — general debugging
  workflow that complements these case studies.
