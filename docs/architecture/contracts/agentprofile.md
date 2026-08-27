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
> and this header says DRAFT until he rules. §0.2 states what that costs the CI lane, and §0.2 is
> not a footnote — it decides the merge ORDER of this whole program.
>
> Epistemic legend: ✅ ratified · 🔶 derived-but-settled · ⚠️ load-bearing assumption · 🧩 open fork.

## 0. The rulings this contract implements, and the gate that judges it

### 0.1 The authority, carried inline

⚠️ **This contract carries its own authority rather than citing a file that is deleted before
merge.** An earlier revision's only authority citation was `.dev/instrumentation-contracts.md`
"Authority" — this lane's own state file, which `.claude/rules/git-process.md` §5 condition 4
**deletes in the last commit before merge** (*"the `.dev/<slug>.md` is ARCHIVED then deleted …
**PROVE the removal**"*), and which §2.7 of this document says so itself. A contract whose
authority chain dangles after merge is the failure `git-process.md` §14 names in its own closing
lesson. The rulings are therefore reproduced here.

**Mateo, 2026-08-26**, AskUserQuestion decision prompt, interactive session `f9c810a8` (not an
orchestrator session). Two of four rulings reach this contract:

> 1. Instrumentation source of truth = **central schema + renderer** — one agentprofile schema
>    (role × harness matrix: claude/omp/codex) in eden; a renderer emits each harness's native
>    files (CLAUDE.md, .claude/rules, skills, settings; omp/codex equivalents).
> 2. **Commit-time rendering + drift gate** — rendered files are committed; CI fails on drift,
>    following the estate's existing generated-file pattern.

⚠️ **Those two paragraphs are the rulings AS RELAYED TO THIS LANE, in this lane's words. They are
NOT a transcript and are NOT presented as verbatim.** `git-process.md` §13 rule 4 reserves
"verbatim" for a quote carrying his exact words and a timestamp, and this lane does not hold the
transcript. The distinction is load-bearing rather than pedantic: the **freeze** in §10 is a §5
human gate, and a gate is EXERCISED only on a verbatim quote — so the freeze cannot be built on
the paraphrase above, no matter how faithful it is. Where this document needs his exact words, it
must get them from him.

Everything below is either a consequence of those two rulings, a citation, a measurement, or a
question put back to him in §10. Nothing below is a third ruling.

### 0.2 The gate this draft actually meets — and the merge order it forces

⚠️ **Corrected.** An earlier revision of this header said the expected failure was a red
`bash ./ctl.sh phase-gate architecture` for `libs/go/agentprofile`, driven by
`_gate_contract_frozen` at `libs/go/_ctl/lib.sh:1076-1090`, and instructed the reader not to edit
the header to make it green. Every part of that is now false. The function is at
**`libs/go/_ctl/lib.sh:1191-1222`** (`:1076` is inside `cmd_apidiff_record`), and — more
importantly — **eden `main` merged pull request #18 (`b4ff75c`) AFTER this branch was cut** (the
branch point is `bc84ea2`, pull request #14). That change moved the frozen-contract check out of
the library's own nightly lane and into eden's own workflow, for a reason its comment states:
libs' `_eden_monorepo_root` resolves to eden only when libs is a SUBMODULE, so in libs' standalone
CI the dimension *"could never pass"* and short-circuited three later phases with it.

✅ **What runs today**, read from `git show origin/main:.github/workflows/harness-conformance.yml`
(step *"Frozen-contract gate for the libraries whose contracts live here"*). For each
`docs/architecture/contracts/*.md` except `README.md`:

| the contract's state | what the step does |
|---|---|
| no matching `libs/go/<lib>/ctl.sh` | `continue` — not gated, not counted, not an error |
| `Status: Frozen` | runs `phase-gate architecture` in that library; `gated++` |
| DRAFT **and** listed in `DRAFT_REGISTER` | `::warning::REGISTERED DEBT`; `debt++` — the lane stays green |
| DRAFT **and not** listed | `::error::contract <lib> is DRAFT and not in DRAFT_REGISTER` → **`exit 1`** |
| a `Status:` line it cannot classify | `::error::` → `exit 1` |
| `gated == 0` at the end | fails — *"A gate that selected nothing is not evidence"* |

⚠️ **So a DRAFT contract that HAS a library does not produce a red architecture gate at all. It
produces an `exit 1` that never reaches `phase-gate`** — and because the glob is sorted and
`agentprofile.md` sorts FIRST, it exits **before gating any of the fifteen frozen contracts**. The
designed state for a draft-that-ships-code is a `DRAFT_REGISTER` row, which is a WARNING. That
register is **empty** (`DRAFT_REGISTER=""`), and the step's own comment calls adding a row a
process change: it *"MAY ONLY SHRINK"* and *"an entry needs the pending-decision citation"*.

✅ **Both directions were EXECUTED, and both results are facts, not predictions:**

- **post-pointer-bump** (the pinned `libs` moved to a commit carrying `go/agentprofile/ctl.sh`):
  `::error::contract agentprofile is DRAFT and not in DRAFT_REGISTER`, **rc=1**.
- **pre-bump control** (the pin as this branch carries it): `frozen-contract gate: 15 gated,
  0 registered-debt`, **rc=0**.

✅ **Merging this contract alone does NOT red `main`.** Measured at the pinned submodule commit
`8683feab1`: `go/agentprofile/ctl.sh` is **absent**, and so is `go/fleettelemetry/ctl.sh` — the
other draft contract in this same pull request. With no `ctl.sh`, the step `continue`s past both,
and the fifteen frozen contracts gate exactly as they do today.

🔶 **The consequence is a merge ORDER, and it is the one operational instruction this section
exists to give:**

```
contract merges  →  Mateo rules (§10)  →  library merges  →  submodule pointer bumps
```

**Landing the pointer bump before he rules reds the whole conformance lane** — not this contract's
own dimension, but every frozen contract behind it in the glob. There are exactly two escapes and
**both are his §5 gate, not an agent's**: freeze the contract, or add the `DRAFT_REGISTER` row
with its pending-decision citation. They are put to him as **§10 Q0**.

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
- **Pod lifecycle, the CRD, `metadata.uid`, `AgentID` minting.** ⚠️ **Corrected — the sibling
  document and the sibling's NAME both moved.** An earlier revision quoted `fleetenvelope.md:63`
  as *"Pod lifecycle, the CRD, the role, the profile — `agentpod` owns those"* and reasoned from
  the phrase "the profile". At the sibling worktree's head `70a979f` (the file's own last edit is
  `9fd66d9`), **`agentpod` appears zero times in `fleetenvelope.md`**, and the line is now
  `fleetenvelope.md:59`: *"**The CRD, the pod, the role, parentage, the legal child set** —
  `agentfleet.md`. The header carries the `AgentID` the controller minted; it does not describe
  the pod, and **it does not carry the tree**"*. Two things changed: the owner is `agentfleet.md`,
  and **"the profile" is no longer in the sentence**. `fleettelemetry.md` — the other contract in
  this same pull request — records the same correction at its `:67-68`. §7.2 states the seam as it
  now stands.
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
⚠️ **Corrected citation:** the sentence is at `orchestrator.md:130-131`, not `:99-100` — `:99-100`
are the `Skills` and `Rules` struct FIELDS of `AgentTemplate`, which is a different claim. The
comment is satisfied unchanged: the orchestrator still *"carries them; it does not parse, fetch,
or execute their contents."* Only the identity of the resolver is disambiguated, and
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

✅ **The name was free, and it is now this lane's.** `agentprofile`, `profileRef` and
`AgentProfile` had **no prior occupant** in eden; every tracked occurrence today belongs to this
branch — this file, the two README index rows it adds, and `.dev/instrumentation-contracts.md`,
which is this lane's own state file and is deleted before merge (`git-process.md` §5 condition 4;
that dangle is why §0.1 carries the authority inline). ⚠️ **Corrected on one word:** the slug no
longer names a *future* library. `libs/go/agentprofile` **EXISTS** — it landed at `436d7f7` on
branch `feat/agentprofile` with a recorded `.apibaseline` — and §4 is now a diff against it rather
than a proposal to it. It is one lowercase HNS-1 word (10 §5).

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
| `eden` | `CLAUDE.md` (root, **172** lines — ⚠️ corrected from 173) · `.claude/agents/merge-agent.md` · `.claude/rules/git-process.md` | 3 |
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

⚠️ **The document below is the SPECIFIED schema, and the built library parses a DIFFERENT one.**
`libs/go/agentprofile` at `436d7f7` parses `{schemaVersion, defaults, roles, overlays}`
(`document.go:20-40`) — three same-shaped layers, each carrying `instruction`, `rules` and
`skills` — with **no `profileVersion`, no `harnesses` list, no `modules` block, no `repositories`
block, no `emitAs`, no `order`, no `minimumFiles`, and no module `version`.** §4.4 is the full
divergence table and states which side wins on each row. Nothing here is quietly retracted: what
the code does not carry is labelled *specified, not yet built*, and it is labelled in the one
place a reader looks for it.

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

⚠️ **Read §4.4 with this section.** The types below are reconciled against the surface built at
`436d7f7`; every member that is specified here and **not built there** is marked `[NOT BUILT]` on
its own line, and §4.4 gives the ruling that kept it.

```go
// Harness is the closed target set.
//
// ⚠️ CORRECTED — the values are NOT the ADR-0021 pin NAMES, and the claude value is not "claude".
// An earlier revision said "The values are the ADR-0021 pin names" and then declared
// HarnessClaude = "claude". Both halves were wrong. The pin NAME in harnesses/versions.env is
// CLAUDE_CODE_VERSION (with OMP_VERSION and CODEX_VERSION), which is a shell key, not a harness
// token. What the values actually are is the STABLE HARNESS ID: upstream's own
// (agentcfg-architecture.md:440, "Name is the stable ID — \"claude-code\", \"aider\", \"kilo\"",
// and :501, `func (h *Harness) Name() string { return "claude-code" }`), which is also the token
// agentsession's adapter key carries. The pin manifest is still what BOUNDS the set — a harness
// with no pin may not be named here — but it supplies the bound, not the spelling.
type Harness string

const (
	HarnessClaudeCode Harness = "claude-code" // built; the only harness with a real renderer
	HarnessOMP        Harness = "omp"
	HarnessCodex      Harness = "codex"
)

// Role is agentsession.RouteKey.Role, in a distinct Go type for compile-time safety. The
// conversion is the identity on the string: Role(routeKey.Role). agentprofile does NOT mint a
// second role vocabulary (agentsession.md:473-480, FROZEN). agentprofile does not import
// agentsession — the two would be a needless dependency for a string — and the invariant is
// carried by a conformance case in agentprofiletest instead (§8 I7).
type Role string

// Target names exactly one render. Comparable, loggable, usable as a map key (the secrets.Reference
// discipline).
//
// ⚠️ CORRECTED — the repository is NOT a Target field in the built library. An earlier revision
// declared Target{Repository, Role, Harness}; the code carries the repository on Config instead
// (compiler.go:17-24, `Repository names the per-repository overlay to apply`), so one Compiler is
// bound to one repository and its Targets are the cells of that repository's matrix. The code
// wins on shape (§4.4). The consequence is stated where it bites: §7.2 G-E.
type Target struct {
	Role    Role
	Harness Harness
}

// String is "<role>/<harness>", the same order the emission path uses.
func (t Target) String() string

// Fragment is one addressable body of instruction content. Name+Version ARE RuleRef/SkillRef.
//
// ⚠️ CORRECTED — this type was specified as `Module{Name, Version, EmitAs, Order, Kind, Body}`.
// The built type is `Fragment{Name, Body}` (agentprofile.go:224-230), and the NAME `Fragment` is
// the code's (§4.4: the code wins on names). Kind is gone for a structural reason rather than a
// preference: the document carries rules and skills as two separate keyed lists, so the kind is
// the list a fragment sits in and a Kind field would be a second, desynchronizable spelling of it.
type Fragment struct {
	Name string // globally unique; == RuleRef.Name / SkillRef.Name (§3.4.1). An HNS-1 slug.
	Body string // the content, already read; New does no I/O (§4.1)

	// [NOT BUILT at 436d7f7 — specified, and kept deliberately. §4.4 gives the ruling.]
	Version string // semver; == RuleRef.Version / SkillRef.Version
	EmitAs  string // on-disk basename (rules/skills) or heading anchor (documents) — §3.4.1
	Order   int    // the filename prefix AND the emission-order key — §3.4.3, §3.6
}

// Resolved is the immutable IR one Target renders from. Every Renderer sees this and nothing else,
// so a renderer cannot reach the document, the filesystem, or the clock. Populated at construction
// and never mutated; safe for concurrent reads.
//
// ⚠️ CORRECTED — the built Resolved (agentprofile.go:236-250) carries no ProfileVersion and no
// single `Modules` slice. It carries Repository, a scalar Instruction, and TWO sorted fragment
// slices. §6.2's banner spec was rewritten to match what this struct can actually supply.
type Resolved struct {
	SchemaVersion int
	Target        Target
	Repository    string     // the overlay that was applied; "" is the base matrix
	Instruction   string     // the composed top-level instruction body (the CLAUDE.md body)
	Rules         []Fragment // composed, precedence applied, sorted by Name
	Skills        []Fragment // composed, precedence applied, sorted by Name

	// [NOT BUILT — specified. Every emitted banner would name it; see §3.5 and §6.2.]
	ProfileVersion string
}

// File is one emitted file. The shape is upstream agentcfg's (agentcfg-architecture.md:451-457),
// MINUS its Sensitive field — see §8 I5 for why that omission is deliberate.
type File struct {
	Path    string      // repository-relative, forward slashes, never absolute, never "..", never a symlink
	Content []byte
	Mode    fs.FileMode // v1 emits 0o644 and refuses anything else (§8 I6)
}

// FileSet is the complete emission for one Target.
//
// ⚠️ CORRECTED — the built type is a bare slice, `type FileSet []File` (agentprofile.go:128), not
// a struct carrying its Target. The code wins on shape. Byte-order sorting is NOT a property of
// this type: Compiler.Render sorts before returning (compiler.go:122) and nothing else does.
// §7.1 states exactly what that costs the digest.
type FileSet []File

// Digest content-addresses a rendered profile: "sha256:<64 lowercase hex>" (§7.1).
//
// ⚠️ CORRECTED — there is no named `Digest` type. The built method returns a plain string
// (agentprofile.go:134). The code wins on names; a one-field string wrapper nothing constructs
// would be exported surface with no reader, which is the class §4.4 deletes elsewhere.
func (s FileSet) Digest() string

// Divergence is one drift finding. The shape is cictl's (internal/cirepo/drift.go:15-21).
type Divergence struct {
	Path   string           // repository-relative
	Reason DivergenceReason // a typed enum in the built code, not a bare string
	Diff   string           // a deterministic summary: both digests and both lengths, then the remedy
}

// DivergenceReason classifies why a rendered file and the committed tree disagree.
type DivergenceReason string

const (
	DivergenceMissing        DivergenceReason = "missing"
	DivergenceContentDiffers DivergenceReason = "content-differs" // hyphen, not a space

	// [NOT BUILT — REQUIRED by §6.4. Each needs a port method the built Tree lacks:
	//  extraneous       — needs Tree.List (guard G5, the reverse sweep)
	//  not-a-regular-file — needs Tree.Stat as an Lstat (guard G3, the symlink refusal)
	//  wrong-mode       — needs Tree.Stat to report a mode (invariant I6)]
	DivergenceExtraneous     DivergenceReason = "extraneous"
	DivergenceNotRegularFile DivergenceReason = "not-a-regular-file"
	DivergenceWrongMode      DivergenceReason = "wrong-mode"
)

// NotImplementedError is the typed cause a declared-but-unbuilt harness renderer returns, so a
// caller branches on the type and reads WHICH harness is unbuilt from the value, never from prose
// (errors.go:14-17). It rides under errors.KindInternal. §3.6 guard G6 is this type.
type NotImplementedError struct{ Harness Harness }
```

⚠️ **`Diagnostic` and `Severity` were specified here and are DELETED.** §4.4 records the removal
and its reason as a fork, because deleting a specified type is not a silent tidy-up.

**A role, defined.** 🔶 A `Role` is *the standing instruction context one agent loop runs under*. It
is not a person, not an authz principal (§2.3), and not a phase. Two roles differ exactly when the
set of modules they select differs; two roles that select the same modules are one role with two
names, and the schema validator rejects that at `New` time so the manifest cannot grow synonyms.

### 3.4 Composition and ordering

#### 3.4.1 Module names are globally unique — and that is FORCED, not chosen

`RuleRef struct{ Name, Version string }` is FROZEN and carries **no repository qualifier**
(`orchestrator.md:133-135`). If two repositories each had a fragment named `identity` with different
bodies, `RuleRef{"identity", "1.0.0"}` would resolve to two different things and the orchestrator
would be carrying an ambiguous ref. **Global uniqueness of `Fragment.Name` is therefore derived from
a frozen contract, not preferred.**

That is also why `EmitAs` exists and is separate from `Name`. Three repositories today each commit a
file called `00-identity.md` with different content (`libs`, `infrastructure`, `.devcontainer` —
measured in §3.1). They become three fragments — `identity-libs`, `identity-infrastructure`,
`identity-devcontainer` — each with `emitAs: identity` and `order: 0`, so each still lands at
`.claude/rules/00-identity.md` in its own repository. The addressable identity is globally unique;
the on-disk name is not required to be.

✅ **And there is a MECHANICAL constraint that forces the split, not just a tidiness argument.** A
fragment name is validated as an HNS-1 slug — `document.go:219-243` implements
`slug := word ("-" word)*`, `word := [a-z][a-z0-9]*` (rule 11, `libs/.claude/rules/11-naming.md`)
— so **a name may not begin with a digit, and `"00-identity"` is REJECTED as a name.** Both halves
of the constraint therefore hold at once: the file on disk must be called `00-identity.md`, and
the fragment that produces it must not be called that. The numeric prefix cannot come from the
author's name field; it can only come from the renderer, out of `Order`. §3.6 states the same
conclusion from the corpus side.

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

⚠️ **UNRECONCILED — the built library does the opposite, and no ruling covers this row.** The
contract above forbids a body-override operator. `document.go:185-201` `composeFragments` is one:
it walks `defaults`, then `role`, then `overlay` into a `map[string]Fragment`, so **a same-named
fragment at a higher layer REPLACES the one below**, silently and by design — the package doc
(`agentprofile.go:28-31`) states it as the intended semantic: *"A rule or skill declared at a
higher layer REPLACES the same-named fragment from a lower one."* `lastNonEmpty` does the same for
the scalar instruction. There is no `add`/`remove` operator in the built document at all.

This is not a naming difference and §4.4's "the code wins on names" ruling does not reach it. It is
a **semantic** disagreement on the section this contract calls its own real content, and it has a
consequence that must be stated rather than absorbed: a silent same-name replacement is a body
override, and §3.4.2's argument that it is what makes a drift gate possible applies to it. **This
document does not choose.** Recorded as fork **F7** (§9) and put to Mateo as part of the freeze.

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

⚠️ **Specified, not yet built.** Neither `Order` nor the four-layer index exists at `436d7f7`. The
built code composes three layers and sorts the result **by `Name` alone**
(`document.go:196-200`), so the emission order there is alphabetical, not authored. The totality
proof above is therefore a proof about the SPECIFIED design; it is not a description of the
library today. That is exactly why §4.4 keeps `Order` rather than deleting it to match the code: a
totality proof resting on a field that does not exist would be the defect, while a
specified-and-labelled field is a build instruction.

### 3.5 Versioning

- ✅ `schemaVersion` is the **schema's** version, an integer, bumped only by a change to the shape.
  E2 requires it: *"No artifact without a schema: every phase input/output validates against a
  versioned schema before acceptance"* (`docs/architecture/README.md` §5).
- 🔶 `profileVersion` is the **document's** semver. It is stamped into the banner of every rendered
  file, so a rendered file names the document version it came from and a reviewer never has to
  guess. ⚠️ **Specified, not yet built:** the parsed document at `436d7f7` has no such key
  (`document.go:20-25` is `schemaVersion` / `defaults` / `roles` / `overlays`), and `Resolved` has
  no such field, so the built banner cannot name it — see §6.2, whose promise was corrected to
  match what the schema can supply.
- 🔶 Each `Fragment` carries its own semver, because `RuleRef`/`SkillRef` carry one (§3.4.1).
  ⚠️ **Specified, not yet built:** `Fragment` at `436d7f7` is `{Name, Body}` only.
- 🔶 **Bumping the schema is a contract revision** (ADR-0016 §1) once this contract is frozen, and
  re-recording `libs/go/agentprofile/.apibaseline` goes with it — the cardinal sin otherwise (10 §9).

### 3.6 The emitted surface, per harness

| Harness | v1 emits (SPECIFIED) | State today |
|---|---|---|
| `claude-code` | `CLAUDE.md` · `.claude/rules/NN-<emitAs>.md` · `.claude/skills/<emitAs>/SKILL.md` · `.claude/settings.json` | ✅ a real target — the §3.1 corpus. ⚠️ the BUILT renderer emits a different layout; see below. |
| `omp` | — | ⚠️ **no committed target exists.** `OMPRenderer` is wired through `Deps.Renderers` and returns a typed `NotImplementedError` under `errors.KindInternal` naming the harness (`renderer.go:73-75`). It never returns an empty `FileSet`. |
| `codex` | — | ⚠️ same, with the same loud failure (`renderer.go:88-90`) |

⚠️ **Corrected against the built renderer, and the CONTRACT wins on both rows.** `ClaudeRenderer`
at `436d7f7` (`renderer.go:34-58`) emits under a per-cell root — `profiles/<role>/<harness>/…`
(`profileRoot = "profiles"`, `:13`) — and names each rule file `.claude/rules/<name>.md` with **no
`NN-` prefix**. Two separate corrections, each with its own reason:

1. **The `NN-` prefix stays, because without it the renderer cannot reproduce the files it exists
   to replace.** §3.1's real corpus IS numerically prefixed — `00-identity`, `10-interface-design`,
   `11-naming`, `12-error-handling`, `20-library-pipeline`, `21-test-taxonomy`,
   `22-harness-versions`, `24-typescript-pipeline` — and **the numbers ARE the load order**, which
   is the one thing an instruction corpus cannot lose. A render that drops them fails §5's
   acceptance corpus on its first golden. And the prefix must be the RENDERER's job rather than
   the author's, because `document.go:219-243` validates every name against HNS-1
   `word := [a-z][a-z0-9]*`: a name may not start with a digit, so **`00-identity` is rejected as a
   NAME** (§3.4.1). The author declares `order: 0`; the renderer writes `00-`.
2. **The emission root is 🧩 OPEN, not settled here.** `profiles/<role>/<harness>/…` and a
   repository-root emission answer two different questions — the first makes one checkout hold
   every cell side by side, which is what a pod mounting one digest wants; the second is what
   ruling 1 names and what §2.4 moves out of the ADR-0026 sync channel. They are not
   interchangeable, and choosing between them decides whether §3.1's corpus is a golden or a
   migration. Recorded as fork **F8** (§9).

🔶 **v1 emits declarative files only.** No hook script, no slash-command script, no `Makefile`. Two
reasons, both concrete:

1. A renderer that emits executable shell is a code generator, and `git-process.md:325` §14 row 13
   (⚠️ corrected from `:323`, which is row **11**, the bot GitHub identity) records that **NOTHING
   gates `.githooks/` today** — *"`.ci/ctl.sh` shellchecks `ctl.sh` files only, so a hook can
   regress silently."* Emitting generated shell onto an ungated surface widens a known hole.
2. The one hook corpus in the estate is *instance* logic, not instruction content: `project-go`'s
   four hooks call `golangci-lint`, `hnslint` and the phase gate. Rendering them from a matrix would
   buy nothing and would put executable code behind a byte-equality gate that cannot read it.

🧩 **`AGENTS.md` and the import stub — decided here rather than left implicit.**
`portable-agent-config-2026-06.md:792` and `:922` record that Claude Code does not auto-read
`AGENTS.md`, so upstream's compiler *"must emit a `CLAUDE.md` containing `@AGENTS.md` (or
symlink)"*. **`agentprofile` does not do that.** For the claude target it emits a **full**
`CLAUDE.md` from the resolved instruction body (`Resolved.Instruction`); if a future omp or codex
target chooses `AGENTS.md`, it is emitted from **the same resolved body**, not by making one file
import the other. Reason: an
import stub creates a second read path whose content is not covered by the digest of the file that
imports it (§7), and a symlink is refused outright by §6.4 guard G3. Two files, one source, both
digested.

## 4. Construction (the spine) and the ports

⚠️ **Corrected — the remedy this section prescribed has now been EXECUTED.** An earlier revision
said *"At the time this section was written, `…/libs-agentprofile/go/agentprofile/` did not
exist"*, and promised *"When the skeleton lands, this section is diffed against it and amended to
match the code."* **The skeleton landed.**

✅ **Measured**: `libs` branch `feat/agentprofile`, commit **`436d7f7`** *"feat(agentprofile): the
schema, ports and deterministic claude renderer"*, on top of `8683fea` — nine Go files
(`agentprofile.go`, `compiler.go`, `document.go`, `errors.go`, `renderer.go`, the
`agentprofiletest` fakes, and three test files), a `ctl.sh`, a `project.json`, and a recorded
`.apibaseline` of 21 exported entries. §4.1 to §4.3 below are the reconciled surface; **§4.4 is
the full divergence table and states which side won each row and why.**

⚠️ **`436d7f7` is NOT the commit this repository pins.** The submodule pointer here is
`8683feab1` (`git rev-parse HEAD:libs`), which is `436d7f7`'s parent and carries no
`go/agentprofile` at all. Every citation below is read from `436d7f7` and says so. §0.2 explains
why the pointer must NOT be bumped ahead of Mateo's ruling.

### 4.1 The spine

```go
func New(configuration Config, dependencies Deps) (*Compiler, error)
```

⚠️ **Corrected — the concrete return type is `*Compiler`, not `*Profile`.** `compiler.go:53`. The
code wins on names (§4.4). The name reads correctly at a call site: the thing New returns is what
turns a document into files, and `agentprofile.Compiler` sits beside `codeinsight.Analyzer` the
same way.

✅ `New` is **PURE** (10 §9): no I/O, no clock read, no environment read, no filesystem walk, no
global — verified in the built code, whose only imports on the construction path are
`encoding/json`, `slices`, `maps`, `strconv`, `strings` and the sibling `errors` library. It
parses `Config.Document`, validates every invariant it carries, checks the overlay selector names
a declared overlay, binds each injected `Renderer` to the harness it claims, and returns a typed
`*errors.Error` of `errors.KindInvalid` on a violation so the composition root fails fast and
loud. Parsing bytes that were handed to it is pure; reading the file is the caller's job.

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
// compiler.go:17-37, as built at 436d7f7.
type Config struct {
	Document   []byte // the authored profile document as JSON bytes, already read by the caller
	Repository string // which repository's overlay this instance resolves; "" is the BASE matrix
}

type Deps struct {
	Renderers []Renderer // at least one, each claiming a distinct Harness; a nil or a duplicate
	                     // claim is a New-time KindInvalid error, never a slice-order accident
	Tree      Tree       // the READ-ONLY view of the committed files; REQUIRED even render-only
}
```

⚠️ **Two corrections to the earlier specification, both in the direction of the code:**

- **`Config.BodyFS` does not exist.** An earlier revision gave `New` an `fs.FS` to read fragment
  bodies from at construction. The built document inlines every body as a JSON string
  (`Fragment.Body string`), so there is nothing to open and `New` reads no filesystem at all. That
  is *stronger* than the specified form, not weaker: a port that cannot be given cannot be misused,
  and the purity claim in §5 no longer rests on "reads only at construction".
- **`Config.Repository == ""` is NOT an error.** The earlier text called it a `ConfigError`;
  `document.go:150-159` makes it the **base matrix** — the correct value for a caller rendering
  with no overlay applied. The error case is a non-empty selector naming an overlay the document
  does not declare, which is `KindNotFound`, refused at `New` rather than resolving to nothing.

✅ **There is no `Clock` port, and its absence is the determinism guarantee made structural.** You
cannot read a clock you were not given. Verified at `436d7f7`: no file in the package imports
`time`. This is the deliberate inverse of `agentruntime`, whose §2 names `Clock` *"the sidecar's
ONLY time source"* — there, time is the product; here, time is the contaminant.

### 4.2 The methods

```go
// Render produces the complete emission for one Target, sorted by Path in byte order before it
// returns (compiler.go:122), then checked against the emission invariants: at least one file,
// every path relative and free of "." / ".." elements, no path emitted twice. Deterministic (§5).
func (c *Compiler) Render(ctx context.Context, target Target) (FileSet, error)

// Drift re-renders ONE target in memory and compares it against the committed Tree. It NEVER
// writes. An empty result means the committed files are exactly what the profile produces (§6).
func (c *Compiler) Drift(ctx context.Context, target Target) ([]Divergence, error)

// Digest content-addresses an emission. It is a method on the VALUE, not on the compiler, so a
// caller digests what it already holds and no second render can disagree with the first (§7.1).
func (s FileSet) Digest() string
```

⚠️ **Corrected — three method-level claims in the earlier revision were false about the code, and
the code wins on all three names** (§4.4):

- **`Check(ctx)` is `Drift(ctx, target)`.** The verb is the estate's own (§6.1's `generate`/`drift`
  pair), and it takes a target: the built `Compiler` checks one cell per call, not a whole
  repository per call.
- **`RenderAll` does not exist.** §5's determinism argument used to lean on it — *"returns a SORTED
  SLICE, never a map"*. That argument is now made by `Render` itself, which sorts, and by
  `composeFragments`, which sorts; §5's table was rewritten accordingly.
- **`Digest` is not a `*Compiler` method and returns no error.** `FileSet.Digest() string`,
  `agentprofile.go:134`.

`*Compiler` is the concrete return type. Accept interfaces, return concrete (10 §9, `ireturn`).

### 4.3 The ports (consumer-defined, ≤5 methods — 10 §9, `interfacebloat`)

```go
// Renderer is the SHAPE OF THE NEED for one harness: turn an immutable Resolved into that
// harness's native files. It is upstream agentcfg's proven Compile seam
// (agentcfg-architecture.md:437-449) with the IR narrowed to one Target. A Renderer sees Resolved
// and nothing else — no document, no filesystem, no clock — which is what makes purity checkable
// rather than promised.
type Renderer interface {
	Harness() Harness
	// BUILT: `Render(ctx, resolved Resolved) (FileSet, error)` — by VALUE, not by pointer, and
	// with no diagnostics slice. The by-value copy is what makes the projection immutable to the
	// renderer, which a pointer would surrender (renderer.go:33 records the reasoning against the
	// gocritic hugeParam warning). Both changes are the code's, and the code wins (§4.4).
	Render(ctx context.Context, resolved Resolved) (FileSet, error)
}

// Tree is the READ-ONLY view of the committed files the drift check compares against. It is
// read-only ON PURPOSE and this is the single most load-bearing line of the port set: a gate that
// can repair its own expectation cannot fail. eden's own .ci/ctl.sh:461-463 states the rule for
// its roster: "It deliberately does NOT run inside graph-guard. A gate that repairs its own
// expectation cannot fail: it would rewrite the roster to match whatever the graph had become and
// report OK, which is the defect this whole file exists to make impossible."
type Tree interface {
	// BUILT (agentprofile.go:213-219). An ABSENT path MUST report an error satisfying
	// errors.Is(err, fs.ErrNotExist) — that is how Drift tells "never written" from "unreadable".
	ReadFile(ctx context.Context, path string) ([]byte, error)

	// [NOT BUILT at 436d7f7 — SPECIFIED, and kept. §4.4 gives the ruling; §6.4 gives the need.]

	// Stat reports the entry at path WITHOUT following a symlink (an Lstat, never a Stat).
	Stat(ctx context.Context, path string) (Entry, error)
	// List returns every entry under prefix, sorted in BYTE order, symlinks not followed.
	List(ctx context.Context, prefix string) ([]Entry, error)
}

// [NOT BUILT — SPECIFIED. Entry is what Stat and List return.]
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

⚠️ **`Tree.Stat`, `Tree.List` and `Entry` are SPECIFIED and NOT BUILT, and they stay in the
contract.** They are not decoration. Three of this document's own requirements are **impossible**
without them, and each one is the kind that fails silently rather than loudly:

| requirement | the method it needs | what happens without it |
|---|---|---|
| §6.4 **G5** — the extraneous-file reverse sweep | `List` | a deleted fragment's rendered file sits on disk forever and every check stays green |
| §6.4 **G3** — a symlink at a rendered path is REFUSED | `Stat`, as an Lstat | the check follows the link, compares the target's bytes, and passes on a path that is not the file it thinks it is |
| §8 **I6** — every emitted file is mode `0o644` | `Stat`, reporting a mode | there is no mode to compare, so the invariant is a sentence rather than a check |

✅ **The library is being extended to add them, and its own test package already anticipates it** —
which is the evidence that this is a build gap rather than a design disagreement.
`agentprofiletest` at `436d7f7` records a symlink flag and a sorted path list on the fake, with
the reason written in: *"It is the data a `Tree` port that grows a `Stat` method would read; the
fake records it today so a test can state the symlink requirement **without this package inventing
the `Entry` type the contract owner must declare**"* (`agentprofiletest.go:117-119`), and the same
for `Paths` and `List` at `:126-129`. The fake is waiting for the port.

### 4.4 The divergence against the built library — every row, with the ruling

⚠️ This table IS the remedy §4's earlier revision promised. Each row is measured at `436d7f7`.
"CONTRACT wins" means the library is to be extended; "CODE wins" means this document was amended.

| # | This contract specified | The built code at `436d7f7` | Ruling |
|---|---|---|---|
| 1 | `HarnessClaude = "claude"` | `HarnessClaudeCode = "claude-code"` (`agentprofile.go:78`) | **CODE** — and the contract's *reason* was wrong too, not just its value (§3.3) |
| 2 | `New → *Profile` | `New → *Compiler` (`compiler.go:53`) | **CODE** |
| 3 | `Check(ctx) ([]Divergence, error)` | `Drift(ctx, target) ([]Divergence, error)` (`compiler.go:132`) | **CODE** |
| 4 | `RenderAll` | absent | **CODE** — §5's rationale rewritten off it |
| 5 | `type Digest string`, `(*Profile).Digest(ctx, target)` | `func (s FileSet) Digest() string` (`agentprofile.go:134`) | **CODE** |
| 6 | `Module{Name,Version,EmitAs,Order,Kind,Body}` | `Fragment{Name,Body}` (`agentprofile.go:224`) | **CODE on the name and on `Kind`; CONTRACT on `EmitAs` and `Order`** — see below |
| 7 | `FileSet{Target, Files}` | `type FileSet []File` (`agentprofile.go:128`) | **CODE** |
| 8 | `Target{Repository, Role, Harness}` | `Target{Role, Harness}`; repository moved to `Config` | **CODE** — consequence stated at §7.2 G-E |
| 9 | `Config.BodyFS fs.FS` | absent; bodies inline as JSON strings | **CODE** |
| 10 | `Renderer.Render(…, *Resolved) (FileSet, []Diagnostic, error)` | `(…, Resolved) (FileSet, error)` (`agentprofile.go:206`) | **CODE** |
| 11 | `Tree{Stat, ReadFile, List}` + `Entry` | `Tree{ReadFile}` only (`agentprofile.go:213`) | **CONTRACT** — G3, G5 and I6 are impossible without them |
| 12 | `Divergence.Reason` ∈ five values | `DivergenceReason` ∈ `missing`, `content-differs` (`agentprofile.go:173-178`) | **CONTRACT on the three missing values** (each waits on row 11); **CODE** on the typed enum and on the hyphen |
| 13 | `Diagnostic` / `Severity` | absent | **CODE — DELETED from this contract.** Recorded as fork **F9** |
| 14 | emits `CLAUDE.md`, `.claude/rules/NN-<emitAs>.md` at the repository root | emits under `profiles/<role>/<harness>/…`, no `NN-` prefix (`renderer.go:13, 34-58`) | **CONTRACT on the prefix** (§3.6); **the ROOT is fork F8, unruled** |
| 15 | canonical digest input uses `decimal(mode)`, over files sorted by `Path` | `strconv.AppendUint(…, 8)` — **octal**; `Digest` does **not** sort (`agentprofile.go:134-147`) | **CONTRACT on sorting; CODE on octal** — §7.1 |
| 16 | banner names `profileVersion` | `Resolved` has no such field; `renderer.go:96` emits `schemaVersion`, `role`, `harness`, `overlay` | **CODE** — §6.2 rewritten to what the schema can supply |
| 17 | overlays **add**/**remove** only, no body override (§3.4.2) | same-name REPLACE across three layers (`document.go:189`) | **UNRULED** — fork **F7**, put to Mateo |

🔶 **Why `EmitAs` and `Order` are kept although the code has neither.** Two of this document's
arguments rest on them, and neither survives their deletion. §3.4.1's cross-repository story —
three repositories each keeping their own `00-identity.md` from three globally-unique fragment
names — is `EmitAs`. §3.4.3's totality proof is a proof about the key `(Layer, Order, Name)`.
**A totality proof that rests on a field that does not exist is the defect. A specified field that
is labelled *not yet built* is a build instruction.** So they are labelled, not deleted, and §3.4.3
now says plainly that the built library sorts by `Name` alone.

🔶 **Why `Diagnostic` and `Severity` are deleted although the contract specified them.** They came
into this document as upstream `agentcfg` surface (`agentcfg-architecture.md:443-446`, where
`Compile` returns `[]diag.Diagnostic` because *"Crush can't express subagents"*). **This contract
has no consumer for them.** Nothing in §6 branches on a diagnostic, no gate reports one, and no
caller is specified that reads one. An exported type that nothing reads is precisely what the
estate's dead-state scans exist to catch — `libs/.claude/rules/21-test-taxonomy.md` §h names
CONFIG-DEAD-STATE and CAPABILITY-WIRED as **gate FAILURES** for exactly this shape, on the grounds
that an exported symbol is invisible to `unused` and *"counts as covered the moment it is merely
ASSIGNED"*. The one thing they were for — a renderer that cannot express a fragment — is already
answered more loudly by `NotImplementedError`, which fails rather than warns. Recorded as fork
**F9** so the removal is a decision with a reason, not a silent tidy-up.

### 4.5 The conformance suite and what it may import

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

⚠️ **Corrected — the fakes exist and carry different names.** An earlier revision named
`agentprofiletest.MemoryTree` and `agentprofiletest.RecordingRenderer`; the built package at
`436d7f7` ships `agentprofiletest.Tree` and `agentprofiletest.Renderer`, each with a builder
chain. The code wins on names (§4.4), and what they DO is what this section claimed:

- `agentprofiletest.NewTree()` — an in-memory `Tree`. `With`, `WithFileSet`, **`WithSymlink`** and
  `FailWith` seed it, so §6.4's guards G3 and G4 are exercised rather than asserted, and a
  transport fault can be told from an absent file. `IsSymlink` and `Paths` are already there,
  holding the data the unbuilt `Stat` and `List` will read (§4.3).
- `agentprofiletest.NewRenderer(harness)` — a `Renderer` that records the `Resolved` it was
  handed, so the purity claim of §4.3 is checked by observation (it never sees a document, a path,
  or a clock) instead of by comment.

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

⚠️ **Corrected — this table used to lean on `RenderAll`, which does not exist (§4.4 row 4).** Each
row below now names a mechanism that is in the built code, or says it is not.

| Forbidden | How the design forbids it |
|---|---|
| Go map iteration order | the document IS parsed into maps (`document.go:23-24`), and every walk over one is `slices.Sorted(maps.Keys(…))` — in `validate` (`:75`, `:80`), so a two-fault document always reports the same fault first, and in `composeFragments` (`:197`), so the emission never depends on map order. No exported type is a map. |
| a clock read | there is no `Clock` port, and no file in the package imports `time` (§4.1) |
| an environment read | `New` is pure; the document arrives as `[]byte` and every fragment body is inline in it |
| a filesystem walk order | the render never walks a directory to decide content. ⚠️ The specified `Tree.List` — used only by the drift check — returns byte-sorted entries; it is **not built** (§4.3) |
| a locale-dependent sort | every sort is a byte comparison: `strings.Compare` on `File.Path` (`compiler.go:122`) and `slices.Sorted` on `string` keys, both of which are byte order. `.ci/ctl.sh` uses `LC_ALL=C sort` on **both** the write side (`:494`) and the read side (`:416`, `:422`) for exactly this reason, and the invariant here is that no `strings.Collate`-style comparison is ever introduced |
| a random iteration seed, a `sync.Map` range, a goroutine race on append | the built `Render` is sequential and holds no per-call state; a `*Compiler` is immutable after `New` and is safe for concurrent use *iff* the injected ports are (`agentprofile.go:47-48`). Any future fan-out assembles by index, never by completion order |

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
<!-- GENERATED by agentprofile from agentprofile.json (schemaVersion 1, role implementer,
     harness claude-code, overlay gophersys/libs) — DO NOT EDIT. -->
<!-- Re-render with `agentprofile render`; the `agentprofile drift` gate fails on any hand-edit. -->
```

⚠️ **Corrected twice, and both were real defects rather than typos.**

1. **The source file is `agentprofile.json`, not `agentprofile.yaml`.** §3.2 and §10 Q5 select
   JSON parsed with `DisallowUnknownFields()`, and the built parser is `encoding/json`
   (`document.go:48-49`). The `.yaml` spelling was copied from cictl's banner, whose source
   genuinely IS `.ci/ci.contract.yaml`. Left uncorrected, the banner and the drift message would
   have sent a developer to edit a file the schema forbids — a generated file telling its reader
   to fix it in a format the parser rejects is worse than no banner.
2. **The banner cannot name a `profileVersion`, because `Resolved` has no such field.**
   `renderer.go:96-102` builds the provenance line from exactly four values —
   **`schemaVersion`, `role`, `harness`, `overlay`** — and `overlayLabel` prints `none` rather than
   an empty string, so a reader is never left interpreting a blank. The specification above now
   names those four. When `profileVersion` is built (§3.5), it is an ADDITIVE fifth value here.

The banner therefore names the **cell and the schema**, so a reviewer reading a rendered file in a
submodule knows which row, which column and which overlay produced it without resolving a pointer.

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

  .claude/rules/11-naming.md        content-differs
      - a hand edit is present on disk that the profile does not produce
      + edit agentprofile.json (fragment `naming`, version 1.0.0) and re-render
  .claude/rules/24-typescript-pipeline.md   missing
      + the profile selects fragment `typescript-pipeline` for role `implementer`

fix: bash ./ctl.sh agentprofile render   (never hand-edit a generated file)
```

⚠️ **`agentprofile.json`, not `.yaml`** — same correction as §6.2, and it matters more here: this
is the line a developer follows. Sending them to a YAML file that `DisallowUnknownFields()` would
refuse to parse is an error message that causes the next error.

### 6.4 The anti-false-green guards — each with its precedent

A drift gate that reports OK when it checked nothing is worse than no gate, because it is believed.
Six guards, and each names the instance that earned it.

⚠️ **These are REQUIREMENTS the drift check must meet. They are NOT properties of the system, and
an earlier revision wrote three of them as though they were.** The **State** column says which is
which at `436d7f7`. A requirement written in the present indicative is exactly the false green this
section exists to forbid, so the tense is fixed rather than the claim softened.

| # | Guard — the REQUIREMENT | Precedent that earned it | State at `436d7f7` |
|---|---|---|---|
| **G0** | The gate cannot repair its own expectation: `Tree` has no write, create or delete method | `.ci/ctl.sh:461-463` — *"A gate that repairs its own expectation cannot fail: it would rewrite the roster to match whatever the graph had become and report OK, which is the defect this whole file exists to make impossible."* | ✅ **BUILT** — `Tree` is `ReadFile` alone, and `agentprofile.go:209-212` states the reason in the code |
| **G1** | An emission of ZERO files is a FAILURE, never a pass | `.ci/ctl.sh:418` refuses a zero-row roster — *"it would match any graph at all"*. A `FileSet` with no files matches any tree at all | ✅ **BUILT** — `validateEmission` (`compiler.go:174-177`), *"an empty emission would make the drift check vacuous, so it is refused"* |
| **G2** | A per-target minimum-count floor, declared in the document | `deploy/servicespec/render_test.go:244` — *"A silent add/drop … fails here before it ships"* | ⚠️ **NOT BUILT** — no `minimumFiles` key exists in the parsed document (§3.2) |
| **G3** | A symlink at a rendered path is REFUSED, never followed | upstream `FileSet.WriteAll` — *"Symlinks are rejected"* (`agentcfg-architecture.md:468`); and the `.devcontainer` twin check uses `cmp`, which **follows** a symlink, so a `cmp` pass over a symlinked path proves nothing | ⚠️ **NOT BUILT** — see below |
| **G4** | An EMPTY rendered file is REFUSED at render time; two empty twins compare equal and prove nothing | the same false-equality argument as G1 | ✅ **BUILT** at the author's end — an empty `Fragment.Body` is a `New`-time `KindInvalid` (`document.go:134-136`), *"an empty body … renders an empty file, which reads to the next human as a rule that was deleted rather than one that was never written"* |
| **G5** | An EXTRANEOUS file under a render root is a `Divergence` | an ADDITION to cictl, not a copy: its `Drift` iterates the *render's* targets only (`internal/cirepo/drift.go:34-45`) | ⚠️ **NOT BUILT** — see below |
| **G6** | An unimplemented harness fails LOUDLY, naming itself, rather than emitting an empty `FileSet` | *"A silent empty emission is the failure mode this whole contract exists to prevent"* | ✅ **BUILT** — `NotImplementedError` under `errors.KindInternal` (`errors.go:14-33`, `renderer.go:73`, `:88`) |

⚠️ **G5 and G3 are SPECIFIED and UNBUILT, and the reason is one sentence: the built `Drift`
iterates the render's targets only.** `compiler.go:132-162` walks `rendered` and calls
`tree.ReadFile` for each path — **which is the exact cictl shape this contract cites G5 as an
improvement on.** So today:

- **G5 has no reverse sweep.** Nothing enumerates what the committed tree holds that the render
  does not produce. Deleting a fragment leaves its rendered file on disk forever and every check
  stays green — the precise failure G5 was written to close, currently open. It needs `Tree.List`
  (§4.3).
- **G3 does not refuse a symlink.** `Tree.ReadFile` has no way to tell one: it returns bytes, and
  `os.ReadFile` — which the port's own doc names as the reference implementation — **follows**
  the link. A symlinked rendered path therefore compares the TARGET's bytes and can pass. It needs
  `Tree.Stat` as an Lstat (§4.3). The test fake already records the symlink flag, waiting for it.

**Neither is a defect in the library.** The library is at an architecture-phase skeleton with a
recorded baseline; both additions are additive to `Tree`. What would be a defect is this document
claiming the sweep runs.

### 6.5 The gate must be PROVEN SELECTED — this is a requirement, not a footnote

⚠️ **A well-written drift gate that no lane runs is a green check that verifies nothing, and this
estate has one right now.** `deploy/servicespec/render_test.go:214` is
`TestCommittedManifestsMatchCatalog` — *"the DRIFT GATE between the typed Catalog and the COMMITTED
generated manifests … A
catalog/renderer change whose regen was forgotten — or a hand-edit of a generated file — fails HERE
instead of shipping stale manifests."* It is a good gate. **Measured here: no eden CI lane selects
it.** `find deploy -name project.json` returns nothing, and the roster holds **49 rows**, none of
which is `deploy`, so `nx affected -t test` never reaches it.

> ⚠️ **Corrected — the roster count was 60, and 60 is the file's line count, not its row count.**
> `.ci/graph-roster.txt` is 60 lines; the gate's own filter is
> `grep -vE '^\s*(#|$)' "$roster" | LC_ALL=C sort` (`.ci/ctl.sh:416`), which drops the comment
> header and the blank lines and yields **49**. 49 is what the `graph-guard` output in this same
> pull request reports. The correction matters beyond arithmetic: this paragraph's whole argument
> is that a roster is the authoritative list of what CI selects, so quoting a number the gate does
> not use would have undercut the point it is making.

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
path || 0x00 || octal(mode) || 0x00 || decimal(len(content)) || 0x00 || content
```

⚠️ **Corrected on the mode, and the sort is a REQUIREMENT the built code does not yet meet.** This
is the value a pod's `profileRef` points at, so it has to be exactly right, and an earlier revision
was wrong on both halves:

1. **`octal(mode)`, not `decimal(mode)`.** `agentprofile.go:140` is
   `strconv.AppendUint(canonical, uint64(file.Mode), 8)` — **base 8**. The code wins (§4.4 row 15);
   octal is also the spelling a human reads a Unix mode in, so `644` in the digest input matches
   `0o644` in the invariant it enforces (§8 I6). The length stays decimal (`:142`, base 10), which
   is what the earlier text said and is correct.
2. **`FileSet.Digest()` does NOT sort, and one real call path hands it an unsorted set.**
   `agentprofile.go:134-147` hashes the slice in whatever order it receives.
   `Compiler.Render` sorts by `Path` with `strings.Compare` before returning
   (`compiler.go:122`), so a `FileSet` obtained THAT way is byte-sorted — but `FileSet` is an
   exported type and `Digest` is a method on it, and `ClaudeRenderer.Render` returns an emission
   ordered `CLAUDE.md`, then `.claude/rules/…`, then `.claude/skills/…` (`renderer.go:38-56`).
   **That is not byte order**: `.` is `0x2E` and `C` is `0x43`, so `.claude/…` sorts BEFORE
   `CLAUDE.md`. A caller that digests a renderer's output directly gets a different digest from one
   that digests the compiler's output over identical bytes.

🔶 **The sorting is the safer guarantee and the contract keeps it.** A content address whose value
depends on which function handed you the slice is not a content address. Requiring `Digest` to
sort its own input costs one `slices.SortFunc` and makes the property hold for every caller,
including one that constructs a `FileSet` by hand — which the test package does. Stated plainly:
**the built code does not yet do it**, and §4.4 row 15 carries the ruling.

🔶 **Why length-prefixed and NUL-separated:** the encoding must be **injective**, or two different
`FileSet`s can concatenate to the same bytes and collide without a hash weakness being involved.
Length-prefixing the content and NUL-separating the fields makes the parse unambiguous, which is the
property that matters — and the built code states the same reason: *"NUL cannot occur in a path or
in a decimal length, so no content can forge a component boundary"* (`agentprofile.go:64-66`).
`Target` is deliberately **not** in the digest input: the digest addresses
the *bytes of a rendered profile*, so two targets that render identically are the same artifact, and
a pod that mounts a digest gets content, not provenance. Provenance rides beside it in the field
that names the digest.

### 7.2 What `profileRef` needs — and who has actually claimed it

⚠️ **Corrected — this section previously reasoned from a word that is no longer in its source.**
An earlier revision quoted `fleetenvelope.md:63` as *"Pod lifecycle, the CRD, the role, **the
profile** — `agentpod` owns those"* and then instructed the reader: *"Read that sentence precisely:
`agentpod` owns the pod's reference to a profile."* Three things were wrong at once, and the third
is the expensive one:

1. **The line number moved.** It is `fleetenvelope.md:59`.
2. **The document name is wrong.** `agentpod` appears **zero** times in the current
   `fleetenvelope.md`; the owner named there is `agentfleet.md`. `fleettelemetry.md` — the other
   contract in this same pull request — records the same correction (`:67-68`).
3. **"The profile" is GONE from the sentence.** At `70a979f` the line reads: *"**The CRD, the pod,
   the role, parentage, the legal child set** — `agentfleet.md`. The header carries the `AgentID`
   the controller minted; it does not describe the pod, and **it does not carry the tree**."* The
   inference the earlier revision drew — that a sibling had already assigned the pod's reference to
   a profile — rested entirely on a word the source deleted. **The argument is therefore replaced,
   not re-cited.**

✅ **What the sibling lane has actually claimed, read at commit `70a979f` (worktree
`~/code/.worktrees/eden-fleet-contracts`, read-only to this lane, `git status` clean).**
`agentfleet.md` exists now and is the kubernetes control surface. On `profileRef` it says three
things, and none of them is a claim of ownership:

- Its own NOT-owns list, `:101-103`: *"**The instrumentation profile schema and its renderer** — a
  live parallel lane owns those … §7 states only the SEAM this contract needs."*
- Its §7.2 PROPOSES the field — `profileRef: {name, version, digest}` — and immediately records
  that it collides with `templateRef`, *"THE CEILING"*: *"**Two pins means two ceilings, and
  nothing in either the 2026-08-18 design or the 2026-08-26 ruling says which wins when they
  disagree.** … **This document does not choose. Fork F4.**"*
- Its §7.3, `:910`: *"**Neither lane may assume the other has landed.** Until the seam is agreed,
  `profileRef` is a PROPOSAL in this contract and its field shape above is illustrative."*

⚠️ **So `profileRef` is a field this contract PROPOSES to a document that has NOT claimed it.** No
document in the estate owns a pod's reference to a profile today. Saying so plainly is the point:
an agreement that both sides believe the other made is worse than an open dependency, because
nobody goes looking for it.

⚠️ **And there is no CRD to carry it either.** Measured: no `AgentPod` CRD and **no Eden-owned CRD
at all** — the agent pod is plain YAML at `infrastructure/apps/eden/58-agent-runtime.yaml`,
Argo-reconciled. `agentfleet.md` is a DRAFT proposing the kinds.

**This section's job is therefore the two halves it can do alone: state what `agentprofile`
GUARANTEES, and name the dependency that is open.**

**The guarantees.** These hold whatever the seam turns out to be, and they are the answer to the
three things `agentfleet.md` §7.3 asks this lane for:

- **G-A — a stable digest over a canonical serialization.** §7.1. Two renders of the same document
  for the same target on any machine produce the same digest. (Answers `agentfleet` §7.3 item 2 —
  *"a content digest … in a form the controller can verify at admission"* — and §7.1 states the
  one requirement the built code does not yet meet.)
- **G-B — immutability at a digest.** A rendered profile at digest `D` never changes. "Changing it"
  produces a different digest; there is no mutation path, because the artifact is content-addressed.
- **G-C — the digest covers the FULL emitted tree for one target.** A pod that mounts digest `D`
  cannot receive a partial profile: a missing file is a different digest.
- **G-D — the digest is non-secret and loggable.** It may appear in a `fleetenvelope` header, a
  span attribute, a status field and a log line. This is only true because §8 I5 forbids a secret in
  any emitted file; a digest over content that could hold a credential would be a secret-adjacent
  value and could not be logged.
- **G-E — one target, one digest.** ⚠️ **Corrected from a four-tuple to a pair plus the
  construction selector.** The earlier text said `(profileVersion, repository, role, harness)`
  determines the digest. In the built shape, `Target` is `{Role, Harness}` and the repository is a
  `Config` field (§4.4 row 8), and `profileVersion` does not exist (§3.5). So the accurate
  statement is: **a `Compiler` constructed over one `(document, repository)` and asked for one
  `Target{Role, Harness}` yields exactly one artifact.** The addressing scheme
  `agentfleet.md` §7.3 item 1 asks for is that pair, qualified by the document the compiler was
  built from — which is what a `profileVersion` would name, and is the strongest argument for
  building it.

🧩 **Two things are NOT decided here, and both are named rather than assumed.**

- **Where the artifact lives.** The bytes are already in git; whether a pod reads them from a
  checkout, from an OCI artifact, or from object storage is a deployment decision. G-A and G-B make
  the digest identical in all three cases, which is what lets the decision be made later without
  reopening this one. It is `agentfleet.md`'s question and OD-13's. This is `agentfleet.md` §7.3
  item 3 — *"who publishes the artifact and where it is fetched from, so step 4 knows what
  'absent' means"* — and it is the one of its three that this contract cannot answer alone.
- **`templateRef` versus `profileRef`.** `agentfleet.md` fork **F4** routes its own resolution to
  *"the instrumentation lane's seam"* — that is, to here. This contract does not resolve it either,
  because both pins are ceilings on a POD and this contract owns no pod. It is carried into §10 as
  a named cross-lane dependency so it is answered by someone rather than by neither.

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
