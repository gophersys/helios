# Platform UI Paradigms — how deep professional tools stay learnable, and which patterns Eden adopts

> Research date: June 12, 2026 · Lens: the Ableton-like "mega-tool" (C11) — tool depth & learnability,
> document UX, diagrams-as-runtime (C10), onboarding, desktop/web parity, multi-altitude navigation.
> Point-in-time; never canonical (docs/README.md §1). Promote findings into specs with a citation.
>
> **Epistemic legend:** ✅ verified across ≥2 independent sources · 🔶 hypothesis / single-source / inferred.
> Tags are claim-local: a paragraph may carry both.

## Thesis

> **Density is earned, not imposed.** A mega-tool reads as professional rather than punishing when one
> typed model is projected into many task-postured views, every verb is reachable two ways
> (discoverable click *and* keyboard/palette), the structure is legible (breadcrumb + color-coded
> types + bounded depth), and learning *is* the work (the tutorial builds your first real artifact
> and ticks itself off when you actually do the thing). Eden's hardest, most-defensible bet —
> the **design-time diagram that doubles as the runtime observability surface (C10)** — is the one
> place where no shipped product fully closes the loop; existing tools implement one side of it.

The deep-tool field has converged on a small set of load-bearing primitives. ✅ Across Ableton,
Blender, Figma, DaVinci Resolve, Unreal, TouchDesigner, Linear, VS Code, Backstage, Datadog,
GitLab, GitHub, and Vercel, the *same* patterns recur (verified by independent appearance in each):
**(1)** one model, multiple lenses — change the *posture*, not the *data*; **(2)** named, ordered,
single-click task stops that teach the workflow by their order; **(3)** dual-path actions (click +
key); **(4)** a command palette as the scale-proof escape hatch *and* live documentation;
**(5)** context-sensitive panels/help that mutate to the selection; **(6)** hierarchy-as-navigation
with a breadcrumb; **(7)** persisted, task-scoped layouts; **(8)** spatial muscle-memory
accelerators; **(9)** type-as-color with enforced legal connections; **(10)** the design diagram
as the runtime observability surface. Eden should treat (1)–(9) as solved patterns to copy and (10)
as the unclaimed capability Eden is positioned to own — because Eden *generates* both code and model, it alone holds
ground truth on both sides of the drift comparison (T2/T4/C13).

---

## 1. Tool depth & learnability — the Ableton/Blender/Figma/Linear playbook (C11)

✅ **One model, multiple task-postured views** is the single most-cited pattern. Ableton projects
the *same* tracks/clips into **Session View** (grid, divergent/exploratory) and **Arrangement
View** (timeline, convergent/committing); `Tab` toggles. DaVinci Resolve has *both* a Cut page and
an Edit page over the identical timeline (fast rough-cut vs. precise edit). Blender workspaces
reconfigure the *entire* screen per task (Modeling/Sculpting/Shading) but — a hard-won 2.8 decision —
**switching a workspace never switches the underlying scene**: UI and data are decoupled so you are
never disoriented. The lesson is exact: a view change must alter the *toolset and posture*, never
the *content you are looking at*.

✅ **Dual-path actions — neither path second-class.** Blender's 2.8 active-tool system added a
clickable left toolbar with on-canvas gizmos *without removing a single shortcut* — the explicit
rationale: "the keyboard-oriented workflow will still be a first-class citizen; a tool system will
be added without disturbing the workflow of users who prefer key shortcuts." Figma's UI3 pairs a
toolbar with a command palette. This is the textbook resolution of "deep but learnable": discoverable
tools for learners layered over the same operations experts hit by key.

✅ **The command palette is the highest-ROI single feature.** `Cmd/Ctrl+K` (Linear, Vercel),
`Cmd/Ctrl+/` (Figma), `Ctrl+P` (VS Code), `Tab` (TouchDesigner OP-create) — fuzzy-find and run any
verb. It is beginner-friendly (you don't need to know where a command lives) *and* expert-fast (no
clicks), and it **doubles as live documentation** of what's possible. Two teaching sub-mechanics
recur ✅: the palette *lists the keyboard shortcut next to each command*, migrating users from
search → muscle memory; and Raycast *prompts you to set a hotkey* on a command's first use.

✅ **Context-sensitive help and density dials.** Ableton's **Info View** (toggle `?`) explains
whatever the cursor hovers in a fixed pane — every cryptic knob self-documents without a tooltip
cloud. Figma UI3 ships **toggleable text labels** on controls (on = guidance for novices; off =
icon-density for experts) — *one surface, two densities, the user's choice* — the cleanest single
mechanism for serving a split persona without forking the UI.

🔶 **Progressive disclosure must be user-commanded, never silently automatic, for power tools.**
Figma *tried* a super-minimal UI that revealed controls only on hover and **rejected it** —
experts scan controls they can see; auto-hiding destabilizes them (first-party blog; treat as
Figma's self-narrative). They settled on resizable + fully-hideable panels. NN/g concurs: progressive
disclosure improves learnability but "power users rely on scanning controls quickly… allow
personalization or persistent expansion for expert roles." 🔶 **Spatial stability of controls
outranks aesthetic improvement** — Figma reverted an Auto-Layout grid restyle because it "disrupted
muscle memory too much" (single-source, first-party, but a clear warning for Eden's redesign cycles).

🔶 **Ship ~6 load-bearing verbs, not 200 shortcuts.** Ableton's community canon converges on a small
spine (`Cmd+D` duplicate, `Cmd+J` consolidate, `Tab` switch view, `B` draw, `Q` hot-swap) — the
"way to do things" is partly *a deliberately small canonical vocabulary repeated until automatic*
(community consensus, not an Ableton claim). 🔶 **Spatial muscle-memory accelerators**: Blender pie
menus put options at compass points (humans recall *directions* better than *list positions* — Blender
blogs + CMU pie-menu lineage; effect direction well-established, exact size unverified this round),
and **Quick Favorites (`Q`)** is a *user-built* radial of one's own most-used operators.

**Implications for Eden:**
- Ship named **workspaces as the top-level posture switch** (*Specify · Build/Watch · Operate ·
  Review/Gates · Founder*) that reconfigure panels around the **same project model** — never swap
  the project out from under the user (Blender's decoupling rule).
- Make the **design-view and the observability-view two views on one system model**, not two
  products — this is the Session/Arrangement duality applied to C10.
- One **command palette over every Eden verb** (create project, run gate, open transcript, jump to
  component/run) is the depth-unlock *and* the always-on learnability layer; show shortcuts inline.
- Give **photosphere a density dial** (Figma-style label toggle) so the **founder persona (C1)** and
  the technical operator share one UI at two densities — do not fork.
- A persistent **Info pane** explaining the currently-focused **gate, doc 11 artifact, or diagram
  node** is how Eden earns its density without a manual (C11 "the tool tells you the way").

---

## 2. Document UX — docs-as-data, typed pages, review rails (C8, C9, C10)

✅ **Docs-as-data is the through-line of every serious player.** Stripe's **Markdoc** parses
Markdown + declarative tags to an **AST**, validates content like code in CI, and *personalizes*
(injects the reader's API keys, renders conditionally on account state) — "docs behave like an app
over a single source of truth." GitBook syncs two-way with git and runs **change requests = PRs for
docs**. Notion's wikis are **databases in disguise** — every page carries typed properties
(owner/status/tags/verification). ReadMe drives reference from OpenAPI. ✅ The convergent principle:
**documents are structured, validated, versioned data rendered with context — not prose files.**
This is the foundational architecture decision for Eden's doc 11 system.

✅ **The prose↔code highlight (Stripe) is the most-praised single reading mechanic** — hovering an
element in the description highlights the corresponding lines in the live code panel, removing the
cognitive mapping cost between explanation and implementation. It generalizes directly to Eden's
differentiating capability: **document ↔ diagram ↔ code ↔ runtime sync** (hover a component in a design doc →
highlight it in the diagram → in the code → in the live observability overlay).

✅ **Review/merge rails generalize from code to docs.** GitBook ships branch → request review →
**merge rules that block merge until approvals are met** → **outdated-review marking** (prior
approvals auto-stale when new changes land) → an **AI agent selectable as a reviewer**. Notion's
2025 **page verification** marks pages verified (until a date), ranks verified pages higher in
search/@-mention, and sends **re-verification reminders on expiry** so content can't silently go
stale. These are documentation-flavored copies of the exact gates-and-review-queue surface Eden
needs — proof the pattern carries.

✅ **Findability collapses with depth; structure beats search at scale.** Enterprise search shows
~10% first-attempt success vs Google's ~95% (~9.5× gap); failures trace to flat structure, no
faceting, tool sprawl. Notion/Confluence both rot into "a labyrinth" under unbounded nesting. ✅ The
fix is *generated structure + faceted/scoped search* (Confluence's "Pages under", Notion property
filters), not a search box. 🔶 **Prefer typed relations over undifferentiated backlinks** — Roam's
graph view is "not always useful at scale" and link-hairballs degrade in signal (the precise
"too noisy → useless" framing is soft/single-source); semantically labeled edges (*this doc
implements that system; this diagram observes that component*) beat a backlink hairball.

✅ **Professional-tool feel = opinionation + speed + keyboard grammar (the Linear lesson, C11).**
Density is earned by being *fast* (optimistic UI, skeleton states, ~47ms responses) and *consistent*
(one blessed workflow reduces decision fatigue), with a command palette + memorable keyboard grammar
(`C` create, `G`-then-letter go-to) as the depth-unlock. This is the Ableton analogy made concrete
for a software tool.

**Implications for Eden:**
- Build **doc 11 documents as validated, typed, AST-backed artifacts** (Markdoc-class), each a
  reading surface *and* a typed object with owner/status/version/**gate-state** — render with live
  system context, not as static prose.
- Lift GitBook's **branch/review/merge-rule/outdated-review** semantics and Notion's
  **verification-with-expiry** wholesale onto doc 11 + **gates** — Eden already has git as authority
  (C8); docs ride the same review rails, and an **AI reviewer is a gate** (T3).
- Make **document↔diagram↔code↔runtime hover-sync** the signature reading mechanic — the Stripe
  prose↔code pattern extended across Eden's altitudes.
- Free **agent-readable export** via per-page `.md` + an `/llms.txt`-style index (C8 git-integrated,
  machine-consumable doc sets).
- Reject Notion's failure mode: Eden's altitudes (org→project→system→component) are a **fixed,
  opinionated, *generated* tree** (T4), not freeform nesting; lean on faceted/scoped search +
  verified-content ranking, never a bare search box.

---

## 3. Diagrams as runtime observability surfaces — the C10 keystone (greenfield)

🔶 **The headline finding: no shipped product fully delivers "the same diagram for design AND
production observation."** The field splits cleanly and has *not* merged: **design-first** tools
(Structurizr, IcePanel, Ilograph, AWS Composer) author a model where reality-linkage is a *drift
alarm*, not a live overlay; **runtime-first** tools (Datadog, New Relic, Grafana, Multiplayer)
auto-build topology from telemetry but have weak/no notion of *intended* design. The only vendors at
the seam are **vFunction** (reconciles live flows against a C4 reference) and **Multiplayer**
(auto-doc from OTel + drift alerts). ✅ This gap is corroborated across both the document-UX and
diagrams streams independently. **Treat C10 as greenfield, not a solved pattern to copy** — and as
defensible *because* Eden generates the system and owns both sides of the comparison.

✅ **Model→view derivation (Structurizr / the C4 author's reference impl).** The DSL enforces
**"models as code," not "diagrams as code"** — define elements/relationships *once*, and the tool
*generates* Context/Container/Component/Code/Deployment/Dynamic views. The C4 levels are a *property
of the model*, not hand-maintained parallel drawings. **Deployment views** map the same containers
onto where they run — the bridge concept. This *is* Eden's "architecture is always known and
maintainable" (C13): author/generate the model, derive every altitude.

✅ **Health painted onto structure + anomaly-driven altitude (the live-overlay template).** Unreal's
Blueprint is the proof in a shipping pro tool: at Play-in-Editor the *same graph* you authored
becomes the debugger — **exec wires highlight as execution flows**, breakpoints sit *on nodes*, a
watch tab shows live values. New Relic's **Dynamic Flow Map** is the richest overlay vocabulary
found: edges **blue = latency anomaly, pink = error anomaly, striped = both**; nodes get latency/error
dots; **low-anomaly nodes auto-cluster** so the map *itself decides what to show by health*. Datadog's
Service Map does the same in production (click to isolate; **upstream renders right, downstream left**;
filter by incident status). ✅ Across New Relic + Datadog + Grafana, **altitude is done by semantic
grouping/anomaly state, not geometric zoom** — strong convergent signal.

✅ **Bidirectional projection works when the diagram is a deterministic projection of an owned
artifact.** AWS Infrastructure Composer keeps canvas ↔ CloudFormation template in sync both
directions. ✅ **Drift is real and measured**: vFunction's 2025 study (600+ IT pros) — **56% say
production no longer matches documentation** — validating T7 as solving a quantified pain. IcePanel
ships a **quantified "Accuracy Score"** that decays as link-existence drift accumulates (re-checks
linked repo/branch/file every 30–60 min) — a cheap, shippable approximation that does *not* verify
the architecture is semantically real.

🔶 **The AI-closes-the-loop pattern (2025-26, vendor blogs, not benchmarked):** AI discovers
architecture from code, detects drift, generates the corrected model, **opens a PR, requests human
approval** — mapping exactly onto Eden's evidence-gated autonomy (T3) + remediation-offered (T7).
🔶 **Perspectives as the design/observe split (Ilograph):** the design-view and production-view could
literally be *two perspectives on one model* — the cleanest conceptual fit found anywhere, but
unproven as a shipped fusion.

**Implications for Eden:**
- **Generate every altitude from one owned model** (Structurizr's model→view derivation): Context/
  Container/Component/Code/Deployment/Dynamic are *projections*, never hand-drawn — this is C13.
- The **photosphere diagram is the observability canvas**: paint latency/error onto edges and nodes
  (New Relic vocabulary), **auto-cluster healthy nodes**, click a node to descend to its run/transcript
  (altitude descent), set "alerts" on the same nodes you designed with (the Unreal-Blueprint move).
- **Ship the cheap drift first, then the differentiated version:** start with IcePanel-style
  quantified Accuracy Score / link-existence drift; upgrade to **true semantic drift** by reconciling
  Eden's *generated model* against *live OTel topology* — which IcePanel/Multiplayer can't, because
  Eden owns both sides (T2/T4/C13) — plus **AI-generated remediation PRs** (T3/T7).
- **Default diagrams to depth-1 + explicit expansion** (Backstage's graph scale lesson, §6) — never
  render 1000 nodes; the observability canvas must survive scale by clustering and filtering.

---

## 4. Onboarding a mega-tool — making "you must learn it" feel premium (C1, C11)

✅ **The keystone mechanic: the tutorial checks itself off when you actually do the thing.** VS Code
**Walkthroughs** are a multi-step checklist where each step carries `completionEvents`
(`onCommand:`, `onSettingChanged:`, `onView:`, `onLink:`, `extensionInstalled:`) that auto-tick the
step **when the user genuinely performs the action in the real UI**, not when they read about it
(verified, primary source). This is the difference between a passive checklist and a *progress
mirror*: the tutorial *is* the work. It is the single most transferable onboarding mechanic for Eden.

✅ **The tutorial should be the first *real* project, not a sim.** Game design, Notion, and VS Code
all collapse tutorial and first artifact: the best game tutorial *is* level 1; Notion lands you in a
**functional Getting-Started doc** that teaches by doing (`Type "/" for slash commands` — performed
live). ✅ **Active beats passive** (load-bearing, two sources agree directionally; exact figures soft
🔶): practice-by-doing far outretains passive video; the **IKEA effect** (Norton/Mochon/Ariely 2012,
HBS) — people value self-assembled things ~63% more, *but the effect requires successful completion*.
Completion that auto-ticks on real actions delivers that payoff.

✅ **Opinionated + interruptive + interactive + sandboxed is fine even when *mandatory* — for the
right quadrant.** Superhuman's productized principles: **interruptive full-screen setup hit 98%
completion vs 30% for passive checklists** and lifted feature opt-in 45%→~80%; their 2×2 says
**high-price + high-complexity → human-led onboarding potentially forever**. Eden sits squarely in
that quadrant. The mandatory tutorial is a *completion mechanism*, not a friction tax — *if* it is
interactive and produces value, with a **safe sandbox** (Eden's cheap PoC tier, C2) to practice
without consequence and a skip/accelerate path for experts.

✅ **A persistent in-app Learn/Info pane beats a one-shot tour** (Ableton's Learn View opens by
default, is dockable, marks lessons complete, restores last page, and ships new lessons *out of
band* — learning is a living channel, not a frozen manual). 🔶 **Avoid generic overlay tooltip tours**
("guide fatigue") and video-only learning — native, action-completing, artifact-producing onboarding
reads as premium; overlay click-through reads as burdensome (Chameleon/Pendo market framing).

✅ **Templates/archetypes cure the cold start.** Blender's splash launches into named templates
("what kind of file?") and **Application Templates** ship an opinionated config as a first-class
object — directly analogous to Eden's archetype picker ("what kind of system?", charter §5). Notion
surfaces ~5 *personalized* templates from signup answers (progressive disclosure against an
overwhelming library).

**Implications for Eden:**
- Onboarding **drives the user's first cheap PoC (C2)**: completing the tutorial = having a working
  system, not a throwaway sim — the IKEA-effect payoff lands on a real artifact.
- Build the tutorial as a **Walkthrough whose steps auto-tick on real Eden events** — navigating an
  altitude, opening a diagram, ruling on a **gate**, regenerating a doc 11. `when`-conditions surface
  the right step for the surface the user is on (altitude-aware onboarding).
- **Full-screen, opinionated, interactive, and even mandatory is acceptable for Eden's quadrant**
  (C1 founder, high price/complexity) — provided the **PoC tier is the safe sandbox** and experts can
  skip.
- Ship a **persistent Learn/Info pane** (Ableton model) with **out-of-band lessons**; make the
  **archetype picker** the cold-start cure and surface release-notes-in-splash for **C9** version-awareness.

---

## 5. Desktop / web parity — what a Tauri shell earns (ADR-0006, C4, C11)

✅ **Tauri v2 makes "same Svelte bundle, two delivery wrappers" structurally native** — the frontend
is bundled as static assets (the exact HTML/JS/CSS the web app serves), with a Rust core + OS-native
WebView over an IPC bridge. Eden's ADR-0006 claim ("delivery wrapper, not a cell") is built-in, not
aspirational. ✅ **The defining tradeoff is the native per-OS WebView** (WebView2/Chromium on Windows,
WKWebView on macOS, **WebKitGTK on Linux** — the weakest/most divergent): tiny bundles (~8 MB vs
Electron 80–244 MB) and low RAM, but **CSS/font/rendering divergence** that bites *exactly* a dense
custom canvas UI. Budget a per-engine visual-regression pass; treat **Linux/WebKitGTK as a
first-class test target** — this is the one place "same bundle" leaks.

✅ **The VS Code Remote split is Eden's architecture already.** VS Code "splits itself in half": a
local **client** (UI, themes, keybindings) and a **Server** running anywhere (SSH/container/WSL/Tunnel)
that hosts the workspace, terminal, language servers, extensions, runtime; extensions are explicitly
classified UI/client-side vs workspace/remote-side. This is *exactly* C4/C5: client = control surface,
compute = the cluster the user points at. The lesson: formalize a **client-capability vs
server-capability split** and a **Tunnel-style secure connect** so one shell drives hosted-EKS (C6)
and self-hosted (C7) without per-deployment shell variants.

✅ **What desktop concretely earns** (verified capability deltas): **global shortcuts that fire when
unfocused** (command-palette-from-anywhere; Tauri `global-shortcut` plugin — use it *only* for
system-wide keys, JS listeners for in-window); **real filesystem access** for true folder export of
doc 11 sets (C10) vs the browser's per-file/IndexedDB confinement; **local system fonts** (Figma
desktop's cited advantage); **native menubar + tray + multi-window + custom title bars**; and
**OS notifications / dock badges / always-on presence** — precisely and *only* what Linear's
co-founder says their desktop adds ("nicer notifications, dock badge, and most importantly: it's
always on"). For Eden this is the seam for **build-complete / gate-waiting / incident alerts** to
reach an away-from-keyboard operator. 🔶 A macOS **NSPanel** (`tauri-nspanel`) is needed to float a
command palette over fullscreen apps (single canonical library; not independently benchmarked).

🔶 **Avoid the Figma failure mode.** Figma desktop is "a specialized browser window" with no functional
delta — and users revolt ("not an app but a crap website"). If Eden ships desktop it must *feel*
native (real menubar, OS notifications, global shortcut, multi-window) or it damages the mega-tool
positioning (C11). 🔶 **Offline is the expensive feature** (Notion's local-first took years: SQLite +
push-sync + CRDT). For a control-surface app where compute is always remote (C4), full offline editing
is out of scope, but **offline *reading* of downloaded doc 11 sets** (C10) is a realistic bounded
target — mirror Notion's "download + sync deltas," not full CRDT.

🔶 **Two standing risks.** (a) WebKitGTK/WKWebView divergence on a dense UI (mitigate: per-engine
visual regression). (b) **No marquee Svelte-5-in-Tauri app at Eden's density** — the big Svelte
proofs (Apple Music, Yelp) are *web*; Tauri+Svelte5 evidence is boilerplate, not a flagship —
mitigated by Tauri's strong dev-tool track record (GitButler, Hoppscotch, k8s GUIs) but not eliminated.

**Implications for Eden:**
- **Parity contract, not parity promise:** web = the **zero-friction default for the founder (C1)**;
  desktop = the power-user shell earning *exactly* global shortcut, native menubar/tray, OS
  notifications/always-on (gate/build/incident alerts), folder export of doc 11, offline *reading*,
  multi-window (diagram on one screen, transcript on another — serves C10/C11 full-screen focus).
- **Adopt the VS Code Remote client/server split explicitly** (it *is* C4/C5); one Tunnel-style
  connect drives hosted-EKS (C6) and self-hosted (C7).
- The desktop **signing/notarization/updater pipeline is itself a C9/T5 dogfood target** — Eden's
  release-engineering story, applied to its own shell.
- Keep one **narrow, audited Tauri bridge** (`invoke` + typed events) — never expose raw OS/Rust to
  the WebView (Slack's preload discipline); the natural use is a thin local agent for cluster
  auth/tunnel/git-drift (C8) and provider keys in the OS keychain (C15), not heavy compute.

---

## 6. Multi-altitude navigation — surviving org→project→system→component→code→run (C10)

✅ **A typed entity kind controls the surface that renders for it.** Backstage formalizes Eden's exact
ladder — **Domain → System → {Component, Resource, API}** plus an org axis (Group/User) — where a
Component's `type` "may affect what features are exposed in the interface." This is T4/C13 expressed
as information architecture: opinionation means the entity type drives the panels. ✅ Crucially the
model is a **relation graph, not a strict tree** (components implement/consume APIs; systems own
components) — navigated via a catalog graph where **clicking a node navigates to that entity**.

✅ **At scale you must default to local views.** Backstage's dependency graph had a CPU-spiking
infinite-rerender bug; the documented mitigations are **depth-limiting (default depth-1), relation/kind
filtering, and zoom/step-through** — *never render the whole graph*. ✅ Corroborated by the canvas
research: infinite canvases win for *relationship comprehension* but "you can get so lost" — they need
**structured anchor points** (breadcrumb + bounded depth + filtering); they *lose* for getting back to
a known place, which is why every production system pairs the map with a breadcrumb + palette + saved
views (verified across 3 independent 2025-26 sources).

✅ **Global vs contextual must be visually coded, and depth capped.** GitLab's redesign is the best
documented failure: "users could finish a usability test without understanding global vs. contextual
content." The fixes: a **super-sidebar** (constant header, body that swaps with context), **two levels
only — a hard depth cap**, **color as the global/contextual differentiator**, and **breadcrumbs for
the vertical "where am I + go up" path**. ✅ NN/g concurs: breadcrumbs are for wayfinding in deep
hierarchies, must **supplement not replace** global/local nav, and must show **hierarchy, not history**
(the entity's place in the model, not the user's click path). Eden's ~6-level ladder makes a
**hybrid mandatory**: breadcrumb for the vertical path + a contextual panel for siblings at the
current altitude.

✅ **One model, many lenses, re-scoped by altitude — not different pages.** Vercel's **scope switcher**
flips the *same* view between team and project ("projects-as-filters"); Datadog's **Saved Views**
(Ownership/Reliability/Infrastructure) pin altitude-specific lenses over one entity graph; the same
nodes used at design time pivot to live telemetry. ✅ **Past ~1000 entities, saved/filtered views
replace deep trees** — GitHub's Repository Dashboard (GA 2026-02) is a *saved-view manager*, not a
folder tree ("you stop browsing trees and start saving filtered queries"); Linear removed
tree-heaviness in favor of saved Views + palette. ✅ **Breadcrumbs auto-generate from the route/page
tree** (Grafana Scenes: `getParentPage` builds the breadcrumb; the URL *is* the hierarchy; data-links
are the drill-down edges) — single source of truth for hierarchy + breadcrumb + routing. 🔶 Breadcrumbs
need **truncation at depth** (Grafana collapses center items at ~45-50% screen width — from a GitHub
issue, directionally right, exact number unverified).

✅ **VS Code extends the breadcrumb *below* the file into the symbol path** (org → project → system →
component → file → symbol → cursor as one unbroken trail) and offers editor groups + pinned tabs — the
workspace model Eden's desktop shell should adopt to compare a diagram + transcript + doc at once.

**Implications for Eden:**
- Make the **typed entity (archetype) drive which panels render** at each altitude (T4/C13) — the
  C4-style ladder (org→project→system→component→code→run) is a **relation graph**, with the
  **photosphere node = a navigation device** (click to descend).
- **One unbroken breadcrumb spanning all altitudes** (VS Code's file→symbol extension), auto-generated
  from the route tree (Grafana), showing **hierarchy not history**, truncating at depth; pair it with a
  **contextual sidebar for siblings** (the hybrid NN/g requires at 6 levels).
- **Color-code global vs contextual** and **cap nav-control depth** (GitLab) — global queues/review
  vs. this-system context must be visually distinct.
- **Saved/filtered views + the command palette are the scale escape hatch** past ~1000 entities
  (1000+ production deployments, C2) — not deep trees; the palette is the cross-altitude jump tool.
- **Diagrams default to depth-1 + explicit expansion + clustering** (Backstage) so the
  design=observability canvas survives a 1000-deployment org.

---

## Candidate UI theses for Eden (numbered · falsifiable · 🔶)

1. 🔶 **U1 — One model, many postures.** A single project model projected into named workspaces
   (Specify/Build/Operate/Review/Founder) that swap *toolset*, never *content*, will outperform
   separate per-task screens on task-switch time. *Falsified if* users report disorientation
   ("where did my project go?") on workspace switch in usability tests.
2. 🔶 **U2 — The palette is the spine.** A single fuzzy command palette over every Eden verb +
   cross-altitude jump, with inline shortcuts, becomes the primary navigation for power users within
   one week. *Falsified if* telemetry shows <20% of expert sessions invoke it, or users still rely on
   tree-drilling at 1000+ entities.
3. 🔶 **U3 — The diagram is the observability surface.** Painting live latency/error onto photosphere
   edges/nodes (New Relic vocabulary) and clicking a node to its run/transcript lets operators triage
   an incident *from the design diagram alone*. *Falsified if* operators still leave for a separate
   dashboard to diagnose, or the canvas can't stay legible at production node counts.
4. 🔶 **U4 — Semantic drift, because Eden owns both sides.** Because Eden generates both the model and
   the code (T2/C13), it can compute *semantic* drift (does the code match the architecture) that
   link-existence tools (IcePanel) and OTel-only tools (Multiplayer) cannot, and offer an AI
   remediation PR (T3/T7). *Falsified if* generated-model↔live-topology reconciliation produces more
   false-positive drift than IcePanel's cheap link-existence check.
5. 🔶 **U5 — The tutorial is the first PoC.** A Walkthrough whose steps auto-tick on real Eden events
   (navigate altitude, open diagram, rule a gate) and that ends with a working cheap PoC (C2) yields
   higher activation than any passive tour. *Falsified if* completion <80% (the Superhuman
   interruptive bar) or users abandon before a working system exists.
6. 🔶 **U6 — Density dial, not forked UI.** One photosphere UI with a label/density toggle serves both
   the non-technical founder (C1) and the technical operator without a separate "simple mode."
   *Falsified if* either persona demands a distinct UI, or the toggle fails to bridge the comprehension gap.
7. 🔶 **U7 — Docs are typed artifacts on review rails.** Doc 11 documents as AST-backed typed objects
   with owner/status/gate-state, riding branch→review→merge-rule→outdated-review (GitBook) +
   verification-with-expiry (Notion), keep docs in sync with code better than freeform prose.
   *Falsified if* doc staleness vs. code (vFunction's 56% baseline) is not measurably reduced.
8. 🔶 **U8 — Hover-sync across altitudes.** document↔diagram↔code↔runtime highlight-on-hover (Stripe's
   prose↔code, generalized) measurably reduces the cognitive mapping cost between a design doc and its
   live system. *Falsified if* users don't discover or use the sync, or it can't be kept consistent
   across the four surfaces.
9. 🔶 **U9 — Breadcrumb + sibling-panel hybrid beats either alone.** At Eden's 6-level ladder, an
   unbroken auto-generated breadcrumb (hierarchy-not-history) + a contextual sibling panel + color-coded
   global/contextual zones keeps "where am I" answered. *Falsified if* users still get lost descending
   org→run, or breadcrumb truncation hides the load-bearing altitude.
10. 🔶 **U10 — Desktop earns its place on presence, not features.** The Tauri shell's whole value is
    global shortcut + native menubar/tray + OS notifications/always-on + folder export + offline reading
    + multi-window; everything else is identical (same bundle). *Falsified if* desktop needs
    desktop-*exclusive* features to justify itself, or reads as "a crap website" (the Figma failure).

---

## Open questions

| # | Question | Why it matters | Lean |
|---|----------|----------------|------|
| Q1 | Geometric zoom vs. semantic grouping for altitude on the photosphere canvas? | New Relic/Datadog/Ilograph all chose grouping+perspective over scale-zoom. | 🔶 Semantic grouping + drill-down + perspectives; reserve zoom for within-altitude |
| Q2 | Is "design view" vs "observability view" one perspective-toggle (Ilograph) or two workspaces (Blender)? | Determines whether C10 is a view flip or a posture switch. | 🔶 Perspective toggle on *one* canvas; workspace only if panels diverge hard |
| Q3 | How is semantic drift surfaced without false-positive fatigue? | IcePanel's link-existence is cheap but shallow; semantic is differentiated but noisier (U4). | 🔶 Ship link-existence Accuracy Score first; gate semantic drift behind confidence + remediation-PR |
| Q4 | Mandatory tutorial for the founder (C1) but skippable for experts — one flow or two? | Superhuman says mandatory works for the quadrant; games say respect expertise. | 🔶 One Walkthrough, tiered/skippable steps with `when`-conditions |
| Q5 | Web-first or desktop-first for the founder's *first* PoC? | C1 needs zero friction; desktop needs install + signing. | ✅ Web is the zero-friction entry; desktop is the power-user upgrade |
| Q6 | How much of doc 11's Markdoc-class validation runs client-side vs. in the cluster (C4)? | Personalization/validation needs system context that lives on the cluster. | 🔶 Validate in-cluster (where ground truth is); client renders + hover-syncs |
| Q7 | Does the breadcrumb extend into code/symbol (VS Code) or stop at component? | Determines whether code/run are true altitudes or leaf detail. | 🔶 Extend to file→symbol when a browser/VS Code editor is the active surface |
| Q8 | Pie/radial accelerators (Blender `Q`) — worth the learning cost on a software ops tool? | Spatial muscle memory is powerful but unproven outside creative tools. | 🔶 Defer; ship palette + small canonical shortcut set first, measure demand |
| Q9 | Is Linux/WebKitGTK a supported desktop target or web-only? | Rendering divergence on a dense UI is the main "same bundle" leak. | 🔶 Support but treat as first-class visual-regression target; degrade to web if it lags |
| Q10 | What is Eden's "~6 load-bearing verbs" canonical set? | Ableton's lesson: ship few, repeated-until-automatic, not 200 shortcuts. | 🔶 Likely: create-project, run-gate, open-transcript, jump-altitude, regenerate-doc, redeploy |

## Sources

**Deep tools / learnability:** ableton.com/en/manual/first-steps · ableton.com/en/live-manual/12/working-with-the-browser ·
docs.blender.org/manual/en/latest/interface/window_system/workspaces.html · docs.blender.org/manual/en/latest/interface/tool_system.html ·
wiki.blender.jp/Dev:2.8/UI/Workshop_Writeup · figma.com/blog/behind-our-redesign-ui3 · help.figma.com/hc/en-us/articles/23954856027159-Navigating-UI3 ·
blackmagicdesign.com/products/davinciresolve · dev.epicgames.com/documentation/unreal-engine/unreal-engine-interface-and-navigation ·
docs.derivative.ca/Operator · nngroup.com/articles/progressive-disclosure · cs.cmu.edu/~jasonh/projects/piemenu

**Document UX:** notion.com/product/wikis · notion.com/releases/2025-03-26 · linear.app/docs/project-documents · figma.com/blog/the-linear-method-opinionated-software ·
stripe.dev/blog/markdoc · docs.stripe.com/building-with-llms · gitbook.com/features/git-sync · gitbook.com/docs/collaboration/merge-rules ·
docs.readme.com/main/docs/versions · zapier.com/blog/coda-vs-notion · moesif.com/blog/best-practices/api-product-management/the-stripe-developer-experience-and-docs-teardown ·
matrixflows.com/blog/prevent-knowledge-base-implementations-failure

**Diagrams as runtime:** structurizr.com/as-code · c4model.com · docs.icepanel.io/integrations/linking-to-reality · ilograph.com/blog/posts/breaking-up-the-master-diagram ·
multiplayer.app/blog · datadoghq.com/blog/service-map-team-application-boundaries · docs.newrelic.com/docs/service-architecture-intelligence/maps/dynamic-flow-map ·
grafana.com/docs/tempo/latest/metrics-from-traces/service_graphs/service-graph-view · backstage.io/docs/features/software-catalog/system-model ·
aws.amazon.com/infrastructure-composer · vfunction.com/use-cases/architectural-drift · dev.epicgames.com/documentation/unreal-engine/blueprint-debugger-in-unreal-engine

**Onboarding:** code.visualstudio.com/api/ux-guidelines/walkthroughs · code.visualstudio.com/api/references/contribution-points ·
ableton.com/en/live/learn-live · docs.blender.org/manual/en/latest/advanced/app_templates.html · candu.ai/blog/the-anti-onboarding-strategy-how-linear-converts-philosophy-into-product-adoption ·
review.firstround.com/superhuman-onboarding-playbook · goodux.appcues.com/blog/notions-lightweight-onboarding ·
gamedeveloper.com/design/how-onboarding-should-be-applied-to-tutorials · hbs.edu/ris/Publication%20Files/11-091.pdf (IKEA effect) ·
raycast.com/faq

**Desktop / web parity:** v2.tauri.app/concept/architecture · v2.tauri.app/plugin/global-shortcut · v2.tauri.app/distribute ·
gethopp.app/blog/tauri-vs-electron · code.visualstudio.com/docs/remote/remote-overview · code.visualstudio.com/api/advanced-topics/remote-extensions ·
slack.engineering/building-hybrid-applications-with-electron · linear.app/changelog/2019-04-25-linear-desktop-app ·
blog.nobledesktop.com/learn/figma/understanding-the-differences-between-web-app-and-desktop-app-for-figma · notion.com/blog/how-we-made-notion-available-offline ·
github.com/ahkohd/tauri-nspanel · github.com/tauri-apps/awesome-tauri · okupter.com/blog/companies-using-svelte

**Multi-altitude navigation:** backstage.io/docs/features/software-catalog/system-model · roadie.io/backstage/plugins/catalog-graph ·
datadoghq.com/blog/service-map · datadoghq.com/blog/software-catalog-custom-entities · about.gitlab.com/blog/redesigning-gitlabs-navigation ·
github.blog/news-insights/product-news/exploring-github-with-the-redesigned-navigation · github.blog/changelog/2026-02-24-repository-dashboard-is-now-generally-available ·
vercel.com/changelog/command-menu-now-available-in-deployments · grafana.com/developers/scenes/scene-app-drilldown ·
linear.app/docs/conceptual-model · code.visualstudio.com/docs/editing/editingevolved · nngroup.com/articles/breadcrumbs · nngroup.com/articles/local-navigation ·
arxiv.org/pdf/2601.05401 · arxiv.org/pdf/2602.00947 · arxiv.org/pdf/2509.21685
