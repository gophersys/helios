# Rate Limit Resilience Protocol

Claude Code has hard limits that break autonomous execution if not respected. This rule prevents the three most common failure modes.

## Problem 1: API Rate Limits (429/529)

5+ concurrent teammates trigger rate limit errors within 5-10 minutes. Retrying simultaneously worsens congestion.

### Staggered Teammate Launches

**DO NOT** launch all wave agents simultaneously. Stagger by 30-60 seconds:

```
For each teammate in the wave:
  1. Launch teammate N
  2. Sleep 45 seconds
  3. Launch teammate N+1
  4. Sleep 45 seconds
  ...

Total stagger for 4 teammates: ~2.5 minutes (acceptable startup cost)
```

**Why 45 seconds:** Claude Code's API allocates per-minute token budgets. Staggering ensures each agent's first turn completes before the next starts, preventing burst congestion.

### Retry with Exponential Backoff

If a teammate hits 429/529:
```
Attempt 1: Wait 30 seconds, retry
Attempt 2: Wait 60 seconds, retry
Attempt 3: Wait 120 seconds, retry
After 3 failures: Log in MEMORY.md, continue with reduced parallelism
```

### Max Concurrent Teammates

| Plan | Safe Concurrent | Risky | Will Hit 429s |
|------|:--------------:|:-----:|:-------------:|
| Pro | 2 | 3 | 4+ |
| Max5 | 3 | 4 | 5+ |
| Max20 | 4-5 | 6 | 7+ |

When in doubt, use fewer teammates. Serial execution that completes is better than parallel execution that crashes.

## Problem 2: Tool Call Limits (pause_turn)

Claude Code pauses execution after ~10-20 tool calls per turn. This interrupts multi-step workflows.

### Tool Call Budget

Agents should plan their turns to stay under 8 tool calls:

```
GOOD (8 calls, fits in one turn):
  1. Read STATUS.md
  2. Read stage file
  3. Write test file
  4. Run tests
  5. Write implementation
  6. Run tests again
  7. Update STATUS.md
  8. Commit

BAD (15+ calls, will be paused):
  1. Read STATUS.md
  2. Read MEMORY.md
  3. Read PLAN.md
  4. Read stage file
  5. Read story file
  6. Glob for existing files
  7. Read file 1
  8. Read file 2
  9. Read file 3
  10. Write test 1
  11. Write test 2
  12. Write impl 1
  13. Write impl 2
  14. Run tests
  15. Update STATUS.md
  → PAUSED at step 10-12, loses momentum
```

### Batching Strategy

- **Read phase**: Read up to 3 files, then plan what to write
- **Write phase**: Write 1-2 files, then run tests
- **Verify phase**: Run tests, update status, commit
- **Repeat** in next turn

## Problem 3: Context Degradation

Performance degrades significantly when context usage exceeds 60-70%. Instructions get ignored, basic coding errors increase.

### Proactive Compaction

The cron supervisor should monitor context health:

```
On each cron fire:
  1. Check if lead session is approaching context limit
  2. If context > 50%: consider running /compact before launching new agents
  3. If context > 70%: MUST compact before any new work
  4. Teammates have independent context windows — only the lead needs monitoring
```

### Keep Teammate Prompts Lean

When launching teammates, include ONLY what they need:
- Stage file content (REQUIRED)
- Relevant MEMORY.md decisions (SELECTIVE — only decisions that affect this stage)
- Resource pooling rules (REQUIRED — 3 lines)
- Bounded retry protocol (REQUIRED — 5 lines)

Do NOT include: full SPEC.md, full PLAN.md, all 27 decisions, all story files. Include only what the stage actually needs. A smaller prompt = more room for the agent to work.

### Teammate Context Budget

| Prompt Section | Target Size | Purpose |
|---------------|:-----------:|---------|
| Stage file | 100-200 lines | Full instructions |
| MEMORY decisions | 10-20 lines | Only relevant ones |
| Resource pooling | 5 lines | Prefix rules |
| Retry protocol | 5 lines | Bounded retry |
| **Total** | **~150-250 lines** | Leaves room for work |
