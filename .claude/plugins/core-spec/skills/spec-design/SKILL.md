---
name: core-spec:spec-design
description: "Spec creation and design workflow. Load when user requests a new project, wants to plan work, or mentions 'spec', 'plan', or 'design'."
user-invocable: true
allowed-tools: Read, Write, Glob, Grep
argument-hint: "project description or 'resume'"
---

# Spec Design — Creating Project Specifications

Guide the user through creating a well-structured project specification.

## When to Use This Skill

- User asks to "build", "create", "make" something substantial
- User mentions "spec", "plan", "design", "architect"
- Starting a new multi-phase project
- Resuming work on an existing spec

## Workflow

### 1. Get Session ID and Check for Active Spec

First, determine the Claude session ID:

```bash
# Find most recent session in Claude's project dir
CWD_SLUG=$(pwd | sed 's|/|-|g')
SESSION_DIR="$HOME/.claude/projects/$CWD_SLUG"
SESSION_ID=$(ls -t "$SESSION_DIR"/*.jsonl 2>/dev/null | head -1 | xargs -I{} basename {} .jsonl)

# Fallback: generate from timestamp if not found
if [ -z "$SESSION_ID" ]; then
  SESSION_ID="session-$(date +%Y%m%d-%H%M%S)"
fi

echo "Session ID: $SESSION_ID"
```

Then check if there's an active spec:

```
.claude/specs/<session-id>/.active
```

If found, offer to resume rather than create new.

### 2. Gather Requirements (Interactive Mode)

Ask questions to understand:

| Category | Key Questions |
|----------|---------------|
| **Goal** | What outcome? What problem solving? |
| **Scope** | What's in/out? MVP vs full? |
| **Stack** | Language? Framework? Infrastructure? |
| **Constraints** | Time? Budget? Compliance? |

### 3. Evidence-Based Decisions (Autonomous Mode)

When `--autonomous` or user requests no questions:

1. Search codebase for evidence (go.mod, package.json, etc.)
2. Apply domain heuristics
3. Document each decision with reasoning
4. Proceed with best-guess, note confidence level

### 4. Create Spec Structure

Write to `.claude/specs/<session-id>/<spec-name>/`:

```
.claude/specs/<session-id>/
├── .active              # Contains: <spec-name>
└── <spec-name>/
    ├── SPEC.md          # Requirements + acceptance criteria
    ├── PLAN.md          # Stage overview + dependencies
    ├── STATUS.md        # Live progress with test counts
    ├── MEMORY.md        # Learnings (empty initially)
    ├── ENVIRONMENT.md   # Hardware/resource requirements
    └── stages/
        └── STAGE-NN.md  # Detailed stage files
```

### ENVIRONMENT.md — Required Content

Document the execution environment before starting implementation:

```markdown
# Environment Specification

## Hardware Available
| Resource | Available | Required | Status |
|----------|-----------|----------|--------|
| CPU Cores | <nproc> | <needed> | ✅/❌ |
| Memory | <free -g> | <needed> | ✅/❌ |
| Disk | <df -h> | <needed> | ✅/❌ |
| GPU | <if any> | <if needed> | ✅/❌ |

## External Resources
| Resource | Purpose | Access | Status |
|----------|---------|--------|--------|
| Remote server | <why> | <ssh user@host> | Untested |
| USB device | <why> | </dev/ttyUSB0> | Untested |
| API endpoint | <why> | <https://...> | Untested |

## Software Dependencies
| Package | Required Version | Installed | Status |
|---------|------------------|-----------|--------|
| gcc | >= 11 | <gcc --version> | ✅/❌ |
| make | any | <make --version> | ✅/❌ |

## Verification Commands
Run at spec creation to populate "Available" columns:
- `nproc` — CPU cores
- `free -g | awk '/Mem:/{print $2}'` — Memory GB
- `df -h . | awk 'NR==2{print $4}'` — Available disk
- `nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo "None"`
```

### 5. Define Phases

Each phase needs:
- **Name**: Descriptive identifier
- **Description**: What this phase accomplishes
- **Tasks**: Concrete work items
- **Artifacts**: Expected outputs
- **Gate**: Criteria to advance

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Start coding without spec | Create spec first, even minimal |
| Spec everything upfront | Start with Phase 1, refine later |
| Skip unclear requirements | Document as questions |
| Assume user preferences | Ask or document as decision |

## Phase Templates by Kit

### Embedded Kit
```
01-hardware-bringup
02-driver-collection
03-architecture-design
04-implementation
05-production-readiness
```

### Cloud Kit
```
01-scaffold
02-database-setup
03-api-implementation
04-testing
05-deployment
```

### Frontend Kit
```
01-setup
02-component-library
03-page-implementation
04-testing
05-deployment
```

### Compiler/Systems Kit (Tier 3 REQUIRED)
```
01-foundation        # Utilities, memory, error handling
02-frontend          # Lexer, parser, AST
03-type-system       # Types, symbol tables, semantic analysis
04-ir                # Intermediate representation (if applicable)
05-optimization      # Optimization passes
06-codegen           # Code generation per target
07-integration       # Driver, CLI, build system
08-self-hosting      # Bootstrap verification
```

#### Tier 3 Mandatory Artifacts — STOP GATE

For compiler/systems tasks, you CANNOT proceed until ALL of these exist in `.claude/specs/<session-id>/<spec-name>/`:

| # | Artifact | Purpose | Create Order |
|---|----------|---------|--------------|
| 1 | `SPEC.md` | Detailed requirements | FIRST |
| 2 | `PLAN.md` | Phased execution (8+ phases) | SECOND |
| 3 | `STATUS.md` | Progress with timestamps | THIRD |
| 4 | `MEMORY.md` | Learnings and decisions | FOURTH |
| 5 | `ENVIRONMENT.md` | Hardware/resource requirements | FIFTH |
| 6 | `.active` | Points to this spec | SIXTH |
| 7 | `stages/STAGE-*.md` | At least 8 stage files | SEVENTH |
| 8 | `tests/unit/` | Test stubs for each module (in workspace) | BEFORE implementation |

**BLOCKING RULE:** Do NOT create ANY `.c` implementation file until:
1. All 6 spec artifacts exist in `.claude/specs/`
2. At least 8 stage files exist
3. The corresponding `test_<module>.c` exists in workspace

This is non-negotiable. Verify the checklist before each file write.

**SPEC LOCATION RULE:** Spec files go in `.claude/specs/`, NOT in the workspace. Implementation code and tests go in the workspace.

## What This Does NOT Cover

- Spec execution (see spec-execute)
- Hardware-in-loop testing (see embedded kit)
- CI/CD setup (see core-devops)
