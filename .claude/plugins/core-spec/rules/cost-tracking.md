# Cost Tracking Protocol

Overnight autonomous execution can consume significant API tokens. Track costs
to prevent silent budget exhaustion and provide visibility.

## Per-Stage Cost Tracking

Each agent reports estimated token usage in STATUS.md after completing:

```markdown
## Cost Summary
| Stage | Tokens (est.) | Duration | Turns |
|-------|:------------:|:--------:|:-----:|
| 1 | ~45K | 35 min | 12 |
| 5 | ~30K | 20 min | 8 |
| **Wave 1 Total** | **~75K** | **55 min** | **20** |
```

### How to Estimate

Agents don't have direct token counters, but can estimate:
- Each file Read: ~500-2000 tokens (depending on file size)
- Each file Write: ~1000-5000 tokens
- Each Bash command: ~200-1000 tokens
- Each agent prompt: ~2000-10000 tokens (depending on stage file size)
- Each tool call overhead: ~100 tokens

**Rule of thumb:** Count your tool calls × 1000 tokens for a rough estimate.

## Budget Ceiling

If `--max-budget-usd` is configured, the cron watchdog monitors:

```
On each cron fire:
  1. Read cost summary from STATUS.md
  2. Sum all stage costs
  3. If total > 80% of budget → WARNING notification
  4. If total > 95% of budget → HALT notification, stop launching
```

## Discord Cost Reporting

Include cost in every milestone notification:

```
"✅ Wave 1 complete. Stages 1,5 merged. ~75K tokens, ~$0.45 est."
"🚀 Wave 2 launching. Budget used: ~75K/500K tokens (15%)"
"🎉 All complete! Total: ~350K tokens, ~$2.10 est. across 16 stages."
```

## Cost Optimization Tips

For spec authors and agents:

1. **Lean teammate prompts** — Include only relevant MEMORY.md decisions, not all 27
2. **Read selectively** — Don't read entire files when you need 10 lines
3. **Batch operations** — 1 Write with 100 lines < 5 Writes with 20 lines each
4. **Compact proactively** — At 50% context, compact to reclaim budget
5. **Use haiku for exploration** — If a stage is mostly reading/exploring, use `model: "haiku"` for the agent
6. **Cache results in files** — If multiple agents need the same data, one writes it to a file, others read it
