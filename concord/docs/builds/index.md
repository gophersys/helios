---
min_role: DEVELOPER
---
# Builds

Compiles firmware source into hex files (J-Link flashing) and CFW files (FUOTA). Push to a watched branch → git poller detects → build service compiles → artifacts stored in MinIO.

## Sections

- **[Triggering builds](triggering-builds.md)** — manual from UI/API, or automatic on push
- **[Build configuration](build-configuration.md)** — recipes, toolchain, output mapping per firmware type
- **[CI integration](ci-integration.md)** — branch watches and automatic triggers via the git poller
- **[Monitoring](monitoring.md)** — build detail page with status, job list, log streaming
- **[Artifacts](artifacts.md)** — hex files, CFW files, build.json manifest per successful build
