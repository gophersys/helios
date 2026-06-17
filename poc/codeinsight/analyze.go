package codeinsight

import (
	"context"
	"math"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// SchemaVersion is the semver of the Report contract this PoC emits.
const SchemaVersion = "0.1.0-poc"

// Config selects what to analyze. Zero values are valid: an empty Since analyzes all
// history, and CouplingMinShared defaults to a young-repository floor.
type Config struct {
	RepositoryPath    string
	Identifier        string
	Since             string // git --since window bound; empty = full history
	Until             string
	CouplingMinShared int // minimum shared revisions for a coupling edge (research §3: ≥10 on mature repos)
	MaxEntities       int // cap on entities emitted, by hotspot rank; 0 = all
	MaxCouplings      int // cap on coupling edges emitted, by degree; 0 = all
}

// fileStat accumulates the per-file aggregates mined from history.
type fileStat struct {
	path          string
	churn         int
	changes       int
	authorCommits map[string]int
	lastCommit    time.Time
}

// Analyze walks the repository and assembles one Report. It is the PoC realization of the
// contract's Analyze entrypoint (contract §1): mine history → aggregate → compute the
// verified metrics → emit the Report plus its Views render-plan.
func Analyze(ctx context.Context, configuration Config) (*Report, error) {
	if configuration.CouplingMinShared == 0 {
		configuration.CouplingMinShared = 3
	}
	identifier := configuration.Identifier
	if identifier == "" {
		identifier = filepath.Base(strings.TrimRight(configuration.RepositoryPath, "/"))
	}

	head, err := headCommit(ctx, configuration.RepositoryPath)
	if err != nil {
		return nil, err
	}
	commits, err := mineHistory(ctx, configuration.RepositoryPath, historyOptions{
		since: configuration.Since,
		until: configuration.Until,
	})
	if err != nil {
		return nil, err
	}

	stats, pairs, newest := aggregate(commits)
	entities := buildEntities(configuration.RepositoryPath, stats, newest)
	rankEntities(entities)
	couplings := buildCouplings(pairs, stats, configuration.CouplingMinShared)
	ownership := buildOwnership(stats)

	report := &Report{
		SchemaVersion: SchemaVersion,
		Repository: RepositoryRef{
			Identifier:  identifier,
			HeadCommit:  head,
			AnalyzedAt:  time.Now().UTC().Format(time.RFC3339),
			CommitCount: len(commits),
		},
		Window:    buildWindow(commits, configuration),
		Entities:  capEntities(entities, configuration.MaxEntities),
		Couplings: capCouplings(couplings, configuration.MaxCouplings),
		Ownership: ownership,
		Summary:   buildSummary(entities, stats),
		Trends:    buildChurnTrend(commits),
		Views:     defaultViews(),
	}
	return report, nil
}

// aggregate folds the commit stream into per-file stats and pairwise co-change counts.
func aggregate(commits []commit) (map[string]*fileStat, map[pairKey]int, time.Time) {
	stats := map[string]*fileStat{}
	pairs := map[pairKey]int{}
	var newest time.Time

	for _, c := range commits {
		when, _ := time.Parse(time.RFC3339, c.dateISO)
		if when.After(newest) {
			newest = when
		}
		touched := make([]string, 0, len(c.changes))
		for _, delta := range c.changes {
			stat := stats[delta.path]
			if stat == nil {
				stat = &fileStat{path: delta.path, authorCommits: map[string]int{}}
				stats[delta.path] = stat
			}
			stat.churn += delta.added + delta.deleted
			stat.changes++
			stat.authorCommits[c.authorKey]++
			if when.After(stat.lastCommit) {
				stat.lastCommit = when
			}
			touched = append(touched, delta.path)
		}
		recordCoChanges(touched, pairs)
	}
	return stats, pairs, newest
}

// pairKey is an order-independent key for a pair of co-changed files (coupling is symmetric).
type pairKey struct{ a, b string }

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

// buildEntities turns the per-file stats into Entity rows, attaching native-AST static
// metrics for Go files and the relative-churn / age behavioral metrics for all files.
func buildEntities(repoPath string, stats map[string]*fileStat, newest time.Time) []Entity {
	entities := make([]Entity, 0, len(stats))
	for _, stat := range stats {
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

		if strings.HasSuffix(stat.path, ".go") && !strings.HasSuffix(stat.path, "_test.go") {
			if metrics, ok := analyzeGoFile(filepath.Join(repoPath, stat.path)); ok {
				entity.Lines = metrics.lines
				entity.Cyclomatic = metrics.cyclomatic
				entity.Cognitive = metrics.cognitive
				entity.Maintainability = round(metrics.maintainability, 1)
			}
		}
		if entity.Lines > 0 {
			entity.ChurnRelative = round(float64(stat.churn)/float64(entity.Lines), 3)
		}
		entities = append(entities, entity)
	}
	return entities
}

// rankEntities computes the normalized hotspot score (changeFrequency × complexity) and
// sorts entities by it, descending — the active-development triage order (research §3).
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

// buildCouplings emits a coupling edge per file pair whose shared-revision count clears the
// floor. Degree = sharedRevs / averageRevs × 100 (code-maat's definition, research §3).
func buildCouplings(pairs map[pairKey]int, stats map[string]*fileStat, minShared int) []Coupling {
	couplings := make([]Coupling, 0)
	for key, shared := range pairs {
		if shared < minShared {
			continue
		}
		statA, statB := stats[key.a], stats[key.b]
		if statA == nil || statB == nil {
			continue
		}
		averageRevs := float64(statA.changes+statB.changes) / 2.0
		if averageRevs == 0 {
			continue
		}
		couplings = append(couplings, Coupling{
			EntityA:     key.a,
			EntityB:     key.b,
			Degree:      round(float64(shared)/averageRevs*100, 1),
			SharedRevs:  shared,
			AverageRevs: round(averageRevs, 1),
		})
	}
	sort.SliceStable(couplings, func(i, j int) bool {
		return couplings[i].Degree > couplings[j].Degree
	})
	return couplings
}

// buildOwnership derives fractional author ownership and a >50%-coverage bus factor per file
// (OD-CI-3 default: the fewest authors whose combined share exceeds half the commits).
func buildOwnership(stats map[string]*fileStat) []Ownership {
	ownership := make([]Ownership, 0, len(stats))
	for _, stat := range stats {
		total := 0
		for _, n := range stat.authorCommits {
			total += n
		}
		if total == 0 {
			continue
		}
		authors := make(map[string]float64, len(stat.authorCommits))
		shares := make([]float64, 0, len(stat.authorCommits))
		for author, n := range stat.authorCommits {
			share := float64(n) / float64(total)
			authors[author] = round(share, 3)
			shares = append(shares, share)
		}
		ownership = append(ownership, Ownership{
			Path:      stat.path,
			Authors:   authors,
			BusFactor: busFactor(shares),
		})
	}
	sort.SliceStable(ownership, func(i, j int) bool { return ownership[i].Path < ownership[j].Path })
	return ownership
}

// busFactor is the fewest top contributors whose combined ownership exceeds 50%.
func busFactor(shares []float64) int {
	sort.Sort(sort.Reverse(sort.Float64Slice(shares)))
	cumulative, count := 0.0, 0
	for _, share := range shares {
		cumulative += share
		count++
		if cumulative > 0.5 {
			break
		}
	}
	return count
}

// buildSummary computes the repo-level scalars. TechnicalDebtRatio is a transparent PoC
// proxy — the fraction of analyzed lines living in files below the maintainability "green"
// band (MI < 20) — mapped to an A–E rating via the SQALE bands (research §2 F5). The gated
// library replaces this with the real SQALE rule-engine debt ratio.
func buildSummary(entities []Entity, stats map[string]*fileStat) Summary {
	totalLines, redLines := 0, 0
	for _, e := range entities {
		totalLines += e.Lines
		if e.Lines > 0 && e.Maintainability < 20 {
			redLines += e.Lines
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

// repositoryBusFactor applies the >50% rule across total commit authorship (research §3:
// typically 2–3 even on large teams).
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

// buildChurnTrend buckets commits by month and emits one commit-hash-stamped point per
// bucket — the long-term monitoring series (contract §3 TrendPoint).
func buildChurnTrend(commits []commit) []TrendSeries {
	type bucket struct {
		churn  int
		commit string
		at     time.Time
	}
	order := []string{}
	buckets := map[string]*bucket{}
	for _, c := range commits {
		when, err := time.Parse(time.RFC3339, c.dateISO)
		if err != nil {
			continue
		}
		key := when.Format("2006-01")
		b := buckets[key]
		if b == nil {
			b = &bucket{}
			buckets[key] = b
			order = append(order, key)
		}
		for _, delta := range c.changes {
			b.churn += delta.added + delta.deleted
		}
		// commits stream newest→oldest, so the first seen in a bucket is its latest commit.
		if b.commit == "" {
			b.commit, b.at = c.hash, when
		}
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
	if len(points) == 0 {
		return nil
	}
	return []TrendSeries{{Metric: "churn", Points: points}}
}

func buildWindow(commits []commit, configuration Config) Window {
	window := Window{
		ToCommit:  "",
		Since:     configuration.Since,
		Until:     configuration.Until,
		Revisions: len(commits),
	}
	if len(commits) > 0 {
		window.ToCommit = commits[0].hash                // newest
		window.FromCommit = commits[len(commits)-1].hash // oldest in window
	}
	return window
}

func capEntities(entities []Entity, max int) []Entity {
	if max > 0 && len(entities) > max {
		return entities[:max]
	}
	return entities
}

func capCouplings(couplings []Coupling, max int) []Coupling {
	if max > 0 && len(couplings) > max {
		return couplings[:max]
	}
	return couplings
}

func primaryAuthor(authorCommits map[string]int) (string, int) {
	best, bestCount := "", 0
	for author, n := range authorCommits {
		if n > bestCount || (n == bestCount && author < best) {
			best, bestCount = author, n
		}
	}
	return best, len(authorCommits)
}

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

func daysBetween(earlier, later time.Time) int {
	if earlier.IsZero() || later.IsZero() {
		return 0
	}
	return int(later.Sub(earlier).Hours() / 24)
}

func round(value float64, places int) float64 {
	scale := math.Pow(10, float64(places))
	return math.Round(value*scale) / scale
}
