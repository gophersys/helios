# Git commits

## Identity

Author every commit as **yourself** — your own name and corekinect email. Set repo-local identity on the first commit in a fresh clone:

```bash
git config user.name "Your Name"
git config user.email "you@corekinect.com"
```

Use repo-local config (`git config` without `--global`) so other repos aren't affected.

(Before the 2026 handoff this rule pinned every commit to a single fixed identity; it now reflects per-person authorship — e.g. Jared Walton as project owner/lead/admin, Blake Ottinger as test & tools engineer. The "no Claude/AI attribution" rule below is unchanged and unconditional.)

## Format — Conventional Commits

```
<type>(<scope>): <imperative subject>

<body — optional, wrapped at 80, explains WHY, not WHAT>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`, `build`, `style`.

Scope is optional but encouraged. Use the project/app name or domain: `http-api`, `frontend`, `mtib-server`, `prisma`, `deploy`, `concord-remote`.

Subject: ≤72 chars, imperative mood ("add", not "added" or "adds"), no trailing period.

Examples (from this repo's recent history):

- `fix(http-api): wire BITBUCKET_WORKSPACE + add CI guard`
- `chore(release): v0.9.18`
- `feat(fixture): allow MOTION_ENABLED per fixture type`

## Forbidden in commit messages, code, or docs

**Never** mention Claude, Anthropic, AI, LLM, copilot, or any automated tool in:

- Commit messages (no `Co-Authored-By: Claude`, no AI attribution footers)
- Code comments
- Documentation
- PR titles or descriptions
- Branch names

This is unconditional.

## The `[no-arch-change]` marker

When a commit is purely cosmetic (typo, log message wording, formatting, version bump, lockfile update) and does not change behavior or shape, add `[no-arch-change]` somewhere in the commit message. This signals to the knowledge-freshness hook that no `.claude/knowledge/` update is required.

Examples:

- `chore(deps): bump prisma 5.6 → 5.7 [no-arch-change]`
- `fix(http-api): typo in log message [no-arch-change]`

Do not use it to bypass a knowledge update you should be writing. The hook is there to keep `.claude/` honest.

## Pushes

- New branches: `git push -u origin <branch>`.
- Never force-push to `main` (or any release branch) without explicit confirmation.
- Pre-push hooks (if present) shouldn't be bypassed.

## Branching

- `main` is the trunk.
- Feature branches: `feat/<short-name>`, `fix/<short-name>`, `chore/<short-name>`.
- Release branches: cut by `/concord-release` skill — don't create by hand.

## PR-less direct commits

Direct pushes to `main` are technically allowed for trivial fixes but discouraged. Prefer a feature branch + PR even for one-line changes — the diff is easier to read in review.
