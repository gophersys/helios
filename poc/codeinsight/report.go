// Package codeinsight is the proof-of-concept analyzer for the "point Eden at a
// codebase → generate the insight dashboards" feature. It walks an arbitrary git
// repository and emits one self-describing Report — the schema frozen in
// docs/architecture/contracts/codeinsight.md (§3). This PoC validates that contract
// and the verified metric formulas (docs/research/06-codebase-insight-visualization.md)
// against the real Eden repository before the gated libs/go/codeinsight build.
//
// Scope of the PoC: the verified behavioral spine (churn, change-frequency, hotspot,
// logical coupling, ownership/bus-factor) plus native-AST static metrics for Go
// (cyclomatic, a cognitive approximation, Halstead volume → maintainability index).
// Non-Go languages, the SQALE rule engine, and DORA (which needs a deploy/incident feed)
// are out of scope here and surface as omitempty fields, exactly as the contract states.
package codeinsight

// Report is the single self-describing result envelope (contract §3). Every numeric
// datum is reproducible from (Repository, Window) so a Report replays and diffs across
// history.
type Report struct {
	SchemaVersion string        `json:"schemaVersion"`
	Repository    RepositoryRef `json:"repository"`
	Window        Window        `json:"window"`
	Entities      []Entity      `json:"entities"`
	Couplings     []Coupling    `json:"couplings"`
	Ownership     []Ownership   `json:"ownership"`
	Summary       Summary       `json:"summary"`
	Trends        []TrendSeries `json:"trends"`
	Views         []View        `json:"views"`
}

// RepositoryRef identifies the analyzed repository at the commit the snapshot was taken.
type RepositoryRef struct {
	Identifier  string `json:"identifier"`
	HeadCommit  string `json:"headCommit"`
	AnalyzedAt  string `json:"analyzedAt"`
	CommitCount int    `json:"commitCount"`
}

// Window is the slice of history that fed the temporal metrics.
type Window struct {
	FromCommit string `json:"fromCommit,omitempty"`
	ToCommit   string `json:"toCommit"`
	Since      string `json:"since,omitempty"`
	Until      string `json:"until,omitempty"`
	Revisions  int    `json:"revisions"`
}

// Entity is a per-file node carrying its static + behavioral metrics.
type Entity struct {
	Path            string   `json:"path"`
	Kind            string   `json:"kind"`
	Language        string   `json:"language,omitempty"`
	Lines           int      `json:"lines"`
	Cyclomatic      int      `json:"cyclomatic,omitempty"`
	Cognitive       int      `json:"cognitive,omitempty"`
	Maintainability float64  `json:"maintainability,omitempty"`
	ChurnAbsolute   int      `json:"churnAbsolute"`
	ChurnRelative   float64  `json:"churnRelative"`
	ChangeFrequency int      `json:"changeFrequency"`
	HotspotScore    float64  `json:"hotspotScore"`
	AgeDays         int      `json:"ageDays"`
	Coverage        *float64 `json:"coverage,omitempty"`
	PrimaryAuthor   string   `json:"primaryAuthor,omitempty"`
	AuthorCount     int      `json:"authorCount,omitempty"`
}

// Coupling is a pairwise logical-coupling edge: files that repeatedly change together.
// Degree is symmetric (same-commit co-change cannot indicate direction — research §3).
type Coupling struct {
	EntityA     string  `json:"entityA"`
	EntityB     string  `json:"entityB"`
	Degree      float64 `json:"degree"`
	SharedRevs  int     `json:"sharedRevisions"`
	AverageRevs float64 `json:"averageRevisions"`
}

// Ownership maps authors to their fractional ownership of a file and the file's bus factor.
type Ownership struct {
	Path      string             `json:"path"`
	Authors   map[string]float64 `json:"authors"`
	BusFactor int                `json:"busFactor"`
}

// Summary holds the repo-level scalars and the A–E maintainability rating.
type Summary struct {
	Lines                 int               `json:"lines"`
	EntityCount           int               `json:"entityCount"`
	TechnicalDebtRatio    float64           `json:"technicalDebtRatio"`
	MaintainabilityRating string            `json:"maintainabilityRating"`
	Coverage              *float64          `json:"coverage,omitempty"`
	BusFactor             int               `json:"busFactor"`
	Dora                  *DoraKeys         `json:"dora,omitempty"`
	Ratings               map[string]string `json:"ratings,omitempty"`
}

// DoraKeys is reserved (contract §4): populated only when a deploy/incident feed is wired,
// since deploy-frequency and change-failure-rate need data beyond the git repository.
type DoraKeys struct {
	DeploymentFrequency string  `json:"deploymentFrequency,omitempty"`
	LeadTimeHours       float64 `json:"leadTimeHours,omitempty"`
	ChangeFailureRate   float64 `json:"changeFailureRate,omitempty"`
	RecoveryHours       float64 `json:"recoveryHours,omitempty"`
	Performer           string  `json:"performer,omitempty"`
}

// TrendSeries is a commit-hash-stamped time series for the long-term monitoring lens.
type TrendSeries struct {
	Metric string       `json:"metric"`
	Points []TrendPoint `json:"points"`
}

// TrendPoint samples one metric at one commit.
type TrendPoint struct {
	Commit string  `json:"commit"`
	At     string  `json:"at"`
	Value  float64 `json:"value"`
}

// View is one entry in the dynamic render-plan: which widget primitive renders which
// slice of the Report at which SDLC attention point (contract §5).
type View struct {
	ID             string            `json:"id"`
	Title          string            `json:"title"`
	Primitive      string            `json:"primitive"`
	AttentionPoint string            `json:"attentionPoint"`
	Encoding       map[string]string `json:"encoding"`
	Source         string            `json:"source"`
}
