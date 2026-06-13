# ADR-0017: Quality bar — post-wave architecture review, true coverage, no shortcuts

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo (intake C24)

## Context

ADR-0016 established the wave model with adversarial verification and review between waves. C24
sharpens the standard: every wave must be followed by a dedicated **review-and-architecture
audit** (reviewers + architects, not a single verifier); test coverage must be **true** —
behavioral and integration and end-to-end, not line-count theatre — with integration and E2E
explicitly valued; and the agent-chat surface is named the long-term load-bearing feature, so its
observability, event mechanism, and scale/reliability properties are held to a Google-level bar
(no shortcuts; every function and feature implemented and tested). Go 1.26.

## Decision

1. **Post-wave review wave (mandatory).** Each implementation wave is followed by a review wave
   running in parallel lanes: (a) **architecture cohesion** — do the libraries compose cleanly,
   honor the contracts and 10 §6.1 uniformity, and avoid the easy-way-out (no stubs masquerading
   as implementations, no skipped error paths, no "TODO" load-bearing gaps); (b) **true coverage
   audit** — every contract behavior has a test; substrate libraries have integration tests
   against real docker/k3d; user-facing flows have E2E; coverage gaps are reported as findings,
   not hidden; (c) **adversarial correctness** — find bugs, race conditions, resource leaks. Its
   findings are triaged and fixed before the wave is declared done; then Mateo reviews.
2. **Three test tiers, all first-class** (sharpening 08): **unit + conformance** (every library),
   **integration** (real substrate — docker daemon, k3d cluster — for any library that touches
   one; mocks are not acceptable substitutes), **end-to-end** (Playwright forced-CRUD over the
   running frontend: objects created through the UI are destroyed through the UI before exit;
   nested creation covered — C23). A feature is not "done" until its tier-appropriate tests pass
   against real dependencies.
3. **The agent-chat event mechanism is held to an explicit bar** (REQ-0020..0024): server-triggered
   sequence-numbered events; per-session fan-out scaling to hundreds of concurrent sessions per
   project; start/stop/resume reliable for both the agent and the stream; lossless,
   no-duplication reconnect/replay from persisted events; the full telemetry taxonomy
   (message/thinking/tool/skill/file/branch/token/cost/model) captured structured and rendered,
   never flattened to log text. This is a correctness requirement, not a polish item.
4. **No shortcuts as a reviewable property.** "It compiles and a happy-path test passes" is not
   acceptance. Reviewers specifically hunt for: unimplemented branches, swallowed errors,
   mock-only coverage of real-substrate features, and display-only UI state with no persisted
   backing.

## Consequences

- Every wave costs more (a full review wave follows it) and is more trustworthy; this is the
  intended trade.
- Wave 3B's definition of done now includes integration tests against k3d/docker and a Playwright
  E2E lane, plus a post-wave architecture audit before Mateo's review.
- 08 (testing strategy) is amended on next touch to name the three tiers and the
  real-substrate-not-mock rule.
- The agentsession contract's resumability and fan-out sections (contracts/agentsession.md) become
  acceptance-bearing against REQ-0023/0022.
