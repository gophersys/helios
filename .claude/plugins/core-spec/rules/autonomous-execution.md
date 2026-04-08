# Autonomous Overnight Execution Protocol

This protocol enables specs to execute autonomously for hours without human intervention, surviving context compaction, agent stalls, and bug loops.

## When to Activate

Activate when the user says ANY of:
- "run overnight", "leave it running", "come back tomorrow"
- "set up cron", "autonomous execution"
- "agent swarm", "parallel teams"
- "don't stop", "keep going"

## Architecture: Cron-Driven Stateless Execution

A long-running conversation WILL fail because context compacts. The solution:

```
Every 15 minutes, a cron fires a SELF-CONTAINED prompt that:
1. Reads STATUS.md from disk (always fresh)
2. Follows the state machine
3. Does ONE thing (launch, check, merge, advance)
4. Updates STATUS.md
5. Returns — keeps context small
```

The conversation is a mailbox. The cron prompt is the brain. STATUS.md is the memory.

## Setup Checklist

When autonomous mode is requested, do ALL of these:

### 1. Pre-Flight Checks

Before starting, verify:
```bash
# Dependencies
docker --version          # Container runtime
node --version            # Frontend tooling
python3 --version         # Backend
npx playwright --version  # Browser testing (if E2E)

# Services (if needed)
curl -s localhost:9001/v2/docs  # Backend API health
kubectl cluster-info            # K8s access (if needed)

# External (if needed)
timeout 3 curl -s https://api.bitbucket.org/2.0/  # Bitbucket
timeout 3 ping -c 1 <hardware-ip>                  # Hardware
```

Log results in ENVIRONMENT.md. Flag any failures.

### 2. Create the Cron Job

Use `CronCreate` with these EXACT parameters:
```
CronCreate({
  cron: "*/15 * * * *",
  durable: true,        // MUST be true — survives session restart
  recurring: true,
  prompt: <the state machine prompt — see below>
})
```

### 3. Cron Prompt Template

The cron prompt MUST be completely self-contained. Include the spec path:

```
You are the spec orchestrator. This fires every 15 minutes via cron.

MANDATORY FIRST STEPS (even if you think you remember):
1. Read <spec-path>/STATUS.md
2. Read <spec-path>/ORCHESTRATOR.md (if exists) or <spec-path>/PLAN.md
3. Read <spec-path>/MEMORY.md

Then follow the STATE MACHINE:

State: READY_TO_LAUNCH_WAVE_N
  → Read stage files for this wave
  → Launch agents with isolation: "worktree", mode: "bypassPermissions"
  → Launch ALL wave agents in a SINGLE message (parallel)
  → Update STATUS.md: State → WAVE_N_RUNNING

State: WAVE_N_RUNNING
  → Check STATUS.md stage rows for completion
  → If all COMPLETE → State: READY_TO_MERGE_WAVE_N
  → If any stalled >2h → re-launch (max 3 re-launches)
  → If some done, some running → do nothing, wait

State: READY_TO_MERGE_WAVE_N
  → Merge worktree branches
  → Run post-stage reconciliation
  → Deploy to staging if applicable
  → State: READY_TO_LAUNCH_WAVE_(N+1)

State: ALL_COMPLETE → Notify and stop
State: BLOCKED → Try to unblock, else report

After EVERY action, update STATUS.md.
Notify at milestones (see Notifications section).
```

### 4. Discord/Webhook Notifications (Optional)

If the user provides a webhook URL, notify at:
- Wave launched
- Stage complete
- Stage BLOCKED (with error summary)
- Wave merged + staging results
- All complete

```bash
curl -s -H "Content-Type: application/json" \
  -d '{"content": "MESSAGE"}' \
  "<WEBHOOK_URL>"
```

Store the webhook URL in ENVIRONMENT.md.

## State Machine States

```
READY_TO_LAUNCH_WAVE_N → WAVE_N_RUNNING → READY_TO_MERGE_WAVE_N
     → READY_TO_LAUNCH_WAVE_(N+1) → ... → ALL_COMPLETE
```

At any point: → BLOCKED (if >4 stages blocked and no forward progress)

## Agent Spawning Rules

### Worktree Isolation (MANDATORY for parallel agents)

```
Agent({
  description: "Stage N: <name>",
  isolation: "worktree",
  mode: "bypassPermissions",
  prompt: <SELF-CONTAINED — full stage file + memory decisions>
})
```

Each agent gets its own git branch. No conflicts between parallel agents.

### Agent Prompt Must Include

1. Full stage file content (not a reference — the ACTUAL content)
2. Relevant decisions from MEMORY.md
3. Relevant story files (if applicable)
4. The bounded retry protocol
5. Instructions to update STATUS.md after every significant action
6. Instructions to commit with descriptive messages (no AI attribution)

### Wave-Based Parallelism

Group stages into waves based on dependency graph. All stages in a wave
launch simultaneously. Merge all worktrees between waves.

## Bounded Retry Protocol

Every agent must follow:

| Metric | Limit | Action on exceed |
|--------|-------|-----------------|
| Attempts per bug/test | 5 | Mark BLOCKED, move on |
| Time per stage | 3 hours | Cron re-launches |
| Re-launches per stage | 3 | Mark stage BLOCKED |
| Total blocked stages | 4 | Halt if no forward progress possible |

### What "5 different approaches" means:
1. Fix the obvious error
2. Read source code more carefully, fix root cause
3. Check MEMORY.md for hints from other stages
4. Try completely different implementation approach
5. Simplify — reduce scope to minimum that works

After 5, log in MEMORY.md and move on.

## Post-Stage Reconciliation (MANDATORY)

After EVERY completed stage:

1. **Diff Report:** Compare actual vs planned (tests written vs spec, files created vs expected)
2. **Write Reconciliation section** at bottom of stage file
3. **Global Coherence Check:** Read SPEC.md, verify downstream stages still valid
4. **Update MEMORY.md** with learnings
5. **Update STATUS.md** with completion

## Staging Promotion (if applicable)

After each wave merge, if the project deploys to staging:

1. Deploy: `nx update platform -c staging`
2. Re-run wave tests against staging
3. Compare dev vs staging results
4. Log deviations in MEMORY.md
5. Staging failures don't block dev progress (marked STAGING_BLOCKED)
