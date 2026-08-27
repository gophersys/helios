# agentic-instrumentation

phase: green
repo: gophersys/eden
branch: docs/agentic-instrumentation
worktree: ~/code/.worktrees/eden-agentic-instrumentation
pr: -
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

## Blocked

-

## Next

Commit and push the working slice, then prove instruction discovery through the
installed Claude Code and Codex harnesses.
