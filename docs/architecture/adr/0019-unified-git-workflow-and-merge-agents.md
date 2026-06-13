# ADR-0019: One git workflow machine for all artifact classes; merge agents

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Mateo (intake C26)

## Context

Worktree/merge discipline (09 §3), interface negotiation (09 §4), swarm + FileLease isolation (02
§2, 04 §7), gate policy (04 §5), library lifecycle (10 §8), and document versioning (11 §4)
already exist piecemeal. C26 asks for them to be unified into one **versioning + git workflow
standard** with clear naming conventions, applied identically to documents, architecture, and
implementation as the platform scales — plus **merge agents** that drive a branch to green and
merge. The risk of leaving this implicit is divergence: three artifact classes drifting into three
incompatible workflows, which does not scale.

## Decision

1. **One git workflow machine** governs every versioned artifact (doc 13 §1): the shape
   `propose(branch) → isolate(worktree) → author → validate(gates) → review(policy) → merge →
   version` is uniform; only the gate profile varies by artifact class.
2. **A published branch + commit naming grammar** (doc 13 §2/§4): `<class>/<slug>[/run-<id>]`
   with classes `docs · arch · impl · infra · fix · release · ws<N>`; Conventional Commits with
   actor identity and artifact trailers; enforced by a hook (the ADR-0018 enforcement layer).
3. **Worktree isolation with disjoint FileLeases** is the standard concurrency primitive at all
   scales (doc 13 §3); contracts are frozen before swarm fan-out so members never contend.
4. **Merge agents** (doc 13 §6) are a defined agent role: run the class's gates, fix mechanical
   failures to green within budget, merge fast-forward-only — and **escalate, never decide**,
   frozen contracts, approved artifacts, human-policy gates, real bugs, or budget exhaustion. The
   gates remain deterministic machinery (P8); the agent only does mechanical green-making.
5. **Versioning is git-native and per-class** (doc 13 §7): document envelope versions, library
   semver tags, platform releases, contract freezes — one synthesis table, every version a
   commit/tag.

## Consequences

- doc 13 is the canonical home; 09 §3 (worktree discipline) cites it on next touch; the
  branch-name + commit hook is added to the ADR-0018 enforcement layer.
- Merge agents are an orchestrator capability (02 §2 Swarm kinship) built in a later wave (3B/3C);
  speced now so the workflow is uniform from the first multi-agent run.
- The document case (documents/) is the running proof; architecture and implementation adopt the
  identical machine as they scale — the answer to "same system for docs, architecture, and
  implementation" (C26).
- Open autonomy/strictness questions recorded in doc 13 §9.
