# agentic-instrumentation

phase: wait
repo: gophersys/eden
branch: docs/agentic-instrumentation
worktree: ~/code/.worktrees/eden-agentic-instrumentation
pr: 25
attempt: 0/2

## Goal

Replace Eden's Claude-only, prose-heavy entrypoint with a small dual-harness
operating contract. Claude Code and Codex should discover the same repository
truth, route repeatable work into named processes, and rely on mechanical gates
instead of carrying the architecture corpus in every prompt. Establish the
minimal schema and high-level graph that later process documents—feature, CI,
parallel work, review, release—will extend one at a time.

## Plan

plan: SELF-APPROVED — the risk is creating another documentation system beside
the existing `documents/`, `schemas/`, and `docs/architecture/` systems. This
slice therefore adds only a thin operational index and one machine-checkable
instrumentation contract, cites existing product/architecture homes, and does
not migrate or rewrite canonical product decisions.

Slice contract:

1. Inventory the supported Claude Code and Codex instruction, skill, hook,
   automation, and noninteractive surfaces from official documentation.
2. Inventory Eden's existing agent-session library and current instrumentation;
   cite it rather than inventing a new provider abstraction.
3. Add a failing structural test that requires one canonical operational
   contract, one concise root entrypoint for each harness, valid links, and no
   provider-specific process definitions in those entrypoints.
4. Add the smallest operational schema instance and generated/readable graph
   needed to answer: what is canonical, what is an adapter, what is enforced,
   and where does a repeated workflow live?
5. Replace the root Claude entrypoint with a concise router and add the Codex
   entrypoint. Keep harness-specific configuration only where capabilities
   genuinely differ.
6. Prove the structural test red then green, render/validate the documentation,
   and exercise instruction discovery through both installed harnesses.

Affected project: repository documentation and agent instrumentation only.
Fastest proof: a focused shell structural test plus the existing documentation
checks that cover changed files.

Explicit exclusions:

- No Codex adapter in `libs/go/agentsession`.
- No rewrite or deletion of the architecture corpus.
- No CI, deployment, or devcontainer rebuild.
- No implementation of feature/CI/parallel/release processes beyond registering
  their stable names and future homes.
- No migration of organization tooling repositories.

## Proven

- Official Codex manual refreshed on 2026-08-26; it documents `AGENTS.md` as
  concise durable guidance, `.agents/skills` for on-demand workflows, hooks for
  mechanical lifecycle behavior, and `codex exec`/the GitHub Action for
  automation.
- Official Claude Code documentation reviewed on 2026-08-26; it recommends a
  concise project `CLAUDE.md` (target under 200 lines), skills for reusable
  workflows, hooks for enforcement, and isolated subagents/worktrees for
  parallel tasks.
- Read-only inventory: Eden has a long root `CLAUDE.md` and no root `AGENTS.md`.
- Read-only inventory: `libs/go/agentsession` already owns normalized sessions,
  events, capabilities, credentials, and Claude/OMP adapters; Codex is not yet
  an adapter.
- RED — `bash scripts/agent-instrumentation_test.sh`: exit 1 with
  `agent-instrumentation: missing AGENTS.md`, proving the current repository has
  no Codex entrypoint and does not satisfy the new dual-harness contract.
- GREEN — `bash scripts/agent-instrumentation_test.sh`: exit 0 with
  `engineering-system: OK` and `agent-instrumentation: OK` after adding the
  schema-backed map, validator, and both concise harness entrypoints.
- `shellcheck -S style scripts/agent-instrumentation_test.sh`: exit 0, silent.
- `prettier --write` completed for every changed Markdown, JSON, and JavaScript
  file; `git diff --check`: exit 0, silent.
- The first green attempt failed because an uninitialized parent worktree does
  not populate paths below the `libs` gitlink. The validator now accepts a
  missing nested path only when its top-level owner is a registered `160000`
  gitlink, keeping the check hermetic without weakening ordinary path checks.
- `bash scripts/ctl.sh lint`: exit 0, shellchecked all 12 repository scripts.
- `bash scripts/ctl.sh test`: ran and passed `agent-instrumentation_test.sh` and
  `assert-harness-conformance-preconditions_test.sh`, then stopped on the
  pre-existing host guard `GNU mktemp is required; this host has none`; the
  output explicitly routes that test to the devcontainer. This is partial
  integration evidence, not a green repository gate.
- REAL CODEX — `codex exec --ephemeral --sandbox read-only --json <discovery
probe>` loaded `AGENTS.md`, read the contract, and returned
  `{"entrypoint":"AGENTS.md","contract":"docs/engineering/system.json","schemaVersion":"eden.engineering/v1","featureStatus":"planned"}`.
  The read-only sandbox made no repository changes.
- REAL CLAUDE CODE discovery — interactive `/memory` on Claude Code 2.1.246
  reported `Project instructions — Checked in at ./CLAUDE.md`; the session
  remained at `$0.00`. The one-turn semantic API probe reached Anthropic but
  returned HTTP 429, `You've hit your weekly limit · resets Aug 30 at 12am`,
  with zero input/output tokens and zero cost.
- Mateo explicitly accepted the Claude semantic probe as deferred until the
  subscription limit renews: “assume it works, and just ensure it will start
  working once the limit renews” (2026-08-26). The checked-in `CLAUDE.md`
  discovery is proven locally; no implementation workaround or alternate
  credential path is required.
- Adversarial verifier at detached commit `97a8213`: changing the feature
  status to `unknown` made the structural test fail with
  `invalid process status: feature`; removing `AGENTS.md` made it fail with
  `missing AGENTS.md`. Both guards are proven able to fail.
- Final reference review found four live documents that attributed rules to the
  removed long `CLAUDE.md`. They now cite `docs/README.md`, the root adapter
  pair, or the Claude-specific plugin directly; historical ADR and upstream
  references remain historical records.
- Final focused test, shellcheck, Prettier check, Node syntax check, and
  `git diff --check`: all exit 0.

## Blocked

-

## Next

Poll pull request 25, inspect every completed check's log, and fix any verified
finding before the final cleanup and merge.
