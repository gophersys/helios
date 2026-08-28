package codeinsight_test

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/codeinsight"
)

// fixedClock is a deterministic codeinsight.Clock for the root unit tests: Now always returns a
// frozen instant so a Report's AnalyzedAt is reproducible.
type fixedClock struct{}

func (fixedClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// stubHistory is a minimal History binding for the New validation tests — it is never walked (New is
// pure), so it returns an empty result.
type stubHistory struct{}

func (*stubHistory) Walk(context.Context, string, codeinsight.WalkWindow) ([]codeinsight.Commit, string, error) {
	return nil, "", nil
}
