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
