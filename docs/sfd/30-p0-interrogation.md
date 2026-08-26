# P0 — the interrogation

Status: v0, depth D1 (designed with Mateo, 2026-08-26; every rule below was
decided in-session). The machine-readable graph lives in
[`30-p0-graph.yaml`](30-p0-graph.yaml) — that file is the artifact Eden
runs; this file is its contract.

P0's job: when a new Eden project declares (or hints at) a physical
product, extract the intent from the human's head into a typed **PIR** —
Product Intent Record — that P1 can score and S1 can consume. The
interrogation is extraction from a human the way the catalog is extraction
from Zephyr; the same laws apply, with the user's verbatim words playing
the role of the pinned SHA.

## The five rules

| # | Rule | Meaning |
|---|---|---|
| R1 | **Graph, not list** | Answers open and close branches. A battery answer opens battery-life asks; wall power closes them. |
| R2 | **Every question earns its place** | Each question `feeds` ≥ 1 PIR field or P1 metric. A question feeding nothing is dead; a metric no question feeds is unanswerable. Two-way trace — the same law as G3. |
| R3 | **The user states intent, never technology** | The user never picks "BLE"; they say "talks to a phone nearby". The system derives the radio, the certification, the storage part. That IS software-first. |
| R4 | **Quotes are provenance** | Every PIR field cites the question id + the user's verbatim words + a timestamp. Chat may DISCOVER; only the schema RECORDS. |
| R5 | **UNKNOWN is data** | An unanswered field is recorded UNKNOWN and listed with the P1 metrics it blocks. Never silently defaulted. |

## Register (decided: mixed, with a tech fast-path)

Questions assume a non-technical answerer — plain product language. A
technical answerer may volunteer specifics ("must be ESP32", "has to be
LoRa"). Volunteered technology NEVER becomes a derivation; it lands in the
**constraints channel**:

1. The system asks one follow-up: *"Is that a requirement, or a
   preference?"*
2. `hard` → filters the P4 fit matrix. `preference` → breaks ties only.
3. Both are recorded with the verbatim quote (R4).

## Tiers (decided: three)

Tier is per-question, declared in the graph. "Required" means required
**when reachable** — a question closed by branching is N/A, not UNKNOWN.

| Tier | At G0 | Count in v0 graph |
|---|---|---|
| required | UNKNOWN hard-blocks the gate | 11 |
| scoring | UNKNOWN passes, raised as risk in P1 | 18 |
| color | optional, context only | 1 |

Fixed questions total 30, across nine sections S1–S9. Two adaptive
mechanisms ride alongside: `q.fn.rate` (spawned per named sense/act) and
the constraint ask-back. Adaptive follow-ups obey R4: their findings land
in typed PIR fields with quotes, or they force a versioned schema change —
never a loose note.

## Gate G0 — pass condition

1. Every reachable **required** question is answered (not UNKNOWN).
2. Every UNKNOWN is listed with the metrics it blocks (R5).
3. The graph itself lints clean (below).
4. `q.comp.safety = serious` flags a **human gate** in P1 — the system
   never scores a safety-critical product alone.

## Graph lint — the G0 mechanical check

Declared here, enforced by `sfd graph lint` (**PLANNED**, next tool
increment; until it exists the check runs in review, named as such):

- every question `feeds` ≥ 1 existing PIR field or P1 metric id;
- every `opens` target id exists in the graph;
- every branch key in `opens` is a value of the question's own enum;
- every PIR field marked required is fed by ≥ 1 required-tier question;
- no two questions share an id.

## PIR v0 — the output record

```yaml
schema: sfd.pir/v0
summary: ...                     # q.intent.what
users: ...                       # q.intent.who
functions: []                    # S3 answers, in S1's closed capability
                                 # vocabulary (10-p3-pipeline.md)
environment: {where: ..., conditions: [], on_body: ...}
power_class: PC0 | PC1 | PC2     # derived from q.power.source
modes: []                        # from q.power.duty → P3 power budget
targets:
  battery_life: {delight: ..., floor: ...}
  unit_cost: {build: ..., sell: ...}
  volume: {y1: ..., y3: ...}
physical: {size_class: ..., carry: ..., controls: ...}
timeline: {proto: ..., production: ...}
assets: []                       # q.time.exists
novelty: {different: ..., hard: ..., magic: ..., moat: ...}
compliance: {regions: [], safety: ..., personal_data: []}
constraints: []                  # volunteered tech: {tech, strength, quote}
unknowns:                        # R5 — first-class
  - {field: ..., blocks: [metric ids]}
provenance:                      # R4 — per answered field
  <field>: {question: <id>, quote: "...", at: <iso8601>}
```

## Enforcement status (stated exactly)

| Piece | Status |
|---|---|
| the graph (30 questions, typed, branching) | **AUTHORED v0** — `30-p0-graph.yaml` |
| graph lint | PLANNED (`sfd graph lint`) |
| PIR record type + provenance verification | PLANNED (tool) |
| Eden runner (fixed set + adaptive chat) | PLANNED (Eden-side) |
