# 12 — Presentation Layer

> Status: Draft · 2026-06-12 · Canonical home for: the presentation-layer thesis, the altitude
> model (A0–A4), the diagram-as-projection contract and its three lenses, the global navigation /
> command / breadcrumb inventory, document-consumption reading paths, the learnability surface, and
> the v0→v1 dogfood path. This is the information architecture (IA) of every Eden surface — the
> rendering side of doc 11's projection (11 §5, §9) and the design-brief's experience
> (documents/design-brief.md) made concrete. Decision basis: ADR-0004 (Svelte), ADR-0006 (Tauri
> shell). Research grounding: `docs/research/04-platform-ui-paradigms.md` (theses U1–U10), cited by
> claim with its ✅/🔶 status.
>
> Cohesion: this document owns _how the model is presented and navigated_. It never redefines the
> model (02), the documents (11), the connectors (05), or observability planes (03 §1 S6, P9) — it
> cites them and specifies their surface.

## 1. Thesis — the visual model is the primary surface

🔶 **Visual representation is Eden's primary surface (C10), and consumption is navigation, not
reading order.** A shallower tool treats its UI as a window onto a database; Eden treats _one typed
project model_ as the thing the user manipulates directly, projected into many task-postured views
(U1, ✅ in research-04 §1 across Ableton/Blender/Figma/Linear). The same model renders three ways —
its **design** (the intended architecture), its **build status** (what the pipeline has produced),
and its **runtime** (live telemetry) — and these are _lenses on one surface_, never three products
(C10; U3 🔶). The user does not read Eden top-to-bottom the way one reads this document; the user
_moves through it_ — descending altitudes, switching lenses, jumping by command — and the IA's whole
job is to make those moves legible and reversible.

This realizes the charter's product spine (00 §4: create → specify → build → operate → evolve) as a
_spatial_ experience rather than a sequence of screens, and it carries the design-brief's two
commitments without compromise: density is the default (the engineer's altitude, PER-0002), and the
non-technical signal is _lifted out of_ that density rather than forked into a separate "simple mode"
(the founder's altitude, PER-0001; U6 🔶). The depth is the point; the IA is what makes the depth
navigable (documents/design-brief.md §Intent).

## 2. The altitude model — A0–A4

✅ Research-04 §6 establishes that surviving a deep org→project→system→component→run ladder requires
a **typed entity that drives the surface rendered for it** (Backstage's `kind`/`type`), a relation
graph rather than a strict tree, and an unbroken breadcrumb showing **hierarchy not history**. Eden
adopts a C4-inspired altitude ladder (the C4 _levels are a property of the model_, derived not drawn
— research-04 §3, ✅ Structurizr) mapped onto Eden's own entities (02 §1–§2):

| Altitude | Name                            | Eden entity (02)                                  | What renders                                                                                   | Primary persona     |
| -------- | ------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ------------------- |
| **A0**   | Organization / portfolio        | Organization, Project\*                           | the project grid; fleet roll-up (C17/OD-13); org-wide gate & spend roll-ups                    | founder (PER-0001)  |
| **A1**   | Project context                 | Project, Monorepo, Environment × Platform         | the project home: maturity ladder (C2), document set, system diagram, dashboards, gate queue   | both                |
| **A2**   | System                          | system-design components (CMP-\*, 11 §6)          | the **photosphere diagram** at depth-1 — components and their connectors as a relation graph   | both                |
| **A3**   | Component internals / contracts | a CMP-\* and its CTR-\* (11 §3), depends_on edges | component responsibility, its contracts, its documents, its drift status                       | engineer (PER-0002) |
| **A4**   | Runs / transcripts / evidence   | Run, Transcript, Evidence, Observation (02 §2)    | the build/runtime detail: a transcript, an evidence envelope, an incident, a deployment record | engineer (PER-0002) |

These view altitudes (A0–A4, navigation depth) are distinct from the **engine** altitudes of 04 §3
(product/component recursion depth); one word, two registered homes — qualify on use.

**Navigation is altitude moves.** Descending = clicking a node to its detail (research-04 §6, ✅
"clicking a node navigates to that entity"; the photosphere node _is_ a navigation device, §3 below).
Ascending = the breadcrumb. Lateral = the contextual sibling panel (§4). 🔶 The ladder is a
**relation graph, not a tree** (U9-adjacent; research-04 §6 ✅): a CMP at A2 implements a CTR, depends
on sibling CMPs, and is realized by documents at A1 — these are typed edges (11 §3), navigable in any
direction, with reverse edges _derived_ (11 §3 direction rule), never authored.

**"Where am I" is permanent.** Two affordances, always present (research-04 §6, ✅ GitLab's
documented failure was users unable to tell global from contextual): (a) **one unbroken breadcrumb**
spanning A0→A4 (extending into file→symbol when a code editor is the active surface — research-04 §6
✅ VS Code, Q7 lean 🔶), auto-generated from the route tree (research-04 §6 ✅ Grafana Scenes — the
URL _is_ the hierarchy), truncating center segments at depth; (b) **color-coded global-vs-contextual
zones** so org-wide queues read differently from this-system context (research-04 §6 ✅ GitLab).
Geometric zoom is reserved for _within_ an altitude; _between_ altitudes is semantic descent, not
scale (research-04 §6 ✅, Q1 lean 🔶: New Relic/Datadog/Ilograph all chose grouping over zoom).

## 3. The diagram system — projections with three lenses

🔶 **Diagrams are projections of model data, never hand-drawn artifacts that can drift.** This is the
single most load-bearing rule of this document, and it is C13 (architecture always known and
maintainable) expressed as a rendering contract. A diagram is a deterministic function of: the doc 11
documents (the system-design `components[]` with their `depends_on` and `connectors`, 11 §6), the
typed link graph (11 §3), and — for the build and runtime lenses — DeploymentRecords and Observations
(04 records; 03 §1 S6 plane c). Because the projection is derived, it _cannot_ fall out of sync with
the model the way a hand-maintained drawing does (research-04 §3, ✅ Structurizr's "models as code,
not diagrams as code"; ✅ the field's measured pain: vFunction's 56% report production no longer
matches documentation — research-04 §3).

**One diagram, three lenses (C10).** The _same_ node-and-edge structure carries three overlays; the
user toggles the lens, the geometry never moves (research-04 §1 ✅ Session/Arrangement decoupling;
§3 ✅ Unreal Blueprint becomes its own debugger at play-time):

| Lens        | Source plane                                       | What it paints                                                                            | Research grounding                                                                                                 |
| ----------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **design**  | doc 11 documents + link graph                      | intended components, contracts, dependencies; status chips from document state            | ✅ research-04 §3 (model→view derivation)                                                                          |
| **build**   | pipeline records (Run, Evidence, DeploymentRecord) | which components are generated / gated / deployed; gate state on the node                 | 🔶 research-04 §3 (Blueprint debugger overlay)                                                                     |
| **runtime** | observability plane c (03 §1 S6)                   | latency/error onto edges and nodes; healthy nodes auto-cluster; click → A4 run/transcript | 🔶 U3; research-04 §3 ✅ New Relic edge vocabulary (latency/error/both), ✅ Datadog upstream-right/downstream-left |

🔶 **Drift is the seam Eden uniquely owns (U4).** Because Eden _generates_ both the model and the
code (T2/T4/C13), it can compute _semantic_ drift — does the code match the architecture — that
link-existence tools (IcePanel) and OTel-only tools (Multiplayer) cannot, and offer an AI remediation
PR (T7; research-04 §3 🔶). The ship order is the cheap thing first (research-04 §3 ✅ + Q3 lean 🔶):
an IcePanel-style link-existence accuracy score, then true generated-model↔live-topology
reconciliation behind a confidence gate. Drift surfacing on the diagram is the primary product
experience in byo-authority mode (ADR-0013).

🧩 **v0 bootstrap exception.** Until the projection renderer exists, canon documents may carry
**hand-authored mermaid blocks**, each explicitly marked `<!-- to-be-generated: projection of
system-design CMP-* -->`. These are the _only_ hand-drawn diagrams Eden tolerates, and they are
temporary by construction: **diagram-from-projection is a standing renderer obligation** (a build
target, not a backlog item), and each hand-authored block is a TODO against it. A diagram that is not
a projection of an owned artifact is, by this document's contract, a bug.

## 4. Navigation, menus, commands

**Global navigation inventory** (the always-reachable destinations, color-coded as global per §2):
**Projects** (A0 grid) · **Documents** (the doc 11 reading surface, §5) · **Diagrams** (the
photosphere canvas, §3) · **Gates queue** (the human's home screen, below) · **Runs** (A4
transcripts/evidence) · **Observability** (plane c dashboards + drift) · **Settings** (connectors,
credentials, integration mode/enforcement per ADR-0013). Each project re-scopes these to its context
(research-04 §6 ✅ Vercel scope switcher — "projects-as-filters"); past ~1000 entities (the C2
production target), saved/filtered views and the palette replace deep trees (research-04 §6 ✅).

🔶 **The command palette is the spine (U2).** One fuzzy palette over _every_ Eden verb — create
project, run a gate, open a transcript, jump to a component/run, regenerate a doc, redeploy (the
"~6 load-bearing verbs" of research-04 Q10 🔶) — is simultaneously the expert accelerator and the
always-on learnability layer (research-04 §1 ✅ highest-ROI single feature; it doubles as live
documentation). It **lists the keyboard shortcut beside each command** to migrate users from search
to muscle memory (research-04 §1 ✅), and it is the cross-altitude jump tool the breadcrumb cannot be.

🔶 **The gate queue is the human's home screen (P13).** Humans sit at gates, not in loops; the queue
of pending rulings is therefore the founder's and the engineer's actual landing surface, not a
buried tab. It renders each pending gate with its evidence summary (02 Evidence envelope) and the
policy action it awaits (`auto · approve · edit`, 04 §5). This is the _only_ blocking human
interaction the platform imposes (P13; open-decisions.md preamble), so it earns top-level placement.

**Posture workspaces (U1, 🔶).** Above the global nav sits a named-workspace switch — _Specify ·
Build/Watch · Operate · Review/Gates · Founder_ — that reconfigures _panels around the same project
model_, never swapping the project out from under the user (research-04 §1 ✅ Blender's hard-won
decoupling rule). The founder workspace is the density dial turned down (U6 🔶: one UI, two
densities — a label/detail toggle, not a forked product), honoring the design-brief's
no-simple-mode commitment (documents/design-brief.md §Audience).

## 5. Document consumption

Doc 11 owns the documents; this section owns _reading them_. A document is its projection (11 §5);
the surface renders `{meta, data, sections}` with live system context, not a static prose file
(research-04 §2 ✅ docs-as-data; U7 🔶 typed artifacts on review rails).

**Reading paths by persona** (PER-0001/0002/0003 of the product-charter; the brief names the first
two):

- **Founder (PER-0001)** lands at A1 on the **charter view, the maturity ladder, the gate queue, and
  the dashboard roll-up** (documents/design-brief.md §Audience) — calm, status-first, the
  release-engineering burden invisible (C9). Status chips state _deployed · healthy · gated_ without
  demanding the machinery be understood.
- **Engineer (PER-0002)** lands deeper — **drift detail across connector families, enforced-vs-
  advisory guarantee badges (ADR-0013, permanently visible), the full release machinery, contracts
  and conformance** — nothing rounded off (documents/design-brief.md §Audience; C8/C18).

**Surface affordances on every document:** status chips (`draft · review · approved · superseded`,
11 §4); **backlinks** rendered as _typed_ relations, not an undifferentiated hairball (research-04
§2 🔶 — "this doc realizes that requirement; this diagram observes that component" beats a backlink
graph view); supersession history (11 §4 append-only chain); download/export (per-page `.md` + an
`/llms.txt`-style index for agent-readable consumption — research-04 §2 ✅; C10 download requirement).
🔶 **Hover-sync (U8)** is the signature reading mechanic: hovering a component in a design doc
highlights it in the diagram, in the code, and in the runtime overlay (research-04 §2 ✅ Stripe
prose↔code, generalized across Eden's altitudes).

**The review/edit loop is the gate loop (11 §9).** `edit`-policy documents are amendable in place
before approval; everything after approval is supersession through a gate (11 §9; 04 §5). The visual
editor's contract holds (OD-10): edits re-enter as document versions through gates, never as canvas
mutations. Findability leans on _generated structure + faceted/scoped search_ over the fixed altitude
tree, never a bare search box (research-04 §2 ✅ — enterprise flat-search succeeds ~10% of the time).

## 6. Learnability

🔶 **Eden is a mega-tool; the way to do things is taught, not discovered (C11).** The design-brief
makes the tutorial layer carry the warmth so the working surfaces stay dense and quiet
(documents/design-brief.md §Audience). The presentation layer provides three learnability surfaces,
each lifted from research-04 §1/§4 with its status:

- **A persistent Learn/Info pane** (research-04 §4 ✅ Ableton's Learn View; §1 ✅ the Info pane) — a
  dockable pane that explains the currently-focused gate, doc 11 artifact, or diagram node in place,
  and hosts out-of-band lessons. This is how Eden earns its density _without a manual_ (C11).
- **Progressive density, user-commanded** (research-04 §1 🔶 — Figma rejected auto-hiding controls;
  power users scan what they can see). The U6 density dial is the mechanism: the founder sees guidance
  labels on; the engineer turns them off for icon-density. One surface, the user's choice — never a
  silent automatic hide.
- **The tutorial is the first real PoC, not a sim** (U5 🔶; research-04 §4 ✅ — VS Code Walkthroughs
  whose steps auto-tick on _real_ events; the IKEA effect requires successful completion). Completing
  onboarding = having a working cheap PoC (C2/C20), with the local-cluster tier as the safe sandbox
  (C19). Steps are altitude-aware — navigating an altitude, opening a diagram, ruling a gate, and
  regenerating a doc all tick their own step (research-04 §4 ✅; Q4 lean 🔶: one Walkthrough, tiered
  and skippable for experts).

## 7. Dogfood path — v0 static renders, v1 Svelte app

🔶 **v0 = the static renders implement _this spec's_ IA over Eden's own corpus.** Three artifacts,
each generated and never hand-edited (`docs/README.md` generated-artifact rule), are the conformance instances of this
document at bootstrap:

- `eden-architecture.html` (exists; `docs/tools/render-html.mjs`) — the canon doc set as a
  navigable reading surface (the A1 document altitude for Eden-the-project).
- `documents.html` (exists; `docs/tools/render-documents.mjs`) — a _project's_ document set rendered
  from the validator's projection (11 §5), demonstrating the §5 reading paths.
- **`eden-atlas.html`** (the new artifact this spec calls for) — the first surface that implements
  the **altitude model (§2) + the three-lens diagram (§3)** over Eden's own architecture corpus. The
  atlas is the first conformance instance of this document: it must render the A0–A4 ladder, the
  breadcrumb, and the design-lens photosphere diagram (build/runtime lenses are stubbed at v0, since
  Eden-the-project has no live telemetry plane yet).

✅ **v1 = the Svelte app (ADR-0004) renders the same projections via the gateway.** The platform UI
(`apps/frontend`, Svelte 5) and the Tauri shell (`apps/desktop`, the same bundle — ADR-0006) consume
the doc 11 projection and the observability planes through the Connect gateway (03 §1 S1), rendering
the identical IA this document specifies. The desktop shell earns _exactly_ presence — global
shortcut, native menubar/tray, OS notifications for gate-waiting/build-complete/incident, folder
export, offline _reading_ of downloaded doc sets, multi-window (diagram on one screen, transcript on
another) — and nothing else (U10 🔶; research-04 §5 ✅). The static renders and the Svelte app are
the _same IA at two fidelities_; the atlas is the bridge, and "the atlas conforms to doc 12" is a
gate the v1 app inherits.

## 8. Open questions

| #   | Question                                                                                      | Why it matters                                                                | Disposition / lean                                                                                       |
| --- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Q1  | Is design↔runtime a perspective-toggle on one canvas or a posture workspace switch?           | Determines whether C10 is a lens flip (§3) or a panel reconfiguration (§4).   | 🔶 Lens toggle on one canvas; workspace only if panels diverge hard (research-04 Q2).                    |
| Q2  | Does the breadcrumb extend into code/symbol (A4+) or stop at the component?                   | Decides whether code/run are true altitudes or leaf detail.                   | 🔶 Extend to file→symbol only when a browser/VS Code editor is the active surface (research-04 Q7).      |
| Q3  | How is semantic drift (U4) surfaced without false-positive fatigue on the runtime lens?       | Cheap link-existence is shallow; semantic is differentiated but noisier.      | 🔶 Ship accuracy-score first; gate semantic drift behind confidence + remediation-PR (research-04 Q3).   |
| Q4  | What renders the photosphere diagram at v0 — mermaid projection or a Svelte canvas component? | Bounds the atlas's effort and whether v0 and v1 share a renderer.             | 🧩 Open: hand-authored mermaid (§3 exception) at v0; the v1 canvas is an OD when the renderer is scoped. |
| Q5  | Is the gate queue one global surface or re-scoped per project at A1?                          | Affects whether the founder's home is org-wide or project-local.              | 🔶 Both, color-coded global vs contextual (§2); the global queue is the A0 landing.                      |
| Q6  | Pie/radial spatial accelerators (Blender `Q`) — worth the learning cost on an ops tool?       | Powerful but unproven outside creative tools.                                 | 🔶 Defer; ship palette + small canonical shortcut set first (research-04 Q8/Q10).                        |
| Q7  | How much doc-projection validation runs client-side vs in the cluster?                        | Personalization/validation needs ground-truth that lives on the cluster (C4). | 🔶 Validate in-cluster; client renders + hover-syncs (research-04 Q6; 11 §8 CI re-validation).           |
