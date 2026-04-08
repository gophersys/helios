# Orchestrator Protocol — Cron-Driven Stateless Execution

**This file defines how the E2E project executes autonomously overnight via cron.**

---

## Architecture: Why Cron, Not a Long-Running Orchestrator

A long-running conversation WILL fail overnight because:
1. Context compacts after enough turns — orchestrator forgets its job
2. Agents spawned early get garbage-collected from context
3. After 10-20 agent launches, the conversation becomes sluggish

**Solution:** A cron job fires every 15 minutes. Each fire sends a SELF-CONTAINED prompt that:
1. Reads STATUS.md from disk (always fresh, never from context)
2. Decides what to do (launch agents, merge, advance wave)
3. Does ONE thing (launch a wave, or merge a wave, or check on agents)
4. Updates STATUS.md
5. Returns — keeps context small

The conversation is just a mailbox. The cron prompt is the brain. STATUS.md is the memory.

---

## Cron Prompt (fires every 15 minutes)

The cron prompt is designed to work even if ALL prior context has been compacted:

```
You are the E2E orchestrator for Concord. This prompt fires every 15 minutes via cron.

MANDATORY FIRST STEPS — do these EVERY time, even if you think you remember:
1. Read .claude/specs/5a050d23-af4b-44bf-a73a-01a83b23a1b6/e2e/STATUS.md
2. Read .claude/specs/5a050d23-af4b-44bf-a73a-01a83b23a1b6/e2e/ORCHESTRATOR.md
3. Read .claude/specs/5a050d23-af4b-44bf-a73a-01a83b23a1b6/e2e/MEMORY.md

Then follow the STATE MACHINE below based on what STATUS.md says.
```

---

## State Machine

STATUS.md contains `**State:**` which is one of:

### State: READY_TO_LAUNCH_WAVE_N

**Action:** Create an AGENT TEAM for Wave N (not plain subagents!).

1. Create a team with one teammate per stage in the wave
2. Each teammate gets `isolation: "worktree"` for git branch isolation
3. Each teammate prompt includes FULL stage file content + MEMORY.md decisions
4. Teammates can SendMessage to each other about discoveries
5. Update STATUS.md: stage status → IN_PROGRESS, State → WAVE_N_RUNNING

**IMPORTANT:** Use AGENT TEAMS (not plain subagents). Teams are long-lived instances that can message each other via SendMessage and share a task list. This requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings (already configured).

Create a team for the wave. Each teammate gets `isolation: "worktree"` for git branch isolation. Teammates should use SendMessage when they discover something that affects other stages.

### State: WAVE_N_RUNNING

**Action:** Check on running agents.

1. For each IN_PROGRESS stage in the wave, check if the worktree has commits:
   ```bash
   git worktree list  # See active worktrees
   # For each worktree, check last commit time
   ```
2. Read STATUS.md `**Last Updated:**` timestamps for each stage
3. If ALL stages in the wave show COMPLETE → transition to READY_TO_MERGE_WAVE_N
4. If any stage has been IN_PROGRESS for >2 hours with no STATUS.md update:
   - Check attempt count in STATUS.md
   - If attempts < 5: re-launch the stage with hint "Previous attempt stalled"
   - If attempts >= 5: mark as BLOCKED, log in MEMORY.md, continue
5. If some stages complete but others still running: do nothing, wait for next cron fire

### State: READY_TO_MERGE_WAVE_N

**Action:** Merge all worktree branches from Wave N.

1. For each completed stage in the wave:
   ```bash
   cd /workspaces/concord
   git merge worktree-<branch-name> --no-edit
   ```
2. If merge conflict: resolve it (read both versions, keep all new code)
3. Run quick validation:
   ```bash
   npx nx typecheck http-api 2>&1 | tail -5
   npx nx typecheck app 2>&1 | tail -5
   ```
4. If typecheck fails: fix the issues
5. Run the POST-STAGE RECONCILIATION for each merged stage
6. Commit the merge: `git commit -m "merge: wave N complete — stages X, Y, Z"`
7. DEPLOY TO STAGING and re-run wave tests (see Staging Promotion below)
8. Update STATUS.md: State → READY_TO_LAUNCH_WAVE_(N+1)

### State: ALL_COMPLETE

**Action:** Nothing. Log "All 16 stages complete" and stop.

### State: BLOCKED

**Action:** Log the blocking issue. Try to unblock if possible. If not, report status.

---

## Staging Promotion Protocol (after every wave merge)

After merging a wave and passing reconciliation, deploy to staging and re-run tests:

```
1. Deploy to staging:
   nx update platform -c staging
   # Rebuilds images, pushes to registry, helm upgrade, zero downtime

2. Verify staging health:
   nx run platform:status -c staging
   # All pods Running, health probes passing

3. Re-run the wave's tests against staging:
   # Tests must support configurable base URLs
   PLAYWRIGHT_BASE_URL=https://staging.concord.local \
   API_URL=https://staging.concord.local \
   AUTH_MODE=api_key \
   npx playwright test --config=e2e.config.ts <wave-test-files>

4. Compare results:
   # Same tests must pass on both dev and staging
   # If a test passes dev but fails staging → K8s-specific bug
   # Document in MEMORY.md under "Staging Deviations"

5. If staging tests fail:
   - Try to fix (max 3 attempts)
   - If unfixable: mark as STAGING_BLOCKED in STATUS.md
   - Continue to next wave (staging failures don't block dev progress)
   - Log for morning review

6. Notify Discord:
   "🚀 Wave N → staging. Dev: X/Y passing, Staging: X/Y passing"
```

### Auth Difference: Dev vs Staging

| Aspect | Dev (docker-compose) | Staging (K8s) |
|--------|---------------------|---------------|
| AUTH_ENABLED | false | true |
| Login method | Dev-login buttons (no password) | API key or real credentials |
| Test auth | `loginAsRole(page, 'admin')` via dev-login | `loginViaAPIKey(page)` via CI admin key |
| API calls | No auth header needed | `Authorization: ApiKey ck_ci_admin_...` |

Tests must be written to handle BOTH modes. The auth helpers should detect the environment:

```typescript
async function ensureAuth(page: Page) {
  if (process.env.AUTH_MODE === 'api_key') {
    await loginViaAPIKey(page);  // staging: use CI admin key
  } else {
    await loginAsRole(page, 'admin');  // dev: use dev-login
  }
}
```

### What Staging Catches That Dev Misses

- K8s service discovery (DNS-based, not localhost)
- Init container migration timing (race conditions)
- Resource limits (OOM, CPU throttling)
- Ingress routing (path-based, TLS termination)
- Real auth flow (JWT verification, permission enforcement)
- Inter-service communication (http-api ↔ build-service ↔ git-poller)
- PVC-backed storage (vs docker volumes)

---

## Resource Pooling — Shared Platform Between Teammates

All teammates in a wave share ONE running platform (docker-compose stack).
No separate instances per teammate. This saves resources but requires discipline.

### Global Setup (ONCE, before any wave)

```bash
# Lead does this before creating any team:
nx stop platform                     # Stop everything
npx prisma migrate reset --force     # Wipe DB completely
npx prisma migrate deploy            # Re-run migrations
python3 -m seed.main --platform-only # Seed roles, permissions, dev users ONLY
nx start platform                    # Restart
curl -s localhost:9001/v2/docs       # Verify health
```

After this, the platform stays running for ALL waves. No more wipes.

### Stage-Prefixed Test Data (MANDATORY)

Every teammate prefixes ALL test data with `s{STAGE_NUMBER}-`:

| Teammate | Prefix | Example Product | Example Branch |
|----------|--------|-----------------|----------------|
| Stage 2 (Auth) | `s2-` | `s2-test-product` | `e2e/s2-branch` |
| Stage 3 (Products) | `s3-` | `s3-Alpha-Test` | `e2e/s3-feature` |
| Stage 7 (Fixtures) | `s7-` | `s7-E2E-Fixture` | — |
| Stage 10 (Mfg) | `s10-` | `s10-mfg-config` | — |
| Stage 14 (Users) | `s14-` | — (creates `s14-test@e2e.dev`) | — |

### Cleanup Per Teammate

Each teammate cleans up ITS OWN prefixed data at stage end.
Stage 16 does a final sweep to catch stragglers.
NEVER wipe the entire DB during wave execution.

### Hardware Is Serial

MTIB (10.4.45.33) can only be used by ONE stage at a time.
Stages 9 and 13 (which need MTIB) run in Wave 4 SEQUENTIALLY, never parallel.

### Include in EVERY Teammate Prompt

```
RESOURCE POOLING: You share the platform with other teammates.
- DO NOT wipe the database or restart the platform
- Prefix ALL test data with "s{YOUR_STAGE}-" (e.g., "s3-Alpha-Product")
- Clean up your prefixed data when your stage completes
- The API (localhost:9001) and frontend (localhost:4200) handle concurrent access
- MTIB hardware is NOT available to you unless you are in Wave 4
- Use SendMessage to coordinate if you need data another teammate created
```

---

## Agent Prompt Template

Every agent gets this prompt structure. It MUST be self-contained — the agent has NO conversation history.

```
You are implementing Stage {N}: {Name} for the Concord E2E test project.

## YOUR TASK
{Paste the FULL content of STAGE-NN.md here}

## KEY DECISIONS (from MEMORY.md)
{Paste relevant decisions — D1 through D20}

## RELEVANT USER STORY
{Paste the relevant story file content if applicable}

## GAP ANALYSIS FINDINGS FOR THIS STAGE
{Paste the relevant section from GAP-ANALYSIS-DEEP.md}

## RULES
1. TDD: Write tests FIRST, then implementation
2. Commit frequently with descriptive messages (NO "Co-Authored-By" or AI references)
3. After completing the stage, write a ## Reconciliation section at the bottom of the stage file
4. Update STATUS.md after every significant action (test file created, implementation done, tests passing)
5. If you encounter a bug that takes more than 3 attempts to fix:
   - Log it in MEMORY.md under "## Errors Encountered"
   - Try up to 5 different approaches total
   - If still failing after 5 approaches, mark the specific test as BLOCKED in STATUS.md and move on
   - DO NOT loop forever
6. Keep your changes scoped to this stage's files. Don't modify files owned by other stages.
7. When done, update the stage status to COMPLETE in STATUS.md

## BOUNDED RETRY PROTOCOL
- Max 5 attempts per failing test/bug
- Each attempt should try a DIFFERENT approach, not repeat the same thing
- After attempt 3, re-read MEMORY.md for hints from other stages
- After attempt 5, mark as BLOCKED and move on
- NEVER loop more than 5 times on the same issue

## FILE PATHS
Working directory: /workspaces/concord
Spec directory: .claude/specs/5a050d23-af4b-44bf-a73a-01a83b23a1b6/e2e/
Status file: .claude/specs/5a050d23-af4b-44bf-a73a-01a83b23a1b6/e2e/STATUS.md
Memory file: .claude/specs/5a050d23-af4b-44bf-a73a-01a83b23a1b6/e2e/MEMORY.md
```

---

## Wave Definitions

### Wave 1 (2 parallel agents)
| Stage | Worktree Branch | Agent Name |
|-------|----------------|------------|
| 1 | e2e-foundation | stage-1-foundation |
| 5 | e2e-bitbucket | stage-5-bitbucket |

### Wave 2 (4 parallel agents)
| Stage | Worktree Branch | Agent Name |
|-------|----------------|------------|
| 2 | e2e-auth | stage-2-auth |
| 7 | e2e-fixtures | stage-7-fixtures |
| 10 | e2e-mfg-backend | stage-10-mfg-backend |
| 14 | e2e-users | stage-14-users |

### Wave 3 (3 parallel agents)
| Stage | Worktree Branch | Agent Name |
|-------|----------------|------------|
| 3 | e2e-products | stage-3-products |
| 11 | e2e-mfg-frontend | stage-11-mfg-frontend |
| 12 | e2e-mfg-wizard | stage-12-mfg-wizard |

### Wave 4 (sequential — real system needed)
Stages 4 → 6 → 8 → 9 then 13
Each runs sequentially (no worktree — direct on branch)

### Wave 5 (sequential — final)
Stages 15 → 16
Each runs sequentially

---

## Bounded Retry Policy

| Metric | Value | What Happens |
|--------|-------|-------------|
| Max attempts per bug/test | 5 | After 5, mark BLOCKED and move on |
| Max time per stage | 3 hours | After 3h with no STATUS.md update, re-launch |
| Max re-launches per stage | 3 | After 3 re-launches, mark stage BLOCKED |
| Max total blocked stages | 4 | If >4 stages blocked, halt and report |

### What "5 different approaches" means:
1. **Attempt 1:** Fix the obvious error
2. **Attempt 2:** Read the actual source code more carefully, fix root cause
3. **Attempt 3:** Check MEMORY.md and GAP-ANALYSIS-DEEP.md for known issues
4. **Attempt 4:** Try a completely different implementation approach
5. **Attempt 5:** Simplify — reduce test scope to the minimum that works

After 5, add to MEMORY.md:
```markdown
### BLOCKED: Stage N — test_name
**Error:** <exact error>
**Attempts:** 5
**Approaches tried:** <list>
**Root cause hypothesis:** <best guess>
**Impact:** <what downstream stages are affected>
```

---

## STATUS.md State Format

The cron prompt reads STATUS.md and looks for these exact fields:

```markdown
**State:** READY_TO_LAUNCH_WAVE_1
**Wave:** 1 of 5
**Stage:** 0 of 16
**Progress:** 10%
**Last Updated:** 2026-04-09T01:00:00Z

## Stage Detail
| # | Status | Attempts | Started | Last Update | Worktree |
|---|--------|----------|---------|-------------|----------|
| 1 | PENDING | 0 | - | - | e2e-foundation |
...
```

Fields the cron prompt uses for decisions:
- `**State:**` — which state machine action to take
- `Attempts` column — for bounded retry logic
- `Last Update` column — for stall detection (>2h = stalled)
- `Status` column — PENDING, IN_PROGRESS, COMPLETE, BLOCKED

---

## Overnight Execution Timeline (Expected)

```
T+0:00  Cron fires → State: READY_TO_LAUNCH_WAVE_1 → launches 2 agents
T+0:15  Cron fires → State: WAVE_1_RUNNING → checks agents, still working
T+0:30  Cron fires → Stage 5 (Bitbucket) complete, Stage 1 still running
T+0:45  Cron fires → Stage 1 complete → State: READY_TO_MERGE_WAVE_1
T+1:00  Cron fires → merges Wave 1 → State: READY_TO_LAUNCH_WAVE_2
T+1:15  Cron fires → launches 4 agents (auth, fixtures, mfg-backend, users)
T+1:30  Cron fires → Wave 2 running, some stages progressing
...
T+3:00  Wave 2 complete → merge → launch Wave 3
T+4:00  Wave 3 complete → merge → start Wave 4 (sequential)
T+5:00  Stages 4, 6 complete → validation queue tests
T+6:00  Stage 9 (MTIB tests — if reachable) → complete or BLOCKED
T+7:00  Wave 5: Role stories running
T+8:00  All complete or max blocked reached → State: ALL_COMPLETE
```

Total estimated: 6-10 hours of autonomous execution.

---

## Discord Notifications

Send notifications to Discord at major milestones. Use curl:

```bash
curl -s -H "Content-Type: application/json" \
  -d '{"content": "MESSAGE_HERE"}' \
  "https://discord.com/api/webhooks/1478806971934179490/itB9fJ2tuhvy74ivLusiiipHJS5PyEYwY1571fO9JhigBMuAZ_OFZ7Hhmgpb5zUzADXp"
```

### When to notify:

| Event | Message Format |
|-------|---------------|
| Wave launched | `🚀 Wave N launched — Stages X, Y, Z (N agents in parallel)` |
| Wave complete | `✅ Wave N complete — all stages merged. Progress: X%` |
| Stage complete | `📦 Stage N ({name}) complete — {tests_written} tests, {tests_passing} passing` |
| Stage BLOCKED | `⚠️ Stage N ({name}) BLOCKED after 5 attempts. Error: {summary}. Skipping to continue progress.` |
| Agent stalled + re-launched | `🔄 Stage N ({name}) stalled — re-launching (attempt {n}/3)` |
| All complete | `🎉 E2E project complete! {stages_done}/16 stages, {tests_passing}/{tests_written} tests passing. {blocked_count} blocked.` |
| Critical error | `🔴 Critical: {description}. Continuing with remaining stages.` |
| Spec deviation found | `📋 Reconciliation: Stage N found {count} deviations from spec. See STATUS.md.` |

### CRITICAL RULE: Never halt the entire project

If a stage is BLOCKED:
1. Notify Discord
2. Log full details in MEMORY.md
3. Mark stage as BLOCKED in STATUS.md
4. **CONTINUE TO THE NEXT STAGE/WAVE**
5. If a blocked stage is a dependency for later stages, try the later stage anyway — it may partially work or reveal useful information
6. Only halt if >4 stages are blocked AND no forward progress is possible

The goal is maximum forward progress. The user will fix blocked items tomorrow.

## Key Principle

**Every cron fire is a stateless function call. STATUS.md is the only memory. The cron prompt re-reads it every time. No conversation context is relied upon. Agents are bounded by retry limits. The system makes forward progress or explicitly halts. Discord gets notified at every milestone.**
