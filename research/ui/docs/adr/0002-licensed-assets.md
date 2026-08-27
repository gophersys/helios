# ADR-0002: Licensed Assets Stay Out of the Tree

- **Status:** Accepted
- **Date:** 2026-08-14
- **Deciders:** Mateo

## Context

The Operator fidelity demo needs Ableton's own assets to be honest: the Ableton Sans fonts
(from the licensed Live install on this machine) and a reference screenshot of Live 12. The
assembled `operator.html` embeds those fonts as data URIs. None of this is ours to
redistribute, and the repo — while private today — must not become a distribution channel by
accident (a visibility flip, a fork, a CI artifact).

## Decision

Licensed assets never enter git history beyond the private-repo research fixture, and never
enter a build artifact that leaves the machine:

- Assembled pages that embed licensed fonts (`demos/*/operator.html` and kin) are gitignored;
  the build re-assembles them locally from the solver output plus locally-resolved fonts.
- CI builds with free faces (DejaVu) — the solver and audits must hold under BOTH faces, which
  is itself a real test (font-swap centring is covered by the cap-table gate).
- The reference screenshot (`demos/operator/reference@2x.png`) is the ONE sanctioned
  exception: it is committed as the research fixture the measurements were taken from, and it
  is what "beyond the private-repo research fixture" means. It never enters a build artifact,
  and flipping the repo public requires purging it from history first.
- `ctl.sh geometry` runs fidelity mode only where the licensed fonts exist; their absence in
  CI selects `--font` mode explicitly — a stated substitution, not a silent skip (ADR-0001).

## Consequences

Easier: the repo can be shared, forked, or opened later without an assets audit; CI needs no
font secrets. Harder: fidelity numbers are reproducible only on a machine with a Live
license, and the README's illustrations must use the free-font builds. Invalid: committing an
assembled page, committing font binaries, or uploading fidelity artifacts from CI.
Alternative rejected: a git-crypt/LFS vault for the fonts — encryption inside a repo still
distributes the ciphertext and invites exactly the accident this ADR exists to prevent.
