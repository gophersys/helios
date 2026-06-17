package codeinsight_test

import (
	"context"
	"encoding/json"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/codeinsight"
	"github.com/gophersys/libs/go/codeinsight/codeinsighttest"
)

// secretCanary is a needle seeded where a secret could plausibly travel through the analyzer (the
// repository path) so the no-leak property has a concrete value. The library's typed errors carry
// the LOGICAL identifier, never the raw path/stderr, so the needle must not surface in a surfaced
// error. (ADR-0020 dimension (f); secretscan runs `go test -run 'Canary|Redact|Secret'`.)
const secretCanary = "SEEDED-CANARY-token-do-not-leak" // #nosec G101 -- a deliberate test needle, not a real credential; the no-leak property hands it to the analyzer.

// TestCanary_HistoryErrorNeverLeaksPath asserts a History-walk failure surfaces an error classified
// by Kind whose message carries the LOGICAL identifier, never the raw repository path that could
// embed a credential. The fake History fails; the analyzer wraps it as a HistoryError stamped with
// the configured identifier, not the secret-bearing path.
func TestCanary_HistoryErrorNeverLeaksPath(t *testing.T) {
	t.Parallel()
	analyzer, err := codeinsight.New(
		codeinsight.Config{
			RepositoryPath: "/secret/" + secretCanary + "/repo",
			Identifier:     "safe-identifier",
		},
		codeinsight.Deps{
			History:   &codeinsighttest.FakeHistory{Err: errCanaryWalk},
			Providers: []codeinsight.MetricProvider{codeinsight.NewGoMetricProvider()},
			Clock:     codeinsighttest.FixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	_, walkErr := analyzer.Analyze(context.Background())
	if walkErr == nil {
		t.Fatalf("Analyze over a failing History returned nil error")
	}
	if strings.Contains(walkErr.Error(), secretCanary) {
		t.Fatalf("history error leaked the repository path canary: %q", walkErr.Error())
	}
	if !strings.Contains(walkErr.Error(), "safe-identifier") {
		t.Errorf("history error should carry the logical identifier, got %q", walkErr.Error())
	}
}

// TestCanary_ReportCarriesNoUnexpectedSecret asserts the serialized Report — the wire shape an
// edenhttp consumer serves — never carries a secret seeded into the repository PATH. The Report
// stamps the logical identifier and per-file metrics; the on-disk path (which could embed a token)
// must not travel into the payload.
func TestCanary_ReportCarriesNoUnexpectedSecret(t *testing.T) {
	t.Parallel()
	dir := codeinsighttest.NewRealRepo(t, codeinsighttest.CanonicalSeed())
	analyzer, err := codeinsight.New(
		codeinsight.Config{RepositoryPath: dir, Identifier: "safe-identifier"},
		codeinsight.Deps{
			History:   codeinsight.NewSystemGitHistory(),
			Providers: []codeinsight.MetricProvider{codeinsight.NewGoMetricProvider()},
			Clock:     codeinsighttest.FixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	report, err := analyzer.Analyze(context.Background())
	if err != nil {
		t.Fatalf("Analyze: %v", err)
	}
	payload, err := json.Marshal(report)
	if err != nil {
		t.Fatalf("marshal report: %v", err)
	}
	// The absolute temp-dir path (a stand-in for any secret-bearing path) must not appear in the
	// payload: entity paths are repository-relative, the identifier is logical.
	if strings.Contains(string(payload), dir) {
		t.Fatalf("Report payload leaked the absolute repository path %q", dir)
	}
}

// errCanaryWalk is the seeded History fault for the canary test.
var errCanaryWalk = canaryError("git walk failed")

type canaryError string

func (e canaryError) Error() string { return string(e) }
