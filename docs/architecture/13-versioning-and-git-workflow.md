# 13 — Versioning & Git Workflow

> Status: Draft · 2026-06-13 · Canonical home for: the artifact-agnostic git workflow machine,
> branch/commit naming grammar, worktree conventions, the merge-agent role, and the
> versioning-per-artifact-class synthesis. Decision basis: ADR-0019.
> Mechanisms are owned elsewhere and cited, never redefined: worktree/merge discipline → 09 §3;
> interface negotiation → 09 §4; swarm + FileLease → 02 §2, 04 §7; gate policy → 04 §5; library
> lifecycle → 10 §8; document versioning → 11 §4; platform releases → 06 §3; git operations →
> the `gitrepository` contract (contracts/gitrepository.md).

## 1. Thesis — one machine, every artifact class

Documents, architecture, and implementation are not three processes; they are one **git workflow
machine** run with three gate profiles. Every change — a charter revision, a system-design edit, a
library implementation — moves through the identical shape:

```
propose (branch) → isolate (worktree) → author → validate (gates for the class) → review (policy) → merge → version
```

Only the **gates** vary by class (a document validates against its schema + traceability; a
library validates against the enforcement gate + tests). The machine, the branch grammar, the
worktree discipline, and the merge mechanics are uniform. Uniformity is what lets the flow scale
to hundreds of concurrent agents (REQ-0022): one mental model, one toolchain, per-class gates the
only variable (C26).

## 2. Branch naming grammar

```
branch := <class> "/" <slug> [ "/" <agent-suffix> ]
class  := docs | arch | impl | infra | fix | release | ws<N>
slug   := word ("-" word)*          (HNS-1 word grammar, 10 §5)
agent-suffix := run-<run-id-short>   (set when an agent owns the branch; omitted for human work)
```

| Class | For | Example |
|---|---|---|
| `docs/` | product/architecture **documents** (tier P/A, doc 11) | `docs/charter-personas`, `arch/system-design-v2` → use `arch/` |
| `arch/` | architecture-tier artifacts + canon specs/ADRs | `arch/connector-fleet` |
| `impl/` | implementation: libraries, apps, code | `impl/secrets-vault-adapter` |
| `infra/` | infrastructure / substrate | `infra/k3d-overlay` |
| `fix/` | bug-report → fix flow (C9) | `fix/REQ-0023-replay-gap` |
| `release/` | a versioned release cut | `release/eden-v0.2.0` |
| `ws<N>/` | swarm member of workstream N (09 §3) | `ws3/observability` |

A pre-push hook (the enforcement layer, ADR-0018) rejects branches outside this grammar.

## 3. Worktree conventions

Concurrent work is **worktree-isolated** — the swarm primitive (02 §2 Swarm/FileLease, 04 §7, 09
§3). One worktree per concurrent unit of work (a swarm member, a merge agent, an agent task), each
on its own branch, holding **disjoint FileLeases** so two never write the same path. Lifecycle
(over the `gitrepository` contract): branch from base → work in the worktree → run gates → merge
through review → **remove the worktree**. Overlapping leases are a planning error, fixed in the
plan, never in a merge (no edit wars — Bender mode 8). At hundreds of concurrent agents this is
what holds: contracts are frozen *before* fan-out (09 §4), so members never negotiate at runtime.

## 4. Commit conventions

- **Conventional Commits**; **no AI/LLM attribution** (ADR-0010 — omit Co-Authored-By).
- **Actor identity**: agent commits carry the Run identity (`meta.authors` linkage, 02 §1); human
  commits carry the human. The audit trail (02 §1 Monorepo) is who-changed-what, queryable.
- **Artifact trailers**: a commit links to what it serves — `Spec: SPEC-0012`, `Requirement:
  REQ-0023`, `Run: <run-id>` — so the provenance chain (03 §5) is reconstructable from git alone.

## 5. The unified flow, per artifact class

Same shape (§1); the **gate column** is the only difference:

| Class | Author | Validate (gate) | Review policy (04 §5) | Version on merge |
|---|---|---|---|---|
| **Document** (11) | intake/arch agent | schema + traceability T1–T7 (documentvalidator) | `edit` (P), `approve` (A freeze) | envelope `version`++ / supersession (11 §4) |
| **Architecture** (canon) | architect agent + human | cohesion + cross-ref + ADR for 🧩 | `approve` | ADR recorded; doc status header |
| **Implementation** (libs/apps) | implementing agent | enforcement gate (ADR-0018) + tests + conformance + integration/E2E (ADR-0017) | `auto` (build/test), `approve` (contract freeze) | library semver tag (10 §8) / app build |

## 6. Merge agents

A **merge agent** (C26) is an agent role that takes a branch claiming to be done and drives it to
a clean merge:

1. Provision a clean worktree at the branch; run the class's full gate set.
2. **Fix mechanical failures to green within budget** — formatting, lint, failing tests it can
   correct, trivial conflicts, missing doc comments — re-running gates until clean.
3. Merge to the base (fast-forward-only; merges go through gates, never a custom merge engine —
   `gitrepository` contract) and remove the worktree.
4. **Escalate, never decide**, anything it may not touch: a change to a **frozen contract** (09
   §4) or an **approved artifact** (11 §4 T5), a gate requiring a human ruling (`approve`/`edit`),
   a non-mechanical test failure (a real bug — routed to a fix branch), or budget exhaustion.

Merge agents are deterministic-where-possible and bounded: they are the scalable answer to "10×
review" (Bender mode 4) without becoming a load-bearing token engine (P8) — the *gates* are
deterministic machinery; the agent only does the mechanical green-making the gates score.

## 7. Versioning, per artifact class (one synthesis)

| Artifact | Version unit | Mechanism | Canonical home |
|---|---|---|---|
| Document | `meta.version` (monotonic) + status lifecycle + `supersedes` | append-only; approved is immutable (T5) | 11 §4 |
| Library | semver, git tag `go/<lib>/vX.Y.Z` | dev→release→adopt; `buf breaking`/`gorelease` gate | 10 §8, ADR-0018 |
| Platform release | one unit (apps + schemas + library floor) | projects pin a version; migration pipelines (LSC) | 06 §3 |
| Contract | freeze + revision-on-renegotiation | frozen at the contract-PR gate; overturn = new negotiation | 09 §4, ADR-0016 |

All four are **git-native** — every version is a commit/tag; history is the audit trail. The
document case is the proof instance Eden runs on itself today (documents/ is version-controlled
exactly this way); the same machine applies to architecture and implementation as we scale (C26).

## 8. Scaling properties

- **No edit wars**: FileLease disjointness + contracts-frozen-before-fan-out (§3) ⇒ concurrent
  worktrees never contend.
- **VCS throughput** (Bender mode 6): short-lived branches, fast-forward-only merges, worktree
  isolation; the platform's own git (eden-authority) or the host's (byo-authority, ADR-0013).
- **Review throughput** (Bender mode 4): merge agents absorb mechanical green-making; humans rule
  only at `approve`/`edit` gates.
- **Statistical validation at org scale** (D5): the gate model already admits sampled/statistical
  evidence (08 §5), so "require all green" can become "require the gate policy" without reshaping
  the machine.

## 9. Open questions

| # | Question | Disposition |
|---|---|---|
| Q1 | Merge-agent autonomy ceiling — may it merge to a protected base unattended, or always open a PR a human can veto? | Default: opens a PR; auto-merges only `auto`-policy classes (build/test) — revisit with run data 🔶 |
| Q2 | Cross-repo versioning (eden ↔ gophersys/libs submodule) — pin-by-SHA vs branch-tracking as the platform scales | pin-by-SHA now (current practice); revisit when release trains exist |
| Q3 | Branch-name enforcement strictness for human ad-hoc work vs agent work | hook warns for humans, blocks for agent branches — confirm |
