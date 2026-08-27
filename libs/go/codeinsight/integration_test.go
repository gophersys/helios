//go:build integration

package codeinsight_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/codeinsight"
	"github.com/gophersys/libs/go/codeinsight/codeinsighttest"
)

// The integration lane runs the SAME conformance suite over the REAL system-git History against a
// seeded on-disk repository (never a mocked git). The substrate is "go git" (contract §7): git is
// always present in the devcontainer, so an absent git is a gate FAILURE, not a skip. This is the
// real arm of the fake≡real closure (08 §2).

// TestSystemGit_Conforms drives the one conformance suite over the real system-git History.
func TestSystemGit_Conforms(t *testing.T) {
	t.Parallel()
	codeinsighttest.RunAnalyzerSuite(t, codeinsighttest.RealArm(t))
}

// TestSystemGit_WalkMinesRealHistory walks a seeded repository directly through the system-git
// History and asserts the real numstat parse yields the seeded commits with line deltas — the
// behavioral spine against a genuine git log.
func TestSystemGit_WalkMinesRealHistory(t *testing.T) {
	t.Parallel()
	dir := codeinsighttest.NewRealRepo(t, codeinsighttest.CanonicalSeed())
	history := codeinsight.NewSystemGitHistory()
	commits, head, err := history.Walk(context.Background(), dir, codeinsight.WalkWindow{})
	if err != nil {
		t.Fatalf("Walk: %v", err)
	}
	if head == "" {
		t.Errorf("Walk returned an empty HEAD")
	}
	if len(commits) != 8 {
		t.Fatalf("want 8 mined commits, got %d", len(commits))
	}
	// Newest commit is the last pair edit touching both pair files.
	if len(commits[0].Changes) != 2 {
		t.Errorf("newest commit touched %d files, want 2 (the coupled pair)", len(commits[0].Changes))
	}
	totalChurn := 0
	for i := range commits {
		for _, c := range commits[i].Changes {
			totalChurn += c.Added + c.Deleted
		}
	}
	if totalChurn == 0 {
		t.Errorf("real numstat parse yielded zero churn across %d commits", len(commits))
	}
}
