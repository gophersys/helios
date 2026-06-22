//nolint:testpackage // white-box: exercises the unexported dev fakes (in-memory project/create-step/audit stores) directly.
package devserve

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/libs/go/errors"
)

// patchClock is a fixed test Clock distinct from devClockInstant, so a re-stamped UpdatedAt is
// provably the store's clock read and not a leftover create-time value.
type patchClock struct{}

var patchInstant = time.Date(2026, time.June, 22, 9, 30, 0, 0, time.UTC)

func (patchClock) Now() time.Time { return patchInstant }

// ── project store: UpdateStatus (the saga's mutation seam) ────────────────────────────────────.

// TestInMemoryProjectStore_UpdateStatusMergesAndRestamps proves the patch path's merge + re-stamp: a
// recorded draft is patched forward, each non-nil field overwrites while a nil field is left
// untouched, UpdatedAt is re-stamped from the store clock, and CreatedAt is immutable.
func TestInMemoryProjectStore_UpdateStatusMergesAndRestamps(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	projectStore := newInMemoryProjectStore(patchClock{})

	created, err := projectStore.Create(ctx, gateway.Project{
		ID: "project-aa", Name: "pay-backend", Status: gateway.ProjectStatusDraft,
		CreatedAt: devClockInstant, UpdatedAt: devClockInstant,
	})
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	advancing := gateway.ProjectStatusProvisioningRepo
	owner, repository := "gophersys", "pay-backend"
	patched, err := projectStore.UpdateStatus(ctx, "project-aa", gateway.ProjectStatusPatch{
		Status: &advancing, GitHubOwner: &owner, GitHubRepo: &repository, SagaStep: strptr("provision-repo"),
	})
	if err != nil {
		t.Fatalf("UpdateStatus: %v", err)
	}
	if patched.Status != gateway.ProjectStatusProvisioningRepo || patched.GitHubOwner != owner || patched.GitHubRepo != repository {
		t.Fatalf("saga scratch not merged: %+v", patched)
	}
	if patched.Name != created.Name {
		t.Fatalf("Name overwritten by a nil patch field: got %q want %q", patched.Name, created.Name)
	}
	if !patched.UpdatedAt.Equal(patchInstant) {
		t.Fatalf("UpdatedAt = %v, want re-stamped %v", patched.UpdatedAt, patchInstant)
	}
	if !patched.CreatedAt.Equal(devClockInstant) {
		t.Fatalf("CreatedAt mutated: got %v want %v", patched.CreatedAt, devClockInstant)
	}
}

// TestInMemoryProjectStore_UpdateStatusClearAndDurability proves a pointer-to-empty clears a field
// (the saga clearing LastError on recovery), the patch is durable, and a missing id is 404.
func TestInMemoryProjectStore_UpdateStatusClearAndDurability(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	projectStore := newInMemoryProjectStore(patchClock{})
	if _, err := projectStore.Create(ctx, gateway.Project{ID: "project-aa", Status: gateway.ProjectStatusDraft}); err != nil {
		t.Fatalf("Create: %v", err)
	}

	withError, err := projectStore.UpdateStatus(ctx, "project-aa", gateway.ProjectStatusPatch{LastError: strptr("repository conflict")})
	if err != nil || withError.LastError != "repository conflict" {
		t.Fatalf("set LastError: err=%v last=%q", err, withError.LastError)
	}
	cleared, err := projectStore.UpdateStatus(ctx, "project-aa", gateway.ProjectStatusPatch{LastError: strptr("")})
	if err != nil || cleared.LastError != "" {
		t.Fatalf("clear LastError: err=%v last=%q", err, cleared.LastError)
	}

	got, err := projectStore.Get(ctx, "project-aa")
	if err != nil || got.LastError != "" {
		t.Fatalf("Get after clear: err=%v last=%q", err, got.LastError)
	}
	if _, missErr := projectStore.UpdateStatus(ctx, "project-nope", gateway.ProjectStatusPatch{SagaStep: strptr("x")}); errors.KindOf(missErr) != errors.KindNotFound {
		t.Fatalf("UpdateStatus(missing) kind = %v, want not-found", errors.KindOf(missErr))
	}
}

// TestInMemoryProjectStore_UpdateStatusRejectsOffContractStatus proves the closed-set guard: a patch
// naming a status outside the lifecycle set is a typed KindInvalid and never written.
func TestInMemoryProjectStore_UpdateStatusRejectsOffContractStatus(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	projectStore := newInMemoryProjectStore(patchClock{})
	if _, err := projectStore.Create(ctx, gateway.Project{ID: "project-bb", Status: gateway.ProjectStatusDraft}); err != nil {
		t.Fatalf("Create: %v", err)
	}
	bogus := "halfway-done"
	_, err := projectStore.UpdateStatus(ctx, "project-bb", gateway.ProjectStatusPatch{Status: &bogus})
	if errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("off-contract status kind = %v, want invalid", errors.KindOf(err))
	}
	got, getErr := projectStore.Get(ctx, "project-bb")
	if getErr != nil || got.Status != gateway.ProjectStatusDraft {
		t.Fatalf("a rejected patch mutated the row: err=%v status=%q", getErr, got.Status)
	}
}

// ── create-step ledger ────────────────────────────────────────────────────────────────────────.

// TestInMemoryCreateStepStore_RecordIsIdempotent proves Record is idempotent on (projectID, step): a
// replay with a different key returns the first record unchanged.
func TestInMemoryCreateStepStore_RecordIsIdempotent(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	ledger := newInMemoryCreateStepStore(patchClock{})

	first, err := ledger.Record(ctx, gateway.CreateStep{ProjectID: "project-aa", Step: "provision-repo", IdempotencyKey: "key-1"})
	if err != nil {
		t.Fatalf("Record: %v", err)
	}
	if first.Status != gateway.CreateStepStatusPending || !first.StartedAt.Equal(patchInstant) || !first.FinishedAt.IsZero() {
		t.Fatalf("recorded step shape: %+v", first)
	}
	replay, err := ledger.Record(ctx, gateway.CreateStep{ProjectID: "project-aa", Step: "provision-repo", IdempotencyKey: "key-2"})
	if err != nil {
		t.Fatalf("Record replay: %v", err)
	}
	if replay.IdempotencyKey != "key-1" {
		t.Fatalf("replay changed the idempotency key: got %q want key-1", replay.IdempotencyKey)
	}
}

// TestInMemoryCreateStepStore_AdvanceAndList proves Advance moves a step to a terminal status with its
// Output, rejects a non-terminal/missing Advance, and List scopes a project's steps in record order.
func TestInMemoryCreateStepStore_AdvanceAndList(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	ledger := newInMemoryCreateStepStore(patchClock{})
	if _, err := ledger.Record(ctx, gateway.CreateStep{ProjectID: "project-aa", Step: "provision-repo", IdempotencyKey: "key-1"}); err != nil {
		t.Fatalf("Record: %v", err)
	}

	output := gateway.RawJSON(`{"repoNodeId":"R_123"}`)
	done, err := ledger.Advance(ctx, "project-aa", "provision-repo", gateway.CreateStepStatusDone, output)
	if err != nil {
		t.Fatalf("Advance: %v", err)
	}
	if done.Status != gateway.CreateStepStatusDone || done.FinishedAt.IsZero() || string(done.Output) != string(output) {
		t.Fatalf("advanced step drift: %+v", done)
	}
	if _, badErr := ledger.Advance(ctx, "project-aa", "provision-repo", gateway.CreateStepStatusPending, nil); errors.KindOf(badErr) != errors.KindInvalid {
		t.Fatalf("Advance(pending) kind = %v, want invalid", errors.KindOf(badErr))
	}
	if _, missErr := ledger.Advance(ctx, "project-aa", "seed-template", gateway.CreateStepStatusDone, nil); errors.KindOf(missErr) != errors.KindNotFound {
		t.Fatalf("Advance(missing) kind = %v, want not-found", errors.KindOf(missErr))
	}

	if _, err = ledger.Record(ctx, gateway.CreateStep{ProjectID: "project-aa", Step: "seed-template", IdempotencyKey: "key-3"}); err != nil {
		t.Fatalf("Record second step: %v", err)
	}
	if _, err = ledger.Record(ctx, gateway.CreateStep{ProjectID: "project-zz", Step: "provision-repo", IdempotencyKey: "key-9"}); err != nil {
		t.Fatalf("Record other project: %v", err)
	}
	steps, err := ledger.List(ctx, "project-aa")
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(steps) != 2 || steps[0].Step != "provision-repo" || steps[1].Step != "seed-template" {
		t.Fatalf("List(project-aa) drift: %+v", steps)
	}
}

// ── audit store ───────────────────────────────────────────────────────────────────────────────.

// TestInMemoryAuditStore_AppendsAndPages proves the append-only trail: Append assigns a monotonic Seq,
// List returns newest-first scoped to a project, and the cursor pages the remainder.
func TestInMemoryAuditStore_AppendsAndPages(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	trail := newInMemoryAuditStore()

	for _, action := range []string{"project.created", "saga.step.started", "saga.step.done"} {
		event, err := trail.Append(ctx, gateway.AuditEvent{ProjectID: "project-aa", Action: action, Actor: "system", OccurredAt: patchInstant})
		if err != nil {
			t.Fatalf("Append(%s): %v", action, err)
		}
		if event.Seq == 0 {
			t.Fatalf("Append(%s): seq not assigned", action)
		}
	}
	if _, err := trail.Append(ctx, gateway.AuditEvent{ProjectID: "project-zz", Action: "project.created", OccurredAt: patchInstant}); err != nil {
		t.Fatalf("Append(other project): %v", err)
	}

	first, err := trail.List(ctx, gateway.AuditFilter{ProjectID: "project-aa", Limit: 2})
	if err != nil {
		t.Fatalf("List(limit=2): %v", err)
	}
	if len(first.Events) != 2 || first.Events[0].Action != "saga.step.done" || first.Next == "" {
		t.Fatalf("List page-1 drift: events=%+v next=%q", first.Events, first.Next)
	}
	second, err := trail.List(ctx, gateway.AuditFilter{ProjectID: "project-aa", Limit: 2, Cursor: first.Next})
	if err != nil {
		t.Fatalf("List(cursor): %v", err)
	}
	if len(second.Events) != 1 || second.Events[0].Action != "project.created" || second.Next != "" {
		t.Fatalf("List page-2 drift: events=%+v next=%q", second.Events, second.Next)
	}
}

// strptr returns a pointer to s — the patch's "set this field" form (a nil field is "leave unchanged").
func strptr(s string) *string { return &s }
