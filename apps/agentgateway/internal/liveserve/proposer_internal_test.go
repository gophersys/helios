package liveserve

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// TestParseProductConfig proves the live proposer's robust parse: a bare JSON object parses, a
// fenced/prose-wrapped object is isolated and parses, a partial object parses (the gateway fills
// the gaps), and non-JSON falls back (ok=false) so the gateway applies sane defaults. The parse is
// best-effort by design — a parse failure is NOT an error, it is a defaults fallback.
func TestParseProductConfig(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name     string
		input    string
		wantOK   bool
		wantName string // productName when ok (pre-normalization, as parsed)
		wantKind string
	}{
		{
			name:     "bare object",
			input:    `{"productName":"invoice-service","productKind":"service","summary":"bills"}`,
			wantOK:   true,
			wantName: "invoice-service",
			wantKind: "service",
		},
		{
			name:     "markdown fenced object",
			input:    "Here is the config:\n```json\n{\"productName\":\"cli-tool\",\"productKind\":\"cli\"}\n```\nHope that helps!",
			wantOK:   true,
			wantName: "cli-tool",
			wantKind: "cli",
		},
		{
			name:     "partial object (gateway fills the rest)",
			input:    `{"productName":"lib-x"}`,
			wantOK:   true,
			wantName: "lib-x",
			wantKind: "", // empty → the gateway defaults it to service
		},
		{name: "prose only, no object", input: "I cannot do that.", wantOK: false},
		{name: "empty", input: "", wantOK: false},
		{name: "malformed object", input: `{"productName": }`, wantOK: false},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			configuration, ok := parseProductConfig(testCase.input)
			if ok != testCase.wantOK {
				t.Fatalf("parseProductConfig(%q) ok = %v, want %v", testCase.input, ok, testCase.wantOK)
			}
			if !testCase.wantOK {
				return
			}
			if configuration.ProductName != testCase.wantName {
				t.Fatalf("productName = %q, want %q", configuration.ProductName, testCase.wantName)
			}
			if configuration.ProductKind != testCase.wantKind {
				t.Fatalf("productKind = %q, want %q", configuration.ProductKind, testCase.wantKind)
			}
		})
	}
}

// scriptedFactory is a fake agentsession.Factory for the proposer's one-shot drive: Open returns a
// session whose Events stream ends on a terminal Result carrying resultText, OR Open returns
// openErr (the infrastructure-fault path). No real harness, no process.
type scriptedFactory struct {
	resultText string
	openErr    error
}

//nolint:ireturn,gocritic // satisfies the agentsession.Factory port (Spec is the contract's by-value session input).
func (f scriptedFactory) Open(_ context.Context, _ agentsession.Spec) (agentsession.Session, error) {
	if f.openErr != nil {
		return nil, f.openErr
	}
	return &scriptedSession{resultText: f.resultText}, nil
}

// scriptedSession is the fake one-shot session: Events yields a single terminal Result, Control is
// a no-op admit, Close is idempotent. It carries exactly the surface the proposer drives.
type scriptedSession struct {
	resultText string
}

//nolint:ireturn // satisfies the agentsession.Session port for the proposer drive.
func (s *scriptedSession) Events(_ context.Context, _ agentsession.Cursor) agentsession.Stream {
	return &scriptedStream{resultText: s.resultText}
}

func (s *scriptedSession) Control(_ context.Context, _ agentsession.Command) (agentsession.Ack, error) {
	return agentsession.Ack{Seq: 1}, nil
}

func (s *scriptedSession) Resolve(_ context.Context, _ string, _ agentsession.Decision) (agentsession.Ack, error) {
	return agentsession.Ack{}, nil
}

func (s *scriptedSession) Close(_ context.Context) error { return nil }

// scriptedStream yields one terminal Result event then ends cleanly.
type scriptedStream struct {
	resultText string
	done       bool
}

func (s *scriptedStream) Next(_ context.Context) (agentsession.Event, bool) {
	if s.done {
		return agentsession.Event{}, false
	}
	s.done = true
	return agentsession.Event{
		Seq:      1,
		Kind:     agentsession.EventResult,
		Terminal: &agentsession.TerminalPayload{ResultText: s.resultText},
	}, true
}

func (s *scriptedStream) Err() error { return nil }

// TestHarnessProposerDrivesOneShot proves the live proposer opens a session, drains the one-shot
// turn to its terminal Result, and parses the result text into the proposed ProductConfig.
func TestHarnessProposerDrivesOneShot(t *testing.T) {
	t.Parallel()
	proposer := &harnessProposer{
		sessions: scriptedFactory{resultText: `{"productName":"billing-api","productKind":"service","summary":"invoices"}`},
		spec:     agentsession.Spec{Workspace: "/tmp/x", Routing: liveRouteKey()},
	}
	configuration, err := proposer.Propose(context.Background(), "build a billing api")
	if err != nil {
		t.Fatalf("Propose returned an error on a clean one-shot: %v", err)
	}
	if configuration.ProductName != "billing-api" || configuration.ProductKind != "service" {
		t.Fatalf("Propose parsed config = %+v, want billing-api/service", configuration)
	}
}

// TestHarnessProposerFallsBackOnNonJSON proves a model reply that is NOT JSON is NOT an error: the
// proposer returns the zero config and the gateway normalizes it to sane defaults (no model fault).
func TestHarnessProposerFallsBackOnNonJSON(t *testing.T) {
	t.Parallel()
	proposer := &harnessProposer{
		sessions: scriptedFactory{resultText: "I think you should build something nice."},
		spec:     agentsession.Spec{Workspace: "/tmp/x", Routing: liveRouteKey()},
	}
	configuration, err := proposer.Propose(context.Background(), "build a thing")
	if err != nil {
		t.Fatalf("a non-JSON reply must NOT error (the gateway fills defaults), got: %v", err)
	}
	// The zero config is returned; gateway.NormalizeProductConfig (proven in the gateway tests)
	// turns it into a complete spec. Here we only assert the proposer did not fabricate fields.
	if configuration.ProductName != "" || configuration.ProductKind != "" {
		t.Fatalf("non-JSON fallback returned non-zero config: %+v", configuration)
	}
}

// TestHarnessProposerSurfacesOpenFault proves an INFRASTRUCTURE fault (the session cannot open) is
// returned as a wrapped, classified error — distinct from a parse fallback.
func TestHarnessProposerSurfacesOpenFault(t *testing.T) {
	t.Parallel()
	proposer := &harnessProposer{
		sessions: scriptedFactory{openErr: errors.New(errors.KindUnavailable, "harness unreachable")},
		spec:     agentsession.Spec{Workspace: "/tmp/x", Routing: liveRouteKey()},
	}
	_, err := proposer.Propose(context.Background(), "build a thing")
	if err == nil {
		t.Fatal("an Open fault must surface as an error, got nil")
	}
	if errors.KindOf(err) != errors.KindUnavailable {
		t.Fatalf("open-fault error Kind = %v, want unavailable", errors.KindOf(err))
	}
	if !strings.Contains(err.Error(), "open propose session") {
		t.Fatalf("open-fault error = %q, want it to name the open step", err.Error())
	}
}

// compile-time assertions for the fakes.
var (
	_ agentsession.Factory = scriptedFactory{}
	_ agentsession.Session = (*scriptedSession)(nil)
	_ agentsession.Stream  = (*scriptedStream)(nil)
	_ gateway.Proposer     = (*harnessProposer)(nil)
)
