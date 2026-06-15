package gateway_test

import (
	"context"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// This file is the gateway test harness: a real gateway.New over the REAL record plane
// (orchestratortest.Manager — a real orchestrator.Pool over in-memory fakes) and the REAL
// live plane (a real agentsession.Pool over the agentsessiontest scripted Adapter + a real
// in-memory Transcript), served via httptest. No real claude/omp process, no container —
// the proof is the gateway's translation, fan-out, replay, control, and credential seam
// against the real frozen library seams, not a re-implementation.

// credentialRef is the loggable secrets.Reference the gateway threads into every Spec; the
// seeded secretstest provider resolves it to the agentsessiontest canary server-side. The
// VALUE (agentsessiontest.SeededCanary) must never reach a response/SSE/log.
//
//nolint:gosec // G101: an opaque vault REFERENCE (path), not a credential value — loggable by design.
const credentialRef = "vault://eden/anthropic#setup-token"

// fixedClock is a deterministic gateway.Clock / agentsession.Clock so the harness is
// reproducible.
type fixedClock struct{}

func (fixedClock) Now() time.Time { return time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC) }

// recordingLogger captures emitted log lines so a test asserts the credential canary never
// reaches a log. It is safe for concurrent use (the gateway logs from request goroutines).
type recordingLogger struct {
	mu    sync.Mutex
	lines []string
}

func (l *recordingLogger) Info(message string, fields ...any)  { l.record(message, fields) }
func (l *recordingLogger) Error(message string, fields ...any) { l.record(message, fields) }

func (l *recordingLogger) record(message string, fields []any) {
	l.mu.Lock()
	defer l.mu.Unlock()
	line := message
	for _, f := range fields {
		line += " " + sprint(f)
	}
	l.lines = append(l.lines, line)
}

// snapshot returns a copy of every recorded log line (used by the integration credential
// scan to prove the canary never reaches a log line).
func (l *recordingLogger) snapshot() []string {
	l.mu.Lock()
	defer l.mu.Unlock()
	out := make([]string, len(l.lines))
	copy(out, l.lines)
	return out
}

// sprint renders a log field value for the canary scan.
func sprint(v any) string {
	switch x := v.(type) {
	case string:
		return x
	default:
		return ""
	}
}

// harness bundles the served gateway plus the seams a test inspects (the scripted adapter
// for command assertions, the logger for the no-leak scan, the manager for record reads).
type harness struct {
	server  *httptest.Server
	gateway *gateway.Gateway
	adapter *agentsessiontest.Adapter
	manager *orchestratortest.Manager
	logger  *recordingLogger
	baseURL string
}

// newHarness builds a gateway over a scripted session and serves it. The script is the
// agentsession.Event sequence the opened session streams after the first Prompt. Every
// server/session is reaped on t.Cleanup (no leak).
func newHarness(t *testing.T, script ...agentsession.Event) *harness {
	t.Helper()
	return newHarnessWithAdapter(t, agentsessiontest.New(script...))
}

// newHarnessWithAdapter builds a gateway over a PREPARED scripted adapter (so a test can pin
// reactions — e.g. OnPermissionAnswer — before the session opens) and serves it. It is the
// variant the permission round-trip uses; newHarness is the bare-script convenience over it.
func newHarnessWithAdapter(t *testing.T, adapter *agentsessiontest.Adapter) *harness {
	t.Helper()

	provider := secretstest.New(map[string]string{credentialRef: agentsessiontest.SeededCanary})
	transcript := agentsessiontest.NewTranscript()

	routing := map[agentsession.RouteKey]agentsession.Route{
		gatewayRouteKey(): {Harness: "fake", Model: "fake-fable-5"},
	}
	pool, err := agentsession.New(
		agentsession.Config{Routing: routing},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"fake": adapter},
			Secrets:    provider,
			Transcript: transcript,
			Clock:      fixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("agentsession.New: %v", err)
	}

	manager := orchestratortest.New(orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()))
	logger := &recordingLogger{}

	g, err := gateway.New(
		gateway.Config{
			Credential: secrets.Ref(credentialRef),
			Routing:    gatewayRouteKey(),
			Workspace:  "/workspace/eden",
			Grants:     []agentsession.ToolGrant{{ID: "grant-write", Tool: "Write"}},
		},
		gateway.Deps{
			Manager:    manager,
			Sessions:   pool,
			Transcript: transcript,
			Clock:      fixedClock{},
			Logger:     logger,
		},
	)
	if err != nil {
		t.Fatalf("gateway.New: %v", err)
	}

	server := httptest.NewServer(g.Handler())
	t.Cleanup(func() {
		server.Close()
		_ = g.Close(context.Background()) //nolint:errcheck // test cleanup reap; a close fault is not a test signal (the reaper is best-effort).
	})

	return &harness{
		server:  server,
		gateway: g,
		adapter: adapter,
		manager: manager,
		logger:  logger,
		baseURL: server.URL,
	}
}

// gatewayRouteKey is the RouteKey the harness routes the opened session under (matches the
// gateway Config.Routing). It is independent of the orchestrator template's routing — the
// gateway opens its OWN session on the live plane.
func gatewayRouteKey() agentsession.RouteKey {
	return agentsession.RouteKey{Role: "assistant"}
}

// createBody is the canonical create-session request body for a project under the default
// template.
func createBody(prompt string) map[string]any {
	return map[string]any{
		"organizationId":  "org-eden",
		"projectId":       "proj-chat",
		"templateName":    orchestratortest.DefaultTemplate().Ref.Name,
		"templateVersion": orchestratortest.DefaultTemplate().Ref.Version,
		"by":              "tester",
		"prompt":          prompt,
	}
}

// compile-time assertion: the orchestratortest manager satisfies the gateway's record port.
var _ orchestrator.Manager = (*orchestratortest.Manager)(nil)
