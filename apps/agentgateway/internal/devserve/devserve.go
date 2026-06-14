// Package devserve is the DEV-ONLY composition root for the agentsession gateway: it wires
// a fully working gateway.Gateway over IN-MEMORY FAKES so the SvelteKit frontend has a real,
// runnable REST+SSE backend to develop against WITHOUT the gated real claude setup-token, a
// real harness process, a container, or a persistence substrate.
//
// It is the deliberate counterpart to cmd/agentgateway (the production entrypoint, which
// awaits the kernel composition root + real adapters and imports NO test fakes). The fakes
// live here, behind a clearly dev-only package, so the production command stays fake-free.
//
// What it wires (the same hexagon gateway.New validates, but every port is a fake):
//
//   - Manager: orchestratortest.Manager — a real orchestrator.Pool over in-memory fakes,
//     seeded with a default AgentTemplate so Spawn succeeds (the record plane).
//   - Sessions: a REAL agentsession.Pool whose Adapter is the agentsessiontest scripted
//     harness emitting a realistic demo turn (message + thinking + text deltas, a granted
//     tool start/end, a four-token usage tick, a clean terminal Result), with a secretstest
//     provider seeded so the fake setup-token reference resolves server-side, a real
//     in-memory Transcript, and a fixed Clock (the live plane).
//   - Transcript: the SAME real in-memory Transcript the Pool appends to, so a post-mortem
//     transcript read still serves the full ordered Run.
//   - Clock: a fixed, deterministic dev clock.
//
// No credential value ever reaches the browser: the seeded reference is resolved INSIDE
// agentsession.Open (server-side), exactly as production resolves the real setup-token.
package devserve

import (
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// CredentialReference is the loggable secrets.Reference the dev gateway threads into every
// opened session's Spec. The seeded secretstest provider resolves it to a FAKE setup-token
// server-side, so the live plane exercises the credential seam without the real, gated
// claude setup-token. The resolved value never reaches the browser (REQ-0021).
//
//nolint:gosec // G101: an opaque vault REFERENCE (path), not a credential value — loggable by design.
const CredentialReference = "vault://eden/development#setup-token"

// fakeSetupToken is the FAKE setup-token the seeded provider resolves CredentialReference to.
// It is intentionally not a real credential: the dev gateway never authenticates to anything
// (the scripted adapter has no upstream). The value still never leaves the harness seam.
//
//nolint:gosec // G101: a deliberately FAKE dev token (never a real credential) for the fake harness.
const fakeSetupToken = "DEV-FAKE-setup-token-not-a-real-credential"

// devHarnessName is the adapter key the dev Route binds, matched in the Pool's Adapters map.
const devHarnessName = "fake"

// devModelName is the model the dev Route reports (surfaced in usage/ledger projections).
const devModelName = "fake-fable-5"

// devClockInstant is the fixed wall-clock the dev Clock reports, so dev runs are reproducible
// and timestamps in the SSE/REST projections are stable.
var devClockInstant = time.Date(2026, time.June, 13, 12, 0, 0, 0, time.UTC)

// devClock is the deterministic gateway.Clock / agentsession.Clock the dev composition
// injects so New stays pure and dev output is reproducible.
type devClock struct{}

// Now returns the fixed dev instant.
func (devClock) Now() time.Time { return devClockInstant }

// Logger is the narrow structured-log seam the dev composition adapts the command's logger
// onto (it mirrors gateway.Logger so the cmd does not import the gateway package directly
// for the port). A field is NEVER a secret — the credential seam is enforced upstream.
type Logger interface {
	Info(message string, fields ...any)
	Error(message string, fields ...any)
}

// Config is the immutable dev-composition input. It is deliberately tiny: the dev gateway
// has no real routing/grants/workspace to resolve, so the only knob is the optional Logger.
type Config struct {
	// Logger, when non-nil, is wired onto the gateway so dev requests emit structured lines.
	// Optional: a nil Logger is a no-op (the gateway tolerates a nil Logger seam).
	Logger Logger
}

// BuildDevGateway builds a fully wired, runnable gateway.Gateway over in-memory fakes (the
// dev composition root). It is PURE in the gateway sense — it opens no listener and spawns no
// goroutine (the caller's Serve does the I/O) — but it does construct the fake ports. It
// returns the concrete *gateway.Gateway the caller serves, or a wrapped error if any seam
// fails to construct.
func BuildDevGateway(configuration Config) (*gateway.Gateway, error) {
	clock := devClock{}

	// The live plane: a REAL agentsession.Pool whose Adapter is the scripted demo harness, a
	// seeded secrets provider resolving the fake setup-token server-side, and a real in-memory
	// Transcript the Pool appends to (so the transcript route reconstructs the full Run).
	adapter := agentsessiontest.New(DemoScript()...)
	provider := secretstest.New(map[string]string{CredentialReference: fakeSetupToken})
	transcript := agentsessiontest.NewTranscript()

	pool, err := agentsession.New(
		agentsession.Config{
			Routing: map[agentsession.RouteKey]agentsession.Route{
				devRouteKey(): {Harness: devHarnessName, Model: devModelName},
			},
		},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{devHarnessName: adapter},
			Secrets:    provider,
			Transcript: transcript,
			Clock:      clock,
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "devserve: build agentsession pool", err)
	}

	// The record plane: a real orchestrator.Pool over in-memory fakes, seeded with the default
	// template so a create request's Spawn succeeds.
	manager := orchestratortest.New(orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()))

	g, err := gateway.New(
		gateway.Config{
			Credential: secrets.Ref(CredentialReference),
			Routing:    devRouteKey(),
			Workspace:  "/workspace/eden-development",
			Grants:     []agentsession.ToolGrant{{ID: "grant-write", Tool: "Write"}},
		},
		gateway.Deps{
			Manager:    manager,
			Sessions:   pool,
			Transcript: transcript,
			Clock:      clock,
			Logger:     configuration.Logger,
			// The create-flow wizard's propose seam: a DETERMINISTIC, prompt-derived fake (no model
			// call) so POST /product/propose is stable for the Playwright E2E.
			Proposer: fakeProposer{},
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "devserve: build gateway", err)
	}
	return g, nil
}

// DefaultCreateTemplate exposes the template Name/Version a create request must name so the
// seeded record plane's Spawn resolves the default template. The dev frontend (or a smoke
// test) posts these on POST /sessions.
func DefaultCreateTemplate() (name, version string) {
	template := orchestratortest.DefaultTemplate()
	return template.Ref.Name, template.Ref.Version
}

// devRouteKey is the RouteKey the dev gateway opens its live session under (matched in the
// Pool's Routing). It is independent of the orchestrator template's routing — the gateway
// opens its OWN session on the live plane.
func devRouteKey() agentsession.RouteKey {
	return agentsession.RouteKey{Role: "assistant"}
}

// DemoScript is the realistic demo turn the scripted dev adapter streams after the create
// request's first prompt: an assistant message with a thinking block and streamed text
// deltas, a granted tool start/end, a four-token usage tick, and a clean terminal Result
// carrying the authoritative ledger. It is the agentsessiontest canonical full-taxonomy run,
// so the dev frontend renders every REQ-0024 event type against a working backend.
func DemoScript() []agentsession.Event {
	return agentsessiontest.CanonicalScript()
}
