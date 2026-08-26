# Contract — codeinsight

> Status: Frozen (ADR-0020, verify-then-freeze) · 2026-08-26 · The analyzer library + canonical
> insight-payload for the "point Eden at a codebase → generate the right dashboards" feature (Eden
> self-feeding). `codeinsight` walks an arbitrary git repository and emits ONE self-describing
> `Report` — per-entity static + behavioral metrics, pairwise logical coupling, repo-level ratings,
> ownership, trends, and a `Views` render-plan — every datum stamped with the commit it was computed
> at. The `Report` schema is the **abstraction seam**: the Go analyzer (producer) and
> `@eden/visualization` (consumer) build independently against it, so a frontend renders any repo's
> dashboard with zero per-repo code.
> Frozen with the library built: `libs/go/codeinsight` shipped through phase-gate qa with its
> exported surface mechanically recorded at `libs/go/codeinsight/.apibaseline` (the freeze made
> mechanical, ADR-0020). This text was diffed claim-by-claim against that baseline at libs
> `1b8f668` — which is AHEAD of eden's submodule pin `50940e1d` (the pointer bump is eden #14, in
> flight; this library's surface is byte-identical at both commits) — then the diff was ADVERSARIALLY
> REFUTED, which found drift the first pass had missed. Every claim found false was AMENDED before the
> flip: the history walk is a `codeinsight`-owned `History` port, not a `gitrepository` capability
> (§1, §2); the entry point is `New(configuration, dependencies)` then `(*Analyzer).Analyze(ctx)`,
> not a package-level `Analyze` (§6); `Deps` injects `History` + `[]MetricProvider` + `Clock` (§7);
> ownership is COMMIT-share, never line-share (§3, §8); coverage and the Martin/DORA metrics are
> declared and never computed (§1, §3, §4); the coupling gate is on `SharedRevs`, not `AverageRevs`
> (§3); `Window.Since`/`Until` carry git `--since`/`--until` values, not RFC3339 (§3); v1 emits file
> entities only (§3); and `@eden/visualization` ships one of the eight primitives with no
> primitive-token registry yet (§5). §7 also now transcribes the rest of `.apibaseline` —
> `Config`, `Deps`, the ports, `Analyze`, and the error taxonomy — because a cardinal-sin guard the
> contract text does not carry cannot be read against it. Frozen under **Mateo's ruling, 2026-08-26**
> (decision prompt in the coordinating session), verbatim: *"Verify-then-freeze (Recommended)"* —
> mechanical diff of contract vs the library's real exported surface; clean → freeze; drift → amend
> the doc to match reality first, then freeze. A breaking change to the surface requires a contract
> revision (ADR-0016 §1) + re-recording the `.apibaseline` — the cardinal sin otherwise (10 §9).
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

It is NOT: a git engine (it consumes an injected `History` port — §2), an HTTP server (an `edenhttp`
consumer mounts it — §6), a renderer (`@eden/visualization` owns pixels — §5), or a linter/gate (it is
a READER of existing gate output, never an enforcer — though no reader is wired in v1: the coverage
fields stay unpopulated, §4). It does **not** shell out to
code-maat (JVM) or PyDriller (Python) — those are reference algorithms; Eden computes them natively
in Go.

## 2. The history walk: a `codeinsight`-owned `History` port ✅

The temporal metrics (churn-over-time, change frequency, logical coupling, code age, authorship)
require walking commit history. `libs/go/gitrepository` owns provision / inspect
(status·diff·branches·worktrees) / author / transfer and **still exposes no commit-log / rev-list
surface** — its `InspectKind` set is unchanged. The propagation the earlier draft of this contract
proposed onto `gitrepository` did NOT happen; the built library owns the walk itself, and
`codeinsight` does not import `gitrepository` at all:

```go
// History walks a repository's commit log into a structured stream of Commits (newest→oldest), the
// Go-native equivalent of PyDriller's Commit/ModifiedFile surface. It is the behavioral spine:
// churn, change-frequency, hotspot, coupling, age and ownership are all mined from it. One method.
type History interface {
    // Walk returns the commits in the window, newest first, plus the current HEAD commit hash (the
    // commit the static snapshot is taken at). Merges are excluded so churn is attributed to the
    // commit that authored each line, not the merge.
    Walk(ctx context.Context, repositoryPath string, window WalkWindow) ([]Commit, string, error)
}

type WalkWindow struct { // the zero value walks all history
    Since string // a git --since value, e.g. "3 months ago"; empty means all history
    Until string // empty means up to HEAD
}

type Commit struct {
    Hash    string       // full commit hash — the addressability key for trends and the window
    Author  string       // ownership identity, "Name <email>"
    At      string       // authored time, RFC3339
    Changes []FileChange // the files this commit touched, with their line deltas
}

type FileChange struct {
    Path    string
    Added   int
    Deleted int
}

// SystemGitHistory is the shipped adapter, with no gitrepository import. Walk spawns TWO git
// invocations: `rev-parse HEAD` for the snapshot commit, then one
// `git log --no-merges --numstat` pass it parses into Commits.
func NewSystemGitHistory() *SystemGitHistory
```

🔶 **OD-CI-1 realized as neither offered option.** The register (`open-decisions.md` OD-CI-1) offers
`gitrepository.Inspector` (recommended) or a `codeinsight`-local reader **over `gitrepository`'s
`Backend`**. The library took a third road: a `codeinsight`-local `History` port with a
`SystemGitHistory` adapter that shells `git` directly. That keeps `gitrepository`'s frozen
`.apibaseline` untouched and the walk fakeable, at the cost of a second place that shells `git`. The
register row is not closed by this freeze — closing it is its own change.

## 3. The `Report` payload (the abstraction seam)

One envelope. Go types below; JSON tags are the wire shape. Every numeric datum is reproducible from
`(repository, window)` so a `Report` is replayable and diff-able across history.

```go
type Report struct {
    SchemaVersion string        `json:"schemaVersion"` // semver of THIS contract
    Repository    RepositoryRef `json:"repository"`
    Window        Window        `json:"window"`        // the commit range analyzed
    Entities      []Entity      `json:"entities"`      // per-file nodes (v1; §3 OD-CI-2)
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
    Since      string `json:"since,omitempty"`      // the WalkWindow selector verbatim: a git
    Until      string `json:"until,omitempty"`      // --since / --until value, NOT RFC3339
    Revisions  int    `json:"revisions"`            // commits in the window
}

type Entity struct {
    Path            string   `json:"path"`
    Kind            string   `json:"kind"`           // v1 emits "file" only (OD-CI-2)
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
    Coverage        *float64 `json:"coverage,omitempty"` // reserved; never populated in v1 (§4)
    PrimaryAuthor   string   `json:"primaryAuthor,omitempty"`
    AuthorCount     int      `json:"authorCount,omitempty"`
}

type Coupling struct {
    EntityA     string  `json:"entityA"`
    EntityB     string  `json:"entityB"`
    Degree      float64 `json:"degree"`              // 0–100 = sharedRevisions / averageRevisions
    SharedRevs  int     `json:"sharedRevisions"`     // the gated field: an edge needs
                                                     // SharedRevs ≥ Config.CouplingMinShared
    AverageRevs float64 `json:"averageRevisions"`    // the Degree denominator, not a gate
}

type Ownership struct {
    Path        string             `json:"path"`
    Authors     map[string]float64 `json:"authors"`  // author → fractional COMMIT ownership (0–1)
    BusFactor   int                `json:"busFactor"` // #authors covering >50% (default; OD-CI-3)
}

type Summary struct {
    Lines                int            `json:"lines"`
    EntityCount          int            `json:"entityCount"`
    TechnicalDebtRatio   float64        `json:"technicalDebtRatio"`   // SQALE; 0–1
    MaintainabilityRating string        `json:"maintainabilityRating"`// "A"…"E" (<5/<10/<20/<50/≥50%)
    Coverage             *float64       `json:"coverage,omitempty"`   // never populated in v1 (§4)
    BusFactor            int            `json:"busFactor"`            // the same >50% commit-share
                                                                      // rule, applied repo-wide
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

🔶 **OD-CI-2 realized as file granularity.** v1 emits one `Entity` per file and nothing else — no
directory/package roll-up is derived today, and method-level hotspots (CodeScene's "X-Ray") remain a
later refinement. The register row is not closed by this freeze.

## 4. Metric catalog binding

The `Report` fields realize research-note §2. Research confidence (✅ ratified · 🔶 derived) is a
separate axis from what v1 COMPUTES, so both are stated:

- **computed by v1** — ✅ cyclomatic, cognitive complexity (15/30), maintainability index (🔶 Halstead
  volume feeds it), debt ratio + A–E rating, hotspot, logical coupling, churn (relative preferred),
  ownership/bus-factor, code age.
- **ratified but NOT computed by v1** — ✅ Martin I/Ca/Ce (no `Report` field exists for them),
  ✅ DORA operationalization (`Summary.Dora` is declared and never populated), and coverage
  (`Entity.Coverage` / `Summary.Coverage` are declared, `omitempty`, and never assigned: no coverage
  profile is read anywhere, and `Config` names no coverage input). Each lands as an additive
  computation; the `Report` schema does **not** change.

**OD-CI-4 resolved → native-AST per-language `MetricProvider` port.** A `MetricProvider` computes the
static metrics for one language; the **Go provider computes cyclomatic + cognitive natively from
`go/ast`** (formulas verified, no subprocess), with Halstead volume from `go/scanner` per file.
Non-Go providers would shell to the language tool and parse JSON (TS/Svelte: dependency-cruiser
`-T json` for I/Ca/Ce + cycles, jscpd for duplication, knip for dead code — research §5a); **none is
shipped.** v1 ships the Go provider only (covers the `libs/go/*` self-feeding target); the port keeps
the rest additive. **Martin A/D have no emitting tool**, so abstractness would be computed natively
when a provider needs it. **DORA is partial without a deploy/incident feed:** deploy-frequency +
change-failure need CI/CD + incident data beyond the repo, so `Summary.Dora` stays `omitempty` until
a source is wired (only lead-time approximates from git merge→tag).

## 5. The `Views` render-plan → `@eden/visualization` (the 8 primitives)

```go
type View struct {
    ID            string         `json:"id"`
    Title         string         `json:"title"`
    Primitive     string         `json:"primitive"`    // one of the 8 widget primitives below
    AttentionPoint string        `json:"attentionPoint"`// "pre-commit"|"pull-request"|"release-gate"|"monitoring";
                                                        // v1's default plan emits the last three only
    Encoding      map[string]string `json:"encoding"`  // channel → report field, e.g. {"x":"churnRelative","y":"cyclomatic","size":"lines","color":"hotspotScore"}
    Source        string         `json:"source"`        // which Report collection feeds it: "entities"|"couplings"|"ownership"|"trends"|"summary"
}
```

🔶 The frontend is to iterate `Views` and, for each, instantiate the named primitive bound to the
encoded fields — so adding a view is data, not code. The eight primitives (research §5) are the
`@eden/visualization` asset set, each themeable via `@eden/theme` and gated by the UI math
(contrast/APCA, perceptual ordering) as a mechanical test dimension. **Neither half of that seam is
complete today, and the sentence above is the design, not the state:** `@eden/visualization` ships
one primitive, `hotspot-map` (its `.apibaseline` declares that single component), and no
`primitive`-token → component registry exists there yet, so the tokens the analyzer emits resolve to
nothing automatically. On the producer side the shipped default render-plan emits seven `View`s —
every row below except `heatmap`. Because `Views` is data, each remaining primitive and the registry
that resolves it land without a `Report` change:

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

`edenhttp` endpoint (consumer) → `codeinsight.New(configuration, dependencies)` →
`(*Analyzer).Analyze(ctx)` → `*Report` → JSON envelope → `@eden/visualization` renders `Views`. There
is no package-level `Analyze`: the pure spine builds the `Analyzer` once, and each `Analyze(ctx)` call
assembles one `Report`. SDLC attention points filter which views surface where:
**pre-commit** complexity delta · **PR review** hotspot + coupling on changed files ·
**release gate** ratings + coverage-on-new-code · **monitoring** trends + ownership SPOFs. First
self-feeding target: run `codeinsight` on the Eden monorepo itself (`libs/go/*`) and render the
hotspot map — Eden analyzing Eden.

## 7. Construction & obligations (10 §4 / ADR-0020)

`New(configuration Config, dependencies Deps) (*Analyzer, error)` spine · HNS-1 naming (no
`util`/`common`/`core`; `configuration` not `config`) · `context.Context` first on `Analyze` (`New`
is pure and takes none) · interfaces ≤5 methods, accept-interfaces-return-concrete · `Deps` injects
`History` + `[]MetricProvider` + `Clock`, and nothing else — no `gitrepository` reader and no
`observability` sink · public fakes in `codeinsighttest` · Go 1.26 floor · module path
`github.com/gophersys/libs/go/codeinsight`. Built phase-by-phase through `ctl.sh phase-gate
<architecture|implementation|testing|qa>` with the 8-dimension taxonomy on a **real** repository
fixture (a seeded git history — never mocked), TDD-order (fake + conformance red before bodies green),
and the frozen `.apibaseline` as the cardinal-sin guard.

The rest of that frozen surface — everything in `.apibaseline` that §2, §3 and §5 do not already
transcribe. A cardinal-sin guard the contract text does not carry cannot be read against it, so it is
recorded here rather than left to the baseline file alone:

```go
// SchemaVersion is the semver of the Report contract this library emits (§3).
const SchemaVersion = "0.1.0"

// Config selects what to analyze — the immutable, fully-resolved input. Zero values are valid: an
// empty Window walks all history and CouplingMinShared falls back to a young-repository floor.
type Config struct {
    RepositoryPath    string     // the local git repository to analyze (required)
    Identifier        string     // logical name stamped into the Report; empty derives it from the
                                 // path's base name. Never a secret or a URL carrying credentials.
    Window            WalkWindow // the history slice the temporal metrics are mined from
    CouplingMinShared int        // minimum SharedRevs for a coupling edge; 0 takes the floor
    MaxEntities       int        // cap entities by hotspot rank; 0 means all
    MaxCouplings      int        // cap coupling edges by degree; 0 means all
}

// Deps is the injected hexagon. New constructs no port and spawns no process.
type Deps struct {
    History   History          // the behavioral spine (§2). Required.
    Providers []MetricProvider // per-language static metrics; first Supports wins. ≥1 required.
    Clock     Clock            // stamps RepositoryRef.AnalyzedAt. Required.
}

// Clock keeps New pure and the fake deterministic.
type Clock interface{ Now() time.Time }

// MetricProvider computes the static metrics for one language. Two methods (≤5).
type MetricProvider interface {
    Supports(language string) bool
    // Metrics reports ok=false when the file cannot be analyzed — a skip, never fatal, so one odd
    // file never aborts a whole Report.
    Metrics(language, absolutePath string) (FileMetrics, bool)
}

// FileMetrics is the per-file static result. Cyclomatic and Cognitive are file sums; Maintainability
// is the LOC-weighted average of the PER-FUNCTION index, which is what stops a large file from
// saturating to 0 and rating everything E.
type FileMetrics struct {
    Lines           int
    Cyclomatic      int
    Cognitive       int
    Maintainability float64
}

// GoMetricProvider is the one provider v1 ships (§4).
func NewGoMetricProvider() *GoMetricProvider

// Analyzer is the concrete handle New returns: immutable after construction and safe for concurrent
// Analyze calls. The zero value is unusable.
type Analyzer struct{ /* unexported */ }

func (a *Analyzer) Analyze(ctx context.Context) (*Report, error)
func (a *Analyzer) RepositoryPath() string

// The error taxonomy: distinct types, each carrying the offending input — never a secret, never raw
// stderr — and each mapping to a stable errors.Kind, so the transport boundary needs no per-port
// table (errors.md, 10 §9). Inspect with errors.AsType; classify with errors.KindOf.
type InvalidInputError struct{ What string }       // -> errors.KindInvalid
type HistoryError struct{ Repository string }      // -> errors.KindUnavailable
```

## 8. Open forks — what the built library realized

All four were realized by the implementation that this freeze records. The rows in
`docs/architecture/open-decisions.md` are the register and still read Open; closing them is its own
change, not this freeze.

- **OD-CI-1** — history-walk home: realized as a `codeinsight`-local `History` port with a
  `SystemGitHistory` adapter shelling `git` directly (§2) — neither of the two offered options.
- **OD-CI-2** — entity granularity: realized as file only; no directory/package roll-up and no
  method-level X-Ray (§3).
- **OD-CI-3** — bus-factor algorithm: realized as the >50%-coverage rule the register recommends —
  the fewest authors whose combined share exceeds 50% — but over **COMMIT counts, not lines**, both
  per file and repo-wide. Line-level ownership is not computed anywhere.
- **OD-CI-4** — complexity source: realized as the native-AST `MetricProvider` port; the Go provider
  computes cyclomatic + cognitive from `go/ast` and Halstead volume from `go/scanner`, with no
  subprocess (§4).
