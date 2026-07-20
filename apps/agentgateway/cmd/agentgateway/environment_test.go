package main

import (
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets/vaultadapter"
)

// getenvFrom returns a getenv closure over a fixed map (the pure env source parseConfiguration
// reads), so the table drives the parse without mutating the process environment.
func getenvFrom(environment map[string]string) func(string) string {
	return func(key string) string { return environment[key] }
}

// productionEnv is the complete, valid token-file-mode environment the production manifest declares
// (the Helm happy path). Cases clone + mutate it to isolate one missing/overridden field.
func productionEnv() map[string]string {
	return map[string]string{
		"EDEN_GATEWAY_ADDRESS":        ":8080",
		"EDEN_NATS_URL":               "nats://nats:4222",
		"EDEN_GATEWAY_JWT_SECRET_REF": "vault://eden/production#agentgateway-jwt-signing-key",
		"EDEN_VAULT_MODE":             "token-file",
		"EDEN_VAULT_TOKEN_FILE":       "/vault/secrets/token",
		"VAULT_ADDR":                  "http://vault:8200",
	}
}

// without returns a clone of environment with key removed (an unset env var).
func without(environment map[string]string, key string) map[string]string {
	clone := make(map[string]string, len(environment))
	for k, v := range environment {
		if k == key {
			continue
		}
		clone[k] = v
	}
	return clone
}

// with returns a clone of environment with key set to value.
func with(environment map[string]string, key, value string) map[string]string {
	clone := make(map[string]string, len(environment)+1)
	for k, v := range environment {
		clone[k] = v
	}
	clone[key] = value
	return clone
}

func TestParseConfiguration_ProductionHappyPath(t *testing.T) {
	t.Parallel()
	configured, err := parseConfiguration(getenvFrom(productionEnv()))
	if err != nil {
		t.Fatalf("parseConfiguration: unexpected error: %v", err)
	}
	if configured.VaultMode != vaultadapter.ModeTokenFile {
		t.Fatalf("VaultMode = %v, want ModeTokenFile (EDEN_VAULT_MODE=token-file)", configured.VaultMode)
	}
	if configured.JWTSecretReference != "vault://eden/production#agentgateway-jwt-signing-key" {
		t.Fatalf("JWTSecretReference = %q, want the manifest reference", configured.JWTSecretReference)
	}
	if configured.Address != ":8080" {
		t.Fatalf("Address = %q, want :8080", configured.Address)
	}
}

func TestParseConfiguration_LocalUserpass(t *testing.T) {
	t.Parallel()
	// The local docker/dev path: no EDEN_VAULT_MODE (folds to userpass), a development-stage ref, and
	// the userpass bootstrap credential present.
	environment := map[string]string{
		"EDEN_GATEWAY_JWT_SECRET_REF": "vault://eden/development#agentgateway-jwt-signing-key",
		"VAULT_ADDR":                  "http://127.0.0.1:8200",
		"VAULT_USERNAME":              "eden",
		"VAULT_PASSWORD":              "s3cr3t",
	}
	configured, err := parseConfiguration(getenvFrom(environment))
	if err != nil {
		t.Fatalf("parseConfiguration: unexpected error on userpass path: %v", err)
	}
	if configured.VaultMode != vaultadapter.ModeUserpass {
		t.Fatalf("VaultMode = %v, want ModeUserpass (EDEN_VAULT_MODE unset)", configured.VaultMode)
	}
}

func TestParseConfiguration_Defaults(t *testing.T) {
	t.Parallel()
	// EDEN_GATEWAY_ADDRESS and EDEN_VAULT_TOKEN_FILE unset must fold to their defaults.
	environment := without(without(productionEnv(), "EDEN_GATEWAY_ADDRESS"), "EDEN_VAULT_TOKEN_FILE")
	configured, err := parseConfiguration(getenvFrom(environment))
	if err != nil {
		t.Fatalf("parseConfiguration: unexpected error: %v", err)
	}
	if configured.Address != defaultAddress {
		t.Fatalf("Address = %q, want default %q", configured.Address, defaultAddress)
	}
	if configured.VaultTokenFilePath != vaultTokenFilePath {
		t.Fatalf("VaultTokenFilePath = %q, want default %q", configured.VaultTokenFilePath, vaultTokenFilePath)
	}
}

// TestParseConfiguration_ExplicitOverridesAreRead kills the surviving-mutant gap: every defaulted
// field is also proven to honor a NON-default operator value (an envOr always returning the
// fallback would pass the defaults test but fail here).
func TestParseConfiguration_ExplicitOverridesAreRead(t *testing.T) {
	t.Parallel()
	environment := with(with(productionEnv(), "EDEN_GATEWAY_ADDRESS", ":9999"), "EDEN_VAULT_TOKEN_FILE", "/custom/token-path")
	configured, err := parseConfiguration(getenvFrom(environment))
	if err != nil {
		t.Fatalf("parseConfiguration: unexpected error: %v", err)
	}
	if configured.Address != ":9999" {
		t.Fatalf("Address = %q, want the explicit :9999 override", configured.Address)
	}
	if configured.VaultTokenFilePath != "/custom/token-path" {
		t.Fatalf("VaultTokenFilePath = %q, want the explicit override", configured.VaultTokenFilePath)
	}
}

// fullSurfaceEnv is the complete token-file-mode environment that ALSO wires the full REST/record
// plane (prodserve) — the production happy path the v0.1.7 manifest declares. It adds the DSN
// reference (the load-bearing seam), the propose credential reference, and the harness/workspace
// knobs onto the bridge-only productionEnv.
func fullSurfaceEnv() map[string]string {
	//nolint:gosec // G101: every value here is an opaque vault:// REFERENCE (a path) or a non-secret literal, never a credential VALUE.
	base := map[string]string{
		"EDEN_GATEWAY_DATABASE_DSN_REF": "vault://eden/production#database-dsn",
		"EDEN_CREDENTIAL_REF":           "vault://eden/production#setup-token",
		"EDEN_HARNESS":                  "claude-code",
		"EDEN_MODEL":                    "opus",
		"EDEN_WORKSPACE":                "/tmp/eden-gateway-workspace",
	}
	for k, v := range productionEnv() {
		base[k] = v
	}
	return base
}

// TestParseConfiguration_FullSurfaceHappyPath proves the v0.1.7 full-surface env parses: the DSN +
// credential references are read, the harness/workspace/model knobs land, and FullSurfaceConfigured
// reports true (so the command wires prodserve in addition to the bridge).
func TestParseConfiguration_FullSurfaceHappyPath(t *testing.T) {
	t.Parallel()
	configured, err := parseConfiguration(getenvFrom(fullSurfaceEnv()))
	if err != nil {
		t.Fatalf("parseConfiguration: unexpected error: %v", err)
	}
	if !configured.FullSurfaceConfigured() {
		t.Fatal("FullSurfaceConfigured() = false, want true when the DSN reference is set")
	}
	if configured.DatabaseDSNReference != "vault://eden/production#database-dsn" {
		t.Fatalf("DatabaseDSNReference = %q, want the manifest reference", configured.DatabaseDSNReference)
	}
	if configured.CredentialReference != "vault://eden/production#setup-token" {
		t.Fatalf("CredentialReference = %q, want the manifest reference", configured.CredentialReference)
	}
	if configured.Harness != "claude-code" {
		t.Fatalf("Harness = %q, want claude-code", configured.Harness)
	}
	if configured.Model != "opus" {
		t.Fatalf("Model = %q, want opus", configured.Model)
	}
	if configured.Workspace != "/tmp/eden-gateway-workspace" {
		t.Fatalf("Workspace = %q, want the explicit workspace", configured.Workspace)
	}
}

// TestParseConfiguration_BridgeOnlyWhenNoDSN proves the DEGRADE-HONEST partial-rollout path: with no
// DSN reference the command serves the NATS→SSE bridge ALONE (FullSurfaceConfigured false), and the
// harness/workspace still fold to their defaults (the bridge-only env is unchanged from pre-v0.1.7).
func TestParseConfiguration_BridgeOnlyWhenNoDSN(t *testing.T) {
	t.Parallel()
	configured, err := parseConfiguration(getenvFrom(productionEnv()))
	if err != nil {
		t.Fatalf("parseConfiguration: unexpected error on the bridge-only env: %v", err)
	}
	if configured.FullSurfaceConfigured() {
		t.Fatal("FullSurfaceConfigured() = true, want false when EDEN_GATEWAY_DATABASE_DSN_REF is unset")
	}
	if configured.Harness != defaultHarness {
		t.Fatalf("Harness = %q, want the default %q", configured.Harness, defaultHarness)
	}
	if configured.Workspace != defaultWorkspace {
		t.Fatalf("Workspace = %q, want the default %q", configured.Workspace, defaultWorkspace)
	}
}

// TestParseConfiguration_HarnessOverrideIsRead kills the surviving-mutant gap: EDEN_HARNESS/EDEN_MODEL
// honor a NON-default operator value (an envOr always returning the fallback would pass the defaults
// test but fail here).
func TestParseConfiguration_HarnessOverrideIsRead(t *testing.T) {
	t.Parallel()
	environment := with(without(fullSurfaceEnv(), "EDEN_MODEL"), "EDEN_HARNESS", "omp")
	configured, err := parseConfiguration(getenvFrom(environment))
	if err != nil {
		t.Fatalf("parseConfiguration: unexpected error: %v", err)
	}
	if configured.Harness != "omp" {
		t.Fatalf("Harness = %q, want the explicit omp override", configured.Harness)
	}
	if configured.Model != "" {
		t.Fatalf("Model = %q, want empty when EDEN_MODEL is unset (folds to the account default)", configured.Model)
	}
}

func TestParseConfiguration_MissingRequiredIsInvalid(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name string
		env  map[string]string
	}{
		{"missing EDEN_GATEWAY_JWT_SECRET_REF", without(productionEnv(), "EDEN_GATEWAY_JWT_SECRET_REF")},
		{"missing VAULT_ADDR", without(productionEnv(), "VAULT_ADDR")},
		{"userpass mode missing VAULT_USERNAME", without(with(productionEnv(), "EDEN_VAULT_MODE", "userpass"), "VAULT_USERNAME")},
		{"userpass mode missing VAULT_PASSWORD", with(with(productionEnv(), "EDEN_VAULT_MODE", "userpass"), "VAULT_USERNAME", "eden")},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			_, err := parseConfiguration(getenvFrom(testCase.env))
			if err == nil {
				t.Fatalf("parseConfiguration: want a typed error for %q, got nil", testCase.name)
			}
			if got := errors.KindOf(err); got != errors.KindInvalid {
				t.Fatalf("parseConfiguration: error Kind = %v, want KindInvalid for %q (err: %v)", got, testCase.name, err)
			}
		})
	}
}
