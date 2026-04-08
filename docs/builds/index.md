---
min_role: DEVELOPER
---
# Builds

The build system compiles firmware source into hex files (for J-Link flashing) and CFW files (for FUOTA). Push to a watched branch, and the pipeline handles the rest — compile, cache, store artifacts in MinIO.

Builds run through four steps: the [git poller](ci-integration.md) detects a commit, the build service picks up the job, the toolchain compiles against your board target, and the resulting artifacts are stored and recorded in the Concord API with full metadata (commit hash, branch, version, artifact manifest).

Five areas to know:

1. **[Trigger builds](triggering-builds.md)** — manually from the UI/API, or automatically on push. View build history, download hex and CFW artifacts.
2. **[Build configuration](build-configuration.md)** — recipes that define toolchain, commands, and output mapping per firmware type.
3. **[CI integration](ci-integration.md)** — branch watches and automatic triggers via the git poller.
4. **[Build monitoring](monitoring.md)** — the build detail page: status badges, job list, log streaming, and completion tracking.
5. **[Build artifacts](artifacts.md)** — hex files, CFW files, and build.json metadata produced by every successful build.
