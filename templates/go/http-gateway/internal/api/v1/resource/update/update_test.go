package update_test

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	ederrors "github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/update"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// fakeUpdater is the in-memory Updater binding for the unit lane.
type fakeUpdater struct {
	gotID   uuid.UUID
	gotName string
	row     persistence.Resource
	err     error
}

func (f *fakeUpdater) Update(_ context.Context, id uuid.UUID, name string) (persistence.Resource, error) {
	f.gotID, f.gotName = id, name
	if f.err != nil {
		return persistence.Resource{}, f.err
	}
	row := f.row
	row.ID, row.Name = id, name
	return row, nil
}

// TestValidate_RejectsBlankName proves update reuses the shared name rule (a blank name is a 400).
func TestValidate_RejectsBlankName(t *testing.T) {
	t.Parallel()
	if err := update.Validate(update.Request{Name: ""}); ederrors.KindOf(err) != ederrors.KindInvalid {
		t.Fatalf("Validate(blank) Kind = %v, want KindInvalid", ederrors.KindOf(err))
	}
	if err := update.Validate(update.Request{Name: "renamed"}); err != nil {
		t.Fatalf("Validate(valid) = %v, want nil", err)
	}
}

// TestExecute_SetsNameAndProjects proves update execute calls Update with the path id + new name and
// projects the updated row to the wire Response.
func TestExecute_SetsNameAndProjects(t *testing.T) {
	t.Parallel()
	stamp := time.Date(2026, 6, 14, 15, 0, 0, 0, time.UTC)
	id := uuid.New()
	fake := &fakeUpdater{row: persistence.Resource{CreatedAt: stamp, UpdatedAt: stamp}}

	out, err := update.Execute(fake)(context.Background(), edenhttp.Identity{}, update.Request{ID: id, Name: "renamed"})
	if err != nil {
		t.Fatalf("execute: %v", err)
	}
	if fake.gotID != id || fake.gotName != "renamed" {
		t.Fatalf("Update called with {%s,%q}, want {%s,renamed}", fake.gotID, fake.gotName, id)
	}
	if out.ID != id.String() || out.Name != "renamed" {
		t.Fatalf("response = %+v, want id %s name renamed", out, id)
	}
}

// TestExecute_PreservesNotFound proves a missing row's KindNotFound is preserved (→ 404).
func TestExecute_PreservesNotFound(t *testing.T) {
	t.Parallel()
	fake := &fakeUpdater{err: ederrors.New(ederrors.KindNotFound, "resource not found")}

	_, err := update.Execute(fake)(context.Background(), edenhttp.Identity{}, update.Request{ID: uuid.New(), Name: "x"})
	if ederrors.KindOf(err) != ederrors.KindNotFound {
		t.Fatalf("execute Kind = %v, want KindNotFound (preserved)", ederrors.KindOf(err))
	}
}
