package codeinsight

import (
	"context"
	"math"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/gophersys/libs/go/errors"
)

// fileStat accumulates the per-file aggregates mined from history.
type fileStat struct {
	path          string
	churn         int
	changes       int
	authorCommits map[string]int
	lastCommit    time.Time
}

// Analyze walks the repository and assembles one Report: mine history → aggregate → compute the
// verified metrics → emit the Report plus its Views render-plan (contract §1). It honors context
// cancellation (the History port short-circuits) and never mutates the Analyzer.
func (a *Analyzer) Analyze(ctx context.Context) (*Report, error) {
	if err := errors.FromContext(ctx); err != nil {
		return nil, err
	}

	commits, head, err := a.history.Walk(ctx, a.configuration.RepositoryPath, a.configuration.Window)
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable,
			(&HistoryError{Repository: a.identifier()}).Error(), err)
	}

	stats, pairs, newest := aggregate(commits)
	entities := a.buildEntities(stats, newest)
	rankEntities(entities)
	couplings := buildCouplings(pairs, stats, a.configuration.CouplingMinShared)
	ownership := buildOwnership(stats)

	report := &Report{
		SchemaVersion: SchemaVersion,
		Repository: RepositoryRef{
			Identifier:  a.identifier(),
			HeadCommit:  head,
			AnalyzedAt:  a.clock.Now().UTC().Format(time.RFC3339),
			CommitCount: len(commits),
		},
		Window:    buildWindow(commits, a.configuration.Window),
		Entities:  capEntities(entities, a.configuration.MaxEntities),
		Couplings: capCouplings(couplings, a.configuration.MaxCouplings),
		Ownership: ownership,
		Summary:   buildSummary(entities, stats),
		Trends:    buildChurnTrend(commits),
		Views:     defaultViews(),
	}
	return report, nil
}

// identifier resolves the logical repository name: the configured Identifier, else the repository
// path's base name.
func (a *Analyzer) identifier() string {
	if a.configuration.Identifier != "" {
		return a.configuration.Identifier
	}
	return filepath.Base(strings.TrimRight(a.configuration.RepositoryPath, "/"))
}

// metricsFor routes a file to the first provider that Supports its language and returns the static
// metrics. A file no provider supports, or one a provider cannot analyze, yields ok=false.
func (a *Analyzer) metricsFor(language, path string) (FileMetrics, bool) {
	if language == "" {
		return FileMetrics{}, false
	}
	for _, provider := range a.providers {
		if !provider.Supports(language) {
			continue
		}
		return provider.Metrics(language, filepath.Join(a.configuration.RepositoryPath, path))
	}
	return FileMetrics{}, false
}

// aggregate folds the commit stream into per-file stats and pairwise co-change counts, returning the
// stats, the co-change pairs, and the newest authored time seen (the reference for code age).
func aggregate(commits []Commit) (stats map[string]*fileStat, pairs map[pairKey]int, newest time.Time) {
	stats = map[string]*fileStat{}
	pairs = map[pairKey]int{}
	for index := range commits {
		newest = foldCommit(&commits[index], stats, pairs, newest)
	}
	return stats, pairs, newest
}

// foldCommit folds one commit's deltas into the running stats + co-change pairs and advances the
// newest-seen timestamp.
func foldCommit(c *Commit, stats map[string]*fileStat, pairs map[pairKey]int, newest time.Time) time.Time {
	when, _ := time.Parse(time.RFC3339, c.At) //nolint:errcheck // a malformed timestamp folds as the zero time (never "newest"); the commit's churn/coupling still counts.
	if when.After(newest) {
		newest = when
	}
	touched := make([]string, 0, len(c.Changes))
	for _, delta := range c.Changes {
		stat := stats[delta.Path]
		if stat == nil {
			stat = &fileStat{path: delta.Path, authorCommits: map[string]int{}}
			stats[delta.Path] = stat
		}
		stat.churn += delta.Added + delta.Deleted
		stat.changes++
		stat.authorCommits[c.Author]++
		if when.After(stat.lastCommit) {
			stat.lastCommit = when
		}
		touched = append(touched, delta.Path)
	}
	recordCoChanges(touched, pairs)
	return newest
}

// pairKey is an order-independent key for a pair of co-changed files (coupling is symmetric).
type pairKey struct{ a, b string }

// makePairKey returns the order-independent key for a file pair.
func makePairKey(x, y string) pairKey {
	if x < y {
		return pairKey{x, y}
	}
	return pairKey{y, x}
}

// recordCoChanges increments the co-change count for every unique file pair in a commit.
func recordCoChanges(touched []string, pairs map[pairKey]int) {
	unique := dedupeSorted(touched)
	for i := 0; i < len(unique); i++ {
		for j := i + 1; j < len(unique); j++ {
			pairs[makePairKey(unique[i], unique[j])]++
		}
	}
}

// dedupeSorted returns the sorted, de-duplicated copy of values.
func dedupeSorted(values []string) []string {
	if len(values) == 0 {
		return nil
	}
	sorted := append([]string(nil), values...)
	sort.Strings(sorted)
	out := sorted[:1]
	for _, v := range sorted[1:] {
		if v != out[len(out)-1] {
			out = append(out, v)
		}
	}
	return out
}

// buildEntities turns the per-file stats into Entity rows, attaching native-AST static metrics for
// files of a Supported language and the relative-churn / age behavioral metrics for all files.
func (a *Analyzer) buildEntities(stats map[string]*fileStat, newest time.Time) []Entity {
	entities := make([]Entity, 0, len(stats))
	for _, stat := range stats {
		entities = append(entities, a.buildEntity(stat, newest))
	}
	return entities
}

// buildEntity assembles one Entity from its file stat: behavioral metrics for every file, static
// metrics for a file whose language a provider supports.
func (a *Analyzer) buildEntity(stat *fileStat, newest time.Time) Entity {
	entity := Entity{
		Path:            stat.path,
		Kind:            "file",
		Language:        languageOf(stat.path),
		ChurnAbsolute:   stat.churn,
		ChangeFrequency: stat.changes,
		AgeDays:         daysBetween(stat.lastCommit, newest),
	}
	primary, count := primaryAuthor(stat.authorCommits)
	entity.PrimaryAuthor = primary
	entity.AuthorCount = count

	if metrics, ok := a.metricsFor(entity.Language, stat.path); ok {
		entity.Lines = metrics.Lines
		entity.Cyclomatic = metrics.Cyclomatic
		entity.Cognitive = metrics.Cognitive
		entity.Maintainability = round(metrics.Maintainability, 1)
	}
	if entity.Lines > 0 {
		entity.ChurnRelative = round(float64(stat.churn)/float64(entity.Lines), 3)
	}
	return entity
}

// rankEntities computes the normalized hotspot score (changeFrequency × complexity) and sorts
// entities by it, descending — the active-development triage order (research §3).
func rankEntities(entities []Entity) {
	maxProduct := 0.0
	products := make([]float64, len(entities))
	for i := range entities {
		complexity := entities[i].Cyclomatic
		if complexity == 0 {
			complexity = 1 // non-Go / unparsed files still rank by change frequency
		}
		products[i] = float64(entities[i].ChangeFrequency) * float64(complexity)
		if products[i] > maxProduct {
			maxProduct = products[i]
		}
	}
	for i := range entities {
		if maxProduct > 0 {
			entities[i].HotspotScore = round(products[i]/maxProduct, 3)
		}
	}
	sort.SliceStable(entities, func(i, j int) bool {
		return entities[i].HotspotScore > entities[j].HotspotScore
	})
}

// buildCouplings emits a coupling edge per file pair whose shared-revision count clears the floor.
// Degree = sharedRevs / averageRevs × 100 (code-maat's definition, research §3).
func buildCouplings(pairs map[pairKey]int, stats map[string]*fileStat, minShared int) []Coupling {
	couplings := make([]Coupling, 0)
	for key, shared := range pairs {
		coupling, ok := couplingFor(key, shared, stats, minShared)
		if ok {
			couplings = append(couplings, coupling)
		}
	}
	sort.SliceStable(couplings, func(i, j int) bool {
		return couplings[i].Degree > couplings[j].Degree
	})
	return couplings
}

// couplingFor builds one coupling edge for a file pair, or ok=false when it fails the shared-revision
// floor or has no revisions to average.
func couplingFor(key pairKey, shared int, stats map[string]*fileStat, minShared int) (Coupling, bool) {
	if shared < minShared {
		return Coupling{}, false
	}
	statA, statB := stats[key.a], stats[key.b]
	if statA == nil || statB == nil {
		return Coupling{}, false
	}
	averageRevs := float64(statA.changes+statB.changes) / 2.0
	if averageRevs == 0 {
		return Coupling{}, false
	}
	return Coupling{
		EntityA:     key.a,
		EntityB:     key.b,
		Degree:      round(float64(shared)/averageRevs*100, 1),
		SharedRevs:  shared,
		AverageRevs: round(averageRevs, 1),
	}, true
}

// buildOwnership derives fractional author ownership and a >50%-coverage bus factor per file
// (OD-CI-3 default: the fewest authors whose combined share exceeds half the commits).
func buildOwnership(stats map[string]*fileStat) []Ownership {
	ownership := make([]Ownership, 0, len(stats))
	for _, stat := range stats {
		owned, ok := ownershipFor(stat)
		if ok {
			ownership = append(ownership, owned)
		}
	}
	sort.SliceStable(ownership, func(i, j int) bool { return ownership[i].Path < ownership[j].Path })
	return ownership
}

// ownershipFor computes one file's fractional ownership and bus factor, or ok=false for a file with
// no recorded authorship.
func ownershipFor(stat *fileStat) (Ownership, bool) {
	total := 0
	for _, n := range stat.authorCommits {
		total += n
	}
	if total == 0 {
		return Ownership{}, false
	}
	authors := make(map[string]float64, len(stat.authorCommits))
	shares := make([]float64, 0, len(stat.authorCommits))
	for author, n := range stat.authorCommits {
		share := float64(n) / float64(total)
		authors[author] = round(share, 3)
		shares = append(shares, share)
	}
	return Ownership{Path: stat.path, Authors: authors, BusFactor: busFactor(shares)}, true
}

// busFactor is the fewest top contributors whose combined ownership exceeds 50%.
func busFactor(shares []float64) int {
	sorted := append([]float64(nil), shares...)
	sort.Sort(sort.Reverse(sort.Float64Slice(sorted)))
	cumulative, count := 0.0, 0
	for _, share := range sorted {
		cumulative += share
		count++
		if cumulative > 0.5 {
			break
		}
	}
	return count
}

// buildSummary computes the repo-level scalars. TechnicalDebtRatio is the fraction of analyzed lines
// living in files below the maintainability "green" band (MI < 20), mapped to an A–E rating via the
// SQALE bands (research §2 F5).
func buildSummary(entities []Entity, stats map[string]*fileStat) Summary {
	totalLines, redLines := 0, 0
	for i := range entities {
		totalLines += entities[i].Lines
		if entities[i].Lines > 0 && entities[i].Maintainability < 20 {
			redLines += entities[i].Lines
		}
	}
	debtRatio := 0.0
	if totalLines > 0 {
		debtRatio = float64(redLines) / float64(totalLines)
	}
	return Summary{
		Lines:                 totalLines,
		EntityCount:           len(entities),
		TechnicalDebtRatio:    round(debtRatio, 3),
		MaintainabilityRating: sqaleRating(debtRatio),
		BusFactor:             repositoryBusFactor(stats),
	}
}

// sqaleRating maps a debt ratio to the A–E maintainability rating (research §2 F5).
func sqaleRating(ratio float64) string {
	switch {
	case ratio < 0.05:
		return "A"
	case ratio < 0.10:
		return "B"
	case ratio < 0.20:
		return "C"
	case ratio < 0.50:
		return "D"
	default:
		return "E"
	}
}

// repositoryBusFactor applies the >50% rule across total commit authorship (research §3: typically
// 2–3 even on large teams).
func repositoryBusFactor(stats map[string]*fileStat) int {
	totals := map[string]int{}
	grand := 0
	for _, stat := range stats {
		for author, n := range stat.authorCommits {
			totals[author] += n
			grand += n
		}
	}
	if grand == 0 {
		return 0
	}
	shares := make([]float64, 0, len(totals))
	for _, n := range totals {
		shares = append(shares, float64(n)/float64(grand))
	}
	return busFactor(shares)
}

// buildChurnTrend buckets commits by month and emits one commit-hash-stamped point per bucket — the
// long-term monitoring series (contract §3 TrendPoint).
func buildChurnTrend(commits []Commit) []TrendSeries {
	order, buckets := bucketChurnByMonth(commits)
	if len(order) == 0 {
		return nil
	}
	sort.Strings(order) // chronological
	points := make([]TrendPoint, 0, len(order))
	for _, key := range order {
		b := buckets[key]
		points = append(points, TrendPoint{
			Commit: b.commit,
			At:     b.at.UTC().Format(time.RFC3339),
			Value:  float64(b.churn),
		})
	}
	return []TrendSeries{{Metric: "churn", Points: points}}
}

// churnBucket accumulates a calendar month's churn and the latest commit in that month.
type churnBucket struct {
	churn  int
	commit string
	at     time.Time
}

// bucketChurnByMonth folds commits (newest→oldest) into per-month churn buckets, recording each
// bucket's latest commit hash for addressability.
func bucketChurnByMonth(commits []Commit) (order []string, buckets map[string]*churnBucket) {
	order = []string{}
	buckets = map[string]*churnBucket{}
	for index := range commits {
		c := &commits[index]
		when, err := time.Parse(time.RFC3339, c.At)
		if err != nil {
			continue
		}
		key := when.Format("2006-01")
		b := buckets[key]
		if b == nil {
			b = &churnBucket{}
			buckets[key] = b
			order = append(order, key)
		}
		for _, delta := range c.Changes {
			b.churn += delta.Added + delta.Deleted
		}
		// commits stream newest→oldest, so the first seen in a bucket is its latest commit.
		if b.commit == "" {
			b.commit, b.at = c.Hash, when
		}
	}
	return order, buckets
}

// buildWindow records which slice of history fed the temporal metrics, with the commit hashes that
// make a Report reproducible at a point in history.
func buildWindow(commits []Commit, selector WalkWindow) Window {
	window := Window{
		Since:     selector.Since,
		Until:     selector.Until,
		Revisions: len(commits),
	}
	if len(commits) > 0 {
		window.ToCommit = commits[0].Hash                // newest
		window.FromCommit = commits[len(commits)-1].Hash // oldest in window
	}
	return window
}

// capEntities truncates the entity list to max (by hotspot rank); 0 means all.
func capEntities(entities []Entity, maxCount int) []Entity {
	if maxCount > 0 && len(entities) > maxCount {
		return entities[:maxCount]
	}
	return entities
}

// capCouplings truncates the coupling list to max (by degree); 0 means all.
func capCouplings(couplings []Coupling, maxCount int) []Coupling {
	if maxCount > 0 && len(couplings) > maxCount {
		return couplings[:maxCount]
	}
	return couplings
}

// primaryAuthor returns the author with the most commits (ties broken by name) and the total
// distinct author count.
func primaryAuthor(authorCommits map[string]int) (primary string, authorCount int) {
	best, bestCount := "", 0
	for author, n := range authorCommits {
		if n > bestCount || (n == bestCount && author < best) {
			best, bestCount = author, n
		}
	}
	return best, len(authorCommits)
}

// languageOf maps a file extension to its language token (contract §3 Entity.Language).
func languageOf(path string) string {
	switch strings.ToLower(filepath.Ext(path)) {
	case ".go":
		return "go"
	case ".ts", ".tsx":
		return "typescript"
	case ".svelte":
		return "svelte"
	case ".js", ".mjs", ".cjs":
		return "javascript"
	case ".md":
		return "markdown"
	default:
		return ""
	}
}

// daysBetween returns the whole-day span between two times, 0 if either is zero.
func daysBetween(earlier, later time.Time) int {
	if earlier.IsZero() || later.IsZero() {
		return 0
	}
	return int(later.Sub(earlier).Hours() / 24)
}

// round rounds value to the given number of decimal places.
func round(value float64, places int) float64 {
	scale := math.Pow(10, float64(places))
	return math.Round(value*scale) / scale
}
