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
| F2 | **Scores are coarse on purpose** | Scale: `green · amber · red · unknown · absent`. The MEANING of each level is written per metric in the registry, never implied. Numbers wait until P1 has measured history. |
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
| absent | the metric's `absent_when` condition holds — its feeds are closed or unspawned; skipped by every verdict rule. A defined non-state, distinct from unknown. |

## Verdict rules v0 (recommendation only — F4)

The rules are a PRECEDENCE LIST: the first matching rule wins, evaluation
stops there. (Two rules could otherwise fire at once — a safety-serious
product is both "human gate open" and "core red"; precedence resolves it:
the gate wins.)

1. Any human gate open → verdict **blocked** (recorded as such, with the
   gate named in `blockers`) until a human clears it.
2. Any core metric `unknown` → verdict **blocked**; the blocking UNKNOWNs
   are listed in `blockers`, each with what answers it. This is a DESIGNED
   outcome, not a defect: a core metric may be fed by scoring-tier
   questions (economics, tech-exists), so an UNKNOWN can legitimately pass
   G0 and stop here. `reasons` is populated on a blocked verdict too —
   with everything rules 3–4 would have said.
3. Any **core** metric red → recommend **pivot**. Recommend **kill** only
   when the red metric IS the product's stated magic
   (`metric.tech.exists` red ∧ `pir.novelty.magic` IS the differentiation
   stated in `pir.novelty.different`).
4. Otherwise → recommend **go**; every amber AND every minor-metric
   `unknown` is named in the reasons. P2-class metrics never bear on the
   verdict; their ambers may be appended marked non-verdict-bearing.

`minor` metrics never change the verdict; they color the reasons. A metric
that is ABSENT (its `absent_when` holds) is skipped by every rule — a
defined non-state, the registry-side mirror of the graph's
`conditional_fields`.

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
  verdict: go | pivot | kill | blocked
  blockers: []                           # verdict-level: open human gates
  reasons: []                            # and/or core unknowns, each named
  # NOTE the distinct name: scores[].blocked_by lists the UNKNOWN PIR
  # fields behind ONE score; recommendation.blockers lists what blocks
  # the VERDICT. Different levels, different names, never conflated.
decision:                        # F4 — the human call, with provenance
  verdict: ...
  by: ...
  quote: "..."
  at: <iso8601>
  context: "..."                 # optional — what the decision was made against
```

Record-keeping (adopted from reproduction runs): `recommendation` carries
`rule_applied` (which precedence rule stopped evaluation); `scores[]`
entries mirror `scored_by`/`verdict_weight`/`consumer` from the registry
for auditability; `derived` flags carry a sibling `derived_evidence`
block (F3 applies to them too); `pir.hash` is `sha256:` of the PIR file
bytes; a PIR that failed G0 is still scoreable — its G0 state rides in
`reasons[0]`, never hidden.

## scored_by — the three scorer kinds

| Value | Meaning |
|---|---|
| `derived` | computed mechanically from PIR values; no judgment |
| `agent` | judged by the scoring agent from the PIR, with cited reasoning |
| `agent+catalog` | judged with the capability index as the evidence base (below) |

`human_gate_when` names the answer value that raises a structural human
gate (F5); it appears only on `metric.risk.safety` in v0. `derivation`
(optional, `scored_by: derived` metrics) writes the mechanical rule the
score follows — a derived metric WITHOUT one is only as mechanical as its
scale text, which run 3 showed is not always enough.

## The catalog seam (decided: locked)

`metric.tech.exists` and `metric.feasibility.connectivity` are scored
`agent+catalog`: the scorer maps the product's functions onto S1's
capability vocabulary, then queries the capability index — supported SoCs,
component records, per-record depth. A capability the catalog covers at
D2+ scores green on availability; D1 scores amber; no coverage and no
known example scores red, and the gap becomes a named research task.

The evidence bar for "known example" (decided after reproduction run 2 —
this line is verdict-capable): a known example is a shipped product class
or an upstream Zephyr-supported implementation the scorer can NAME in the
evidence. Named example + zero catalog coverage = amber with a research
task; red requires that the scorer searched and can name nothing. The
citation is mandatory either way.
P1 is thereby the catalog's second consumer, after P4.

## Enforcement status (stated exactly)

| Piece | Status |
|---|---|
| metric registry (16 metrics + 2 derived flags, typed) | **AUTHORED v0** — `40-p1-registry.yaml` |
| two-way trace lint (graph ↔ registry) | **TOOL v0** — `sfd graph lint`, wired into `gate.sh` |
| scorer (`sfd score <pir>`) | PLANNED |
| catalog query for tech-exists/connectivity | PLANNED — needs the S2 subsystem map to bind functions → capabilities mechanically |
| recommendation + decision recording | PLANNED (Eden-side) |
