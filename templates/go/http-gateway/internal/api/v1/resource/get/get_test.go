package get_test

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	ederrors "github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/get"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// fakeGetter is the in-memory Getter binding for the unit lane.
type fakeGetter struct {
	row persistence.Resource
	err error
}

func (f *fakeGetter) Get(_ context.Context, id uuid.UUID) (persistence.Resource, error) {
	if f.err != nil {
		return persistence.Resource{}, f.err
	}
	row := f.row
	row.ID = id
	return row, nil
}

// TestExecute_ProjectsRow proves get execute fetches by id and projects the row to the wire Response.
func TestExecute_ProjectsRow(t *testing.T) {
	t.Parallel()
	stamp := time.Date(2026, 6, 14, 9, 30, 0, 0, time.UTC)
	id := uuid.New()
	fake := &fakeGetter{row: persistence.Resource{Name: "widget", CreatedAt: stamp, UpdatedAt: stamp}}

	out, err := get.Execute(fake)(context.Background(), edenhttp.Identity{}, get.Request{ID: id})
	if err != nil {
		t.Fatalf("execute: %v", err)
	}
	if out.ID != id.String() || out.Name != "widget" {
		t.Fatalf("response = %+v, want id %s name widget", out, id)
	}
	if out.UpdatedAt != "2026-06-14T09:30:00Z" {
		t.Fatalf("response updatedAt = %q, want RFC3339 UTC", out.UpdatedAt)
	}
}

// TestExecute_PreservesNotFound proves a persistence KindNotFound is preserved through execute (so
// the envelope renders 404), with the cause chain intact.
func TestExecute_PreservesNotFound(t *testing.T) {
	t.Parallel()
	notFound := ederrors.New(ederrors.KindNotFound, "resource not found")
	fake := &fakeGetter{err: notFound}

	_, err := get.Execute(fake)(context.Background(), edenhttp.Identity{}, get.Request{ID: uuid.New()})
	if ederrors.KindOf(err) != ederrors.KindNotFound {
		t.Fatalf("execute Kind = %v, want KindNotFound (preserved)", ederrors.KindOf(err))
	}
	if !errors.Is(err, notFound) {
		t.Fatal("execute error does not wrap the not-found cause")
	}
}
