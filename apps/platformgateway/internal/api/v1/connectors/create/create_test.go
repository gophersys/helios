package create

import (
	"testing"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/view"
)

// TestValidate_RejectionBranches table-tests the pure validate stage: every malformed input maps to a
// typed errors.KindInvalid (→ 400), and a well-formed request passes. It is the cheapest, most
// valuable test (validate touches no port), covering every rejection arm (kind off-list, empty name,
// empty value, bad scope level, unparseable user-scope target id).
func TestValidate_RejectionBranches(t *testing.T) {
	t.Parallel()
	goodUser := uuid.New().String()

	cases := []struct {
		name    string
		input   Request
		wantErr bool
	}{
		{
			name:  "valid-org-scoped",
			input: Request{Kind: view.KindClaudeAPI, Name: "My token", Value: "secret", Scope: view.ScopeInput{Level: view.ScopeOrg}},
		},
		{
			name:  "valid-user-scoped",
			input: Request{Kind: view.KindGitHub, Name: "gh", Value: "secret", Scope: view.ScopeInput{Level: view.ScopeUser, TargetID: goodUser}},
		},
		{
			name:    "kind-off-list",
			input:   Request{Kind: "aws", Name: "x", Value: "secret", Scope: view.ScopeInput{Level: view.ScopeOrg}},
			wantErr: true,
		},
		{
			name:    "empty-name",
			input:   Request{Kind: view.KindOpenRouter, Name: "  ", Value: "secret", Scope: view.ScopeInput{Level: view.ScopeOrg}},
			wantErr: true,
		},
		{
			name:    "empty-value",
			input:   Request{Kind: view.KindClaudeAPI, Name: "x", Value: "", Scope: view.ScopeInput{Level: view.ScopeOrg}},
			wantErr: true,
		},
		{
			name:    "bad-scope-level",
			input:   Request{Kind: view.KindClaudeAPI, Name: "x", Value: "secret", Scope: view.ScopeInput{Level: "team"}},
			wantErr: true,
		},
		{
			name:    "user-scope-bad-target",
			input:   Request{Kind: view.KindClaudeAPI, Name: "x", Value: "secret", Scope: view.ScopeInput{Level: view.ScopeUser, TargetID: "not-a-uuid"}},
			wantErr: true,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			err := validate(tc.input)
			if tc.wantErr {
				if errors.KindOf(err) != errors.KindInvalid {
					t.Fatalf("validate(%s): want KindInvalid, got %v", tc.name, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("validate(%s): want nil, got %v", tc.name, err)
			}
		})
	}
}
