# drop-arm64

phase:    plan
repo:     gophersys/.devcontainer
branch:   feat/drop-arm64
worktree: ~/code/.worktrees/dc-drop-arm64
pr:       -
attempt:  0/2

## Goal

Stop publishing an arm64 variant of every devcontainer image. The published
linux/arm64 base image is an amd64 Ubuntu userland carrying aarch64 Go binaries,
so it is mislabelled rather than native, and it emulates its userland anyway on
the only host that would consume it. It therefore delivers none of the benefit of
a native image while costing the larger half of a 41.7-minute build.

When this is done, every image builds and publishes amd64 only, no document
claims otherwise, and a future edit that re-adds arm64 fails loudly at the guard
instead of quietly restoring an emulated build.

## Plan

Phase 1 running. Mateo pre-approved: he asked for the plans to be approved on his
behalf so the 3 features run in parallel.

## Proven

- Measured on ghcr.io/gophersys/base:e0c6bc5 by running each manifest variant:
  amd64 -> uname x86_64, dpkg amd64, gofumpt ELF x86-64, consistent.
  arm64 -> uname x86_64, dpkg amd64, gofumpt ELF aarch64, MIXED.
- The Go tools in the arm64 variant execute on an Apple Silicon host, because the
  host runs the aarch64 binaries natively while Docker Desktop emulates the amd64
  userland. That is why nobody saw this.
- base-runner and zephyr-devbox are already amd64 only by earlier measured
  decisions, and are NOT defects.

## Blocked

Nothing.

## Next

Phase 2 once the plan lands.
