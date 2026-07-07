package main

import (
	"context"
	"io"
	"log/slog"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets/vaultadapter"

	"github.com/gophersys/eden/apps/agentgateway/internal/orchestratorservice"
)

// getenvFrom returns a getenv closure over a fixed map (the pure env source parseConfiguration
// reads), so the table drives the parse without mutating the process environment.
func getenvFrom(environment map[string]string) func(string) string {
	return func(key string) string { return environment[key] }
}

// kubernetesEnv is the complete, valid kubernetes-substrate environment the manifest declares (the
// production happy path). Cases clone + mutate it to isolate one missing/overridden field.
func kubernetesEnv() map[string]string {
	return map[string]string{
		"EDEN_WORKSPACE_SUBSTRATE": "kubernetes",
		"EDEN_LEASE_NAME":          "eden-orchestrator",
		"EDEN_LEASE_NAMESPACE":     "eden-system",
		"EDEN_LEASE_IDENTITY":      "eden-orchestrator-0",
		"DATABASE_URL":             "postgres://eden:eden@eden-postgres:5432/eden?sslmode=disable",
		"EDEN_NATS_URL":            "nats://nats.eden-system.svc:4222",
		"EDEN_LABEL_NAMESPACE":     "central",
		"EDEN_VAULT_MODE":          "token-file",
		"EDEN_VAULT_TOKEN_FILE":    "/vault/secrets/token",
		"VAULT_ADDR":               "http://vault.eden-system.svc:8200",
		"EDEN_CREDENTIAL_REF":      "vault://eden/production#setup-token",
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

func TestParseConfiguration_KubernetesHappyPath(t *testing.T) {
	t.Parallel()
	configured, err := parseConfiguration(getenvFrom(kubernetesEnv()))
	if err != nil {
		t.Fatalf("parseConfiguration: unexpected error: %v", err)
	}
	if configured.Substrate != orchestratorservice.SubstrateKubernetes {
		t.Fatalf("Substrate = %v, want SubstrateKubernetes (EDEN_WORKSPACE_SUBSTRATE=kubernetes)", configured.Substrate)
	}
	if configured.VaultMode != vaultadapter.ModeTokenFile {
		t.Fatalf("VaultMode = %v, want ModeTokenFile (EDEN_VAULT_MODE=token-file)", configured.VaultMode)
	}
	if configured.Lease.LeaseName != "eden-orchestrator" || configured.Lease.Identity != "eden-orchestrator-0" {
		t.Fatalf("Lease = %+v, want the manifest's lease wiring", configured.Lease)
	}
	if configured.Address != defaultAddress {
		t.Fatalf("Address = %q, want the default %q (EDEN_ORCHESTRATOR_ADDRESS unset)", configured.Address, defaultAddress)
	}
	if configured.Harness != defaultHarness {
		t.Fatalf("Harness = %q, want the default %q (EDEN_HARNESS unset)", configured.Harness, defaultHarness)
	}
}

func TestParseConfiguration_Defaults(t *testing.T) {
	t.Parallel()
	// EDEN_HARNESS, EDEN_ORCHESTRATOR_ADDRESS, and EDEN_VAULT_TOKEN_FILE unset must fold to their
	// defaults; an unknown EDEN_WORKSPACE_SUBSTRATE must fold to the docker-first zero.
	environment := without(without(without(kubernetesEnv(), "EDEN_HARNESS"), "EDEN_ORCHESTRATOR_ADDRESS"), "EDEN_VAULT_TOKEN_FILE")
	configured, err := parseConfiguration(getenvFrom(environment))
	if err != nil {
		t.Fatalf("parseConfiguration: unexpected error: %v", err)
	}
	if configured.Harness != defaultHarness {
		t.Fatalf("Harness = %q, want default %q", configured.Harness, defaultHarness)
	}
	if configured.Address != defaultAddress {
		t.Fatalf("Address = %q, want default %q", configured.Address, defaultAddress)
	}
	if configured.VaultTokenFilePath != vaultTokenFilePath {
		t.Fatalf("VaultTokenFilePath = %q, want default %q", configured.VaultTokenFilePath, vaultTokenFilePath)
	}
}

// TestParseConfiguration_ExplicitOverridesAreRead kills the surviving-mutant gap the review fleet
// found: every defaulted field is also proven to honor a NON-default operator value (an envOr that
// always returned the fallback would pass the defaults test but fail here).
func TestParseConfiguration_ExplicitOverridesAreRead(t *testing.T) {
	t.Parallel()
	environment := with(with(with(kubernetesEnv(),
		"EDEN_ORCHESTRATOR_ADDRESS", ":9999"),
		"EDEN_VAULT_TOKEN_FILE", "/custom/token-path"),
		"EDEN_HARNESS", "omp")
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
	if configured.Harness != "omp" {
		t.Fatalf("Harness = %q, want the explicit omp override", configured.Harness)
	}
}

func TestParseConfiguration_UnknownSubstrateFoldsToDocker(t *testing.T) {
	t.Parallel()
	// A non-"kubernetes" substrate token folds to the docker-first zero; the lease fields are then
	// NOT required (dockerLease is the always-leader). Provide only the docker-path requireds.
	environment := map[string]string{
		"EDEN_WORKSPACE_SUBSTRATE": "docker",
		"DATABASE_URL":             "postgres://eden:eden@localhost:5432/eden?sslmode=disable",
		"VAULT_ADDR":               "http://127.0.0.1:8200",
		"EDEN_CREDENTIAL_REF":      "vault://eden/development#setup-token",
		"VAULT_USERNAME":           "eden",
		"VAULT_PASSWORD":           "s3cr3t",
	}
	configured, err := parseConfiguration(getenvFrom(environment))
	if err != nil {
		t.Fatalf("parseConfiguration: unexpected error on docker fallback: %v", err)
	}
	if configured.Substrate != orchestratorservice.SubstrateDocker {
		t.Fatalf("Substrate = %v, want SubstrateDocker (unknown token folds to the zero default)", configured.Substrate)
	}
	if configured.VaultMode != vaultadapter.ModeUserpass {
		t.Fatalf("VaultMode = %v, want ModeUserpass (EDEN_VAULT_MODE unset)", configured.VaultMode)
	}
}

// scriptedLease pops one scripted leadership state per IsLeader consult (repeating the FINAL state
// once the script is exhausted), so a test drives acquire/depose transitions deterministically.
// failWith, when set, makes every consult fail — the lease-consult fault arm.
type scriptedLease struct {
	mu       sync.Mutex
	script   []bool
	failWith error
}

func (s *scriptedLease) IsLeader(context.Context) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.failWith != nil {
		return false, s.failWith
	}
	if len(s.script) == 0 {
		return false, nil
	}
	state := s.script[0]
	if len(s.script) > 1 {
		s.script = s.script[1:]
	}
	return state, nil
}

// countingStart records how many times the supervisor started the loop (and optionally fails).
type countingStart struct {
	mu    sync.Mutex
	count int
	err   error
}

func (c *countingStart) start(context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.count++
	return c.err
}

func (c *countingStart) calls() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.count
}

const testPollInterval = 2 * time.Millisecond

// TestSuperviseLeadership_NilLeaseStartsAndParks proves the docker fallback is a DAEMON: the loop
// starts exactly once and the supervisor then BLOCKS until ctx cancels (the review-fleet HIGH: an
// early nil return resolved run()'s select and exited the process, tearing the loop down — the
// original version of this very test had encoded that bug by asserting the early return).
func TestSuperviseLeadership_NilLeaseStartsAndParks(t *testing.T) {
	t.Parallel()
	starter := &countingStart{}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- superviseLeadership(ctx, nil, starter.start, testPollInterval, discardLogger()) }()

	// The loop must start promptly…
	deadline := time.After(2 * time.Second)
	for starter.calls() == 0 {
		select {
		case <-deadline:
			t.Fatal("the docker-fallback loop never started")
		case <-time.After(time.Millisecond):
		}
	}
	// …and the supervisor must NOT return while ctx is live (the daemon parks).
	select {
	case err := <-done:
		t.Fatalf("supervisor returned (%v) while ctx was live — the docker-fallback daemon must park", err)
	case <-time.After(50 * time.Millisecond):
	}
	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("graceful cancel: unexpected error: %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("supervisor did not return after ctx cancel")
	}
	if starter.calls() != 1 {
		t.Fatalf("start calls = %d, want exactly 1", starter.calls())
	}
}

// TestSuperviseLeadership_FollowerPromotedOnAcquire proves the transition Service.Start cannot see
// on its own (it consults IsLeader once): a replica that starts as follower MUST start the loop
// when it later acquires the Lease — the leaderless-deployment regression this supervisor closes.
func TestSuperviseLeadership_FollowerPromotedOnAcquire(t *testing.T) {
	t.Parallel()
	lease := &scriptedLease{script: []bool{false, false, true}} // follower two polls, then leader
	starter := &countingStart{}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- superviseLeadership(ctx, lease, starter.start, testPollInterval, discardLogger()) }()

	deadline := time.After(2 * time.Second)
	for starter.calls() == 0 {
		select {
		case <-deadline:
			t.Fatal("the promoted follower never started the reconcile loop")
		case <-time.After(time.Millisecond):
		}
	}
	cancel()
	if err := <-done; err != nil {
		t.Fatalf("graceful cancel after promotion: unexpected error: %v", err)
	}
	if starter.calls() != 1 {
		t.Fatalf("start calls = %d, want exactly 1 (started once on acquire, never again)", starter.calls())
	}
}

// TestSuperviseLeadership_DeposedLeaderExits proves a STARTED leader that loses the Lease returns a
// typed error (the process-exit → kubelet-restart → clean re-election convention) rather than
// silently continuing.
func TestSuperviseLeadership_DeposedLeaderExits(t *testing.T) {
	t.Parallel()
	lease := &scriptedLease{script: []bool{true, true, false}} // leader, then deposed
	starter := &countingStart{}
	// Bounded: were the deposition-exit branch removed, this test must FAIL on the deadline
	// rather than hang the suite (the supervisor would poll forever).
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	err := superviseLeadership(ctx, lease, starter.start, testPollInterval, discardLogger())
	if err == nil {
		t.Fatal("deposed leader: want the restart-for-re-election error, got nil")
	}
	if got := errors.KindOf(err); got != errors.KindUnavailable {
		t.Fatalf("deposed leader: error Kind = %v, want KindUnavailable (err: %v)", got, err)
	}
	if starter.calls() != 1 {
		t.Fatalf("start calls = %d, want exactly 1 before deposition", starter.calls())
	}
}

// TestSuperviseLeadership_ConsultFaultIsUnavailable proves a lease-consult fault surfaces as a
// typed startup-path error, never a silent retry-forever.
func TestSuperviseLeadership_ConsultFaultIsUnavailable(t *testing.T) {
	t.Parallel()
	lease := &scriptedLease{failWith: errors.New(errors.KindUnavailable, "test: apiserver unreachable")}
	starter := &countingStart{}
	err := superviseLeadership(context.Background(), lease, starter.start, testPollInterval, discardLogger())
	if err == nil || errors.KindOf(err) != errors.KindUnavailable {
		t.Fatalf("consult fault: err = %v, want KindUnavailable", err)
	}
	if starter.calls() != 0 {
		t.Fatalf("start calls = %d, want 0 (never start on a faulting lease)", starter.calls())
	}
}

// TestSuperviseLeadership_StartFaultSurfaces proves a reconcile-loop start failure on acquisition
// is returned wrapped, not swallowed.
func TestSuperviseLeadership_StartFaultSurfaces(t *testing.T) {
	t.Parallel()
	lease := &scriptedLease{script: []bool{true}}
	starter := &countingStart{err: errors.New(errors.KindInternal, "test: pool refused")}
	err := superviseLeadership(context.Background(), lease, starter.start, testPollInterval, discardLogger())
	if err == nil || errors.KindOf(err) != errors.KindUnavailable {
		t.Fatalf("start fault: err = %v, want the wrapped KindUnavailable", err)
	}
}

// discardLogger returns a slog logger that writes nowhere (the supervisor's log lines are
// diagnostics, not assertions).
func discardLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func TestParseConfiguration_MissingRequiredIsInvalid(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name string
		env  map[string]string
	}{
		{"missing DATABASE_URL", without(kubernetesEnv(), "DATABASE_URL")},
		{"missing EDEN_CREDENTIAL_REF", without(kubernetesEnv(), "EDEN_CREDENTIAL_REF")},
		{"missing VAULT_ADDR", without(kubernetesEnv(), "VAULT_ADDR")},
		{"kubernetes missing EDEN_LEASE_NAME", without(kubernetesEnv(), "EDEN_LEASE_NAME")},
		{"kubernetes missing EDEN_LEASE_NAMESPACE", without(kubernetesEnv(), "EDEN_LEASE_NAMESPACE")},
		{"kubernetes missing EDEN_LEASE_IDENTITY", without(kubernetesEnv(), "EDEN_LEASE_IDENTITY")},
		{"userpass mode missing VAULT_USERNAME", without(with(kubernetesEnv(), "EDEN_VAULT_MODE", "userpass"), "VAULT_USERNAME")},
		{"userpass mode missing VAULT_PASSWORD", with(with(kubernetesEnv(), "EDEN_VAULT_MODE", "userpass"), "VAULT_USERNAME", "eden")},
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
