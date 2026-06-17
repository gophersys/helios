package codeinsight

// Report is the single self-describing result envelope (contract §3). Every numeric datum is
// reproducible from (Repository, Window) so a Report replays and diffs across history. It is both
// the in-process Go API and the JSON wire shape an edenhttp consumer serves to @eden/visualization.
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

// RepositoryRef identifies the analyzed repository at the commit the snapshot was taken. The
// Identifier is a logical name, never a secret or a URL carrying credentials (contract §3).
type RepositoryRef struct {
	Identifier  string `json:"identifier"`
	HeadCommit  string `json:"headCommit"`
	AnalyzedAt  string `json:"analyzedAt"`
	CommitCount int    `json:"commitCount"`
}

// Window is the slice of history that fed the temporal metrics. The commit hashes make every
// view reproducible at a point in history and let two reports diff cleanly (contract §3).
type Window struct {
	FromCommit string `json:"fromCommit,omitempty"`
	ToCommit   string `json:"toCommit"`
	Since      string `json:"since,omitempty"`
	Until      string `json:"until,omitempty"`
	Revisions  int    `json:"revisions"`
}

// Entity is a per-file node carrying its static + behavioral metrics. Maintainability is the
// LOC-weighted average of the per-function maintainability index (contract §4 / the design fix):
// computing it per function and aggregating keeps a large file from saturating to a uniform E.
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

// Coupling is a pairwise logical-coupling edge: files that repeatedly change together. Degree is
// symmetric (a same-commit co-change cannot indicate direction — research §3).
type Coupling struct {
	EntityA     string  `json:"entityA"`
	EntityB     string  `json:"entityB"`
	Degree      float64 `json:"degree"`
	SharedRevs  int     `json:"sharedRevisions"`
	AverageRevs float64 `json:"averageRevisions"`
}

// Ownership maps authors to their fractional ownership of a file and the file's bus factor (the
// fewest authors whose combined share exceeds 50%, OD-CI-3 default).
type Ownership struct {
	Path      string             `json:"path"`
	Authors   map[string]float64 `json:"authors"`
	BusFactor int                `json:"busFactor"`
}

// Summary holds the repo-level scalars and the A–E maintainability rating (contract §3).
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

// DoraKeys is reserved (contract §4): populated only when a deploy/incident feed is wired, since
// deploy-frequency and change-failure-rate need data beyond the git repository.
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

// TrendPoint samples one metric at one commit (the commit hash makes the sample reproducible).
type TrendPoint struct {
	Commit string  `json:"commit"`
	At     string  `json:"at"`
	Value  float64 `json:"value"`
}

// View is one entry in the dynamic render-plan: which widget primitive renders which slice of the
// Report at which SDLC attention point (contract §5). The frontend iterates Views and instantiates
// the named primitive bound to the encoded fields — so adding a view is data, not code.
type View struct {
	ID             string            `json:"id"`
	Title          string            `json:"title"`
	Primitive      string            `json:"primitive"`
	AttentionPoint string            `json:"attentionPoint"`
	Encoding       map[string]string `json:"encoding"`
	Source         string            `json:"source"`
}
