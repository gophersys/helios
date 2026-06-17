# Contract — codeinsight (DRAFT)

> Status: **DRAFT for negotiation** · 2026-06-17 · The analyzer library + canonical insight-payload
> for the "point Eden at a codebase → generate the right dashboards" feature (Eden self-feeding).
> `codeinsight` walks an arbitrary git repository and emits ONE self-describing `Report` — per-entity
> static + behavioral metrics, pairwise logical coupling, repo-level ratings, ownership, trends, and a
> `Views` render-plan — every datum stamped with the commit it was computed at. The `Report` schema is
> the **abstraction seam**: the Go analyzer (producer) and `@eden/visualization` (consumer) build
> independently against it, so a frontend renders any repo's dashboard with zero per-repo code.
> NOT frozen — no library exists yet; this is the 09 §4 step-1/2 negotiation draft. When built, the
> surface is recorded at `libs/go/codeinsight/.apibaseline` and this freezes (ADR-0020).
>
> Epistemic legend: ✅ ratified · 🔶 derived-but-settled · ⚠️ load-bearing assumption · 🧩 open fork.
> Evidence base: research note `docs/research/06-codebase-insight-visualization.md`.

## 1. Scope

🔶 `codeinsight` is the **codebase-analysis library**: given a local git repository (a path + a
commit/window selector), it computes the metrics catalog of research-note §2 and returns a single
`Report` value. It owns three concepts, each with one home (10 §9):

- **the metric computations** — static (complexity, maintainability, coverage ingest) and
  **behavioral/temporal** (churn, change-frequency, hotspot score, logical coupling, code age,
  ownership/bus-factor). The behavioral layer is the spine (research §3): hotspots out-predict static
  properties for defects, so temporal mining is first-class, not an add-on.
- **the `Report` payload** — the self-describing, language-agnostic result envelope (§3), which is
  both the in-process Go API and the JSON wire shape an `edenhttp` endpoint serves.
- **the `Views` render-plan** — the producer's declaration of *which widget primitive renders which
  slice of the report at which SDLC attention point* (§5). This is what makes rendering dynamic.

It is NOT: a git engine (it consumes `gitrepository` — §2), an HTTP server (an `edenhttp` consumer
mounts it — §6), a renderer (`@eden/visualization` owns pixels — §5), or a linter/gate (it *reads*
existing gate output like coverage profiles; it does not enforce). It does **not** shell out to
code-maat (JVM) or PyDriller (Python) — those are reference algorithms; Eden computes them natively
in Go.

## 2. Dependency: `gitrepository` needs a history-walk surface ⚠️

The temporal metrics (churn-over-time, change frequency, logical coupling, code age, authorship)
require walking commit history. `libs/go/gitrepository` today owns provision / inspect
(status·diff·branches·worktrees) / author / transfer — but exposes **no commit-log / rev-list
surface**. The propagation is therefore:

1. **`gitrepository` grows a read-only History capability** — a streaming walk yielding, per commit:
   `CommitID`, author identity, authored/committed time, parent IDs, and per-file change records
   (`path`, `ChangeKind`, added/deleted line counts, rename-from). This is the Go-native equivalent of
   PyDriller's `Commit`/`ModifiedFile` surface (research §3) and a new `InspectKind` (or sibling
   read-op) on the existing `Inspector` seam — additive, but a `.apibaseline` change → contract
   revision on `gitrepository` (ADR-0016 §1, 10 §9).
2. **`codeinsight` consumes that History** to assemble the `Report`.

🧩 **Open fork OD-CI-1:** does the history walk live on `gitrepository`'s `Inspector` (one git home,
preferred) or as a thin `codeinsight`-local reader over `gitrepository`'s `Backend`? Default:
`gitrepository` — it owns git; "one concept, one home."

## 3. The `Report` payload (the abstraction seam)

One envelope. Go types below; JSON tags are the wire shape. Every numeric datum is reproducible from
`(repository, window)` so a `Report` is replayable and diff-able across history.

```go
type Report struct {
    SchemaVersion string        `json:"schemaVersion"` // semver of THIS contract
    Repository    RepositoryRef `json:"repository"`
    Window        Window        `json:"window"`        // the commit range analyzed
    Entities      []Entity      `json:"entities"`      // per-file / per-package nodes
    Couplings     []Coupling    `json:"couplings"`     // pairwise logical-coupling edges
    Ownership     []Ownership   `json:"ownership"`     // author→code, bus-factor inputs
    Summary       Summary       `json:"summary"`       // repo-level scalars + A–E ratings
    Trends        []TrendSeries `json:"trends"`        // time series for the monitoring lens
    Views         []View        `json:"views"`         // the dynamic render-plan (§5)
}

type RepositoryRef struct {
    Identifier string `json:"identifier"`           // logical name (never a secret/URL with creds)
    HeadCommit string `json:"headCommit"`           // 40-hex; the commit the snapshot was taken at
    AnalyzedAt string `json:"analyzedAt"`           // RFC3339; stamped by the caller's Clock
    CommitCount int   `json:"commitCount"`
}

type Window struct {                                // which slice of history fed the temporal metrics
    FromCommit string `json:"fromCommit,omitempty"`
    ToCommit   string `json:"toCommit"`             // usually HeadCommit
    Since      string `json:"since,omitempty"`      // RFC3339 lower bound
    Until      string `json:"until,omitempty"`
    Revisions  int    `json:"revisions"`            // commits in the window
}

type Entity struct {
    Path            string   `json:"path"`
    Kind            string   `json:"kind"`           // "file" | "directory" | "package"
    Language        string   `json:"language,omitempty"`
    Lines           int      `json:"lines"`
    Cyclomatic      int      `json:"cyclomatic,omitempty"`
    Cognitive       int      `json:"cognitive,omitempty"`     // §R2 tooling
    Maintainability float64  `json:"maintainability,omitempty"` // 0–100, VS-rescaled
    ChurnAbsolute   int      `json:"churnAbsolute"`  // added+deleted across the window
    ChurnRelative   float64  `json:"churnRelative"`  // churnAbsolute / Lines (preferred predictor)
    ChangeFrequency int      `json:"changeFrequency"`// #commits touching this entity in the window
    HotspotScore    float64  `json:"hotspotScore"`   // changeFrequency × complexity, 0–1 normalized
    AgeDays         int      `json:"ageDays"`        // since last substantive change
    Coverage        *float64 `json:"coverage,omitempty"` // ingested from a coverage profile if present
    PrimaryAuthor   string   `json:"primaryAuthor,omitempty"`
    AuthorCount     int      `json:"authorCount,omitempty"`
}

type Coupling struct {
    EntityA     string  `json:"entityA"`
    EntityB     string  `json:"entityB"`
    Degree      float64 `json:"degree"`              // 0–100 = sharedRevisions / averageRevisions
    SharedRevs  int     `json:"sharedRevisions"`
    AverageRevs float64 `json:"averageRevisions"`    // gate ≥10 to suppress accidental co-change
}

type Ownership struct {
    Path        string             `json:"path"`
    Authors     map[string]float64 `json:"authors"`  // author → fractional line ownership (0–1)
    BusFactor   int                `json:"busFactor"` // #authors covering >50% (default; OD-CI-3)
}

type Summary struct {
    Lines                int            `json:"lines"`
    EntityCount          int            `json:"entityCount"`
    TechnicalDebtRatio   float64        `json:"technicalDebtRatio"`   // SQALE; 0–1
    MaintainabilityRating string        `json:"maintainabilityRating"`// "A"…"E" (≤5/<10/<20/<50/≥50%)
    Coverage             *float64       `json:"coverage,omitempty"`
    BusFactor            int            `json:"busFactor"`            // repo-level min critical set
    Dora                 *DoraKeys      `json:"dora,omitempty"`       // §R2
    Ratings              map[string]string `json:"ratings,omitempty"` // dimension → "A".."E"
}

type DoraKeys struct { // §R2 — bands + derivation land from research round 2
    DeploymentFrequency string  `json:"deploymentFrequency,omitempty"`
    LeadTimeHours       float64 `json:"leadTimeHours,omitempty"`
    ChangeFailureRate   float64 `json:"changeFailureRate,omitempty"`
    RecoveryHours       float64 `json:"recoveryHours,omitempty"`
    Performer           string  `json:"performer,omitempty"` // Elite|High|Medium|Low
}

type TrendSeries struct {
    Metric string       `json:"metric"`              // "churn" | "debtRatio" | "coverage" | dora key
    Points []TrendPoint `json:"points"`
}
type TrendPoint struct {
    Commit string  `json:"commit"`                   // the commit hash this sample was taken at
    At     string  `json:"at"`                       // RFC3339
    Value  float64 `json:"value"`
}
```

🔶 **Commit-hash addressability.** `Window`, `RepositoryRef.HeadCommit`, and every `TrendPoint.Commit`
carry a commit hash, so any view is reproducible at a point in history and two reports diff cleanly —
the basis of "look at things with commit hashes" (PR-delta views, regression bisection).

🧩 **OD-CI-2:** entity granularity default = file; directory/package roll-ups are derived. Method-level
hotspots (CodeScene's "X-Ray") are a later refinement, not v1.

## 4. Metric catalog binding

The `Report` fields realize research-note §2. Verified-now (✅) vs round-2-dependent (🧩):
✅ cyclomatic, maintainability index, coverage ingest, debt ratio + A–E rating, hotspot,
logical coupling, churn (relative preferred), ownership/bus-factor. 🧩 cognitive complexity, Halstead,
Martin Ca/Ce/I/A/D, DORA — fields are reserved (`omitempty`) and populated once round 2 promotes
formulas + thresholds into research §2. The `Report` schema does **not** change when those land —
only computation fills reserved fields. That stability is the whole point of the seam.

## 5. The `Views` render-plan → `@eden/visualization` (the 8 primitives)

```go
type View struct {
    ID            string         `json:"id"`
    Title         string         `json:"title"`
    Primitive     string         `json:"primitive"`    // one of the 8 widget primitives below
    AttentionPoint string        `json:"attentionPoint"`// "pre-commit"|"pull-request"|"release-gate"|"monitoring"
    Encoding      map[string]string `json:"encoding"`  // channel → report field, e.g. {"x":"churnRelative","y":"cyclomatic","size":"lines","color":"hotspotScore"}
    Source        string         `json:"source"`        // which Report collection feeds it: "entities"|"couplings"|"ownership"|"trends"|"summary"
}
```

🧩 The frontend iterates `Views`, and for each, instantiates the named primitive bound to the encoded
fields — so adding a view is data, not code. The eight primitives (research §5) are the
`@eden/visualization` asset set, each themeable via `@eden/theme` and gated by the UI math
(contrast/APCA, perceptual ordering) as a mechanical test dimension:

| `primitive` | Widget | Default binding |
|---|---|---|
| `hotspot-map` | churn × complexity scatter | x=churnRelative · y=cyclomatic · size=lines · color=hotspotScore |
| `enclosure` | treemap / sunburst / circle-pack | size=lines · color=hotspotScore \| maintainability \| primaryAuthor |
| `dependency-matrix` | DSM / dependency graph | couplings: degree → cell intensity |
| `heatmap` | dir × metric grid | rows=entities · col=metric |
| `ownership-map` | author-colored hierarchy | color=primaryAuthor · annotate busFactor |
| `rating-badge` | A–E badge + KPI tile | summary.maintainabilityRating / ratings / dora.performer |
| `trend` | line / sparkline | trends[metric].points (x=at, value), commit on hover |
| `data-table` | sortable threshold-colored table | any collection; the universal drill-down |

## 6. Productization: the "point-it-at-a-codebase" path

`edenhttp` endpoint (consumer) → `codeinsight.Analyze(ctx, configuration, dependencies)` → `Report`
→ JSON envelope → `@eden/visualization` renders `Views`. SDLC attention points filter which views
surface where: **pre-commit** complexity delta · **PR review** hotspot + coupling on changed files ·
**release gate** ratings + coverage-on-new-code · **monitoring** trends + ownership SPOFs. First
self-feeding target: run `codeinsight` on the Eden monorepo itself (`libs/go/*`) and render the
hotspot map — Eden analyzing Eden.

## 7. Construction & obligations (10 §4 / ADR-0020)

`New(configuration Config, dependencies Deps) (*Analyzer, error)` spine · HNS-1 naming (no
`util`/`common`/`core`; `configuration` not `config`) · `context.Context` first · interfaces ≤5
methods, accept-interfaces-return-concrete · `Deps` injects the `gitrepository` reader + a `Clock` +
an `observability` sink · public fakes in `codeinsighttest` · Go 1.26 floor · module path
`github.com/gophersys/libs/go/codeinsight`. Built phase-by-phase through `ctl.sh phase-gate
<architecture|implementation|testing|qa>` with the 8-dimension taxonomy on a **real** repository
fixture (a seeded git history — never mocked), TDD-order (fake + conformance red before bodies green),
and the frozen `.apibaseline` as the cardinal-sin guard.

## 8. Open forks

- **OD-CI-1** — history-walk home: `gitrepository.Inspector` (default) vs `codeinsight`-local reader.
- **OD-CI-2** — entity granularity: file (default v1) vs method-level X-Ray (later).
- **OD-CI-3** — bus-factor algorithm: >50%-line-ownership (default) vs per-file primary-dev vs
  Minimum-Critical-Set — resolved by research round-2 open-question 4.
- **OD-CI-4** — complexity source: native Go AST vs shelling to gocyclo/gocognit (resolved by round-2
  open-question 3 tooling findings).
