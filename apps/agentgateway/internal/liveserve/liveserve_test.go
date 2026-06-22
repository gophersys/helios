package liveserve_test

import (
	"strings"
	"testing"

	"github.com/gophersys/eden/apps/agentgateway/internal/liveserve"
)

// sentinelSecret is a fake value handed to the Vault-password field so a leak into a surfaced
// error is detectable. It is intentionally NOT a real credential (the live arm reads the real
// token only at runtime from Vault).
const sentinelSecret = "REDACTED-test-needle-do-not-leak" //nolint:gosec // G101: a test needle, not a real credential.

// testCredentialReference is the opaque vault:// REFERENCE (a path, not a value) the test Config
// carries. It is loggable by design; the resolved value lives only server-side at runtime.
const testCredentialReference = "vault://eden/development#setup-token" //nolint:gosec // G101: an opaque vault reference path, not a credential value.

// TestBuildLiveGatewayValidatesBeforeDialing proves BuildLiveGateway rejects an invalid Config
// WITHOUT any I/O (the Vault adapter dials nothing on construct), names the missing field, and
// never leaks the Vault password into the surfaced error.
func TestBuildLiveGatewayValidatesBeforeDialing(t *testing.T) {
	t.Parallel()

	cases := []struct {
		name      string
		mutate    func(*liveserve.Config)
		wantField string
	}{
		{"missing vault address", func(c *liveserve.Config) { c.VaultAddress = "" }, "VaultAddress"},
		{"missing vault username", func(c *liveserve.Config) { c.VaultUsername = "" }, "VaultUsername"},
		{"missing vault password", func(c *liveserve.Config) { c.VaultPassword = "" }, "VaultPassword"},
		{"missing credential ref", func(c *liveserve.Config) { c.CredentialReference = "" }, "CredentialReference"},
		{"missing workspace", func(c *liveserve.Config) { c.Workspace = "" }, "Workspace"},
		{"missing harness", func(c *liveserve.Config) { c.Harness = "" }, "Harness"},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			configuration := validConfiguration()
			testCase.mutate(&configuration)

			gateway, _, err := liveserve.BuildLiveGateway(configuration)
			if gateway != nil || err == nil {
				t.Fatalf("BuildLiveGateway must reject a Config missing %s, got gateway=%v err=%v", testCase.wantField, gateway, err)
			}
			if !strings.Contains(err.Error(), testCase.wantField) {
				t.Errorf("error = %q, want it to name %s", err.Error(), testCase.wantField)
			}
			if strings.Contains(err.Error(), sentinelSecret) {
				t.Fatalf("the build error LEAKED the vault password: %q", err.Error())
			}
		})
	}
}

// TestDefaultCreateTemplate exposes the template the seeded record plane resolves (the UI posts it
// on POST /sessions, so it must be non-empty and stable).
func TestDefaultCreateTemplate(t *testing.T) {
	t.Parallel()
	name, version := liveserve.DefaultCreateTemplate()
	if name == "" || version == "" {
		t.Fatalf("DefaultCreateTemplate returned empty name/version: %q/%q", name, version)
	}
}

// validConfiguration returns a complete liveserve.Config (no real network values; the sentinel
// password stands in for the Vault credential).
func validConfiguration() liveserve.Config {
	return liveserve.Config{
		VaultAddress:        "http://127.0.0.1:8200",
		VaultUsername:       "eden",
		VaultPassword:       sentinelSecret,
		CredentialReference: testCredentialReference,
		Harness:             "claude-code",
		Workspace:           "/tmp/eden-live-workspace/session",
	}
}
