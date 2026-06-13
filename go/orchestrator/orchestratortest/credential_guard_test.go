package orchestratortest_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
)

// recordingT is a minimal orchestratortest.TestingT spy that records whether Errorf fired.
type recordingT struct{ errored bool }

func (r *recordingT) Helper()               {}
func (r *recordingT) Errorf(string, ...any) { r.errored = true }

// TestAssertNoSecretInRecord_CatchesTransientLeak proves the credential-seam guard scans
// the FULL Put history, not only the final record: a canary leaked into a transient record
// field that a later transition OVERWRITES is still caught. This is the regression guard for
// the verify-flagged blind spot where a leak into Detail/By escaped the List()-only scan
// (the guard would have been vacuous for any field a subsequent reconcile pass replaces).
func TestAssertNoSecretInRecord_CatchesTransientLeak(t *testing.T) {
	t.Parallel()
	const canary = "S3CR3T-transient-leak-canary-do-not-leak"
	manager := orchestratortest.New()
	ctx := context.Background()
	store := manager.Store()

	// A transient version leaks the canary into Detail...
	if err := store.Put(ctx, orchestrator.Agent{ID: "agent-x", Status: orchestrator.StatusPending, Detail: canary}); err != nil {
		t.Fatalf("seed transient leak: %v", err)
	}
	// ...then a later transition overwrites it with a CLEAN record (the final List() is clean).
	if err := store.Put(ctx, orchestrator.Agent{ID: "agent-x", Status: orchestrator.StatusFailed, Detail: "clean"}); err != nil {
		t.Fatalf("seed clean overwrite: %v", err)
	}

	// Sanity: the FINAL record is clean — a List()-only guard would MISS the leak.
	final, err := store.Get(ctx, "agent-x")
	if err != nil {
		t.Fatalf("get final: %v", err)
	}
	if final.Detail == canary {
		t.Fatal("setup invalid: the final record must be clean (the leak lives only in the overwritten transient version)")
	}

	// The strengthened guard MUST catch the transient leak by scanning every Put version.
	spy := &recordingT{}
	manager.AssertNoSecretInRecord(spy, canary)
	if !spy.errored {
		t.Error("AssertNoSecretInRecord must catch a canary leaked into a transient (later-overwritten) record version; the guard is scanning only the final record")
	}
}
