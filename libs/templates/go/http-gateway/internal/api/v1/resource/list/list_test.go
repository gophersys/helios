package list_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gophersys/libs/go/edenhttp"
	ederrors "github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/list"
	"github.com/gophersys/libs/templates/go/http-gateway/persistence"
)

// fakeLister is the in-memory Lister binding for the unit lane. It records the window it was asked
// for and returns a canned page.
type fakeLister struct {
	gotLimit  int32
	gotOffset int32
	rows      []persistence.Resource
	err       error
}

func (f *fakeLister) List(_ context.Context, limit, offset int32) ([]persistence.Resource, error) {
	f.gotLimit, f.gotOffset = limit, offset
	return f.rows, f.err
}

// TestParse_DefaultsAndClamps tables the pagination parse: an absent limit defaults to 50; a limit
// over the max clamps to 200; an explicit window is taken verbatim; a non-integer is a 400.
func TestParse_PaginationWindow(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name       string
		query      string
		wantLimit  int32
		wantOffset int32
		wantErr    bool
	}{
		{name: "defaults", query: "", wantLimit: 50, wantOffset: 0},
		{name: "explicit", query: "?limit=10&offset=20", wantLimit: 10, wantOffset: 20},
		{name: "clamped", query: "?limit=9999", wantLimit: 200, wantOffset: 0},
		{name: "bad-limit", query: "?limit=abc", wantErr: true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			request := httptest.NewRequest(http.MethodGet, "/resources"+tc.query, http.NoBody)
			got, err := list.Parse(request)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("Parse(%q) = nil error, want a 400", tc.query)
				}
				return
			}
			if err != nil {
				t.Fatalf("Parse(%q): %v", tc.query, err)
			}
			if got.Limit != tc.wantLimit || got.Offset != tc.wantOffset {
				t.Fatalf("Parse(%q) = {%d,%d}, want {%d,%d}", tc.query, got.Limit, got.Offset, tc.wantLimit, tc.wantOffset)
			}
		})
	}
}

// TestValidate_RejectsNegative proves the validate stage rejects a negative window (KindInvalid).
func TestValidate_RejectsNegative(t *testing.T) {
	t.Parallel()
	if err := list.Validate(list.Request{Limit: -1}); ederrors.KindOf(err) != ederrors.KindInvalid {
		t.Fatalf("Validate(limit=-1) Kind = %v, want KindInvalid", ederrors.KindOf(err))
	}
	if err := list.Validate(list.Request{Offset: -1}); ederrors.KindOf(err) != ederrors.KindInvalid {
		t.Fatalf("Validate(offset=-1) Kind = %v, want KindInvalid", ederrors.KindOf(err))
	}
	if err := list.Validate(list.Request{Limit: 10, Offset: 0}); err != nil {
		t.Fatalf("Validate(valid window) = %v, want nil", err)
	}
}

// TestExecute_NeverNilItems proves the list execute returns an empty (non-nil) Items slice for an
// empty page, so the envelope renders [] not null, and echoes the resolved window.
func TestExecute_NeverNilItems(t *testing.T) {
	t.Parallel()
	fake := &fakeLister{rows: nil}

	out, err := list.Execute(fake)(context.Background(), edenhttp.Identity{}, list.Request{Limit: 25, Offset: 5})
	if err != nil {
		t.Fatalf("execute: %v", err)
	}
	if out.Items == nil {
		t.Fatal("execute returned nil Items (would render JSON null, not [])")
	}
	if len(out.Items) != 0 {
		t.Fatalf("execute Items len = %d, want 0", len(out.Items))
	}
	if out.Limit != 25 || out.Offset != 5 {
		t.Fatalf("execute echoed window {%d,%d}, want {25,5}", out.Limit, out.Offset)
	}
	if fake.gotLimit != 25 || fake.gotOffset != 5 {
		t.Fatalf("Lister called with {%d,%d}, want {25,5}", fake.gotLimit, fake.gotOffset)
	}
}
