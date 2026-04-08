---
min_role: DEVELOPER
---
# CI Integration

The git poller service monitors every linked firmware repo. When it detects new commits on a watched branch, it fires a build request to the build service — no webhooks to configure, no external CI system to maintain.

## Setup

Open the product's build settings and:

1. Enable CI builds for the product
2. Pick which branches trigger builds — typically `main` and `develop`, plus `release/*` for release candidates
3. Optionally configure different build variants per branch (e.g., MFG builds from `develop`, production builds from `release/*`)

## Triggers

| Event | Build behavior |
|-------|---------------|
| Push to watched branch | Automatic build, full caching |
| Manual trigger (UI or API) | Same pipeline, same artifacts |
| Pull request opened/updated | Automatic build if PR builds are enabled, short-lived cache |

## After a Build

Build results appear in the builds list immediately. From there:

- **Logs** show the full compilation output — useful for diagnosing toolchain or overlay errors
- **Artifacts** are downloadable hex and CFW files, ready for validation or J-Link flashing
- **Validation** can be triggered directly against a successful build, pushing the firmware into the five-stage pipeline
