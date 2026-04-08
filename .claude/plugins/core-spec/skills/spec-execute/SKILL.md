---
name: core-spec:spec-execute
description: "Stage-gated spec execution with TDD, worktree agent swarms, cron-driven orchestration, bounded retries, reconciliation, and staging promotion."
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Agent, CronCreate, CronList
argument-hint: "'start', 'resume', 'gate', 'autonomous', or stage number"
---

# Spec Execute — Stage-Gated Test-Driven Execution

Execute specs stage by stage with mandatory test gates, worktree-isolated agent swarms, and optional cron-driven autonomous execution.

## Commands

| Command | Action |
|---------|--------|
| `start` | Begin from stage 1 |
| `resume` | Continue from current stage (reads STATUS.md) |
| `gate` | Run gate check for current stage |
| `stage N` | Jump to stage N (only if dependencies met) |
| `parallel` | Identify and start parallel stages |
| `autonomous` | Set up cron + worktree swarms for overnight execution |

## Core Protocol

### Stage Execution Flow

```
For each stage:
  1. Read stage file: stages/STAGE-NN.md
  2. Check dependencies (must all be COMPLETE in STATUS.md)
  3. Create test files FIRST (TDD)
  4. Implement code
  5. Run acceptance tests
  6. If tests fail → fix and retry (max 5 per bug, 5 different approaches)
  7. Run security check
  8. Update MEMORY.md with learnings
  9. Run POST-STAGE RECONCILIATION (diff actual vs planned)
  10. Mark stage COMPLETE in STATUS.md
  11. Proceed to next (or parallel) stages
```

### Bounded Retry Protocol

```
For each failing test/bug:
  Attempt 1: Fix the obvious error
  Attempt 2: Read source code more carefully, fix root cause
  Attempt 3: Check MEMORY.md and GAP-ANALYSIS for hints
  Attempt 4: Try completely different implementation approach
  Attempt 5: Simplify — reduce scope to minimum that works

  After 5: Mark that specific test BLOCKED in STATUS.md, move on
  NEVER loop more than 5 times on the same issue
```

### Memory Updates

Update `MEMORY.md` after EVERY:
- Stage completion
- Significant bug fix
- Architecture decision
- Non-obvious discovery
- Error after 3+ attempts

## Autonomous Mode (`autonomous` command)

### Setup Sequence

1. **Pre-flight checks:** Verify all dependencies, services, external access
2. **Create ORCHESTRATOR.md** with state machine and wave definitions
3. **Create cron job** using CronCreate:
   ```
   CronCreate({
     cron: "*/15 * * * *",
     durable: true,
     recurring: true,
     prompt: <state machine prompt referencing STATUS.md>
   })
   ```
4. **Set STATUS.md State** to `READY_TO_LAUNCH_WAVE_1`
5. **Launch Wave 1** immediately (don't wait for first cron fire)
6. **Set up notifications** if webhook URL provided

### Cron State Machine

The cron prompt is SELF-CONTAINED — reads STATUS.md every time:

| Status.md State | Cron Action |
|----------------|-------------|
| `READY_TO_LAUNCH_WAVE_N` | Launch wave agents in parallel worktrees |
| `WAVE_N_RUNNING` | Check progress, detect stalls, re-launch if needed |
| `READY_TO_MERGE_WAVE_N` | Merge worktrees, reconcile, promote to staging |
| `ALL_COMPLETE` | Notify and stop |
| `BLOCKED` | Try to unblock or report |

### Stall Detection

If a stage has been `IN_PROGRESS` for >2 hours with no STATUS.md update:
- Increment attempt count
- Re-launch with "previous attempt stalled" hint
- Max 3 re-launches before marking BLOCKED

## Agent Teams (NOT plain subagents)

Use **agent teams** for wave execution. Teams are long-lived instances that can
message each other via SendMessage and share a task list.

### Required Setting

Verify `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set in BOTH:
- `.claude/settings.json` (project)
- `~/.claude/settings.json` (user)

### Launching a Wave as a Team

For each wave, create a team with worktree-isolated teammates:

```
Create an agent team for Wave N with these teammates:

Teammate "stage-1-foundation":
  - isolation: worktree
  - Task: <paste FULL content of STAGE-01.md>
  - Context: <paste relevant MEMORY.md decisions>

Teammate "stage-5-bitbucket":
  - isolation: worktree
  - Task: <paste FULL content of STAGE-05.md>
  - Context: <paste relevant MEMORY.md decisions>

All teammates must:
- Follow TDD (tests first)
- Update STATUS.md after every action
- SendMessage to other teammates on discoveries
- Commit with descriptive messages (no AI attribution)
- Mark stage COMPLETE when done
```

### Why Teams Over Subagents

| Feature | Why It Matters |
|---------|---------------|
| **SendMessage** | Teammates tell each other about API discrepancies, patterns, bugs |
| **Shared task list** | Self-claiming prevents duplicate work |
| **Long-lived** | Don't disappear after one task — can handle follow-up issues |
| **Coordination** | When one teammate discovers a spec error, others adapt immediately |

### Wave Lifecycle

```
WAVE N:
  1. Create team with N teammates (one per stage)
  2. Each teammate works in worktree isolation
  3. Teammates communicate via SendMessage
  4. Shared task list tracks progress
  5. All teammates report COMPLETE
  GATE: Lead merges worktrees
  GATE: Post-stage reconciliation per stage
  GATE: Deploy to staging + verify
  6. Clean up team
  7. Launch Wave N+1
```

### Merging Waves

After all teammates in a wave complete:
1. `git merge worktree-<branch> --no-edit` for each
2. Resolve conflicts if any
3. Run typecheck/tests
4. Reconcile each stage against spec
5. Deploy to staging (if applicable)
6. Clean up team
7. Advance to next wave

## Post-Stage Reconciliation

After EVERY completed stage:

1. **Diff report:** Compare actual vs planned (tests, files, deviations)
2. **Write `## Reconciliation` section** at bottom of stage file
3. **Global coherence check:** Read SPEC.md, verify downstream stages valid
4. **Update downstream stages** if assumptions changed
5. **Update MEMORY.md** with learnings

## Staging Promotion (if applicable)

After each wave merge:

1. Deploy: `nx update platform -c staging` (or project-specific command)
2. Re-run wave tests against staging
3. Compare dev vs staging results
4. Log deviations in MEMORY.md
5. Staging failures marked `STAGING_BLOCKED` — don't block dev

## Notifications

If a webhook URL is configured in ENVIRONMENT.md:

| Event | Message |
|-------|---------|
| Wave launched | Wave N launched — Stages X, Y, Z |
| Stage complete | Stage N complete — X tests passing |
| Stage BLOCKED | Stage N BLOCKED after 5 attempts |
| Wave merged | Wave N merged — deploying to staging |
| Staging results | Dev: X/Y, Staging: X/Y |
| All complete | All done! X/Y stages, Z tests passing |

## Gate Check Protocol

When `gate` is invoked or stage implementation is done:

1. **Files exist:** All files listed in stage spec must exist
2. **Tests pass:** All acceptance tests pass
3. **Security check:** No hardcoded credentials, proper error handling
4. **Reconciliation:** Diff actual vs planned (see above)

| Result | Next Action |
|--------|-------------|
| ALL PASS | Reconcile, mark complete, proceed |
| TEST FAIL | Bounded retry (max 5 attempts) |
| SECURITY FAIL | Fix and retest |
| FILE MISSING | Create missing files |

## Compaction Survival

### Before compaction (hook triggers):
- Update STATUS.md with exact position
- Update MEMORY.md with current context
- Ensure ORCHESTRATOR.md State field is correct

### After compaction (hook triggers):
1. Read STATUS.md → current stage and state
2. Read MEMORY.md → restore context
3. Read ORCHESTRATOR.md → follow state machine
4. Resume from saved position

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Long-running orchestrator in conversation | Cron-driven stateless execution |
| Basic `Agent()` for parallel work | `Agent({isolation: "worktree"})` |
| Unlimited retry loops | Bounded: 5 attempts per bug, then BLOCKED |
| Skip reconciliation | ALWAYS diff actual vs planned after stage |
| Ignore staging | Deploy + test after every wave merge |
| Rely on conversation memory | Read STATUS.md from disk every time |
