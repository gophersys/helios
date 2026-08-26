# P1 — the feasibility scorecard

Status: v0, depth D1 (designed with Mateo, 2026-08-26). The machine-readable
registry lives in [`40-p1-registry.yaml`](40-p1-registry.yaml); this file is
its contract. Together with [`30-p0-graph.yaml`](30-p0-graph.yaml) it closes
R2's two-way trace: the graph may only feed ids the registry defines, and
every registry metric names the questions that feed it.

## The frame

| # | Rule | Meaning |
|---|---|---|
| F1 | **The registry is the contract** | One record per metric id. Graph lint checks BOTH directions: graph feeds ⊆ registry ids, registry fed_by ⊆ graph question ids. |
| F2 | **Scores are coarse on purpose** | Scale: `green · amber · red · unknown`. The MEANING of each level is written per metric in the registry, never implied. Numbers wait until P1 has measured history. |
| F3 | **Evidence over vibes** | Every score carries evidence lines. Where a function maps to a capability the catalog covers, the score is a QUERY — records + depth (D1/D2/D3) cited. Outside coverage → a named research task, cited at D1+. |
| F4 | **The machine recommends, the human decides G1** | Scorecard computed; go/pivot/kill recommended with reasons; the DECISION is the human's, recorded with their verbatim words (R4). |
| F5 | **Human gates are structural** | `q.comp.safety = serious` raises a human gate the system cannot score around: no recommendation until a human clears it. |

## Scale semantics (global; per-metric meanings refine, never contradict)

| Level | Global meaning |
|---|---|
| green | evidence supports it; no action needed |
| amber | a path exists but is unproven or tight; named as a risk in the recommendation |
| red | evidence against it as stated; forces pivot consideration |
| unknown | blocked by an UNKNOWN answer — the blocking PIR field is named (R5) |

## Verdict rules v0 (recommendation only — F4)

1. Any **core** metric red → recommend **pivot**. Recommend **kill** only
   when the red metric IS the product's stated magic
   (`metric.tech.exists` red ∧ the magic is the differentiation in
   `pir.novelty`).
2. No reds → recommend **go**; every amber is named in the reasons.
3. Any human gate open → **no recommendation** until a human clears it.
4. Any core metric `unknown` → no recommendation; the blocking UNKNOWNs
   are listed (G0 should have prevented this — reaching P1 with one is
   itself a defect to report).
5. `minor` metrics never change the verdict; they color the reasons.

## The scorecard record

```yaml
schema: sfd.scorecard/v0
pir: {ref: ..., hash: ...}       # the exact PIR scored
scores:
  - id: metric.tech.exists
    score: amber
    evidence:
      - "catalog: connectivity capability D1 on esp32c6 @ zephyr 413b789d"
    blocked_by: []               # UNKNOWN pir fields, when score=unknown
derived:
  needs_hardware: true           # any sensing/actuation/hmi/physical function
  needs_firmware: true           # needs_hardware AND on-device logic
human_gates: []                  # e.g. {gate: safety-serious, cleared_by: ...}
recommendation:
  verdict: go | pivot | kill
  reasons: []
decision:                        # F4 — the human call, with provenance
  verdict: ...
  by: ...
  quote: "..."
  at: <iso8601>
```

## The catalog seam (decided: locked)

`metric.tech.exists` and `metric.feasibility.connectivity` are scored
`agent+catalog`: the scorer maps the product's functions onto S1's
capability vocabulary, then queries the capability index — supported SoCs,
component records, per-record depth. A capability the catalog covers at
D2+ scores green on availability; D1 scores amber; no coverage and no
known example scores red, and the gap becomes a named research task.
P1 is thereby the catalog's second consumer, after P4.

## Enforcement status (stated exactly)

| Piece | Status |
|---|---|
| metric registry (16 metrics + 2 derived flags, typed) | **AUTHORED v0** — `40-p1-registry.yaml` |
| two-way trace lint (graph ↔ registry) | PLANNED — same `sfd graph lint` increment as G0's |
| scorer (`sfd score <pir>`) | PLANNED |
| catalog query for tech-exists/connectivity | PLANNED — needs the S2 subsystem map to bind functions → capabilities mechanically |
| recommendation + decision recording | PLANNED (Eden-side) |
