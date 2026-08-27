---
name: refresh-claude
description: Audit `.claude/` against the actual codebase. Surface stale knowledge files, missing path-map entries, and dead references. Run periodically or after a large refactor.
---

# /refresh-claude

This is the audit skill — the maintenance counterpart to the per-commit knowledge-freshness hook. The hook catches forgotten updates at commit time; this skill catches the gradual drift that builds up despite the hook.

## What the agent does

1. **Walk the knowledge tree**: for each `.claude/knowledge/<path>.md`, identify the code path it claims to describe. Use the path-mirroring convention (`apps/backend/http-api.md` ↔ `apps/backend/http-api/`).

2. **Verify the code path exists**: if a knowledge file refers to a deleted folder, surface it.

3. **Spot-check content freshness**: read the knowledge file, then read the actual entry points / structure of the code. Are the file paths real? Are the listed routes / models / RPCs still there?

4. **Find orphan code paths**: walk `apps/`, `libs/`, `deploy/`, `.ci/`. For each major folder, check there's a corresponding knowledge file and a row in `.claude/hooks/knowledge-map.txt`. Orphans are surfaces in the system the knowledge tree doesn't cover.

5. **Cross-references**: every internal link in a knowledge file should resolve. Find broken ones.

6. **Produce a report** with three sections:
   - **Stale**: files where content no longer matches reality.
   - **Missing**: code paths without knowledge.
   - **Broken**: links/references that don't resolve.

7. **Don't auto-fix**. Surface the issues; the user decides what to update and when. Each fix is its own commit that satisfies the freshness hook.

## When to run

- Quarterly, as a baseline.
- After any major refactor that moves files between apps.
- After adding or deleting a top-level app.
- When the user says "something feels off in `.claude/`".

## Output

A markdown report at `.claude/refresh-<YYYY-MM-DD>.md`. Includes:
- Per-file findings with file paths and line numbers.
- A suggested order to address them (highest-leverage first).

The report is temporary scratch — delete it once the findings are addressed (or `.gitignore` the `refresh-*.md` pattern if you'd rather not eyeball it every time).

## Don't

- Don't silently delete knowledge files. Empty files are worse than stale files because they signal "this area is unmapped" falsely.
- Don't expand knowledge files preemptively. Only fix what's actually drifted.
