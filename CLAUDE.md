# research-ui — instructions for Claude sessions

This repository is the home of the Dense-UI research programme: general-purpose
tools and framework for blind dense-UI layout. **Nothing outside
`demos/operator/` may be Ableton-specific.**

## Instrumentation precedence (read at session start)

1. `~/.claude/CLAUDE.md` — Mateo's personal defaults (fail-loud, Conventional
   Commits, no AI attribution trailers, always push, ultracode).
2. `~/code/.claude/` — org-level; **does not exist today**. If it appears, it
   outranks personal defaults inside `~/code`.
3. This file + `.claude/` here — outranks both inside this repository.
4. The personal `ui-*` skills and `ui-architect` agent in `~/.claude` cite
   `~/.claude/references/dense-ui/` — a snapshot of this repo's `framework/`.
   THIS repo is the source of truth going forward; sync direction repo -> home
   (PLAN P7 tracks the dedup).

## Hard rules

- Layout is computed, never judged: geometry comes from `tools/densui` +
  measured anchors; every change to a demo re-runs its gates. A hand-edited
  solved-position block is a defect.
- FAIL-NOT-SKIP: a gate that cannot run fails the build and names the missing
  tool. No `continue-on-error`, no advisory checks, no `|| true`.
- Prove new checks can fail before trusting that they pass.
- Licensed assets (Ableton Sans, Live screenshots) are never committed beyond
  the private research fixture already present; builds take font paths as
  parameters and must work with free fonts.

## gophersys standards

- `ctl.sh` is the single entry point (build/test/vet/fmt) — CI and humans call
  the same script, the eden/cictl convention. CI runs on the org ARC fleet
  (`runs-on: arc-org`); eden/infrastructure owns the controller.
- **Another agent may be working in this repo concurrently.** Follow LOOP.md's
  collision protocol strictly: pull before locking AND before pushing, never
  take a foreign ⏳ younger than 40 minutes, never force-push, and on push
  rejection rebase once and retry — then stop and log rather than fight.

## Gates

```sh
cd tools/densui && uv run --extra dev pytest && uv run --extra dev ruff check .
node --check demos/operator/build/*.js
python3 demos/operator/build/assemble.py     # full build: solver + 6 proofs (macOS + local fonts)
```

## The loop

`LOOP.md` is the protocol for the recurring autonomous session working
`PLAN.md`. Human direction goes into `PLAN.md`; the loop's findings go into
`LOG.md`; blockers go into `BLOCKED.md`.
