---
min_role: DEVELOPER
---
# Firmware Repositories

Concord's git poller watches your firmware repo for commits. When new code lands on a watched branch, a build kicks off automatically — no manual trigger needed.

## Linking a Repo

Open the product detail page, go to the repository settings, and enter the Bitbucket repo URL. Pick the branch to watch (`main`, `develop`, or a `release/*` pattern). Once saved, the poller starts monitoring immediately.

## What Happens on Push

A commit hits a watched branch. The git poller picks it up within its polling interval, fires a build request to the build service, and the resulting hex and CFW files get stored in MinIO. The full chain — detect, build, store — runs without intervention.

If CI is disabled for the product, the poller still tracks commits but skips the automatic build trigger. You can still build manually from the UI or API.

## Repo Structure

The build system expects a standard Zephyr project layout:

- Board overlay files matching your product's board revisions
- A `prj.conf` per build variant
- Build recipes under `recipes/` (see [Build Configuration](../builds/build-configuration.md))

Without these, the build will fail at the toolchain step with a missing board or config error.
