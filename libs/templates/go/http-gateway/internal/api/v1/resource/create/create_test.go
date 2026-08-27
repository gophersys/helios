package create_test

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	ederrors "github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/create"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// fakeCreator is the in-memory Creator the unit lane drives execute against (the fake binding of the
// route's persistence port — the conformance two-binding's fast half; the integration lane proves the
// SAME behavior on real postgres). It records the last Create call and returns a canned row or error.
type fakeCreator struct {
	lastID   uuid.UUID
	lastName string
	row      persistence.Resource
	err      error
}

func (f *fakeCreator) Create(_ context.Context, id uuid.UUID, name string) (persistence.Resource, error) {
	f.lastID, f.lastName = id, name
	if f.err != nil {
		return persistence.Resource{}, f.err
	}
	row := f.row
	row.ID, row.Name = id, name
	return row, nil
}

// TestValidate_RejectsBlankName tables the validate stage's rejection branches: a blank/whitespace
// name and an over-long name are KindInvalid (→ 400); a well-formed name passes. validate is pure, so
// this is the cheapest, highest-value coverage (every rejection branch).
func TestValidate_RejectsName(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{name: "blank", input: "", wantErr: true},
		{name: "whitespace", input: "   ", wantErr: true},
		{name: "too-long", input: strings.Repeat("x", 257), wantErr: true},
		{name: "ok", input: "widget", wantErr: false},
		{name: "max-length", input: strings.Repeat("x", 256), wantErr: false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			err := create.Validate(create.Request{Name: tc.input})
			if tc.wantErr {
				if err == nil {
					t.Fatalf("Validate(%q) = nil, want an error", tc.input)
				}
				if ederrors.KindOf(err) != ederrors.KindInvalid {
					t.Fatalf("Validate(%q) Kind = %v, want KindInvalid", tc.input, ederrors.KindOf(err))
				}
				return
			}
			if err != nil {
				t.Fatalf("Validate(%q) = %v, want nil", tc.input, err)
			}
		})
	}
}

// TestExecute_MintsIDAndProjects proves the create execute stage mints a server-side id, calls the
// Creator with the validated name, and projects the persisted row to the wire Response (RFC3339
// timestamps). It drives execute through the assembled handler shape via the exported test seam.
func TestExecute_MintsIDAndProjects(t *testing.T) {
	t.Parallel()
	stamp := time.Date(2026, 6, 14, 12, 0, 0, 0, time.UTC)
	fake := &fakeCreator{row: persistence.Resource{CreatedAt: stamp, UpdatedAt: stamp}}

	out, err := create.Execute(fake)(context.Background(), edenhttp.Identity{Subject: "tester"}, create.Request{Name: "widget"})
	if err != nil {
		t.Fatalf("execute: %v", err)
	}
	if fake.lastName != "widget" {
		t.Fatalf("Create called with name %q, want %q", fake.lastName, "widget")
	}
	if fake.lastID == uuid.Nil {
		t.Fatal("execute did not mint a non-nil resource id")
	}
	if out.ID != fake.lastID.String() {
		t.Fatalf("response id = %q, want the minted id %q", out.ID, fake.lastID.String())
	}
	if out.Name != "widget" {
		t.Fatalf("response name = %q, want %q", out.Name, "widget")
	}
	if out.CreatedAt != "2026-06-14T12:00:00Z" {
		t.Fatalf("response createdAt = %q, want RFC3339 UTC", out.CreatedAt)
	}
}

// TestExecute_WrapsPersistenceError proves a persistence fault is wrapped with the execute Kind
// preserved (a KindConflict stays a conflict → 409 at the boundary), not flattened to a 500.
func TestExecute_WrapsPersistenceError(t *testing.T) {
	t.Parallel()
	fake := &fakeCreator{err: ederrors.New(ederrors.KindConflict, "duplicate id")}

	_, err := create.Execute(fake)(context.Background(), edenhttp.Identity{}, create.Request{Name: "widget"})
	if err == nil {
		t.Fatal("execute with a failing Creator returned nil error")
	}
	if ederrors.KindOf(err) != ederrors.KindConflict {
		t.Fatalf("execute error Kind = %v, want KindConflict (preserved)", ederrors.KindOf(err))
	}
	if !errors.Is(err, fake.err) {
		t.Fatal("execute error does not wrap the persistence cause (chain broken)")
	}
}
