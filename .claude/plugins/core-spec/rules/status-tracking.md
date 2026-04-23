# Status Tracking Protocol

<STOP_AND_CHECK>

## BEFORE Writing Implementation Code

Check for `STATUS.md` in the project root:
- EXISTS → Read it, update "In Progress" section, proceed
- MISSING → CREATE IT NOW using the template below

This is a Tier 3 requirement. Do NOT skip status tracking.

</STOP_AND_CHECK>

<critical>

## Mandatory Progress Tracking

When working on any multi-file or multi-phase task:

1. **Create STATUS.md immediately** — Before writing any code
2. **Update after each milestone** — File created, test passed, phase completed
3. **Include timestamps** — For drift detection and time estimation

## STATUS.md Format

**CRITICAL: Update test counts in REAL-TIME during execution, not just at the end.**

```markdown
# Project Status

**Last Updated:** YYYY-MM-DD HH:MM
**Current Stage:** N of M
**Overall Progress:** X%

## Stage Progress

| Stage | Status | Tests Written | Tests Passing | Duration |
|-------|--------|---------------|---------------|----------|
| 1. Foundation | ✅ Complete | 10 | 10/10 | 5m |
| 2. Lexer | 🔄 In Progress | 15 | 12/15 | — |
| 3. Parser | ⏳ Pending | 0 | — | — |
| 4. Query | ⏳ Pending | 0 | — | — |
| 5. CLI | ⏳ Pending | 0 | — | — |

**Legend:** ✅ Complete | 🔄 In Progress | ⏳ Pending | ❌ Blocked | 🔁 Retry

## Current Stage: [Stage Name]

### Test Progress (LIVE)
| Test File | Tests Written | Passing | Failing | Last Run |
|-----------|---------------|---------|---------|----------|
| test_lexer.c | 15 | 12 | 3 | HH:MM |

### Tasks
- [x] Write test_lexer.c — 15 tests
- [x] Create lexer.h — declarations
- [ ] Implement lexer.c — IN PROGRESS
- [ ] Pass all tests — 3 failing

### Gate Status
| Gate | Status | Details |
|------|--------|---------|
| Files Exist | ✅ | All 3 files created |
| Compiles | ✅ | No errors |
| Tests Pass | ❌ | 12/15 passing |
| Security | ⏳ | Not checked yet |

## Artifacts Created

| File | Lines | Status |
|------|-------|--------|
| src/lexer.c | 150 | in progress |
| src/lexer.h | 45 | complete |
| tests/test_lexer.c | 200 | complete |

## Test Summary (LIVE)

| Stage | Test File | Written | Passing | Failing |
|-------|-----------|---------|---------|---------|
| 1 | test_util.c | 10 | 10 | 0 |
| 2 | test_lexer.c | 15 | 12 | 3 |
| **TOTAL** | — | **25** | **22** | **3** |

## Blockers & Decisions

- [BLOCKER] Issue description — resolution plan
- [DECISION] What was decided — rationale
- [ERROR] Error discovered — root cause — fix applied
```

## Update Frequency

| Event | Action |
|-------|--------|
| Phase start | Add phase section, update current phase |
| File created | Add to artifacts table |
| Test passes | Update build status |
| Blocker hit | Add to blockers section |
| Phase complete | Mark complete, increment progress |

## Recovery Protocol

After context compaction:
1. Read STATUS.md first
2. Verify artifacts table matches disk
3. Resume from "In Progress" items
4. Update timestamp

</critical>
