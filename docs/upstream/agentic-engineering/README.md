# Upstream — Agentic Engineering Research

> Status: Verbatim point-in-time upstream references. Helios-era naming is preserved by design
> (per ADR-0014). Copied 2026-06-12 from `~/Documents/research/agentic-engineering/`, which
> remains the historical original. These files are not maintained here and are not canonical —
> do not edit them; cite the canonical Eden specs for current rulings.

This is a snapshot of the four-part "Agentic Engineering Research" series (May–June 2026): an
opinionated blueprint for a disciplined single-developer agentic-coding setup that counters "vibe
coding" by encoding senior-engineer practice into harness primitives (hooks, skills, specs,
verification). The original upstream README (now replaced here by this index) framed the central
thesis: in mid-2026 the model layer has commoditized, so durable differentiation lives in the
discipline layer above it.

## Index

| File | Summary | Reading time |
|---|---|---|
| [`00-model-harness-discipline-research.md`](00-model-harness-discipline-research.md) | Foundation: hard data on tokens, pricing, and benchmarks shows the model gap has closed, argues the durable edge is the harness discipline layer, and recommends a concrete single-developer stack built up in order, not in parallel. | ~15 min |
| [`01-software-ecology-problems.md`](01-software-ecology-problems.md) | Catalogs 15+ "10x tipping point" failure modes from Bender's talk (review bottleneck, quadratic test compute, edit wars, mentorship gap) and his prescription: invest in capacity visibility, validation, isolation, and abstraction. | ~10 min |
| [`02-ecosystem-components-and-connections.md`](02-ecosystem-components-and-connections.md) | Captures Bender's developer-ecosystem graph (17 nodes, ~35 edges read from a video still), runs a hub analysis (Observability, Code review, Release tie at degree 6), and locates where disciplinary investment fans out. | ~10 min |
| [`03-extended-ecosystem-components.md`](03-extended-ecosystem-components.md) | Extends the graph with 8 defended nodes (Spec, Knowledge, Hooks, Memory, Code intel, MCP, Supply chain, Human gate) and 9 rejected ones; the harness becomes the degree-9 center of mass, yielding a three-concentric-ring solution shape. | ~12 min |
| [`04-universal-sdlc-process-model.md`](04-universal-sdlc-process-model.md) | Consolidated model: a software category = one invariant 10-phase spine plus a 5-parameter vector, with a typed `Cell` and 10 invariants stress-tested across ~20 categories; carries an epistemic legend and a claims ledger. | ~9 min |

Reading order is sequential — each doc builds on the previous. The original upstream README also
listed planned-but-unwritten docs (05 scalable system design, 06 parallel-dev contracts, 07
verification strategy, 08 implementation roadmap); none are present in this snapshot.

## Skipped from the source

The upstream directory also contains an `archive/` subdirectory (the 2026-06-01 working trail for
doc 04: stress-test, cell-parameter schema, instances/validation) and two `.excalidraw` diagram
binaries (`02-ecosystem-diagram.excalidraw`, `03-extended-diagram.excalidraw`). These were not
copied: only top-level `.md` files were brought over, and `archive/` is explicitly skippable.
