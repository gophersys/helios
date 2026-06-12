---
meta:
  id: product-charter
  type: product-charter
  schema_version: 1.0.0
  project: eden
  status: draft
  version: 1
  created: 2026-06-12
  updated: 2026-06-12
  authors:
    - run: founder-intake-01
    - human: mateo
  links:
    realizes: []
    supersedes: null
    informs: []
  source:
    - run: founder-intake-01
      span: "C1, C2, C7, C8, C9, C12, C18, C20"
data:
  personas:
    - id: PER-0001
      name: The product founder
      description: |
        A founder with a clear product vision and little architecture knowledge (C1). They want to
        create a cheap proof-of-concept that "just works" — first for themselves to test the idea,
        then for a small cohort of real test users, then for 1000+ user production deployments
        (C2) — without ever becoming an operator. They think in features and users, not in
        clusters, release trains, or git internals; the platform's job is to lift the technical
        burden off them while leaving the door open to scale. They describe what they want in a
        conversation and gate the results; they do not supervise the build (charter 00 §4, T3).
    - id: PER-0002
      name: The picky platform engineer
      description: |
        A highly technical operator who insists on bring-your-own-everything (C7): their own
        cluster, their own cloud, their own git host. In this posture Eden's backend holds only
        organizational metadata about their projects — their repos and infrastructure live entirely
        on their platforms (C8, charter 00 §5 byo-authority). They will not accept hand-wavy
        guarantees: they demand either real, enforced gates (Eden installed as a GitHub/GitLab app
        with required status checks and branch protection) or an explicit, permanently visible
        advisory badge that says the guarantee is off (C8, C18). What earns their trust is that
        Eden is extremely well git-integrated and always knows exactly what has drifted between
        their repo and the state Eden knows about (C8). Done right, the release-engineering
        discipline produces a time saving large enough to be the persona's primary adoption
        driver (C9).
    - id: PER-0003
      name: The builder
      description: |
        Us — the team developing Eden, with Eden. Eden is project #1 of its own document system and
        is built through its own gates (C12, charter 00 T5, doc 11 §1). The builder needs the
        self-build to be visible as the standing proof that the platform can code anything: every
        Eden library that ships should pass through Eden's own evidence-gated pipeline, with the
        local k3d/kind cluster as the dogfooding home (C19). The builder's interest is that
        pluggability and extensibility hold — connectors and archetypes are added without
        architectural change (C12) — so the proof keeps proving itself as the platform grows.
---

## Vision

A founder with a product idea and no architecture knowledge should be able to describe what they
want, watch it become schema-valid documents, and see a working system deployed and observable —
without learning what a cluster is (C1, C2, C20). Eden is the discipline layer that makes that
true: it turns an intake conversation into a typed document chain, generates a real monorepo the
user owns from opinionated archetypes, drives evidence-gated agent pipelines to build it, and
keeps the result observable, billable, and maintainable from a one-person PoC to a 1000+ user
production fleet (charter 00 §1, C2, C12).

The same platform that hides every technical detail from the founder exposes all of it to the
engineer who wants it. A picky platform engineer connects their own cluster and their own git host,
keeps full guarantees, and gets release engineering — versioning, release trains, hotfix flow,
drift detection — as a product feature so good it genuinely saves them time (C7, C8, C9, C18). When
it works, release engineering is invisible to the founder and a measurable time-saving for the engineer, and
Eden's own libraries are the standing proof: Eden builds Eden, through Eden's own gates (C12).

## Problem

Two people are underserved by everything that exists today, at opposite ends of the same gap.

The **founder** (PER-0001) has a product vision but no path to a running, trustworthy system
without hiring operators or learning infrastructure they will never want to own. Today they either
stall at the prototype, glue together tools they cannot maintain, or pay for a team to carry the
operational burden — releases, versioning, maintenance, bug-fix flows — that they should never have
to think about (C9). The cost is that good product ideas never reach the small cohort of test users
that would validate them, let alone production (C2).

The **picky platform engineer** (PER-0002) has the opposite problem: the tools that promise to lift
the burden take control they will not surrender. They want to keep their own cluster, cloud, and
git host, and they will not trust a platform that cannot prove what it actually enforces or tell
them precisely what has drifted from the state it knows (C7, C8). Platforms that "set it and forget
it" by taking ownership are non-starters for them; platforms that only advise without ever
enforcing are theater. Nobody offers them real, per-project gate guarantees with honest, permanent
badges when a guarantee is off (C18).

Underneath both is a trust problem: a platform that claims it can build and operate software at
scale has to prove it. The standing proof is self-build — if Eden cannot build Eden through its own
gates, no founder should believe it can build their product (C12).

## Success criteria

- **A founder ships an observable PoC with zero infrastructure knowledge.** PER-0001 completes the
  intake conversation, the system is generated and deployed onto a cluster (central metered or a
  free local k3d), and they observe its deploys, health, and spend in the dashboard — without ever
  naming a cluster, a registry, or a release process (C2, C20).
- **Eden's own libraries are built through Eden's own gates.** Every Eden library that ships passes
  through Eden's evidence-gated pipeline, and the self-build is visible as the standing proof that
  the platform can code anything (C12).
- **A technical user keeps full guarantees on their own footprint.** PER-0002 connects their own
  cluster and their own git host, and retains the complete set of gate guarantees and drift
  detection — or sees an explicit, permanently visible advisory badge naming exactly which
  guarantee is off (C8, C18).
- **Release engineering is invisible to founders and a time-saver for engineers.** The same
  versioning, release-train, hotfix, and bug-report-to-fix machinery that a founder never has to
  think about is the feature a technical user values most — and it genuinely saves them time (C9).

## Non-goals

- **Not making the founder an operator.** Eden lifts the operational burden; it does not teach the
  founder to run clusters, cut releases, or manage git. The technical surface stays optional, never
  required, for PER-0001 (C1, C9).
- **Not taking ownership from the engineer.** In byo-authority mode Eden holds organizational
  metadata only; repos, infrastructure, and god-mode credentials stay with the user. Eden never
  silently absorbs or rewrites what lives on the user's platforms (C7, C8, charter 00 §5).
- **Not hiding what is off.** Eden does not present advisory-only mode as if it were enforced; when
  a guarantee is not enforced, the dashboard says so, permanently and visibly (C18).
- **Not a model play.** Eden's bet is the discipline layer — contracts, evidence, observability —
  not a better agent; the proof of the platform is that it builds itself, not that it has a
  cleverer model (C12, charter 00 §2).
