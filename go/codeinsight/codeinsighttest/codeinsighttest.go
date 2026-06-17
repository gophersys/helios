// Package codeinsighttest is the public test support for codeinsight: a deterministic fake History
// (FakeHistory), a seeded-real-git fixture builder (NewRealRepo), a fixed Clock, and the one
// conformance suite (RunAnalyzerSuite) that proves an Analyzer assembled over any History binding
// holds the contract's invariants. The conformance suite is run twice — over the fake History and
// over the REAL system-git History against a seeded on-disk repository (never a mocked git) — so
// substitutability is EXECUTED, not asserted (08 §2).
package codeinsighttest

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/codeinsight"
)

// SeededCanary is a needle the redaction property hands the analyzer so the no-leak assertions have
// a concrete value: it is seeded as an author identity, and must NOT surface in any Report field
// that is not an explicit ownership entry (the Report carries no credential surface, so the canary's
// only legitimate home is the ownership/author maps it was deliberately placed in).
const SeededCanary = "Canary Author <canary@do-not-leak.example>"

// epoch is the frozen instant the fixed Clock reports, so a Report's AnalyzedAt is reproducible.
var epoch = time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC)

// FixedClock is a deterministic codeinsight.Clock: Now always returns a frozen instant so a Report's
// AnalyzedAt is reproducible across runs.
type FixedClock struct{ At time.Time }

// Now returns the frozen instant.
func (c FixedClock) Now() time.Time { return c.At }

// FakeHistory is the in-memory History binding: it replays a fixed commit slice and HEAD without
// touching disk, so the conformance suite's fake arm is hermetic and deterministic. The same suite
// runs over the real system-git History (NewSystemGitHistory) against a seeded repository.
type FakeHistory struct {
	// Commits are replayed verbatim (newest→oldest, as a real log yields).
	Commits []codeinsight.Commit
	// Head is the HEAD hash returned alongside the commits.
	Head string
	// Err, when non-nil, is returned from Walk (the fault arm: a history-walk failure).
	Err error
}

// compile-time assertion: *FakeHistory implements the History port.
var _ codeinsight.History = (*FakeHistory)(nil)

// Walk returns the seeded commits and HEAD (or the seeded error). The window is ignored: the fake
// replays exactly what it was given, which is what makes the fake arm deterministic.
func (h *FakeHistory) Walk(_ context.Context, _ string, _ codeinsight.WalkWindow) ([]codeinsight.Commit, string, error) {
	if h.Err != nil {
		return nil, "", h.Err
	}
	commits := make([]codeinsight.Commit, len(h.Commits))
	copy(commits, h.Commits)
	return commits, h.Head, nil
}
