---
min_role: DEVELOPER
---
# Firmware Repositories

Link Bitbucket repos to a product. The git poller watches them for commits and PRs.

## Setup

Product detail → repository settings. Enter the repo slug, select the watch branch. Polling starts immediately.

Two repos per product:

- **Production firmware** — main application
- **Manufacturing firmware** — POST and factory test code

## Trigger behavior

Commit on a watched branch → poller detects → build run triggers. No manual step.

Polling can be disabled per product. Commits are still tracked, but builds don't auto-trigger. Manual builds work via UI or API.

## Expected repo structure

Standard Zephyr layout — board overlays matching your revisions, `prj.conf` per variant. Missing definitions fail at the toolchain step.
