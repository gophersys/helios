# Contract — agentprofile (DRAFT)

> Status: **DRAFT for negotiation** · 2026-08-26 · `agentprofile` is the **authoring surface** for
> the agent instrumentation of every gophersys repository, plus the **deterministic renderer** that
> emits each harness's native files from it and the **commit-time drift gate** that keeps the
> committed files equal to the render. It exists because Mateo ruled on 2026-08-26 that the source
> of truth is a central schema and a renderer, and that rendered files are committed and gated on
> drift (§0). The **producer** is the library under construction in `gophersys/libs` on branch
> `feat/agentprofile`. The **consumers** are four, and they are meant to build in parallel against
> this text: the CI drift gate, the agent pod that mounts a rendered profile by digest, the
> telemetry lane that records which profile a run used, and `agentconfiguration` when it is built.
>
> It **CITES and never redefines**: `AgentTemplate`, `TemplateRef`, `SkillRef`, `RuleRef` and the
> `Routing` field (`contracts/orchestrator.md`, FROZEN); `agentsession.RouteKey` including its
> `Role` vocabulary (`contracts/agentsession.md`, FROZEN); the `errors.Kind` taxonomy
> (`contracts/errors.md`, FROZEN); the harness pin set (ADR-0021, `harnesses/versions.env`); the
> git process (`.claude/rules/git-process.md`, ADR-0032). It reuses the *shape* of upstream
> `agentcfg`'s `Harness`/`FileSet`/`File` seam, which is a proven mechanism — reusing a shape is
> not duplicating a concept (§2.1).
>
> **Freezing is Mateo's gate**, `.claude/rules/git-process.md` §5: *"a chart or contract PROMISE"*
> is in the list he *"gates personally; no agent authority covers them"*. No agent exercises it,
> and this header says DRAFT until he rules. **A consequence to expect, not to work around:**
> `bash ./ctl.sh phase-gate architecture` for `libs/go/agentprofile` is **RED BY DESIGN** until he
> rules, because `_gate_contract_frozen` (`libs/go/_ctl/lib.sh:1076-1090`) requires
> `^[> ]*Status:[^.]*\bFrozen\b` in this file and a draft correctly fails it. A red architecture
> gate here is the gate working. Do not edit this header to make it green.
>
> Epistemic legend: ✅ ratified · 🔶 derived-but-settled · ⚠️ load-bearing assumption · 🧩 open fork.

## 0. The rulings this contract implements

✅ **Mateo, 2026-08-26**, AskUserQuestion decision prompt, interactive session `f9c810a8` (not an
orchestrator session), recorded in `.dev/instrumentation-contracts.md` "Authority":

> 1. Instrumentation source of truth = **central schema + renderer** — one agentprofile schema
>    (role × harness matrix: claude/omp/codex) in eden; a renderer emits each harness's native
>    files (CLAUDE.md, .claude/rules, skills, settings; omp/codex equivalents).
> 2. **Commit-time rendering + drift gate** — rendered files are committed; CI fails on drift,
>    following the estate's existing generated-file pattern.

Everything below is either a consequence of those two rulings, a citation, a measurement, or a
question put back to him in §10. Nothing below is a third ruling.

## 1. Scope — and the explicit NOT-list

🔶 `agentprofile` owns the **AUTHORING** side of agent instrumentation, and its lifecycle is
**commit-time**. It owns exactly five things, each with one home (10 §9):

1. **The profile document** — one committed, versioned JSON file (§3.2 gives the reason, and it is
   a gate, not a taste) holding the role set, the harness
   target set, the instruction modules (rule bodies, skill bodies, document sections), and the
   per-repository overlays (§3).
2. **Composition and ordering** — which modules a `(repository, role)` selects, and the *total*
   order in which they emit (§3.4). There is deliberately **no body-override operator** (§3.4.2).
3. **The deterministic render** — `(profile document, repository, role, harness) → FileSet`, byte
   -identical on every run (§5).
4. **The digest** that content-addresses a rendered profile (§7).
5. **The drift check** — re-render in memory, compare against the committed tree, report
   `Divergence` (§6). The check is **read-only over the tree by construction** (§4.3).

It does **NOT** own:

- **Runtime binding — which `(harness, model)` a `RouteKey` resolves to, and auth per role.**
  `agentconfiguration` keeps that (reserved, unbuilt — §2). `contracts/orchestrator.md:22` is
  explicit: *"**Routing economics / model selection** — `agentconfiguration` resolves
  `RouteKey → Route`"*. `agentprofile` never resolves a model, never holds a credential, never
  makes an LLM call.
- **The `Role` vocabulary.** `agentsession.RouteKey.Role` is FROZEN and already owns the word
  (`contracts/agentsession.md:473-480`). `agentprofile` uses those values; it does not mint a
  second set (§3.3).
- **Spawn-time template resolution.** `orchestrator` folds an `AgentTemplate` into an
  `agentsession.Spec`; `agentprofile` is not in that path (§2.2 says how the two meet).
- **Pod lifecycle, the CRD, `metadata.uid`, `AgentID` minting.** The sibling lane's
  `fleetenvelope.md:63` assigns those to `agentpod`: *"Pod lifecycle, the CRD, the role, the
  profile — `agentpod` owns those."* Read that sentence precisely: `agentpod` owns the **pod's
  reference to** a profile and the pod's role **field**; this contract owns the profile's
  **content, render and digest**. §7 states the guarantees the two need to meet on.
- **Executable instrumentation.** v1 emits **declarative files only** — no hook script, no slash
  -command script, no `Makefile`. Reason in §3.6; the resulting mode rule is an invariant (§8 I6).
- **Harness invocation.** A renderer writes files and never starts a harness. That keeps the E1
  connector story clean: nothing external is touched, so no connector contract is required here.
- **Whether a CI agent actually loaded its profile.** That is a different gate with a different
  owner — `git-process.md` §14 row 10, owner `cictl`. §6.6 keeps the two apart.
- **Personal instrumentation.** `~/.claude/` never enters a render. `git-process.md:257-258`:
  *"An ephemeral runner has no `~/.claude`, so no personal rule, skill or agent reaches it."*
  The render's subject is the repository, and only the repository.

## 2. The cohesion boundary with `agentconfiguration` — the load-bearing section

Eden's cohesion contract says one concept has one home (`docs/architecture/README.md` §4). An
adjacent home is already **RESERVED and UNBUILT**, and its one-line description overlaps this
contract's centre. The overlap is real and must be settled here, not stepped around.

**`10-library-system.md:350`, verbatim:**

```
| `agentconfiguration` | Config + routing + the LLM call binding: model + auth per role; compiles to harness formats (upstream design: agentcfg-architecture) |
```

**`contracts/orchestrator.md:129-135` (FROZEN), verbatim:**

```go
// SkillRef / RuleRef are opaque, versioned names of capability modules the
// agentconfiguration/TemplateStore resolves into harness-native artifacts. The
// orchestrator carries them; it does not parse, fetch, or execute their contents.
type (
	SkillRef struct{ Name, Version string }
	RuleRef  struct{ Name, Version string }
)
```

**`docs/architecture/open-decisions.md:20`** keeps OD-7 open — *"agentconfiguration open items
inherited from upstream (CLI module split, yaml v3 vs v4, harness plugin model, per-call key
rotation, content-based routing) … rule during WS2."*

✅ **`libs/go/agentconfiguration` DOES NOT EXIST.** Measured here:
`ls /Users/mateo/code/.worktrees/libs-agentprofile/go/` lists `_ctl agentruntime agentsession
codeinsight configuration dependencies edenhttp envelope errors forge gitrepository objectstorage
observability orchestrator secrets testing workspaceprovider` — 16 libraries and no
`agentconfiguration`. So the boundary is being drawn against a **name and a one-line description**,
not against running code. That is the cheapest moment to draw it, and the last cheap one.

### 2.1 What the upstream design actually contains — verified, with two corrections

The upstream design of `agentcfg` is `docs/upstream/build-system/agentcfg-architecture.md` and
`portable-agent-config-2026-06.md`. They are imported verbatim and are **never canonical**
(`docs/architecture/README.md:22-28`); the promotion path is that a finding is PROMOTED into a spec
with a citation, never edited in place. This section is that promotion.

**Confirmed present, and worth reusing:**

- ✅ A per-harness compile seam. `agentcfg-architecture.md:437-449`:
  `Compile(ctx context.Context, r *ir.Resolved) (FileSet, []diag.Diagnostic, error)`, alongside
  `Name() string` and `Capabilities() cap.Capabilities`.
- ✅ `File{Path, Content, Mode, Sensitive}` and `FileSet{Harness, Files}` — `:451-465`.
- ✅ A `cap/` capability matrix shared by harnesses — `:123-124` and §8 `:550-601`.
- ✅ Per-harness compile packages, `claudecode/` among them, emitting `.claude/settings.json` and
  `.claude/agents/<name>.md` — `:521-547`; and `codex/` at `:109`.
- ✅ A CLI `agentcfg compile|validate|lint|render|route` — `:131-132`.
- ✅ Design rule 1, verbatim `:13`: *"**The IR is the product.** Everything funnels through one
  immutable intermediate representation."*
- ✅ A purity contract on the emitter, `:961`: *"`Harness.Compile` — must be pure."*
- ✅ `FileSet.WriteAll` **rejects symlinks** — `:468`. That is a guard this contract adopts and
  cites (§6.4).

⚠️ **Correction 1 — `File`/`FileSet` are declared TWICE in the upstream document, and the brief
this section was written from named the wrong home.** The package layout lists
`emit/fileset.go   FileSet, File (path + content + mode + sensitive)` at `:126-128`, and *also*
`harness/harness.go   interface Harness, FileSet, File, Register` at `:98`. The code in §7 declares
them in `package harness` (`:451-465`), and the top-level re-export at `:188-189` aliases
`File = harness.File` / `FileSet = harness.FileSet`. So the **operative** home is `harness`, and
`emit/` is a layout entry no code in the document uses. Corrected here rather than repeated.

⚠️ **Correction 2 — the `claudecode` emitter's file list differs between the layout and the code.**
The layout at `:99-100` says it emits `claude-code + .mcp.json + .claude/agents/*.md +
claude-code-router config`; the code at `:521-547` emits `.claude/settings.json`,
`.claude/agents/<name>.md` and an optional `~/.claude-code-router/config.json`, and never
`.mcp.json`. Both are recorded; neither is canonical.

**Measured absences — this is what justifies a new contract, and it is not a turf argument:**

- ✅ `CLAUDE.md` — **zero occurrences** across the 1124 lines of `agentcfg-architecture.md`. The
  emitter that ruling 1 names first is the one upstream never wrote.
- ✅ `drift` — zero. `byte-identical` — zero. `determinism` — zero. Upstream ships the
  *ingredients* — a purity contract, a `FileSet.Diff(root)` primitive (`:470`), golden tests — but
  **a `Diff` you can call is not a check that fails**. There is no gate and no determinism
  guarantee in the design.
- ✅ Its entire instruction-content model is **two scalar paths**.
  `portable-agent-config-2026-06.md:164-167`, verbatim and complete:

  ```yaml
  # --- 7. Rules (cross-harness AGENTS.md compatibility) -----------------------
  rules:
    global: AGENTS.md                          # always-on project rules
    per_mode_root: rules/                      # rules/{mode}/*.md
  ```

  No bodies, no composition, no precedence, no overlays, no skills key. In the IR they are path
  pointers only.
- ✅ Skills are an explicit upstream **NON-GOAL**. `agentcfg-architecture.md:1041`, verbatim:
  *"- **No agent framework.** No tool-loop, no scratchpad, no skills. This is the layer below your
  agent loop."* And `:19`: *"The library's job ends at 'given a request, here is the model and the
  auth headers.'"*

🔶 **Therefore three concepts are genuinely unowned: determinism, the commit-time drift gate, and
the composition / ordering / overlay of instruction content.** That, and not a claim on
`agentconfiguration`'s territory, is what a second library is for.

### 2.2 Collision one — the slash in the frozen line, and the seam it leaves

`orchestrator.md:129-131` says the refs are resolved by *"the **agentconfiguration/TemplateStore**"*.
The slash means the FROZEN contract **reserved the job and left the owner ambiguous**. It did not
assign harness-native rendering to `agentconfiguration`; it named two candidates and moved on. That
ambiguity is the seam this contract proposes to occupy — and it may only be occupied **explicitly,
with that line quoted**, or a second home has been created by silence.

🔶 **The proposal.** `agentprofile` is the resolver of `SkillRef`/`RuleRef` into files.
`orchestrator.md:99-100` is satisfied unchanged: the orchestrator still *"carries them; it does not
parse, fetch, or execute their contents."* Only the identity of the resolver is disambiguated, and
the frozen `struct` fields do not move, so **no contract revision of `orchestrator.md` is required**
under this proposal — the disambiguation is a comment-level clarification, recorded as an ADR (§10
Q1), never a silent edit.

### 2.3 Collision two — `agentsession.RouteKey` already owns "role", and it has two axes

`contracts/agentsession.md:473-480` (FROZEN), verbatim:

```go
// RouteKey is the opaque key agentconfiguration resolves to a concrete (harness,
// model) pair per phase/role (§2.7, 02 §5 agents.yaml). The session port does NOT
// decide which harness/model — it is told. This is C22's "right agent for the right
// phase" selector, kept out of this contract's policy.
type RouteKey struct {
	Phase string // "product-design", "implement", "review", ... | "" for interactive
	Role  string // "assistant" | "implementer" | "reviewer" | ...
}
```

Two consequences, both stated rather than assumed:

1. ✅ **`agentprofile.Role` values ARE `RouteKey.Role` values.** One vocabulary, one home, and that
   home is the frozen contract. `Role` is a distinct Go type here for type safety, and §3.3 states
   the conversion is the identity on the string.
2. 🧩 **A bare "role × harness" matrix DROPS `Phase`.** Ruling 1 names a role × harness matrix, and
   `RouteKey` carries two axes. The proposal keys a render target on `Role` alone. The reason is a
   property of the lifecycle, not a preference: **a git checkout holds one file tree.** A
   repository cannot carry four different `.claude/rules/` for four phases at the same paths, and a
   commit-time render's output is a checkout. `Phase` varies *within* a run; the committed tree does
   not. Where a phase must matter, it is expressed as a phase-scoped *module* the harness loads on
   demand — which is what a path-scoped rule already is. Recorded as fork F1 and put to Mateo as
   §10 Q4.

⚠️ **A hazard to name, not to solve here.** `open-decisions.md:13` OD-16-roles keeps *"a `roles`
library"* alive as an option for **authorization** role→grant mappings. That is a different concept
wearing the same word. `agentprofile.Role` is the routing/instrumentation role of `RouteKey`, never
an authz principal. If OD-16-roles is ever ruled toward a `roles` library, the two must be
distinguished in that ruling.

### 2.4 Collision three — ADR-0026 §B.3 already declares `.claude` rules a 3-way-merge path

This is the collision most likely to be missed, and it is a direct contradiction.

`docs/architecture/adr/0026-templates-in-libs-and-monorepo-maintenance.md:59-72` declares every path
to be exactly one of **template-managed**, **instance-owned** or **submodule**, and it puts
`.claude` rules and `harnesses` in the template-managed set — synced by a **3-way merge**, *"the
copier/cruft pattern: the instance remembers its template version; `template sync` re-applies
upstream changes **while preserving local edits**."*

⚠️ **A path cannot both preserve local edits and fail CI on any diff from the render.** Those are
mutually exclusive treatments of the same bytes. The contract must therefore say which paths move
from the ADR-0026 sync channel into the agentprofile render channel — a boundary that leaves both
claims standing is not a boundary.

🔶 **The proposal.** The paths in §3.6's emitted-surface table move to the **render channel**, and
they are removed from the template-managed set. Everything else ADR-0026 lists — `.githooks`,
`.ci`, root configs, the migrate runner — stays in the sync channel untouched. The good news, and
it is why this is a pre-emption rather than a break: ADR-0026's own Consequences call the BOM
manifest, the migrations tree, the managed-paths manifest and the sync tool *"first-class,
to-be-built machinery."* **None of it is running.** Changing an unbuilt channel's scope costs
nothing today and costs a migration later.

**The related, ratified case — doc 16 §8.** `16-application-template-system.md:157-174` (✅
ADR-0023) is a **real, hand-authored** `.claude/rules/` corpus with an EXTENDS semantic already
written in prose: *"These EXTEND the shared `libs/.claude/rules/` … those still apply; these add the
app shape."* That is exactly the base + overlay composition of §3.4, written in English instead of
in a schema. 🔶 **The proposal: 16 §8 becomes a CONSUMER of the renderer** — its five rules become
modules, its "EXTEND" becomes the `repository` overlay layer, and the prose statement is replaced by
a mechanical one. It is not excluded, because excluding the one ratified corpus that already has the
right shape would leave the contract's central mechanism with no proof.

**Pre-empting a reading a reviewer will find.** `16-application-template-system.md:148-155` states
the estate's rendering doctrine: *"one typed `ServiceSpec` renders to BOTH … no hand-maintained
drift, no re-implemented rendering. … **Reuse, never reinvent** is the load-bearing invariant."*
`deploy/servicespec` is **prior art of exactly this shape in a different domain** — one typed
catalog, two renderers, a byte-comparison gate. `agentprofile` is that pattern applied to
instruction files. It is not a parallel rendering concept, and it re-implements no renderer that
exists.

### 2.5 The proposal, and the honest alternative

**Option A — the seam (proposed).**

| | `agentprofile` | `agentconfiguration` (reserved, unbuilt) |
|---|---|---|
| Owns | the role × harness matrix as a committed, versioned document; composition and ordering of rules and skills; per-repository overlays; the deterministic render to a `FileSet`; the digest; the drift check | which `(harness, model)` a `RouteKey` resolves to; auth per role; the spawn-time resolution of an `AgentTemplate` |
| Lifecycle | **commit-time** | **run-time** |
| Output | files committed to git | a `Route` and auth headers, in memory |
| Touches credentials | never (§8 I5) | yes, by definition |

**The seam.** When `agentconfiguration` is built, it resolves a `SkillRef`/`RuleRef` by naming an
`agentprofile` `Target` and **calling `agentprofile`'s renderer**. **One home for rendering, cited
from two call sites — never two renderers.** The call is one-directional: `agentconfiguration`
imports `agentprofile`, never the reverse, so the commit-time library never gains a dependency on a
runtime library that touches credentials.

**Merits of A:** the two lifecycles stay apart, so a commit-time, git-committed, drift-gated concern
never shares a library with model routing and auth; this lane is not blocked behind OD-7; and the
credential blast radius of the library that writes files into git is structurally zero.

**Costs of A:** it takes the words *"compiles to harness formats"* out of a reserved manifest row
that has said them since doc 10 was written; it needs an ADR to record the supersession; and a
reader of `orchestrator.md:129-131` alone would still guess the wrong owner until that ADR lands.

**Option B — the fold.** One library, `agentconfiguration`, with two verbs: `render` (commit-time)
and `route` (run-time).

**Merits of B:** it honours the reserved name and the 10 §12 manifest row exactly as written; it
needs no supersession ADR; and it avoids a second document that says *"compiles to harness
formats"*.

**Costs of B:** it merges a commit-time concern whose output is committed to git with a runtime
concern that touches credentials and model routing — one library, two lifecycles, one blast radius;
it blocks this lane behind OD-7, which is scheduled for WS2 and whose *"harness plugin model"* item
is an architectural fork this contract does not need to wait for; and the four parallel lanes in
`.dev/instrumentation-contracts.md` §"parallelization map" all wait with it.

🔶 **Recommendation: A.** The deciding reason is the credential boundary, not the tidiness. A
library that writes files into git and a library that resolves auth per role should not be the same
compilation unit — that is the same instinct that keeps `secrets` out of every contract that carries
a `secrets.Reference` instead of a value. The scheduling benefit is real but secondary, and it is
stated as secondary on purpose. Mateo rules: §10 Q1.

### 2.6 What happens to the 10 §12 manifest row and to OD-7 — under each option

A boundary that leaves a stale one-line description in the manifest is not a boundary. So, in the
same change that a ruling lands:

**Under option A:**

- `10-library-system.md:350` is **amended**, not deleted. The proposed replacement pair of rows:

  | Library | Owns |
  |---|---|
  | `agentconfiguration` | Config + routing + the LLM call binding: model + auth per role (upstream design: agentcfg-architecture). **Harness-format rendering is `agentprofile`'s (ADR-00NN); this library CALLS it.** |
  | `agentprofile` | The committed role × harness instrumentation matrix, its deterministic render to harness-native files, and the commit-time drift gate |

- `docs/architecture/README.md` §4 gains **one cohesion row** naming `agentprofile` as the home of
  "agent instrumentation authoring, render and drift". Today that table has no row for agent
  profiles at all; a contract that claims a home without writing it there has claimed nothing.
- **OD-7 stays open and NARROWS to four items.** Its five are *CLI module split, yaml v3 vs v4,
  harness plugin model, per-call key rotation, content-based routing*. Three — per-call key
  rotation, content-based routing, and the CLI module split — are runtime/packaging items and stay
  wholly with `agentconfiguration`. **The yaml v3 vs v4 item does not reach `agentprofile` at all**,
  because this contract's document format is JSON parsed with `encoding/json` (§3.2), so the
  question never arises here. Exactly **one** item is shared and must be ruled once rather than
  twice: the **harness plugin model**, since both libraries register per-harness implementations.
  🔶 Proposal: OD-7 gains one sentence recording that its harness-plugin-model item now binds both
  libraries and that `agentprofile` follows whatever WS2 rules, with an interim position in §9 fork
  F4 so this lane is not blocked.
- **A supersession ADR is required.** `docs/architecture/README.md:22-23`: *"Where this set and the
  upstream corpus conflict, this set wins and **must record the supersession as an ADR**."* Taking
  harness-native emission out of the scope the upstream design gives `agentcfg` is such a conflict.
  ⚠️ The next free ADR number is **0033**; 0030 is a silent gap referenced by nothing and must not
  be reused. **Opening an ADR is Mateo's §5 gate** — it is PROPOSED in §10 Q1 and is not opened by
  any agent.

**Under option B:**

- `10-library-system.md:350` stands **unchanged** — no amendment, and that is B's whole merit.
- This document is **withdrawn** and its §3–§8 are re-homed as sections of a future
  `contracts/agentconfiguration.md`. It is not moved to the attic as a superseded spec; a draft that
  was never frozen is withdrawn, and git history is the archive (`CLAUDE.md` "Documents").
- **OD-7 becomes a blocker on this whole program**, because the harness plugin model would then be a
  decision inside the one library that has to render before any of the four lanes can start.
- No supersession ADR is needed. The `.dev` parallelization map's lane 1 moves from *"NOW — in
  flight"* to *"blocked on OD-7 / WS2"*, and lanes 4 and 7 move with it.

### 2.7 Naming — the warrant, and three disambiguations

✅ **The warrant is already written.** `.claude/rules/git-process.md:260-262`, verbatim: *"**Therefore
the repository's own `CLAUDE.md` and `.claude/` ARE the CI profile, and eden's `.claude/` is
authoritative inside eden.**"* The word "profile" already names exactly this concept in the
repository's own process rule. `:268-269` then records the gap this contract closes: *"ASSUMED, not
yet measured: that each repo's committed instrumentation is complete enough to stand alone as that
profile."*

✅ **The name is free.** `agentprofile`, `profileRef` and `AgentProfile` have zero occurrences
repo-wide outside `.dev/instrumentation-contracts.md`, which is this lane's own state file and is
deleted before merge (`git-process.md` §5 condition 4). Slug is one lowercase HNS-1 word matching
the future `libs/go/agentprofile` (10 §5).

Three disambiguations, one sentence each, because a reviewer will hit all three:

- **`--profile` in `docs/plans/eden-rework-blueprint.md`** (`:482`, `:513`, `:643`, `:732`) is the
  **environment-values axis** of `env up --profile dev|staging`. Unrelated; that axis is `stage`
  in 10 §2 terms and this contract never uses the flag name.
- **Codex and Roo have harness-native things called "profiles"** (`agentcfg-architecture.md:109`
  `codex/  ~/.codex/config.toml + profiles`). Those are *outputs* a renderer may emit; they are not
  this contract's subject.
- **Nothing here is called a "template".** The word is triple-booked in this estate:
  `libs/go/templates` (versioned environment registry, 10 §12), the kernel `template` (per-cell
  scaffolds, 10 §12), and `libs/templates/` (application templates, ADR-0023/0026). A fourth
  meaning would be a defect.

## 3. The schema

### 3.1 What exists today — the requirements evidence the render must reproduce

✅ Measured in this worktree and in `/Users/mateo/code/eden` at the pinned submodule commits, by
`find … -type f` and `git ls-files`. This is the acceptance corpus of §6.5.

| Repository | Committed instrumentation | Count |
|---|---|---|
| `eden` | `CLAUDE.md` (root, 173 lines) · `.claude/agents/merge-agent.md` · `.claude/rules/git-process.md` | 3 |
| `libs` | `.claude/rules/{00-identity, 10-interface-design, 11-naming, 12-error-handling, 20-library-pipeline, 21-test-taxonomy, 22-harness-versions, 24-typescript-pipeline}.md` · `.claude-plugin/marketplace.json` | 8 + 1 |
| `infrastructure` | `.claude/rules/{00-identity, 10-secrets, 20-layering, 30-onboarding, 40-platform-contracts, 50-cluster-architecture}.md` · `.claude/skills/.gitkeep` | 6 + 1 |
| `.devcontainer` | `.claude/rules/00-identity.md` | 1 |
| `apps/platformgateway` | `.claude/README.md` · `.claude/rules/{00-add-resource, 10-five-files-per-route, 20-schema-and-migrations, 30-openapi-and-clients, 40-test-loop}.md` · `.claude/hooks/README.md` | 5 + 2 |

⚠️ **Three corrections to the brief this section was written from, each measured:**

1. **`libs/plugins/project-go/` has FOUR hook scripts plus a shared library, not five hook scripts**
   — `hooks/{post-edit-lint, pre-git-gate, session-start, stop-phase-check}.sh` plus `hooks/_lib.sh`
   and `hooks/hooks.json`, with `.claude-plugin/plugin.json`, `README.md` and
   `skills/api-design/SKILL.md`.
2. **There are TWO registered plugins, not one.** `libs/.claude-plugin/marketplace.json` registers
   `project-go` *and* `supervisor` under the marketplace `eden-libs`.
3. **`apps/platformgateway/.claude/hooks/` holds only `README.md`** — there is no hook script there.
   That matches `16-application-template-system.md:171-174`, which calls it *"a placeholder for the
   lifecycle hooks … wired when the template is promoted to a registered plugin"*.

✅ **`libs/plugins/supervisor/template/.claude/` is already a rendered-instrumentation template
tree, and it is the precedent for the emitted shape**: `settings.json`, `instructions/*.md` (5),
`commands/*.{md,sh}` (11 pairs + `_supervisor.sh`), `hooks/*.sh` (5, including `_hooklib.sh`),
`schemas/*.schema.json` (11), `state/fsm.json`. 🔶 **The lesson it teaches is a design decision:**
it names its instruction directory `instructions/`, while every other tree in the table names it
`rules/`. **The emitted directory name is therefore a consumer/harness choice, not a universal**,
and it belongs to the `Renderer` port (§4.3), never to the schema. A schema that hard-coded
`rules/` would have already been wrong once, inside this estate, before it shipped.

✅ **There is NO committed omp or codex instrumentation anywhere.** `find . -name AGENTS.md` returns
nothing; no `.codex/` or omp configuration file is tracked; the only hits for those names are the
two upstream design documents. The three harnesses exist in the estate **only as version pins**
(`harnesses/versions.env`, ADR-0021): `CLAUDE_CODE_VERSION=2.1.212`, `OMP_VERSION=17.2.5`,
`CODEX_VERSION=0.146.0`. **So the claude renderer has a real target and the other two have none.**
That is precisely why §4.3 stubs them behind the port with an explicit NOT-IMPLEMENTED error rather
than emitting nothing: **a silent empty emission is the failure mode this whole contract exists to
prevent** (§6.4 guard G1).

⚠️ **A measured finding this contract must not overstate, because it sharpens the WHY.** Only
`eden` has a root `CLAUDE.md`; `libs`, `infrastructure` and `.devcontainer` have **none**
(`git ls-files | grep -iE '(^|/)(CLAUDE|AGENTS)\.md$'` returns exactly one path, in eden). Their
rules reach a session through a **hook** — `CLAUDE.md:113-117` says the `project-go` plugin
*"injects `libs/.claude/rules/` at the start of a session"* — and that plugin must be installed with
`claude plugin marketplace add ./libs && claude plugin install project-go@eden-libs`. Grepping
`.ci/`, `.github/` and the `.devcontainer` repository for `plugin install` / `plugin marketplace`
returns **zero matches**. What that measures: **nothing in CI installs the plugin.** What it does
NOT measure: what a CI Claude actually loads — that requires running one and reading the answer,
which is `git-process.md` §14 row 10's probe and is not this contract's gate (§6.6). Stated as ⚠️,
not as ✅, for exactly that reason.

### 3.2 The profile document — and why it is JSON, not YAML

⚠️ **The format is JSON, and a real gate decides it.** `libs/.golangci.yml:193-212` defines a
`depguard` rule named `libs`, scoped to non-test Go (`files: ['!$test']`), whose **entire production
allow-list** is `$gostd` and `github.com/gophersys/libs/go`. Its comment, verbatim:

> *"a leaf pattern library may import the standard library and its SIBLING pattern libraries only.
> Any other third-party import is forbidden here — a vendor SDK is allowed only inside a named
> adapter package, which these leaf libs do not yet have. **If a contract later names a specific
> dependency, add it to `allow` with a comment citing the contract; do not open the gate
> wholesale.**"*

✅ Measured: **no non-test Go file in `libs/go/` imports any YAML package directly.** Every
`yaml` line in every `go.mod` there is marked `// indirect` (`workspaceprovider`, `orchestrator`,
`objectstorage` — pulled by the kubernetes and MinIO SDKs). So a YAML parser cannot enter this
library's production import graph without a shared-config edit.

🔶 **The decision: JSON, parsed with `encoding/json` and `DisallowUnknownFields()`.** Three reasons,
in order of weight:

1. **No gate change and no dependency.** `encoding/json` is `$gostd`. The escape hatch the depguard
   comment describes exists, but taking it is a change to a shared configuration that every library
   in `libs` obeys, and it should be spent on a dependency a contract genuinely needs.
2. **An unknown key must be a typed error.** `DisallowUnknownFields()` makes it one. A silently
   dropped key in an *instrumentation* schema renders a profile that is missing a rule, with nothing
   anywhere to say so — which is the exact failure class this contract exists to prevent.
3. **JSON has no anchors, aliases or merge keys.** Two documents that look different cannot resolve
   to the same value, and one document cannot expand differently under two parsers. When the whole
   product is a deterministic render, a format with no expansion semantics is one less thing to
   prove.

It also matches the estate's existing schema'd artifacts: `eden/schemas/document/v1/*.schema.json`
(9 schemas), `.claude/settings.json`, `libs/.claude-plugin/marketplace.json`.

🧩 The authoring ergonomics genuinely favour YAML, and upstream's `agents.yaml` is YAML. That is a
real fork, not a settled point — §9 F6, and it rides the freeze.

Illustrative and abbreviated; the normative content is the Go types in §3.3 and the rules in
§3.4–§3.6. Comments are prefixed `//` here for readability only — the committed file carries none,
because JSON has none, which is itself part of what F6 weighs.

```json
{
  "schemaVersion": 1,                          // the SCHEMA's version (E2: versioned before acceptance)
  "profileVersion": "0.1.0",                   // semver of THIS document; stamped into every banner
  "harnesses": ["claude", "omp", "codex"],     // closed set; pins in harnesses/versions.env (ADR-0021)

  // A module is one addressable body of instruction content. `name` + `version` ARE
  // RuleRef/SkillRef (orchestrator.md:133-135, FROZEN), so `name` is GLOBALLY UNIQUE — §3.4.1.
  "modules": {
    "rules": [
      { "name": "identity-libs",               // globally unique addressable name == RuleRef.Name
        "version": "1.0.0",                    // == RuleRef.Version
        "emitAs": "identity",                  // on-disk basename, without the order prefix
        "order": 0,                            // the filename prefix AND the emission-order key
        "body": "modules/rules/identity-libs.md" },
      { "name": "interface-design", "version": "1.0.0", "emitAs": "interface-design",
        "order": 10, "body": "modules/rules/interface-design.md" },
      { "name": "naming", "version": "1.0.0", "emitAs": "naming",
        "order": 11, "body": "modules/rules/naming.md" }
    ],
    "skills": [
      { "name": "api-design", "version": "1.2.0", "emitAs": "api-design",
        "order": 0, "body": "modules/skills/api-design/SKILL.md" }
    ],
    // sections of the single always-loaded document (CLAUDE.md / AGENTS.md)
    "documents": [
      { "name": "eden-hard-rules", "version": "1.0.0",
        "emitAs": "hard-rules",                // a heading anchor, not a filename
        "order": 20, "body": "modules/documents/eden-hard-rules.md" }
    ]
  },

  // `name` values ARE agentsession.RouteKey.Role values (agentsession.md:473-480, FROZEN).
  "roles": [
    { "name": "implementer",
      "rules": ["identity-libs", "interface-design", "naming"],
      "skills": ["api-design"],
      "documents": ["eden-hard-rules"] },
    { "name": "reviewer",
      "rules": ["identity-libs", "interface-design"],
      "skills": [],
      "documents": ["eden-hard-rules"] }
  ],

  "repositories": [
    { "name": "gophersys/libs",
      "root": ".",                             // the render root, repository-relative
      "roles": ["implementer", "reviewer"],
      "minimumFiles": 8,                       // the §6.4 G2 floor, declared per repository
      "overlay": {                             // composes with the role selection; §3.4
        "implementer": { "add": ["library-pipeline", "test-taxonomy"], "remove": [] },
        "*":           { "add": ["harness-versions"], "remove": [] }   // every role of this repository
      } }
  ]
}
```

### 3.3 The Go types

```go
// Harness is the closed target set. The values are the ADR-0021 pin names, so a harness that has
// no pin in harnesses/versions.env cannot be named here.
type Harness string

const (
	HarnessClaude Harness = "claude"
	HarnessOMP    Harness = "omp"
	HarnessCodex  Harness = "codex"
)

// Role is agentsession.RouteKey.Role, in a distinct Go type for compile-time safety. The
// conversion is the identity on the string: Role(routeKey.Role). agentprofile does NOT mint a
// second role vocabulary (agentsession.md:473-480, FROZEN). agentprofile does not import
// agentsession — the two would be a needless dependency for a string — and the invariant is
// carried by a conformance case in agentprofiletest instead (§8 I7).
type Role string

// Target names exactly one render. Comparable, loggable, usable as a map key (the secrets.Reference
// discipline). Repository is the canonical "owner/name" of the git repository the render lands in.
type Target struct {
	Repository string
	Role       Role
	Harness    Harness
}

// Module is one addressable body of instruction content. Name+Version ARE RuleRef/SkillRef.
type Module struct {
	Name    string     // globally unique; == RuleRef.Name / SkillRef.Name
	Version string     // semver; == RuleRef.Version / SkillRef.Version
	EmitAs  string     // on-disk basename (rules/skills) or heading anchor (documents)
	Order   int        // the filename prefix AND the emission-order key (§3.4.3)
	Kind    ModuleKind // KindRule | KindSkill | KindDocument
	Body    []byte     // the content, already read; New does no I/O (§4.1)
}

// Resolved is the immutable IR one Target renders from. Every Renderer sees this and nothing else,
// so a renderer cannot reach the document, the filesystem, or the clock. Populated at construction
// and never mutated; safe for concurrent reads.
type Resolved struct {
	SchemaVersion  int
	ProfileVersion string
	Target         Target
	Modules        []Module // ALREADY in emission order (§3.4.3); a Renderer never re-sorts
}

// File is one emitted file. The shape is upstream agentcfg's (agentcfg-architecture.md:451-457),
// MINUS its Sensitive field — see §8 I5 for why that omission is deliberate.
type File struct {
	Path    string      // repository-relative, forward slashes, never absolute, never "..", never a symlink
	Content []byte
	Mode    fs.FileMode // v1 emits 0o644 and refuses anything else (§8 I6)
}

// FileSet is the complete emission for one Target. Files are sorted by Path in BYTE order.
type FileSet struct {
	Target Target
	Files  []File
}

// Digest content-addresses a rendered profile. "sha256:<64 lowercase hex>" (§7).
type Digest string

func (f FileSet) Digest() Digest

// Divergence is one drift finding. The shape is cictl's (internal/cirepo/drift.go:15-21), with one
// added Reason value — "extraneous" — for the reverse-sweep this contract requires (§6.4 guard G5).
type Divergence struct {
	Path   string // repository-relative
	Reason string // "missing" | "content differs" | "extraneous" | "not a regular file" | "wrong mode"
	Diff   string // line-level diff; present only when Reason == "content differs"
}

// Diagnostic reports something a Renderer could not express — a WARNING, never a silent drop. It
// is the upstream diag.Diagnostic role (agentcfg-architecture.md:443-446).
type Diagnostic struct {
	Target   Target
	Severity Severity // SeverityWarning | SeverityError
	Module   string   // the module name the diagnostic is about; "" when target-wide
	Message  string
}
```

**A role, defined.** 🔶 A `Role` is *the standing instruction context one agent loop runs under*. It
is not a person, not an authz principal (§2.3), and not a phase. Two roles differ exactly when the
set of modules they select differs; two roles that select the same modules are one role with two
names, and the schema validator rejects that at `New` time so the manifest cannot grow synonyms.

### 3.4 Composition and ordering

#### 3.4.1 Module names are globally unique — and that is FORCED, not chosen

`RuleRef struct{ Name, Version string }` is FROZEN and carries **no repository qualifier**
(`orchestrator.md:133-135`). If two repositories each had a module named `identity` with different
bodies, `RuleRef{"identity", "1.0.0"}` would resolve to two different things and the orchestrator
would be carrying an ambiguous ref. **Global uniqueness of `Module.Name` is therefore derived from a
frozen contract, not preferred.**

That is also why `EmitAs` exists and is separate from `Name`. Three repositories today each commit a
file called `00-identity.md` with different content (`libs`, `infrastructure`, `.devcontainer` —
measured in §3.1). They become three modules — `identity-libs`, `identity-infrastructure`,
`identity-devcontainer` — each with `emitAs: identity` and `order: 0`, so each still lands at
`.claude/rules/00-identity.md` in its own repository. The addressable identity is globally unique;
the on-disk name is not required to be.

#### 3.4.2 There is NO body-override operator — and that is the point

An overlay may only **add** a module or **remove** one. It may never merge, patch, or partially
replace a body.

- ✅ Removing a module no layer selected is an **error**, never a no-op. A typo that silently does
  nothing is a check that cannot fail.
- ✅ Adding a module a lower layer already selected is an **error**, never a silent de-duplication.
  A silent dedup makes the emitted order depend on which layer got there first, which a reader of
  the document cannot see.
- ✅ **No 3-way merge, ever.** A body merge is exactly the ADR-0026 §B.3 mechanism (§2.4), and it is
  what makes a drift gate impossible: a path that preserves local edits cannot fail on a diff.

🔶 **This is what makes precedence total, and it is the section's real content.** An ambiguous
precedence is a non-deterministic render. The cheapest way to make precedence total is to make it
*unnecessary*: with no override operator, "precedence" reduces to (a) a set resolution and (b) an
emission order, and both are total.

- **The set resolution is total because it is commutative.** Adds and removes across all four layers
  are collected, then applied; both failure modes above are hard errors, so no two orders of
  application can produce different sets. There is nothing left for a precedence chain to decide.
- **The emission order is total by §3.4.3.**

#### 3.4.3 The layers and the total emission order

Four layers, lowest to highest, and the layer index is part of the sort key:

| # | Layer | Selects |
|---|---|---|
| 0 | `base` | modules every role of every repository gets |
| 1 | `role` | modules the role's own block selects |
| 2 | `repository` | modules the repository overlay's `"*"` block adds/removes |
| 3 | `repositoryRole` | modules the repository overlay's per-role block adds/removes |

✅ **The emission order is the ascending lexicographic order of `(Layer, Order, Name)`.**

**Proof that it is total:** `Layer` is a closed enum over `{0,1,2,3}`. `Order` is an author-declared
`int`. `Name` is globally unique across the entire document (§3.4.1), so no two distinct modules can
share all three components; and a module appears at most once in the resolved set (§3.4.2 forbids
duplicates). The key is therefore injective over the resolved set, which makes the order total. No
tie-break of last resort is needed, and none is defined — an undefined tie-break that is never
reached is dead code that a later reader will trust.

**The filename prefix is `Order`, zero-padded to two digits**, so today's real numbering survives
the render exactly: `00-identity.md`, `10-interface-design.md`, `11-naming.md`, `12-error-handling`,
`20-library-pipeline`, `21-test-taxonomy`, `22-harness-versions`, `24-typescript-pipeline`. A
renderer that renumbered `00,01,02,…` would rewrite every filename in the estate on its first run,
which is a diff nobody asked for and a review nobody can read.

**One number, not two.** `Order` is both the emission key and the filename prefix on purpose. Two
numbers would be two sources of truth for one ordering.

### 3.5 Versioning

- ✅ `schemaVersion` is the **schema's** version, an integer, bumped only by a change to the shape.
  E2 requires it: *"No artifact without a schema: every phase input/output validates against a
  versioned schema before acceptance"* (`docs/architecture/README.md` §5).
- ✅ `profileVersion` is the **document's** semver. It is stamped into the banner of every rendered
  file, so a rendered file names the document version it came from and a reviewer never has to guess.
- ✅ Each `Module` carries its own semver, because `RuleRef`/`SkillRef` carry one (§3.4.1).
- 🔶 **Bumping the schema is a contract revision** (ADR-0016 §1) once this contract is frozen, and
  re-recording `libs/go/agentprofile/.apibaseline` goes with it — the cardinal sin otherwise (10 §9).

### 3.6 The emitted surface, per harness

| Harness | v1 emits | State today |
|---|---|---|
| `claude` | `CLAUDE.md` · `.claude/rules/NN-<emitAs>.md` · `.claude/skills/<emitAs>/SKILL.md` · `.claude/settings.json` | ✅ a real target — the §3.1 corpus |
| `omp` | — | ⚠️ **no committed target exists.** `NewOMPRenderer` is registered and returns a NOT-IMPLEMENTED `*RenderError` (`errors.KindInternal`) naming the harness. It never returns an empty `FileSet`. |
| `codex` | — | ⚠️ same, with the same loud failure |

🔶 **v1 emits declarative files only.** No hook script, no slash-command script, no `Makefile`. Two
reasons, both concrete:

1. A renderer that emits executable shell is a code generator, and `git-process.md:323` §14 row 13
   records that **NOTHING gates `.githooks/` today** — *"`.ci/ctl.sh` shellchecks `ctl.sh` files
   only, so a hook can regress silently."* Emitting generated shell onto an ungated surface widens
   a known hole.
2. The one hook corpus in the estate is *instance* logic, not instruction content: `project-go`'s
   four hooks call `golangci-lint`, `hnslint` and the phase gate. Rendering them from a matrix would
   buy nothing and would put executable code behind a byte-equality gate that cannot read it.

🧩 **`AGENTS.md` and the import stub — decided here rather than left implicit.**
`portable-agent-config-2026-06.md:792` and `:922` record that Claude Code does not auto-read
`AGENTS.md`, so upstream's compiler *"must emit a `CLAUDE.md` containing `@AGENTS.md` (or
symlink)"*. **`agentprofile` does not do that.** For the claude target it emits a **full**
`CLAUDE.md` from the `documents` modules; if a future omp or codex target chooses `AGENTS.md`, it is
emitted from **the same resolved modules**, not by making one file import the other. Reason: an
import stub creates a second read path whose content is not covered by the digest of the file that
imports it (§7), and a symlink is refused outright by §6.4 guard G3. Two files, one source, both
digested.

## 4. Construction (the spine) and the ports

⚠️ **Read state, stated exactly.** At the time this section was written,
`/Users/mateo/code/.worktrees/libs-agentprofile/go/agentprofile/` **did not exist** — `ls` on the
parent lists 16 library directories and no `agentprofile`, and `find` on the path errors with "No
such file or directory". So §4 is the **proposed** surface the libs lane builds to, not a
transcription of code that exists. When the skeleton lands, this section is diffed against it and
amended to match the code, exactly as `codeinsight.md`'s freeze header records was done there.

### 4.1 The spine

```go
func New(configuration Config, dependencies Deps) (*Profile, error)
```

✅ `New` is **PURE** (10 §9): no I/O, no clock read, no environment read, no filesystem walk, no
global. It parses `Config.Document`, validates every invariant of §3, builds the immutable module
set, and returns a typed `*ConfigError` (`errors.KindInvalid`) on a violation so the composition
root fails fast and loud. Parsing bytes that were handed to it is pure; reading the file is the
caller's job.

`Config` and `Deps` are the exact required type names. ✅ `libs/.claude/rules/11-naming.md:54-59`,
under the heading *"The two spine types are pinned: `Config` and `Deps`"*, states it and is
stronger than a permission: *"Its two parameter **types** ARE named `Config` and `Deps`. This is
**required**, not merely permitted: `Configuration` and `Dependencies` are rejected as full-spelled
spine outliers, and `hnslint` fails a library that declares them."*

> ⚠️ **Corrected.** An earlier revision of this line quoted *"`Config` or `Deps` is fine; a package
> or directory named `config`/`deps` is not"* and attributed it to `:52`. That sentence exists in a
> SUPERSEDED revision of the rule — it is in the stale eden primary checkout, not in the version
> pinned by this repository (`8683feab1`), where line 52 now holds different text and the pinned
> spine-types section replaced it. The substance was right and the citation was false, which is the
> worse of the two failures: a reader who followed it would have found a rule that no longer says
> that. Verified by `grep` against the pinned submodule copy.
`Configuration`/`Dependencies` as type names fail that rule; the *parameter* names stay
`configuration` and `dependencies` per the 10 §4 spine.

```go
type Config struct {
	Document   []byte // the authored profile document, already read by the caller
	BodyFS     fs.FS  // the module bodies, already opened by the caller; New reads via fs.FS at
	                  // construction only, which is deterministic and injectable (10 §4)
	Repository string // which repository's overlay this instance resolves; "" is a ConfigError
}

type Deps struct {
	Renderers []Renderer // one per Harness named in the document; a gap is a New-time ConfigError
	Tree      Tree       // the READ-ONLY view of the committed files; required by Check
}
```

✅ **There is no `Clock` port, and its absence is the determinism guarantee made structural.** You
cannot read a clock you were not given. This is the deliberate inverse of `agentruntime`, whose
§2 names `Clock` *"the sidecar's ONLY time source"* — there, time is the product; here, time is the
contaminant.

### 4.2 The methods

```go
// Render produces the complete emission for one Target. Deterministic (§5).
func (p *Profile) Render(ctx context.Context, target Target) (FileSet, []Diagnostic, error)

// RenderAll renders every (role, harness) pair the resolved repository declares. It returns a
// SORTED SLICE, never a map — a map in the API would put Go's undefined iteration order on the
// determinism path (§5).
func (p *Profile) RenderAll(ctx context.Context) ([]FileSet, []Diagnostic, error)

// Check re-renders in memory and compares against the committed Tree. It NEVER writes. An empty
// result means the committed files are exactly what the profile produces (§6).
func (p *Profile) Check(ctx context.Context) ([]Divergence, error)

// Digest content-addresses one Target's rendered profile (§7).
func (p *Profile) Digest(ctx context.Context, target Target) (Digest, error)
```

`*Profile` is the concrete return type; `agentprofile.Profile` reads at a call site the way
`agentruntime.Runtime` and `codeinsight.Analyzer` do. Accept interfaces, return concrete (10 §9,
`ireturn`).

### 4.3 The ports (consumer-defined, ≤5 methods — 10 §9, `interfacebloat`)

```go
// Renderer is the SHAPE OF THE NEED for one harness: turn an immutable Resolved into that
// harness's native files. It is upstream agentcfg's proven Compile seam
// (agentcfg-architecture.md:437-449) with the IR narrowed to one Target. A Renderer sees Resolved
// and nothing else — no document, no filesystem, no clock — which is what makes purity checkable
// rather than promised.
type Renderer interface {
	Harness() Harness
	Render(ctx context.Context, resolved *Resolved) (FileSet, []Diagnostic, error)
}

// Tree is the READ-ONLY view of the committed files the drift check compares against. It is
// read-only ON PURPOSE and this is the single most load-bearing line of the port set: a gate that
// can repair its own expectation cannot fail. eden's own .ci/ctl.sh:461-463 states the rule for
// its roster: "It deliberately does NOT run inside graph-guard. A gate that repairs its own
// expectation cannot fail: it would rewrite the roster to match whatever the graph had become and
// report OK, which is the defect this whole file exists to make impossible."
type Tree interface {
	// Stat reports the entry at path WITHOUT following a symlink (an Lstat, never a Stat).
	Stat(ctx context.Context, path string) (Entry, error)
	// ReadFile reads a regular file. It REFUSES a symlink with errors.KindInvalid.
	ReadFile(ctx context.Context, path string) ([]byte, error)
	// List returns every entry under prefix, sorted in BYTE order, symlinks not followed.
	List(ctx context.Context, prefix string) ([]Entry, error)
}

type Entry struct {
	Path string
	Mode fs.FileMode // carries fs.ModeSymlink when the entry is a symlink, because Stat is an Lstat
	Size int64
}
```

Two methods and three methods; both inside the ≤5 ceiling with room, and neither is a mirror of an
underlying API. There is deliberately **no `Write` anywhere in the port set** — writing the render
to disk is the CLI's job in the composition root, so the library that checks and the code that
writes are not the same code.

### 4.4 The conformance suite and what it may import

`agentprofiletest` ships the public fakes and the adapter≡fake conformance suite
(`contracts/testing.md`, the 10 §4 obligation). ⚠️ **What it may import is narrower than a Go author
expects, and it shapes the suite.** `libs/.golangci.yml:213-229` defines a second `depguard` rule, `test-taxonomy`, scoped
to `$test`, whose allow-list is `$gostd`, `github.com/gophersys/libs/go`, `go.uber.org/goleak` and
`pgregory.net/rapid` — annotated *"The set is closed and annotated — not a wholesale opening: only
the eight-dimension mechanisms are listed."*

So: **there is no assertion library.** Every case is `if got != want { t.Errorf(...) }` in the
estate's existing style — which is what `deploy/servicespec/render_test.go` and
`cictl/cmd/cictl/run_test.go` already do, so the golden and drift lanes have working models to copy
rather than a gap to fill. The fakes are:

- `agentprofiletest.MemoryTree` — an in-memory `Tree` that can be seeded with a symlink entry and an
  empty file, so the §6.4 guards G3 and G4 are exercised rather than asserted.
- `agentprofiletest.RecordingRenderer` — a `Renderer` that records the `*Resolved` it was handed, so
  the purity claim of §4.3 is checked by observation (it never sees a document, a path, or a clock)
  instead of by comment.

## 5. The determinism guarantee

✅ **The property, stated so it can be tested:** for a fixed `(Config, Target)`, `Render` returns a
`FileSet` whose serialization is **byte-identical** on every invocation, in every process, on every
machine, under every locale, forever.

The estate already writes this down in two places, and this contract adopts the same words rather
than inventing new ones. `cictl` `internal/workflow/workflow.go:6-10`:

> *"Determinism is load-bearing: the same contract must render byte-identical YAML every time, so
> the renderer iterates in a fixed order and never touches a map's undefined iteration order or a
> clock."*

`.devcontainer` `_ctl/generate.sh:44-53`:

> *"Same manifest, same output, byte for byte: the images are emitted in document order … and
> nothing reads the clock, the environment or the filesystem outside images.yaml and _ctl/lib.sh.
> Running it twice leaves an empty `git diff`, and that is the property to check after any edit
> here."*

**What determinism FORBIDS, concretely:**

| Forbidden | How the design forbids it |
|---|---|
| Go map iteration order | `Resolved.Modules` is a slice already in emission order; `RenderAll` returns a sorted slice, never a map; no exported type is a map |
| a clock read | there is no `Clock` port and no `time` import in the render path (§4.1) |
| an environment read | `New` is pure; the document and bodies arrive as `[]byte` / `fs.FS` |
| a filesystem walk order | the render never walks a directory to decide content; `Tree.List` (used only by `Check`) returns byte-sorted entries |
| a locale-dependent sort | every sort is a byte comparison. `.ci/ctl.sh` uses `LC_ALL=C sort` on **both** the write side (`:494`) and the read side (`:416`, `:422`) for exactly this reason; a Go `sort.Slice` on `string` is already byte order, and the invariant is that no `strings.Collate`-style comparison is ever introduced |
| a random iteration seed, a `sync.Map` range, a goroutine race on append | `RenderAll` may run renderers concurrently, but it assembles results into the sorted slice by index, never by completion order |

**What PROVES it** — three lanes of the ADR-0020 taxonomy, not one:

1. ✅ **Golden tests**, one per `(repository, role, harness)` target, whose goldens are the **real
   committed trees of §3.1**. This is the acceptance corpus: the render is correct when it
   reproduces what the estate committed by hand, byte for byte.
2. ✅ **A render-twice-compare property** (the `property` dimension, `rapid`): render N times over
   generated documents and assert every pair is byte-identical.
3. ✅ **A weaken-to-confirm**, because a property that cannot fail proves nothing. Introduce a `for
   … range` over a map in the renderer and prove the property test FAILS, then revert. This is
   `agentruntime.md` §7's discipline — *"Proven non-vacuous by a weaken-to-confirm"* — applied here.

## 6. The drift gate

### 6.1 The shape — copied from the estate, not invented

🔶 The contract adopts the **`generate` / `drift` verb pair** and the **in-memory re-render plus
`bytes.Equal`** comparison, with four working instances in this estate as precedent:

| Precedent | Path | What is adopted |
|---|---|---|
| `cictl` | `internal/cirepo/drift.go:29-66` | the verb pair; re-render in memory; `bytes.Equal`; `Divergence{Path, Reason, Diff}` with `Reason` ∈ `"missing"` / `"content differs"`; results sorted by path |
| eden | `.ci/ctl.sh:409-500` `graph-guard` + `graph-roster-update` | the anti-self-repair split; the zero-row refusal; `LC_ALL=C sort` on both sides |
| `.devcontainer` | `_ctl/generate.sh` + `.github/workflows/validate.yml:57-65` | the CI step that runs the generator and fails on a non-empty diff, with an actionable `::error::` message |
| `platformgateway` | `tools/openapi -mode emit \| -mode verify` (`main.go:13-39`), wired as the `openapi-no-drift` dimension of its own `phase-gate architecture` | the emit/verify mode pair on one binary, so the check and the generator can never disagree |

✅ **Why in-memory re-render beats `git diff --exit-code`.** cictl's form catches a **missing** file
and an **uncommitted hand edit**, and it needs no clean working tree. `.devcontainer`'s
`git diff --exit-code` form is the simpler one and it works, but it reports nothing when the file is
absent from the index and it is confounded by unrelated dirty state. This contract takes cictl's.

✅ **The ratified precedent for the whole pattern is RD-17** (`open-decisions.md:61`, resolved by
ADR-0023): the Go types are the AUTHORING SURFACE, `contract/openapi.yaml` is EMITTED, and
*"`verify-openapi` re-emits and fails the architecture gate on drift"* — *"Delivered … proven
end-to-end."* Authoring surface → emitted artifact → `verify-*` → fail on drift is a shape this
estate has already shipped. `agentprofile` is that shape applied to instruction files.

### 6.2 The banner every rendered file carries

Modelled on `cictl`'s (`internal/workflow/workflow.go:35`), in each harness's comment syntax:

```
<!-- GENERATED by agentprofile from agentprofile.yaml (profileVersion 0.1.0) — DO NOT EDIT. -->
<!-- Re-render with `agentprofile render`; the `agentprofile drift` gate fails on any hand-edit. -->
```

The banner names the **profileVersion**, so a reviewer reading a rendered file in a submodule knows
which document produced it without resolving a pointer.

### 6.3 Semantics, exit codes, and the message a developer sees

- `agentprofile render` writes the emission to disk. `agentprofile drift` re-renders in memory and
  compares. **One binary, two modes** — the `platformgateway` `-mode emit | -mode verify` shape —
  so the generator and the check can never disagree about what "correct" means.
- ✅ **Exit codes follow cictl's, which are already the estate's convention**
  (`cmd/cictl/run.go:19`): **0** clean · **1** gate failure (invalid document, drift,
  non-conformance) · **2** usage error. Proven in cictl's own round-trip test
  (`cmd/cictl/run_test.go:98-128`): drift after generate must be 0; drift after a hand-edit must be 1.
- The message a developer sees names the fix, never just the fact:

```
agentprofile drift: 2 divergences

  .claude/rules/11-naming.md        content differs
      - a hand edit is present on disk that the profile does not produce
      + edit agentprofile.yaml (module `naming`, version 1.0.0) and re-render
  .claude/rules/24-typescript-pipeline.md   missing
      + the profile selects module `typescript-pipeline` for role `implementer`

fix: bash ./ctl.sh agentprofile render   (never hand-edit a generated file)
```

### 6.4 The anti-false-green guards — each with its precedent

A drift gate that reports OK when it checked nothing is worse than no gate, because it is believed.
Six guards, and each names the instance that earned it.

- **G1 — an emission of ZERO files is a FAILURE, never a pass.** Precedent: `.ci/ctl.sh:418` refuses
  a zero-row roster — *"the roster holds ZERO rows — it would match any graph at all"*. A `FileSet`
  with no files matches any tree at all.
- **G2 — a per-target minimum-count floor, declared in the document.** Precedent:
  `deploy/servicespec/render_test.go:244` `TestCatalogRostersFiveServices` — *"A silent add/drop — a
  service that stops rendering, or a stray one that starts — fails here before it ships."* The floor
  turns a silent shrink into a red gate.
- **G3 — a symlink at a rendered path is REFUSED, never followed.** Precedents: upstream
  `FileSet.WriteAll` already *"Symlinks are rejected"* (`agentcfg-architecture.md:468`); and the
  `.devcontainer` twin check uses `cmp`, which **follows** a symlink — so a symlink at a checked path
  makes a `cmp` pass prove nothing. `Tree.Stat` is an Lstat and `Tree.ReadFile` refuses a symlink
  (§4.3).
- **G4 — an EMPTY rendered file is REFUSED at render time.** Two empty twins compare equal and prove
  nothing. A module whose body is empty is a `New`-time `ConfigError`, so the failure lands on the
  author, not on the gate.
- **G5 — an EXTRANEOUS file under a render root is a `Divergence`.** ⚠️ **This is an addition to the
  cited precedent, not a copy of it, and it is stated as an addition.** cictl's `Drift` iterates the
  *render's* targets only (`internal/cirepo/drift.go:34-45`), so a stale file the render no longer
  produces is invisible to it. `agentprofile drift` runs the **reverse sweep** via `Tree.List` and
  reports `Reason: "extraneous"`. Without it, deleting a module leaves its rendered file on disk
  forever and every check stays green.
- **G6 — an unimplemented harness fails LOUDLY.** `omp` and `codex` have no committed target
  (§3.1), and their renderers return a NOT-IMPLEMENTED error naming the harness rather than an empty
  `FileSet`. G1 would catch it anyway; G6 makes the message name the cause. **A silent empty
  emission is the failure mode this whole contract exists to prevent.**

And the structural guard that is not a check at all: **G0 — the gate cannot repair its own
expectation**, because `Tree` has no write method (§4.3). `.ci/ctl.sh:461-463` is the estate's own
statement of why.

### 6.5 The gate must be PROVEN SELECTED — this is a requirement, not a footnote

⚠️ **A well-written drift gate that no lane runs is a green check that verifies nothing, and this
estate has one right now.** `deploy/servicespec/render_test.go:214` is
`TestCommittedManifestsMatchCatalog` — *"the DRIFT GATE between the typed Catalog and the COMMITTED
generated manifests … A
catalog/renderer change whose regen was forgotten — or a hand-edit of a generated file — fails HERE
instead of shipping stale manifests."* It is a good gate. **Measured here: no eden CI lane selects
it.** `find deploy -name project.json` returns nothing, and `.ci/graph-roster.txt` holds 60 rows,
none of which is `deploy`, so `nx affected -t test` never reaches it.

✅ **Therefore this contract requires evidence of SELECTION, not evidence of authorship.** The drift
gate is satisfied only when a **named lane** is shown to run it, with the run named: the job, the
verb it invoked, and a log line proving the check executed. `git-process.md` §5 condition 1 already
says the same thing for merges — *"Name the gate that RAN. An affected gate that selects no task is
a NO-OP and is not evidence about content"*. A gate written and never selected is that no-op
wearing a test's name.

⚠️ **And the deeper lesson from `.devcontainer`, which is about the render boundary rather than the
check.** `_ctl/generate.sh:20-28` records that a twin `cmp` proved two copies agreed while saying
**nothing** about internal consistency inside one copy: five hand-written jobs drifted from each
other twice, including commit `d9089b2`, *"and NOTHING caught drift between the 5 jobs"*. The fix
was **to raise the render boundary**, not to add a second check — *"A job that is a template applied
to a manifest entry cannot diverge from its siblings, because there is only 1 of it."* That is the
argument for a schema rather than a linter: `agentprofile` exists so that eight rule files in four
repositories cannot diverge from each other, because there is only one of each module.

### 6.6 What this gate does NOT prove

⚠️ Stated plainly, because §12 of the git process is this contract's load-bearing WHY and it must
not be overstated.

`git-process.md:257-273` rules that a Claude launched in CI sees only the checked-out repository, so
*"the repository's own `CLAUDE.md` and `.claude/` ARE the CI profile"*, and it records as
**ASSUMED, not yet measured**, that each repository's committed instrumentation is complete enough
to stand alone as that profile. A schema plus a drift gate turns half of that assumption into
something mechanical: **it makes the committed instrumentation a known, reviewable function of one
document**, so "what is the profile of repository X" stops being an archaeology question.

It does **not** prove:

- that a CI agent **loaded** the profile. That is a different gate with a different owner —
  `git-process.md:322` §14 row 10, *"CI instrumentation probe … echo the loaded profile into the job
  summary; FAIL when it is absent"*, owner `cictl`. §3.1's measurement — zero `plugin install` in any
  CI configuration — is exactly the kind of finding that probe exists to settle, and this gate cannot
  settle it.
- that the profile is **sufficient**. A repository can hold a complete, drift-free render of a
  profile that says the wrong thing. Byte equality is not adequacy.
- that a rendered rule is **obeyed**. `10-library-system.md:284` states the split and it holds here:
  *"Knowledge ≠ enforcement … `.claude` knowledge *guides* authoring; deterministic linters +
  breaking-change gates *enforce*."*

✅ **`git-process.md:318` §14 row 6 names this exact pipeline as unbuilt work**:
`| 6 | contract gates: branch vocabulary, commit format | cictl | struct field + emit + generator + drift |`
— *struct field + emit + generator + drift* is the same four-part shape, for a different subject,
already queued and already owned. This contract does not duplicate row 6; it is row 6's sibling for
instruction files, and §10 Q2 asks whether the two share a home.

## 7. Addressing a rendered profile — artifact + digest

### 7.1 The digest

```
Digest = "sha256:" + hex(SHA-256(canonical(FileSet)))
```

✅ **The canonical serialization must be specified or the digest is not stable.** It is the
concatenation, over the files sorted by `Path` in **byte** order, of:

```
path || 0x00 || decimal(mode) || 0x00 || decimal(len(content)) || 0x00 || content
```

🔶 **Why length-prefixed and NUL-separated:** the encoding must be **injective**, or two different
`FileSet`s can concatenate to the same bytes and collide without a hash weakness being involved.
Length-prefixing the content and NUL-separating the fields makes the parse unambiguous, which is the
property that matters. `Target` is deliberately **not** in the digest input: the digest addresses
the *bytes of a rendered profile*, so two targets that render identically are the same artifact, and
a pod that mounts a digest gets content, not provenance. Provenance rides beside it in the field
that names the digest.

### 7.2 What `profileRef` needs — and what does not exist yet

⚠️ **`profileRef` is a field on a CRD that does not exist.** Measured: there is **no AgentPod CRD
and no Eden-owned CRD at all**; the agent pod is plain YAML at
`infrastructure/apps/eden/58-agent-runtime.yaml`, Argo-reconciled. The sibling lane is drafting
`agentpod`, and at the time this section was written
`/Users/mateo/code/.worktrees/eden-fleet-contracts/docs/architecture/contracts/agentpod.md`
**did not exist** — only `fleetenvelope.md` had landed there. So `profileRef` is a **stated
dependency on a document not yet written**, and this section specifies only what `agentprofile` must
GUARANTEE for it to work.

The one thing the sibling lane HAS written, and this contract cites it rather than reinterpreting
it, is `fleetenvelope.md:63`: *"**Pod lifecycle, the CRD, the role, the profile** — `agentpod` owns
those. The header carries the `AgentID` the controller minted; it does not describe the pod."*
Read precisely: `agentpod` owns the pod's **reference** to a profile and the pod's **role field**.
This contract owns the profile's **content, render and digest**. The two meet on five guarantees:

- **G-A — a stable digest over a canonical serialization.** §7.1. Two renders of the same document
  for the same target on any machine produce the same digest.
- **G-B — immutability at a digest.** A rendered profile at digest `D` never changes. "Changing it"
  produces a different digest; there is no mutation path, because the artifact is content-addressed.
- **G-C — the digest covers the FULL emitted tree for one target.** A pod that mounts digest `D`
  cannot receive a partial profile: a missing file is a different digest.
- **G-D — the digest is non-secret and loggable.** It may appear in a `fleetenvelope` header, a
  span attribute, a status field and a log line. This is only true because §8 I5 forbids a secret in
  any emitted file; a digest over content that could hold a credential would be a secret-adjacent
  value and could not be logged.
- **G-E — one target, one digest.** `(profileVersion, repository, role, harness)` determines the
  digest. A pod that names those four gets exactly one artifact.

🧩 **Where the artifact lives is NOT decided here.** The bytes are already in git; whether a pod
reads them from a checkout, from an OCI artifact, or from object storage is a deployment decision
that belongs to `agentpod` and to OD-13. This contract guarantees the digest is the same in all
three cases, which is what lets that decision be made later without reopening this one.

### 7.3 The cross-repository honesty

⚠️ `eden`, `libs`, `infrastructure` and `.devcontainer` are **four separate git repositories**, and
three of them are submodules of the first (`CLAUDE.md` "Workspace facts"). So a digest computed in
eden over a render destined for `libs` is a **claim about another repository's future state**, not a
fact about its current one. `git-process.md` §8 governs the seam: *"A pointer bump is ALWAYS its own
PR"*, and *"'Merged' is not 'in effect' until the pointer moves."* §10 Q3 puts the consequence to
Mateo rather than deciding it here.

## 8. Invariants (load-bearing)

- **I1 — one home for rendering, cited from two call sites.** Under option A, `agentconfiguration`
  resolves a `SkillRef`/`RuleRef` by naming an `agentprofile` `Target` and calling this renderer.
  Never two renderers. The import is one-directional: `agentconfiguration` → `agentprofile`.
- **I2 — the gate cannot repair its own expectation.** `Tree` is read-only by construction; there is
  no write method anywhere in the port set (§4.3). `.ci/ctl.sh:461-463`.
- **I3 — same input, byte-identical output.** §5, proven by a golden corpus, a render-twice
  property, and a weaken-to-confirm that shows the property can fail.
- **I4 — zero emission is a failure.** §6.4 G1.
- **I5 — no secret value in any emitted file, and no `Sensitive` concept in the type set.** ⚠️ This
  is a **deliberate divergence from upstream**, which carries `File.Sensitive` implying mode 0600
  (`agentcfg-architecture.md:451-457`) because it may emit `~/.claude-code-router/config.json` with
  a key in it. `agentprofile` emits **committed** files only, and `CLAUDE.md` "Workspace facts"
  rules *"Never put a plaintext secret in git."* A `Sensitive` field on a type whose every value is
  committed to git is an invitation, so the field is omitted and its absence is an invariant. A
  credential reaches a harness through the `agentsession` credential seam, never through a file this
  library wrote. G-D in §7.2 depends on this.
- **I6 — every emitted file is mode `0o644`.** The gate REFUSES any other mode with
  `Reason: "wrong mode"`. `File.Mode` exists so a later executable target is an additive change
  rather than a shape change, and until then the only legal value is one.
- **I7 — one role vocabulary.** `agentprofile.Role` values are `agentsession.RouteKey.Role` values
  (`agentsession.md:473-480`, FROZEN). Carried by a conformance case in `agentprofiletest`, not by
  a comment.
- **I8 — a rendered path is render-owned, never 3-way merged.** A path is in the agentprofile render
  channel or in the ADR-0026 sync channel, never both (§2.4). Any future manifest that lists a path
  in both is a defect, and the drift gate is what surfaces it.
- **I9 — the gate is not satisfied until a named lane is proven to run it.** §6.5.
- **I10 — the schema is versioned and validated before acceptance** (E2, `docs/architecture/README.md`
  §5). `schemaVersion` is an integer on the document; `New` refuses an unknown value rather than
  guessing.
- ⚠️ **A note on E4.** `docs/architecture/README.md` §5 states E4 as *"Drift is detected, never
  silently absorbed (= P10/T7; checked per connector family, 05 §5)"* — its checking clause is
  **connector-scoped**. Render drift is not connector drift. Either E4's charter is widened, which
  is a Mateo act on an invariant, or this contract carries its own drift statement and does not cite
  E4 as its authority. **It carries its own**, and the widening is left unproposed rather than
  assumed.

## 9. Open forks

| # | Fork 🧩 | Options | Interim position |
|---|---|---|---|
| F1 | **The `Phase` axis** — `RouteKey` has `{Phase, Role}`; a role × harness matrix drops `Phase` (§2.3) | (a) key on `Role` alone, express phase as a phase-scoped module · (b) key on `{Phase, Role}` and render one tree per phase | (a) — a git checkout holds one file tree. Put to Mateo as Q4 |
| F2 | **Skill emission shape** | `.claude/skills/<name>/SKILL.md` (the personal-instrumentation convention and `project-go`'s) · a plugin `skills/` directory (`libs/plugins/project-go/skills/api-design/SKILL.md`) | emit the first; the plugin path is a `Renderer` option, not a schema field |
| F3 | **`settings.json` scope** | render it (ruling 1 names "settings") · leave it hand-authored | ⚠️ **no repository commits a `.claude/settings.json` today** — the only one in the estate is `libs/plugins/supervisor/template/.claude/settings.json`, which is a template body. So this renderer has **no golden**, and it is registered but emits only when the document declares a `settings` block |
| F4 | **The harness plugin model** — the one OD-7 item that now binds two libraries (§2.6) | follow WS2's ruling | interim: compile-time registration of renderers via `Deps.Renderers` — no `init()` registry, no global. It is the `go-plugin`-free option upstream's §20.4 also votes for, and it keeps `New` pure |
| F5 | **Where the rendered artifact lives for a pod** | git checkout · OCI artifact · object storage | not decided here; `agentpod` and OD-13 own it, and §7.2 G-A/G-B make all three equivalent |
| F6 | **Should the authoring surface be YAML after all?** (§3.2) | **(A) keep JSON** — no `.golangci.yml` change, no dependency, strict `DisallowUnknownFields()`, no anchor/alias/merge-key semantics to prove; but a hand-authored matrix is less pleasant and **JSON carries no comments**, so the *reasons* behind an ordering choice have nowhere to live in the document · **(B) YAML** — pleasant to author and comments survive, but it requires this contract to NAME the dependency (exactly the escape `libs/.golangci.yml:196-199` describes) plus an edit to a config every `libs` library obeys · **(C) YAML authored, JSON parsed** — a conversion step outside the library | **(A), and F6 rides the freeze.** (C) is rejected outright: it trades one problem for two committed files that can disagree, which is the drift this contract exists to remove. Between (A) and (B) the deciding fact is that a shared-config edit is a **process-adjacent change** and the comment loss is recoverable — the *reasons* belong in this contract and in each module's own body, not in the manifest that selects them |

## 10. THE FREEZE QUESTION

Five questions. Each names its options, gives a recommendation, and gives the reason. **None is
decided by an agent.** `.claude/rules/git-process.md` §5 lists *"a chart or contract PROMISE"* and
*"process changes (this file, `.claude/`, the cictl contract)"* among the gates Mateo *"gates
personally; no agent authority covers them"* — and this contract proposes to **render into
`.claude/`**, which lands squarely on the second of those. Under §13 rule 4, a gate counts as exercised only when
the record quotes his verbatim words and a timestamp; until then this document says **DRAFT** and
the libs `phase-gate architecture` stays red by design.

---

**Q1 — The `agentconfiguration` boundary.**

- **Option A — the seam (RECOMMENDED).** `agentprofile` owns authoring, composition, the
  deterministic render, the digest and the drift check, at commit-time. `agentconfiguration` keeps
  `RouteKey → (harness, model)`, auth per role, and spawn-time `AgentTemplate` resolution, at
  run-time. When it is built it CALLS this renderer. One home for rendering, two call sites.
  - `10-library-system.md:350` is **amended** to the two-row pair in §2.6.
  - `docs/architecture/README.md` §4 gains one cohesion row for `agentprofile`.
  - **OD-7 stays open and narrows**: three items stay wholly with `agentconfiguration`; the yaml
    v3-vs-v4 item never reaches `agentprofile` at all, because its document is JSON (§3.2); and only
    the **harness plugin model** becomes shared, ruled once for both (§9 F4 holds an interim
    position so nothing blocks).
  - **A supersession ADR is REQUIRED** (`docs/architecture/README.md:22-23`). Next free number is
    **0033** — 0030 is a silent gap and must not be reused. **Proposed here, not opened**: opening
    an ADR is Mateo's §5 gate.
- **Option B — the fold.** One library, `agentconfiguration`, two verbs. `10-library-system.md:350`
  stands unchanged, no ADR is needed, and this document is withdrawn with §3–§8 re-homed. OD-7
  becomes a blocker on the whole program, and the four parallel lanes wait for WS2.

> **Recommendation: A.** The deciding reason is the credential boundary, not the tidiness: a library
> that writes files into git and a library that resolves auth per role should not be one compilation
> unit. The scheduling benefit — four lanes start now instead of after WS2 — is real and is stated
> as secondary on purpose, because "it unblocks us" is not an architecture argument.

---

**Q2 — Where does the drift gate run?**

- **(a) A `libs` `phase-gate` dimension** — it runs where the library lives, in the ADR-0020 lanes.
- **(b) An eden `.ci/ctl.sh` verb** — it runs where the monorepo's gates run.
- **(c) Both, with a stated split (RECOMMENDED).** The `libs` phase-gate dimension proves the
  **library renders deterministically** (goldens, the render-twice property, the weaken-to-confirm);
  each repository's own gate proves its **committed tree matches its render**.

> **Recommendation: (c), and it is not gold-plating — it is forced by the repository topology.**
> `eden`, `libs`, `infrastructure` and `.devcontainer` are four separate git repositories. Eden's
> `.ci/ctl.sh` **cannot** fail a `libs` pull request, and a `libs` phase-gate cannot reach
> `infrastructure`. So the shape is **one verb, four invocations**: eden's `.ci/ctl.sh` gains it,
> `libs` gains a `phase-gate` dimension, and `infrastructure` and `.devcontainer` each gain a step
> in their existing `validate` workflows. Two facts to weigh with it: **eden has no
> `ci.contract.yaml`** (`git-process.md` §10 — *"One `ci.contract.yaml` exists (`libs`); eden has
> none"*, and §14 row 7), so cictl cannot generate it there; and **`hnslint`, `review` and
> `research-embedded` have zero workflows** (§7's table), so any repository outside the four has no
> gate to add it to.

---

**Q3 — Is committing rendered files into every repository accepted?**

The honest cost, stated before the options. A single logical profile change — say, one word in one
shared rule — becomes: up to **four content pull requests**, one per repository, plus up to **three
submodule pointer-bump pull requests**. `git-process.md` §8: *"A pointer bump is ALWAYS its own PR,
never inside a feature"* and *"'Merged' is not 'in effect' until the pointer moves."* And §8's
unattended clause bites: *"until it does, a pointer-bump PR is merged by a human or by a named
grant-holder — never unattended"*, because the cheap review tier does not exist (§14 row 3). The
cross-repository dispatch that would automate the fan-out is **§14 row 1, unbuilt** — *"needs a
cross-repo PAT (`GITHUB_TOKEN` cannot dispatch), sender step, `on: repository_dispatch`, bot
identity, commit-range extraction"*.

- **(a) Accept the fan-out now** — render into all four repositories from day one and pay seven PRs
  per shared change until row 1 lands.
- **(b) Render into eden only, permanently** — the submodules keep hand-authored instrumentation.
  This rejects the reach of ruling 1, since `libs` holds 8 of the estate's 15 committed rule files.
- **(c) Render into eden first, widen when the dispatch exists (RECOMMENDED)** — the schema and the
  document are estate-wide from day one and the *render* starts in eden, with `libs` second as soon
  as §14 row 1 or a lighter equivalent lands.

> **Recommendation: (c).** It is the only option that is honest about §14 row 1 being unbuilt while
> still putting the schema in place now. (a) buys reach at the cost of a seven-PR tax on every
> wording change, paid by a human because §8 forbids unattended pointer bumps. (b) is stable but
> gives up the estate-wide coherence that is the whole point. (c) costs one deliberate widening
> later and nothing today.

---

**Q4 — Does a render target key on `Role` alone, or on `{Phase, Role}`?**

- **(a) `Role` alone (RECOMMENDED)** — `Phase`, where it matters, is a phase-scoped module the
  harness loads on demand.
- **(b) `{Phase, Role}`** — one rendered tree per phase, matching `RouteKey`'s two axes exactly.

> **Recommendation: (a).** Not a preference — a property of the lifecycle. A git checkout holds one
> file tree, and a commit-time render's output **is** a checkout; (b) would need `.claude/rules/`
> to hold four mutually exclusive contents at the same paths. `RouteKey`'s `Phase` varies *within* a
> run, and a run selects among files that are all already on disk. If Mateo rules (b), §3.3's
> `Target` gains a `Phase` field and §7.2's G-E becomes a five-tuple — an additive change, which is
> why this question can be answered after Q1 without reopening it.

---

**Q5 — Is the authoring document JSON, or is the depguard gate opened for YAML?**

- **(a) JSON, `encoding/json` with `DisallowUnknownFields()` (RECOMMENDED)** — no dependency, no
  shared-config edit, an unknown key is a typed error, and no anchor/alias/merge-key semantics to
  prove deterministic.
- **(b) YAML** — pleasanter to author by hand and comments survive, but it requires this contract to
  NAME a YAML dependency and `libs/.golangci.yml` to be edited, which every library in `libs` obeys.
- **(c) YAML authored, JSON parsed** — rejected in §9 F6: two committed files that can disagree is
  the drift this contract exists to remove.

> **Recommendation: (a).** `libs/.golangci.yml:196-199` explicitly permits (b) — *"If a contract
> later names a specific dependency, add it to `allow` with a comment citing the contract"* — so
> this is a real choice and not a wall. It is asked rather than assumed because the escape is a
> change to a configuration shared by every `libs` library, and because the honest cost of (a) is
> that **JSON carries no comments**, so a reader of the manifest alone cannot see why a module sits
> at `order: 11`. The mitigation is that the reasons belong in this contract and in each module's
> own body, not in the manifest that selects them — but that is a mitigation, not an absence.

---

**Not asked here, deliberately.** The `agentruntime` contract revision that a task id would require
is `fleettelemetry`'s question, not this one. Whether E4's charter widens to cover render drift is
an invariant change and is left unproposed (§8). And the ADR that Q1 option A requires is
**proposed**, never opened.
