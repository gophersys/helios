# ADR-0008: Claude Code is the first agent connector

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** Mateo

## Context

The kernel's `codingharness` needs a first implementing loop behind the F4 agent contract.
Candidates: Claude Code (the harness Eden itself is being built with); pi/oh-my-pi + DeepSeek
(cheapest tokens, clean RPC, ✅ already validated by `poc/knowledge`'s 72-run matrix and
documented in docs/research/01–02); an own loop on `agentconfiguration.Client` (raw model API,
spec-driven §8's original v0.1 plan).

## Decision

**Claude Code first** (headless/SDK mode) as the F4 adapter the L0 kernel drives. pi/oh-my-pi +
DeepSeek is the committed **second** adapter — it proves the contract abstraction with a
maximally different harness and supplies the cheap-model arm of the routing economics. The
own-loop codingharness is re-scoped from "v0.1's biggest item" to a later adapter, built only if
external harnesses prove limiting.

## Consequences

- ⚠️ Amends spec-driven §8's v0.1 cut (own loop first): building Eden with the same harness the
  kernel drives means one set of harness behaviors to learn, and the biggest v0.1 work item is
  replaced by an adapter over a supported product surface.
- The F4 contract must be authored against two known targets from day 1 (Claude Code now, pi RPC
  next) so the first adapter doesn't quietly become the contract.
- Token-cost exposure: v1 kernel runs at Claude prices; the routing split economics (04 §6)
  remain a hypothesis until the second adapter lands. Mitigation: the contract carries the token
  ledger from run 1, so the comparison is measured, not argued.
- `poc/agents`' transport/factory patterns and `poc/knowledge`'s omp harness integration are
  donor material for the adapter layer.
