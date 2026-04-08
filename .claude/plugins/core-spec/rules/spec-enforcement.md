# Spec Enforcement — MANDATORY

<STOP>

## SPEC LOCATION — NON-NEGOTIABLE

All spec files MUST be created in `.claude/specs/`, NOT in the workspace.

### Directory Structure

```
.claude/specs/
└── <session-id>/
    ├── .active              # Contains name of active spec
    └── <spec-name>/
        ├── SPEC.md          # Requirements + acceptance criteria
        ├── PLAN.md          # Stage overview + dependencies
        ├── STATUS.md        # Live progress with test counts
        ├── MEMORY.md        # Survives compaction + error cases
        ├── ENVIRONMENT.md   # Hardware/resource requirements
        └── stages/
            └── STAGE-NN.md  # Detailed stage files
```

### Getting the Session ID

To find the current Claude session ID:

```bash
# Find most recent session in Claude's project dir
SESSION_DIR="$HOME/.claude/projects/$(pwd | sed 's|/|-|g')"
SESSION_ID=$(ls -t "$SESSION_DIR"/*.jsonl 2>/dev/null | head -1 | xargs -I{} basename {} .jsonl)

# Fallback: generate from timestamp if not found
if [ -z "$SESSION_ID" ]; then
  SESSION_ID="session-$(date +%Y%m%d-%H%M%S)"
fi
```

In practice, use Bash tool to run this and capture the session ID.

## YOUR FIRST 5 TOOL CALLS MUST BE Write CALLS

Do NOT start with "let me explore" or "let me plan".
Do NOT start with Glob, Grep, Read, or Bash.

Your FIRST response must include Write tool calls for these files:

**Call 1: Write SPEC.md**
```
Use the Write tool with file_path=".claude/specs/<session-id>/<spec-name>/SPEC.md" containing:
# Project Specification
## Requirements
<extract from user prompt>
## Acceptance Criteria
<extract from user prompt>
```

**Call 2: Write PLAN.md**
```
Use the Write tool with file_path=".claude/specs/<session-id>/<spec-name>/PLAN.md" containing:
# Implementation Plan
## Stages
| # | Name | Description | Dependencies |
|---|------|-------------|--------------|
| 1 | Foundation | Core types and utilities | None |
...
```

**Call 3: Write STATUS.md**
```
Use the Write tool with file_path=".claude/specs/<session-id>/<spec-name>/STATUS.md" containing:
# Project Status
**Stage:** 1 of N
**Progress:** 0%
| Stage | Status | Tests |
|-------|--------|-------|
| 1 | 🔄 In Progress | 0 |
...
```

**Call 4: Write MEMORY.md**
```
Use the Write tool with file_path=".claude/specs/<session-id>/<spec-name>/MEMORY.md" containing:
# Project Memory
## Decisions
## Errors Encountered
## Learnings
```

**Call 5: Write ENVIRONMENT.md** (NEW - MANDATORY)
```
Use the Write tool with file_path=".claude/specs/<session-id>/<spec-name>/ENVIRONMENT.md" containing:
# Environment Specification

## Hardware Requirements
| Resource | Required | Available | Notes |
|----------|----------|-----------|-------|
| CPU | <cores needed> | <detected> | |
| Memory | <GB needed> | <detected> | |
| Disk | <GB needed> | <detected> | |
| GPU | <if needed> | <detected> | |

## External Resources
| Resource | Purpose | Access Method |
|----------|---------|---------------|
| <remote server> | <why needed> | <ssh/api/etc> |
| <USB device> | <why needed> | <ttyUSB0/etc> |

## Software Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| <compiler> | <version> | <why> |

## Network Requirements
| Endpoint | Purpose | Protocol |
|----------|---------|----------|
| <url> | <why> | <http/ssh/etc> |

## Detection Commands
Run these to populate the Available column:
- CPU: `nproc`
- Memory: `free -g`
- Disk: `df -h`
- GPU: `nvidia-smi` or `lspci | grep VGA`
```

**Call 6: Write .active**
```
Use the Write tool with file_path=".claude/specs/<session-id>/.active" containing:
<spec-name>
```

ONLY AFTER these 6 Write calls complete may you explore or implement.

</STOP>

<CRITICAL>

## STOP — Before Writing ANY Code

You MUST check for and create spec files BEFORE writing ANY implementation code.

### Spec Location

All spec files live in: `.claude/specs/<session-id>/<spec-name>/`

NOT in the workspace. The workspace is for implementation code ONLY.

### Enforcement Check

```
BEFORE creating any .c, .h, .py, .ts, .js, or implementation file:

1. CHECK: Does .claude/specs/<session-id>/<spec-name>/SPEC.md exist?
   - NO → CREATE SPEC.md FIRST
   - YES → Continue to step 2

2. CHECK: Does PLAN.md exist in spec dir?
   - NO → CREATE PLAN.md with stages
   - YES → Continue to step 3

3. CHECK: Does STATUS.md exist in spec dir?
   - NO → CREATE STATUS.md with stage tracking
   - YES → Continue to step 4

4. CHECK: Does MEMORY.md exist in spec dir?
   - NO → CREATE MEMORY.md for learnings
   - YES → Continue to step 5

5. CHECK: Does ENVIRONMENT.md exist in spec dir?
   - NO → CREATE ENVIRONMENT.md with hardware/resources
   - YES → Continue to step 6

6. CHECK: Do stages/STAGE-NN.md files exist for current work?
   - NO → CREATE stage files BEFORE implementation
   - YES → Continue to step 7

7. CHECK: Is .active file pointing to this spec?
   - NO → UPDATE .active file
   - YES → NOW you may write implementation code
```

### BLOCKED Actions

You are BLOCKED from:
- Creating src/*.c or src/*.h without SPEC.md existing in spec dir
- Creating implementation files without PLAN.md stages defined
- Writing code without tests written FIRST (TDD)
- Proceeding to next stage without passing ALL gates
- Creating spec files in the workspace (MUST be in .claude/specs/)

### Required Order

```
1. SPEC.md         — Define requirements and acceptance criteria
2. PLAN.md         — Define stages with dependency graph
3. STATUS.md       — Initialize progress tracking
4. MEMORY.md       — Initialize learnings document
5. ENVIRONMENT.md  — Document hardware and resource requirements
6. .active         — Point to this spec
7. stages/         — Create detailed stage files
8. tests/          — Write tests FIRST (TDD) in workspace
9. src/            — ONLY THEN write implementation in workspace
```

### Violation Response

If you find yourself about to write implementation code without spec files:

1. STOP immediately
2. Create the missing spec files
3. THEN proceed with implementation

This is NOT optional. This is a HARD requirement.

</CRITICAL>

## Tier 3 Auto-Detection

For complex projects (20+ files, compiler, kernel, multi-target):

```
IF project complexity >= Tier 3:
  MANDATORY: Create full spec structure
  MANDATORY: Use stages/STAGE-NN.md format
  MANDATORY: Track test counts in STATUS.md live
  MANDATORY: Document errors in MEMORY.md
  MANDATORY: Enforce all gates before stage transitions
```

## TDD Enforcement

```
For EACH implementation file:
  1. FIRST: Create test file (tests/test_<name>.c)
  2. THEN: Create header file (src/<name>.h or include/<name>.h)
  3. LAST: Create implementation (src/<name>.c)

BLOCKED: Creating .c implementation before test file exists
```

## Live Status Updates

```
After EACH significant action:
  - Update STATUS.md with current state
  - Include test counts (written/passing/failing)
  - Update timestamps
```
