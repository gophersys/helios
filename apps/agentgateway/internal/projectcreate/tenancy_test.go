package projectcreate_test

import (
	"regexp"
	"testing"

	"github.com/gophersys/eden/apps/agentgateway/internal/projectcreate"
)

// These exercise the pure tenancy-UUID derivation through the white-box export seam. The orchestrator's
// desired-state store types org_id/project_id as UUID (07 §6), but the gateway mints non-UUID identifiers
// (an org slug, a "project-<hex>" id) — so the saga maps them to a stable RFC-4122 v5 UUID. The real saga
// e2e proved a non-UUID tenancy is rejected by the store; these lock the mapping's contract at the unit
// level (the fake orchestrator the saga unit tests drive does NOT enforce the UUID column).

// rfc4122v5 matches a canonical RFC-4122 version-5 UUID: 8-4-4-4-12 lowercase hex, the 13th hex digit
// (version) is 5, and the 17th (variant) is one of 8/9/a/b.
var rfc4122v5 = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`)

func TestDeriveTenancyUUID_IsValidRFC4122V5(t *testing.T) {
	t.Parallel()
	for _, name := range []string{"eden-integration", "project-aabbccddeeff001122", "eden", "MateoSegura"} {
		got := projectcreate.DeriveTenancyUUIDForTest(name)
		if !rfc4122v5.MatchString(got) {
			t.Errorf("deriveTenancyUUID(%q) = %q, not a canonical RFC-4122 v5 UUID", name, got)
		}
	}
}

func TestDeriveTenancyUUID_IsDeterministic(t *testing.T) {
	t.Parallel()
	const name = "project-aabbccddeeff001122"
	first := projectcreate.DeriveTenancyUUIDForTest(name)
	second := projectcreate.DeriveTenancyUUIDForTest(name)
	if first != second {
		t.Errorf("deriveTenancyUUID is not deterministic: %q != %q (a saga replay must re-Spawn under the same tenancy)", first, second)
	}
}

func TestDeriveTenancyUUID_DistinctNamesDoNotCollide(t *testing.T) {
	t.Parallel()
	a := projectcreate.DeriveTenancyUUIDForTest("project-aaaaaaaaaaaaaaaaaa")
	b := projectcreate.DeriveTenancyUUIDForTest("project-bbbbbbbbbbbbbbbbbb")
	if a == b {
		t.Errorf("distinct project ids derived the SAME tenancy UUID (%q) — two projects would share one supervisor admission class", a)
	}
}
