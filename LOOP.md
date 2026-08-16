# LOOP — protocol for the recurring autonomous session

Fires every 5 minutes (in-session cron; durable launchd form: 300 s). One run = one small,
finished increment. If you are Claude reading this at the start of a run,
follow it exactly.

## Every run, in order

1. `cd ~/code/research-ui && git pull --rebase` (abort the run on conflict; note
   it in LOG.md).
2. Load instrumentation, in precedence order: `~/.claude/CLAUDE.md` (personal
   defaults), `~/code/.claude/` **if it exists** (it does not today — check,
   and if it has appeared, read it and record the fact in LOG.md before
   proceeding), then this repo's `CLAUDE.md` + `.claude/`.
3. Read `PLAN.md` and the last 3 entries of `LOG.md`. If `BLOCKED.md` has an
   unanswered item that blocks the current phase, work the next unblocked task
   instead.
4. Select the task: first `[ ]` in the lowest unfinished phase. **Multi-agent
   rule:** another agent works here too — first check
   `git log --oneline -5 --since="30 minutes ago"` for its activity; a ⏳ you
   did not write is UNTOUCHABLE until 40 minutes old, whatever it looks like.
   Mark your box `⏳ <UTC ISO time> (loop)` and commit the mark immediately
   (the lock). If the lock push is rejected, someone beat you to it: pull,
   pick the next box instead.
5. Work it. Definition of done:
   - code + tests (prove a new check can fail before trusting it passes);
   - gates green: `uv run --extra dev pytest` + `ruff check` in
     `tools/densui`; `node --check` on any touched JS; touched demos re-run
     their assemble gates;
   - docs updated in the same commit; nothing Ableton-specific outside
     `demos/operator/`;
   - PLAN box ticked, LOG.md entry appended (time, task, what was proven,
     what surprised you);
   - Conventional Commit, no AI attribution trailers, pushed.
6. If the task cannot finish in ~8 minutes, land a complete sub-step (tests
   green) and leave the box ⏳ with a one-line handoff in LOG.md.
7. If genuinely blocked on a decision only Mateo can make: write the exact
   question in `BLOCKED.md`, un-mark the box, commit, and pick another task.
8. Leave the tree clean. Never leave the branch unpushed. Push discipline:
   pull --rebase immediately before pushing; on rejection, rebase once and
   retry; on a second rejection, commit locally, log the situation, stop.
   Never force-push, never rewrite another agent's commits.

## Never

- Skip or soften a failing gate; a gate that cannot run is a failure.
- Bypass `ctl.sh`: gates run through it, so CI and humans see the same truth.
- Push to main while a fleet certification run is in flight — the ci
  concurrency group cancels the running proof (a lock-refresh push killed a
  certification at 6m50s on 2026-08-14). Bookkeeping waits for the verdict.
- Pipe a gate's output through grep/tail/head in the same command that decides
  success — the pipeline's exit status masks the gate's (three real bites:
  fmt rc, geometry rc twice). Run the gate BARE, capture rc, read output after.
- Hand-edit solver-emitted geometry.
- Commit fonts or vendor assets whose licence you have not read.
- Rewrite PLAN.md phases (Mateo owns the plan; you own the checkboxes).
- Let three consecutive runs fail on the same task silently — mark ⚠ with the
  failure text and move on.

## Escalation

`BLOCKED.md` is the only channel for questions. Keep each entry to: context
(2 lines), the exact decision needed, the default you would take if forced.
