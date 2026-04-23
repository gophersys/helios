# Stage File Format

ALL stage files MUST be named `stages/STAGE-NN.md` (capitalized).

## stages/STAGE-NN.md Template

Every stage file MUST follow this EXACT format for uniformity and analysis:

```markdown
# STAGE NN: <Name>

## Overview
| Field | Value |
|-------|-------|
| Stage | NN |
| Name | <descriptive name> |
| Estimated Duration | <time estimate> |
| Parallel-Safe | yes/no |
| Dependencies | [stage numbers or "none"] |

## Objectives
1. [Primary objective - what this stage accomplishes]
2. [Secondary objective if any]
3. [Tertiary objective if any]

## Files to Create

### Tests (WRITE FIRST - TDD MANDATORY)
| File | Purpose | Test Count Target |
|------|---------|-------------------|
| tests/test_foo.c | Unit tests for foo | 10+ |
| tests/test_bar.c | Unit tests for bar | 8+ |

### Headers
| File | Purpose | Key Exports |
|------|---------|-------------|
| src/foo.h | Foo declarations | foo_create, foo_destroy |

### Implementation
| File | Purpose | Dependencies |
|------|---------|--------------|
| src/foo.c | Foo implementation | util.h |

## API Specification

```c
// Required function signatures with documentation
/**
 * @brief Creates a new Foo instance
 * @param config Configuration options
 * @return Foo* or NULL on error
 */
Foo* foo_create(FooConfig* config);
```

## Acceptance Criteria

### Automated Tests (MUST ALL PASS)
```bash
make test_foo    # Exit 0, all tests pass
make test_bar    # Exit 0, all tests pass
```

### Manual Verification (if any)
- [ ] Verify X works correctly
- [ ] Check Y displays properly

## Gate Requirements

| Requirement | Check Command | Expected |
|-------------|---------------|----------|
| All files exist | `ls src/foo.c src/foo.h` | Exit 0 |
| Tests compile | `make test_foo` | Exit 0 |
| Tests pass | `./build/test_foo` | Exit 0, 0 failures |
| No warnings | `make CFLAGS+="-Werror"` | Exit 0 |

## Security Checklist
- [ ] No hardcoded credentials
- [ ] Memory bounds checked
- [ ] NULL pointer checks
- [ ] Resource cleanup on error paths

## Error Handling
Document expected error cases and how they should be handled:
| Error Case | Detection | Response |
|------------|-----------|----------|
| NULL input | Check at entry | Return NULL/error code |
| OOM | Check malloc return | Cleanup and return NULL |

## Retry Log
| Attempt | Approach | Error | Result | Timestamp |
|---------|----------|-------|--------|-----------|
(filled during execution — agents MUST document each retry attempt)

## Notes
[Any additional context, gotchas, or implementation hints]
```

## Retry Tracking (MANDATORY)

Every stage file MUST include a `## Retry Log` section. Agents MUST fill it
during execution. If the retry log is empty when a test is marked BLOCKED,
the gate check FAILS — you cannot skip a test without documenting your attempts.

### Required Retry Log Format

```markdown
## Retry Log
| Attempt | Approach | Error | Result | Timestamp |
|---------|----------|-------|--------|-----------|
| 1 | Fix obvious error (wrong import path) | ModuleNotFoundError | Still failing — different module | 02:15 |
| 2 | Read source, found actual module name | TypeError: missing arg | Different error, progress | 02:25 |
| 3 | Checked MEMORY.md D18, found config needed | Config loaded but wrong port | Closer | 02:35 |
| 4 | Different approach: mock the dependency | Mock works but assertion wrong | Partial | 02:45 |
| 5 | Simplify: test basic connectivity only | N/A | BLOCKED — marking and moving on | 02:50 |
```

### Enforcement

- Gate check reads the Retry Log section
- If a test is BLOCKED but Retry Log has <5 entries → gate FAILS
- Each entry must have a DIFFERENT approach (not "tried again")
- Timestamps prove the agent actually spent time investigating

## Gate Check Protocol — STRICTLY ENFORCED

**NO stage may proceed until ALL gates pass.**

### Gate Sequence

1. **Files Exist Gate**
   - ALL files listed in "Files to Create" must exist
   - Check: `ls <each file>` must exit 0

2. **Compilation Gate**
   - ALL code must compile without errors
   - Check: `make` must exit 0

3. **Test Gate**
   - ALL tests must pass with expected counts
   - Check: `make test` must show 0 failures
   - Update STATUS.md with test counts IMMEDIATELY

4. **Security Gate**
   - ALL security checklist items verified
   - Document any security concerns in MEMORY.md

5. **Documentation Gate**
   - MEMORY.md updated with stage learnings
   - STATUS.md updated with test counts and stage status

### Gate Failure Protocol (Bounded Retry)

```
IF any gate fails:
  1. Document error in MEMORY.md under "Errors Discovered"
  2. Fix the issue — try a DIFFERENT approach each time
  3. Re-run ALL gates from the beginning
  4. Maximum 5 retry attempts per individual test/bug
  5. Maximum 3 hours per stage before cron re-launches
  6. After 5 attempts on same bug: mark that test BLOCKED, move to next test
  7. After all tests attempted: if >50% pass, mark stage PARTIAL, continue
  8. If <50% pass after 5 attempts each: mark stage BLOCKED, continue to next stage

WHAT "5 DIFFERENT APPROACHES" MEANS:
  Attempt 1: Fix the obvious error
  Attempt 2: Read source code more carefully, fix root cause
  Attempt 3: Check MEMORY.md and GAP-ANALYSIS for hints
  Attempt 4: Try completely different implementation approach
  Attempt 5: Simplify — reduce test scope to minimum that works
```

### Gate Success Protocol

```
IF all gates pass:
  1. Update STATUS.md: Mark stage COMPLETE with test counts
  2. Update MEMORY.md: Add learnings and any errors discovered
  3. Run POST-STAGE RECONCILIATION (see below)
  4. Proceed to next stage (or parallel stages if available)
```

### Post-Stage Reconciliation (MANDATORY after every stage)

```
AFTER every completed stage:
  1. DIFF REPORT: Compare actual vs planned
     - Tests written vs spec count
     - Files created vs expected
     - Any deviations from stage spec
  2. Write ## Reconciliation section at bottom of stage file
  3. GLOBAL COHERENCE CHECK: Read SPEC.md
     - Does spec still match reality?
     - Are downstream stages still valid?
     - Any new permissions/models/endpoints discovered?
  4. If SPEC.md needs updates, apply them with clear comment
  5. If downstream stage files need correction, update them
  6. Update MEMORY.md with learnings
  7. Update STATUS.md with reconciliation summary
```
