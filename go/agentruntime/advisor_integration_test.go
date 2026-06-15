//go:build integration

// Package agentruntime_test's advisor integration arm drives the REAL Eden permission ADVISOR
// against a REAL `claude` reviewer subagent — but ONLY when an external setup-token is explicitly
// supplied (CLAUDEADAPTER_LIVE_TOKEN, read verbatim from /workspace/.env.development). It is an
// HONEST SKIP by default (no token => skip; no claude binary => skip). It NEVER mints a token,
// NEVER launches interactive auth, and NEVER logs the token: the value is read from the env file,
// wrapped as a fake secret, and threaded through the SAME server-side injection path agentsession
// uses, asserted never to leak onto the reviewer's event stream.
//
//	go test -tags integration ./... -race
//
// It gives the reviewer ONE concrete LOW-risk request (a Read of an in-workspace doc) and asserts a
// SANE allow with a non-empty rationale — proving the advisor opens a real reasoning subagent,
// prompts it from the AdviceContext, parses its structured verdict, and audit-logs the decision.
package agentruntime_test

import (
	"bufio"
	"context"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/agentruntime/agentruntimetest"
	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// liveTokenEnvFile is the operator-managed env file the live token is read from (never committed
// with a value; the key is present so the harness knows where to look).
const liveTokenEnvFile = "/workspace/.env.development"

// liveTokenKey is the env-file key carrying the operator's claude setup-token.
const liveTokenKey = "CLAUDEADAPTER_LIVE_TOKEN"

// liveCredentialRef is the loggable opaque reference the reviewer credential resolves under.
const liveCredentialRef = "vault://eden/anthropic#setup-token" // #nosec G101 -- a secrets.Reference URI (loggable), not a secret value

// TestIntegration_LiveAdvisor_AllowsLowRiskRead is the wired-but-gated live arm: it adjudicates ONE
// concrete LOW-risk out-of-grant request (a Read) through a REAL claude reviewer subagent and
// asserts a sane allow + a non-empty rationale. SKIPPED (honest) without the live token / claude.
func TestIntegration_LiveAdvisor_AllowsLowRiskRead(t *testing.T) {
	t.Parallel()
	token := liveTokenOrSkip(t)

	advisor := newLiveAdvisor(t, token)

	request := agentsession.PermissionRequest{
		RequestID: "live-req-read-1",
		Tool:      "Read",
		Input:     []byte("path=README.md"),
		Reason:    "needs to read the project README to understand the repository layout before editing",
	}
	advice := agentsession.AdviceContext{
		SessionGoal:      "make a small, reversible documentation edit",
		Role:             "implementer",
		Phase:            "implement",
		Grants:           []agentsession.ToolGrant{{ID: "g-write", Tool: "Write"}},
		RecentTranscript: "assistant: I should read the README first to find the right section.",
		SecurityPosture:  "sandboxed-with-standing-grants",
		Risk:             agentsession.RiskLow, // a Read is read-scoped, reversible — the advisor MAY allow
	}

	// Bound the whole live adjudication so a slow model never hangs CI.
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()

	decision, err := advisor.Advise(ctx, request, advice)
	if err != nil {
		t.Fatalf("live Advise returned an error: %v", err)
	}
	if !decision.Allow {
		t.Errorf("the live reviewer denied a benign low-risk Read; decision=%+v", decision)
	}
	if strings.TrimSpace(decision.Rationale) == "" {
		t.Errorf("the live reviewer returned an empty rationale; every AI decision must be explainable")
	}
	if !strings.Contains(decision.By, "advisor:") {
		t.Errorf("the live decision By = %q, want an advisor:<name> stamp", decision.By)
	}
	// The token must NEVER leak into the decision's loggable surface.
	if strings.Contains(decision.Rationale, token) || strings.Contains(decision.By, token) {
		t.Fatalf("the live setup-token leaked into the decision surface")
	}
	t.Logf("live advisor decision: allow=%t scope=%s by=%q", decision.Allow, decision.Scope, decision.By)
}

// newLiveAdvisor builds an Advisor whose reviewer Factory is backed by the REAL claude-code adapter
// (empty model => claude's own default real model). The provider resolves the credential reference
// to the operator token; the value never enters a log, a Spec, or an Event.
func newLiveAdvisor(t *testing.T, token string) *agentruntime.Advisor {
	t.Helper()
	reviewerRoute := agentsession.RouteKey{Role: "reviewer", Phase: "review"}
	adapter, err := claudeadapter.New(claudeadapter.Config{})
	if err != nil {
		t.Fatalf("construct claude-code adapter: %v", err)
	}
	pool, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			reviewerRoute: {Harness: "claude-code", Model: ""}, // empty == claude's default real model
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"claude-code": adapter},
			Secrets:    secretstest.New(map[string]string{liveCredentialRef: token}),
			Transcript: agentsessiontest.NewTranscript(),
			Clock:      liveClock{},
		},
	)
	if err != nil {
		t.Fatalf("construct live reviewer Pool: %v", err)
	}
	advisor, err := agentruntime.NewAdvisor(
		agentruntime.AdvisorConfig{
			ReviewerRoute:      reviewerRoute,
			ReviewerWorkspace:  t.TempDir(),
			ReviewerCredential: secrets.Ref(liveCredentialRef),
			WallClock:          80 * time.Second,
		},
		agentruntime.AdvisorDeps{
			Sessions: pool,
			Observer: agentruntimetest.NewFakeObserver(),
			Clock:    agentruntimetest.FixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("NewAdvisor (live): %v", err)
	}
	return advisor
}

// liveTokenOrSkip reads CLAUDEADAPTER_LIVE_TOKEN from /workspace/.env.development (preferring an
// already-exported env var), or HONEST-SKIPS the live arm. It NEVER mints a token, launches auth,
// reads ~/.claude, or logs the value. An empty value (the committed placeholder) is a skip.
func liveTokenOrSkip(t *testing.T) string {
	t.Helper()
	token := os.Getenv(liveTokenKey)
	if token == "" {
		token = readTokenFromEnvFile(liveTokenEnvFile, liveTokenKey)
	}
	if token == "" {
		t.Skipf("%s not set (env or %s): the live advisor run is gated and skipped (no token, no auth)", liveTokenKey, liveTokenEnvFile)
	}
	if _, err := exec.LookPath("claude"); err != nil {
		t.Skip("claude binary not on PATH: skipping the live advisor arm")
	}
	return token
}

// readTokenFromEnvFile parses KEY=VALUE lines from the env file and returns the value for key (or
// "" if absent/empty/unreadable). It strips surrounding quotes and whitespace. The value is NEVER
// logged. A missing file is a quiet "" (the honest-skip path), not a failure.
func readTokenFromEnvFile(path, key string) string {
	file, err := os.Open(path) // #nosec G304 -- a fixed operator-managed env-file path, not user input
	if err != nil {
		return ""
	}
	defer func() { _ = file.Close() }() //nolint:errcheck // read-only env-file handle; close error is irrelevant to the read.
	prefix := key + "="
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if !strings.HasPrefix(line, prefix) {
			continue
		}
		value := strings.TrimSpace(strings.TrimPrefix(line, prefix))
		value = strings.Trim(value, `"'`)
		return value
	}
	return ""
}

// liveClock is a deterministic agentsession.Clock for the live reviewer Pool.
type liveClock struct{}

func (liveClock) Now() time.Time { return time.Date(2026, time.June, 15, 12, 0, 0, 0, time.UTC) }
