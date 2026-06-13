# ADR-0016: WS1 contracts frozen as reconciled; the build proceeds in waves

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo (intake C23: "do a full recap of what libraries you need to build, build
  them, full TDD"); ballot default applied by the orchestrator, amendable

## Context

The seven contract drafts (six 10 §4 patterns + the agentsession F4 connector) awaited the
freeze gate (09 §4 step 3). Mateo received the condensed freeze ballot (10 contestable rulings
of 51) and subsequently ordered implementation. Separately, the build now needs a formalized
multi-stage workflow: interface agreement → TDD implementation with real-substrate tests →
integration with user-journey tests (C23).

## Decision

1. **All seven contracts freeze at their reconciler rulings** (the ballot's accept-all default).
   Any of the 10 ballot rows remains overturnable by Mateo at any time; an overturn is a new
   negotiation (09 §4) producing a contract revision before or after the affected library lands —
   never a silent edit.
2. **The build proceeds in waves** (09 §9): each wave = (a) negotiate any new contracts it
   needs, (b) implement frozen contracts TDD-first — tests authored from the contract before
   implementation; conformance suites mandatory; sandbox adapters tested against **real
   substrates** (docker daemon; kind clusters) not mocks, (c) verify adversarially, (d) Mateo
   reviews new contracts/rulings between waves.
3. **Test infrastructure is a first-class deliverable**: the `testing` pattern implementation
   plus real-substrate harnesses (container and kind-cluster helpers, owned where the
   workspaceprovider negotiation places them), and a Playwright user-journey harness for the
   frontend whose tests create real objects through the UI and destroy them through the UI
   before exit (forced CRUD, nested-creation coverage).
4. **Library placement per canon**: implementations land in `libs/go/<name>` (the gophersys/libs
   submodule, ADR-0009 B); during the build phase apps consume them via the root gitignored
   `go.work` (the sanctioned dev override, 10 §8); release tagging + the full adopt machinery
   activate when the first app ships.

## Consequences

- Wave 3A (now): leaf-pattern implementations (errors, dependencies, configuration) + dependent
  patterns (testing, secrets, observability) + new contract negotiations (workspaceprovider,
  gitrepository, orchestrator).
- Wave 3B (after 3A + review): sandbox adapters with real docker/kind tests, git operations,
  orchestrator v0, the agent-session service, the chat surface, the Playwright harness.
- Environment verified: docker 29.4.0 and kind v0.32.0 present; kubernetes adapter tests run
  against ephemeral kind clusters locally.
