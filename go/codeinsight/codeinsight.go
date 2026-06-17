// Package codeinsight is the producer side of "point Eden at a codebase → generate the insight
// dashboards" feature (contract docs/architecture/contracts/codeinsight.md). It walks a local git
// repository and emits ONE self-describing Report — per-entity static + behavioral metrics, pairwise
// logical coupling, repo-level ratings, ownership, trends, and a Views render-plan — every datum
// stamped with the commit it was computed at. The Report is the abstraction seam: the Go analyzer
// (producer) and @eden/visualization (consumer) build independently against it.
//
// Module: github.com/gophersys/libs/go/codeinsight  (go 1.26)
//
// Hexagon: New(configuration, dependencies) is the pure construction spine (10 §4) — it validates
// its inputs and constructs nothing, reads no clock, spawns no process. The behavioral metrics are
// mined through the injected History port (the SystemGitHistory adapter shells `git log`); the
// static metrics come from the injected MetricProvider port (the GoMetricProvider computes
// cyclomatic / cognitive / Halstead volume / the maintainability index natively from go/ast, no
// subprocess); the analysis timestamp comes from the injected Clock. Each port is substitutable by
// a fake, so a Report is computed against a seeded real-git fixture in tests, never a mocked git.
//
// The maintainability index is computed PER FUNCTION and aggregated to the file as a LOC-weighted
// average (the design fix the PoC earned): summing a whole file's cyclomatic into one index
// saturates it to 0 on any large file, rating everything E. Per-function aggregation makes the
// rating discriminate. File cyclomatic/cognitive stay sums; only the maintainability index is
// aggregated from the per-function values.
//
// It is NOT a git engine (it consumes a History port), an HTTP server (an edenhttp consumer mounts
// it), a renderer (@eden/visualization owns pixels), or a linter/gate (it reads existing gate
// output like coverage profiles; it does not enforce).
//
// Concurrency: an Analyzer is immutable after New and safe for concurrent Analyze calls — it holds
// only the injected ports and the frozen configuration; the per-call state is local to Analyze.
package codeinsight

import (
	"context"
	"strings"
	"time"
)

// SchemaVersion is the semver of the Report contract this library emits (contract §3).
const SchemaVersion = "0.1.0"

// defaultCouplingMinShared is the young-repository floor for a coupling edge when Config leaves it
// zero. Research §3 prescribes ≥10 on mature repos; a low default keeps a fresh repo's couplings
// visible while the AverageRevs gate still suppresses accidental one-off co-change.
const defaultCouplingMinShared = 3

// History walks a repository's commit log into a structured stream of Commits (newest→oldest), the
// Go-native equivalent of PyDriller's Commit/ModifiedFile surface (contract §2). It is the behavioral
// spine: churn, change-frequency, hotspot, coupling, age, and ownership are all mined from it. The
// SystemGitHistory adapter shells one `git log --numstat` pass; a fake replays a fixed slice. One
// method (accept-interfaces, ≤5).
type History interface {
	// Walk returns the commits in the requested window, newest first. It also returns the current
	// HEAD commit hash (the commit the static snapshot is taken at). Merges are excluded so churn is
	// attributed to the commit that authored each line, not the merge.
	Walk(ctx context.Context, repositoryPath string, window WalkWindow) ([]Commit, string, error)
}

// MetricProvider computes the static metrics for one file of one language natively (OD-CI-4): the
// GoMetricProvider parses go/ast and needs no subprocess. A non-Go provider would shell its language
// tool; v1 ships the Go provider only, and the port keeps the rest additive. Two methods
// (accept-interfaces, ≤5).
type MetricProvider interface {
	// Supports reports whether this provider computes metrics for the given language token (e.g.
	// "go"). The analyzer skips a file whose language no provider supports — it reports the file
	// with its behavioral metrics only.
	Supports(language string) bool

	// Metrics computes the per-file static metrics for absolutePath (a file of a Supported language).
	// The bool is false when the file could not be analyzed (unreadable, unparseable, e.g. a
	// build-tagged source) — a skip, never fatal, so one odd file never aborts a whole report.
	Metrics(language, absolutePath string) (FileMetrics, bool)
}

// Clock stamps RepositoryRef.AnalyzedAt. Injecting it keeps New pure and the fake deterministic
// (mirrors gitrepository.Clock / observability.Clock).
type Clock interface{ Now() time.Time }

// WalkWindow selects the slice of history a History.Walk mines. The zero value walks all history.
type WalkWindow struct {
	// Since bounds the window below (a git --since value, e.g. "2026-01-01" or "3 months ago");
	// empty means "all history".
	Since string
	// Until bounds the window above; empty means "up to HEAD".
	Until string
}

// Commit is one mined revision: identity + the per-file line deltas it introduced. It is the unit a
// History yields and the analyzer folds into the behavioral metrics.
type Commit struct {
	// Hash is the commit's full hash (the addressability key for trends and the window).
	Hash string
	// Author is the ownership identity in "Name <email>" form.
	Author string
	// At is the authored time (RFC3339); the analyzer parses it for age and the churn trend.
	At string
	// Changes are the files this commit touched, with their line deltas.
	Changes []FileChange
}

// FileChange is one file touched by a commit, with its added/deleted line counts. A binary file
// reports zero line churn but still counts as a change for frequency and coupling.
type FileChange struct {
	Path    string
	Added   int
	Deleted int
}

// FileMetrics is the static per-file result a MetricProvider returns. Cyclomatic and Cognitive are
// the file sums; Maintainability is the LOC-weighted average of the per-function maintainability
// index (the design fix), so it does not saturate to 0 on a large file.
type FileMetrics struct {
	Lines           int
	Cyclomatic      int
	Cognitive       int
	Maintainability float64
}

// Config selects what to analyze. It is the immutable, fully-resolved input (the configuration
// pattern: parsed at the edge, frozen). Zero values are valid: an empty window analyzes all history,
// and CouplingMinShared defaults to a young-repository floor.
type Config struct {
	// RepositoryPath is the local git repository to analyze (required).
	RepositoryPath string
	// Identifier is the logical name stamped into the Report (never a secret/URL with credentials);
	// empty derives it from the repository path's base name.
	Identifier string
	// Window selects the slice of history the temporal metrics are mined from; the zero value walks
	// all history.
	Window WalkWindow
	// CouplingMinShared is the minimum shared revisions for a coupling edge to be emitted (research
	// §3: ≥10 on mature repos); zero defaults to a young-repository floor.
	CouplingMinShared int
	// MaxEntities caps the entities emitted, by hotspot rank; 0 means all.
	MaxEntities int
	// MaxCouplings caps the coupling edges emitted, by degree; 0 means all.
	MaxCouplings int
}

// Deps is the injected hexagon. New constructs no ports and spawns no process.
type Deps struct {
	// History walks the repository's commit log into the behavioral metric stream (the spine).
	// Required.
	History History
	// Providers compute the per-language static metrics; the analyzer routes each file to the first
	// provider that Supports its language. At least one is required.
	Providers []MetricProvider
	// Clock stamps the analysis time; keeps New pure and the fake deterministic. Required.
	Clock Clock
}

// Analyzer is the concrete handle returned by New. It is bound to one Config and the injected ports;
// Analyze assembles one Report per call. Immutable after New and safe for concurrent Analyze calls.
// Zero value unusable; construct via New.
type Analyzer struct {
	configuration Config
	history       History
	providers     []MetricProvider
	clock         Clock
}

// New is the pure constructor spine: no I/O, no clock read, no env read, no process spawn, no repo
// probe. It validates Config + Deps and returns the concrete *Analyzer. The first history walk and
// the first AST parse happen only on the first Analyze call.
//
//nolint:gocritic // contract §7 / 10 §4: New(configuration, dependencies) is the canon spine; Config/Deps pass by value (the frozen, copyable inputs).
func New(configuration Config, dependencies Deps) (*Analyzer, error) {
	if strings.TrimSpace(configuration.RepositoryPath) == "" {
		return nil, wrapKind(&InvalidInputError{What: "configuration.RepositoryPath must not be empty"})
	}
	if configuration.CouplingMinShared < 0 {
		return nil, wrapKind(&InvalidInputError{What: "configuration.CouplingMinShared must not be negative"})
	}
	if configuration.MaxEntities < 0 {
		return nil, wrapKind(&InvalidInputError{What: "configuration.MaxEntities must not be negative"})
	}
	if configuration.MaxCouplings < 0 {
		return nil, wrapKind(&InvalidInputError{What: "configuration.MaxCouplings must not be negative"})
	}
	if dependencies.History == nil {
		return nil, wrapKind(&InvalidInputError{What: "dependencies.History is required"})
	}
	if len(dependencies.Providers) == 0 {
		return nil, wrapKind(&InvalidInputError{What: "dependencies.Providers must have at least one MetricProvider"})
	}
	for index, provider := range dependencies.Providers {
		if provider == nil {
			return nil, wrapKind(&InvalidInputError{What: "dependencies.Providers contains a nil provider"})
		}
		_ = index
	}
	if dependencies.Clock == nil {
		return nil, wrapKind(&InvalidInputError{What: "dependencies.Clock is required"})
	}

	if configuration.CouplingMinShared == 0 {
		configuration.CouplingMinShared = defaultCouplingMinShared
	}

	providers := make([]MetricProvider, len(dependencies.Providers))
	copy(providers, dependencies.Providers)

	return &Analyzer{
		configuration: configuration,
		history:       dependencies.History,
		providers:     providers,
		clock:         dependencies.Clock,
	}, nil
}

// RepositoryPath reports the repository this Analyzer is bound to.
func (a *Analyzer) RepositoryPath() string { return a.configuration.RepositoryPath }
