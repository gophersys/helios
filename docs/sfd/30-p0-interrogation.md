# P0 — the interrogation

Status: v0, depth D1 (designed with Mateo, 2026-08-26; every rule below was
decided in-session, revised after adversarial refutation the same day). The
machine-readable graph lives in [`30-p0-graph.yaml`](30-p0-graph.yaml) —
that file is the artifact Eden runs and the authority for ids, tiers,
branching, derivations and lint; this file is its contract. The metric ids
the graph feeds are defined in [`40-p1-registry.yaml`](40-p1-registry.yaml)
— the two files land together because the trace between them is one
contract.

P0's job: when a new Eden project declares (or hints at) a physical
product, extract the intent from the human's head into a typed **PIR** —
Product Intent Record — that P1 can score and S1 can consume. The
interrogation is extraction from a human the way the catalog is extraction
from Zephyr; the same laws apply, with the user's verbatim words playing
the role of the pinned SHA.

## The five rules

| # | Rule | Meaning |
|---|---|---|
| R1 | **Graph, not list** | A question that appears as an `opens` target is CONDITIONAL — asked only when opened; closed means N/A, never UNKNOWN. Every other question is unconditional. The conditional set is declared machine-readably (`conditional_questions` in the graph) and lint checks SET EQUALITY against the computed opens targets — so silently making a question conditional goes red. v0: `q.power.life` (opened by battery-class power sources) and `q.fn.offline` (opened by any connectivity; a product that talks to nothing gets no internet question). |
| R2 | **Every question earns its place** | Each `feeds` ENTRY (per-feed, not per-question) names an existing PIR field (`pir_fields` in the graph) or a registry metric. Both directions lint: no dead feeds, no unfed metrics. |
| R3 | **The user states intent, never technology** | The user never picks "BLE"; they say "talks to a phone nearby". The system derives the radio, the certification (from region), the power class (from source), security and timekeeping (from answers) — see the graph's `derivations:` block. |
| R4 | **Quotes are provenance** | Every PIR value cites the question id + the user's verbatim words + a timestamp. Multi-fed fields (like `functions`) carry provenance PER ITEM, inline. Chat may DISCOVER; only the schema RECORDS. |
| R5 | **UNKNOWN is data** | An unanswered field is recorded UNKNOWN and listed with the P1 metrics it blocks. Never silently defaulted. UNKNOWN is a sentinel of the record, never an enum value — an enum member named "unknown" would collide with it and pass the gate empty (refuted 2026-08-26; `q.power.source` lost its `unknown` value for exactly this). |

## Register (decided: mixed, with a tech fast-path)

Questions assume a non-technical answerer — plain product language. A
technical answerer may volunteer specifics ("must be ESP32", "has to be
LoRa"). Volunteered technology NEVER becomes a derivation; it lands in the
**constraints channel**:

1. The system asks one follow-up (`q.constraint.strength`): *"Is that a
   requirement, or a preference?"* — tier `required`: an unclassified
   volunteered technology blocks G0.
2. `hard` → filters the P4 fit matrix. `preference` → breaks ties only.
3. Both are recorded with the verbatim quote (R4).

## Tiers (decided: three; safety and personal data promoted to required)

Tier is per-question, declared in the graph. "Required" binds **when the
question is reachable** (R1 defines reachability); adaptive questions bind
when spawned.

| Tier | At G0 | Count in v0 graph |
|---|---|---|
| required | UNKNOWN hard-blocks the gate | 13 fixed (2 conditional) + 1 adaptive |
| scoring | UNKNOWN passes, raised as risk in P1 | 16 fixed + 2 adaptive |
| color | optional, context only | 1 fixed |

Fixed questions total 30 across nine sections S1–S9. Three adaptive
mechanisms ride alongside: `q.fn.rate` (per named sense/act),
`q.followup.range` (per extreme condition or tight size), and
`q.constraint.strength` (per volunteered technology). Adaptive findings
land in typed PIR fields with quotes (R4) — an answer that fits no field
forces a versioned schema change, never a loose note.

## Capability coverage — S1's nine words, honestly

S1's vocabulary (10-p3-pipeline.md) is CLOSED: `connectivity · sensing ·
actuation · storage · compute · hmi · power · security · time`. P0 covers
it three ways, stated exactly:

| Word | How it is fed |
|---|---|
| sensing | `q.fn.senses` |
| actuation | `q.fn.acts` |
| connectivity | `q.fn.talks` |
| storage | `q.fn.stores` |
| hmi | `q.fn.shows` + `q.phys.controls` |
| compute | adaptive `q.fn.rate` (rates/reactions → demand) |
| power | DERIVED from S4 (`pir.power_class` + `pir.modes`) — always present |
| security | DERIVED: baseline whenever the product talks to anything or collects personal data (`derivations.capability.security`) |
| time | DERIVED: whenever duty is wakes-on-schedule (`derivations.capability.time`) |

No word is silently unfed; the derivations are in the graph, versioned
with it.

## Question record vocabulary

`mode`: `fixed` (always in the graph) — adaptive mechanisms live in the
`adaptive:` block instead and carry `spawned_by`. `type`: `text` · `enum`
· `multi` (multi-select enum) · `bool` (unused in v0; `q.env.body` is an
enum to keep opens keys string-typed) · `date` · `number-unit` ·
`pair-number` · `pair-number-unit`. Optional keys: `values` (enum/multi),
`opens`, `adaptive` (spawn ref), `glosses` (per-value plain-language
gloss, keys ⊆ values), `routing` (adaptive only: spawn source → target
field). All keys are linted; an unknown key is an error.

## Gate G0 — pass condition

1. Every reachable **required** question is answered; every spawned
   required adaptive is answered.
2. Every UNKNOWN is listed with the metrics it blocks (R5).
3. No consistency rule is red (the graph's `consistency:` block — e.g. a
   product controlled only by an app cannot talk to nothing). A rule fires
   only when every answer it references is present; UNKNOWN or closed
   answers cannot make a rule red — R5 already surfaces them.
4. The graph itself lints clean (the `lint:` contract in the graph;
   enforcement by `sfd graph lint` is PLANNED — until it exists the check
   runs in review, named as such).
5. `q.comp.safety = serious` flags a **human gate** in P1 — and because
   `q.comp.safety` is tier `required`, the answer cannot be skipped; the
   guarantee holds as authored.

## Derivations (R3 made concrete)

The graph's `derivations:` block is the authority. Highlights:

| Derived | From | Rule |
|---|---|---|
| `pir.power_class` | `q.power.source` | wall-power→PC2 · dock/cable→PC1 · replaceable batteries→PC0 · powers-itself→PC0. **PC0 = cannot recharge** — the budget binds hardest (decided 2026-08-26; `00-process.md` axis updated to match). |
| `pir.compliance.certifications` | `q.comp.region` | us→FCC · eu→CE-RED · uk→UKCA · ca→ISED · other→named research task |
| capability `security` / `time` / `power` | answers | see coverage table above |

`pir.targets.battery_life` is **conditional**: present iff power_class ∈
[PC0, PC1]. A mains product's battery life is ABSENT — a defined state,
distinct from UNKNOWN (the graph's `conditional_fields` block).

## PIR v0 — the output record

```yaml
schema: sfd.pir/v0
summary: ...                     # q.intent.what          [required]
users: ...                       # q.intent.who           [required]
functions:                       # [required] — LIST of typed items, each
  - capability: connectivity     # in S1's closed vocabulary
    detail: "phone-nearby"
    question: q.fn.talks         # R4: provenance PER ITEM, inline
    quote: "it syncs to your phone when you walk in"
    at: 2026-08-26T17:40:00Z
environment: {where: ..., conditions: [], limits: {}, on_body: ...}
power_class: PC0 | PC1 | PC2     # [required] derived (see table)
modes: []                        # [required] from q.power.duty
targets:
  success: ...                   # q.intent.win
  battery_life: {delight: ..., floor: ...}   # CONDITIONAL (PC0/PC1 only)
  unit_cost: {build: ..., sell: ...}
  volume: {y1: ..., y3: ...}
physical: {size_class: ..., dims: {}, carry: ..., controls: ...}
timeline: {proto: ..., production: ...}
assets: []                       # q.time.exists
novelty: {different: ..., hard: ..., magic: ..., moat: ...}
compliance:
  regions: []
  safety: ...                    # [required]
  personal_data: []              # [required]
  certifications: []             # derived from regions
constraints: []                  # volunteered tech: {tech, strength, quote, at}
unknowns:                        # R5 — first-class
  - {field: ..., blocks: [metric ids]}
provenance:                      # R4 — per field; a LIST when multi-fed
  pir.power_class:
    - {question: q.power.source, quote: "it charges on a dock at night", at: "2026-08-26T17:40:00Z"}
```

The flat field list, the required subset, and the conditional fields are
declared machine-readably in the graph (`pir_fields`, `pir_required`,
`conditional_fields`) — lint reads those, not this prose.

## Enforcement status (stated exactly)

| Piece | Status |
|---|---|
| the graph (30 questions, 3 adaptive, derivations, consistency, PIR field authority) | **AUTHORED v0** — `30-p0-graph.yaml` |
| the metric registry (far side of R2) | **AUTHORED v0** — `40-p1-registry.yaml` |
| graph lint (the `lint:` contract, both directions) | PLANNED (`sfd graph lint`) |
| PIR record type + provenance verification | PLANNED (tool) |
| Eden runner (fixed set + adaptive chat) | PLANNED (Eden-side) |
