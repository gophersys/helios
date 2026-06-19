package removal_test

import (
	"context"
	"testing"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	ederrors "github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/removal"
)

// fakeDeleter is the in-memory Deleter binding for the unit lane.
type fakeDeleter struct {
	gotID uuid.UUID
	err   error
}

func (f *fakeDeleter) Delete(_ context.Context, id uuid.UUID) error {
	f.gotID = id
	return f.err
}

// TestExecute_AcknowledgesDeletedID proves removal execute calls Delete with the path id and returns
// the deletion acknowledgement carrying that id.
func TestExecute_AcknowledgesDeletedID(t *testing.T) {
	t.Parallel()
	id := uuid.New()
	fake := &fakeDeleter{}

	out, err := removal.Execute(fake)(context.Background(), edenhttp.Identity{}, removal.Request{ID: id})
	if err != nil {
		t.Fatalf("execute: %v", err)
	}
	if fake.gotID != id {
		t.Fatalf("Delete called with %s, want %s", fake.gotID, id)
	}
	if out.ID != id.String() {
		t.Fatalf("response id = %q, want %s", out.ID, id)
	}
}

// TestExecute_PreservesNotFound proves a delete of an absent resource preserves KindNotFound (→ 404),
// so a delete is never a silent success.
func TestExecute_PreservesNotFound(t *testing.T) {
	t.Parallel()
	fake := &fakeDeleter{err: ederrors.New(ederrors.KindNotFound, "resource not found")}

	_, err := removal.Execute(fake)(context.Background(), edenhttp.Identity{}, removal.Request{ID: uuid.New()})
	if ederrors.KindOf(err) != ederrors.KindNotFound {
		t.Fatalf("execute Kind = %v, want KindNotFound (preserved)", ederrors.KindOf(err))
	}
}
