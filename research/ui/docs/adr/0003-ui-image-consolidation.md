# ADR-0003: The `ui` image absorbs and retires `research-ui-ci`

- **Status:** Accepted
- **Date:** 2026-08-16
- **Deciders:** Mateo Segura

## Context

The 2026-08 image-consolidation program reduces the org's images to one
lineage: `cloud` (the reduced base) plus one delta script per domain.
This repo publishes its own CI image, `ghcr.io/gophersys/research-ui-ci`
(`ci/Dockerfile`), and builds its devcontainer FROM that image. The
census measured zero toolchain drift between dev and CI here — a
property worth keeping. Full build-ready notes: `docs/image-notes.md`.

## Decision

- `ghcr.io/gophersys/ui` is the one image for all UI work: dev
  container, CI container, and the `ui-runner` child. It is built
  `FROM cloud` + `_delta/ui.sh`, which lives in the eden
  `.devcontainer/_delta/` directory and is shared with the `matrix`
  image.
- `ui` absorbs the full `research-ui-ci` toolchain. Nothing from the CI
  toolchain is dropped; the devcontainer comfort layer is not
  re-installed because cloud already carries it.
- When `ui` is green, this repo retires its image build:
  `ci/Dockerfile`, `.devcontainer/Dockerfile`, and
  `.github/workflows/build-ci-image.yml` are deleted. Dev and CI pin
  the SAME `ui` digest.
- If no arm64 Chromium source proves out (risk R3), `ui` narrows to
  `linux/amd64` through the narrow-loudly switch — a stated decision in
  the workflow, never a silent skip.
- The ghcr package `research-ui-ci` stays published as the rollback
  anchor until the program's section-8 consolidation. Mateo authorizes
  its deletion. Nobody else.

## Consequences

- Easier: one image to build, pin, and audit; the zero-drift property
  becomes structural (one digest for dev and CI); the ui delta and the
  matrix ui layer move with one edit.
- Harder: this repo no longer owns its image build. Toolchain changes
  go through eden's `_delta/ui.sh` and the section-4 publish gate.
- Invalid after migration step (c): `ci/Dockerfile`,
  `.devcontainer/Dockerfile`, `build-ci-image.yml`, and the
  `|| (retry without gh)` devcontainer fallback.
- Rollback: the deleted files stay in git history; one commit re-pins
  CI and the devcontainer to `research-ui-ci` until section-8 removes
  it.
- Alternatives rejected: keep a separate `research-ui-ci` (duplicates
  the toolchain across the six-image program and re-opens drift);
  build `ui` from this repo (the delta script is shared with `matrix`
  and belongs where both consumers live).
