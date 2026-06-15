// Package liveserve is the LIVE-LOCAL composition root for the agentsession gateway: it wires
// the full internal/gateway.Gateway over a REAL agentsession.Pool driving a REAL harness CLI
// (claude-code or omp) whose credential is resolved server-side from the REAL local Vault
// (secrets/vaultadapter, ModeUserpass — ADR-0022 #1), behind the EXACT REST+SSE surface the B7
// chat UI already calls. It is the Milestone-B B8 single-process demo path (ADR-0022 #2): one
// binary, no NATS, no pods — the harness runs in-process as an os/exec subprocess, and the
// gateway tails its normalized agentsession.Event stream over SSE.
//
// It is the deliberate sibling of internal/devserve (the in-memory FAKE path) and cmd/agentgateway
// (the STATELESS NATS→SSE production path):
//
//   - devserve  — fake scripted harness + fake secrets; zero external substrate (fast UI dev).
//   - liveserve — REAL harness + REAL Vault; in-process record plane (the live-local demo). ← here
//   - cmd/agentgateway — stateless NATS→SSE bridge over real agent-runtime pods (production).
//
// The RECORD plane (Spawn/list/get/stop — admission + tenancy) is the in-process
// orchestratortest.Manager: it is a real orchestrator.Pool over in-memory fakes, so a create
// request is admitted and recorded WITHOUT a real container/pod (the demo needs no orchestrator-
// provisioned pod — agentsession runs the harness in-process). The LIVE plane the UI streams off
// is the REAL agentsession.Pool injected as Deps.Sessions; the gateway opens its own live Session
// there, folding the gateway's opaque Vault Reference into the Spec, and agentsession.Open
// resolves it server-side. The credential VALUE never reaches the browser, a log, or any record
// (REQ-0021): it crosses only into the harness child env (CLAUDE_CODE_OAUTH_TOKEN), via Secret.Use.
//
// This package imports orchestratortest exactly as devserve does — it is a documented DEV-LOCAL
// convenience entrypoint, not the production command (cmd/agentgateway imports no fakes).
package liveserve

import (
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/claudeadapter"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/vaultadapter"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// Logger is the narrow structured-log seam the live composition adapts the command's logger onto
// (it mirrors gateway.Logger so the cmd does not import the gateway package for the port). A field
// is NEVER a secret — the credential seam is enforced upstream by the harness/secrets contract.
type Logger interface {
	Info(message string, fields ...any)
	Error(message string, fields ...any)
}

// Config is the immutable live-composition input (the configuration pattern: read once at the
// edge, frozen). Every field is resolved by the command from the environment BEFORE New, so this
// package reads NO env and the constructor stays pure. No field is ever a secret value — the Vault
// credential rides as an opaque, loggable secrets.Reference resolved server-side at Open.
type Config struct {
	// VaultAddress is the Vault API address (e.g. http://127.0.0.1:8200). Required.
	VaultAddress string
	// VaultUsername / VaultPassword are the userpass bootstrap credential (ModeUserpass, the local
	// path). VaultPassword is kept off every loggable surface; it lives only in this struct and the
	// adapter's login call body. Required.
	VaultUsername string
	VaultPassword string
	// CredentialReference is the opaque vault:// Reference the gateway folds into every opened
	// session's Spec. Resolved server-side at agentsession.Open to the harness credential VALUE.
	// Canonical form: vault://<mount>/<path>#<key> (e.g. vault://eden/development#setup-token).
	CredentialReference string
	// Harness is the adapter key the live route binds: "claude-code" (default) or "omp".
	Harness string
	// Model is the model id reported on the route (surfaced in usage/ledger projections); empty is
	// fine for claude (it uses its account default).
	Model string
	// Workspace is the directory the harness CLI runs in (its CWD). Required; the command provisions
	// a real local directory (the demo needs no orchestrator-provisioned pod workspace).
	Workspace string
	// Logger, when non-nil, is wired onto the gateway so live requests emit structured lines.
	Logger Logger
}

// systemClock is the production gateway.Clock / agentsession.Clock (the wall clock; the
// composition root is the one place a real clock is read — the libraries stay pure).
type systemClock struct{}

// Now returns the current wall-clock instant.
func (systemClock) Now() time.Time { return time.Now() }

// BuildLiveGateway builds a fully wired, runnable gateway.Gateway over the REAL harness + REAL
// Vault. It is PURE in the gateway sense — it opens no listener and spawns no goroutine (the
// caller's Serve does the I/O) — but it does construct the real ports (the Vault adapter dials
// nothing until the first Open; the harness spawns nothing until the first session). It returns
// the concrete *gateway.Gateway the caller serves, or a wrapped error if any seam is misconfigured.
//
//nolint:gocritic // Config is the frozen, copyable composition input (the configuration pattern, read once at the edge); the builder takes it by value to match BuildDevGateway.
func BuildLiveGateway(configuration Config) (*gateway.Gateway, error) {
	if err := configuration.validate(); err != nil {
		return nil, err
	}
	clock := systemClock{}

	// The credential plane: the secrets Mediator over the REAL Vault backend (userpass), routed
	// under the "vault" scheme. agentsession.Open resolves the opaque Reference through this,
	// server-side, into the harness child env — the value never reaches this package's surface.
	provider, err := buildSecretsProvider(&configuration)
	if err != nil {
		return nil, err
	}

	// The durable Run log: ONE in-process Transcript injected into BOTH the Pool (where the harness
	// stream is appended + the Seq assigned) AND the gateway (the post-mortem transcript route), so a
	// read after the live session is reaped still serves the full ordered Run (REQ-0020).
	runLog := newTranscript()

	// The live plane: a REAL agentsession.Pool whose Adapter is the REAL harness CLI (claude-code |
	// omp), the Vault-backed secrets provider, the shared in-memory Transcript, and the system clock.
	claudeAdapter, err := claudeadapter.New(claudeadapter.Config{})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "liveserve: build claude adapter", err)
	}
	ompAdapter, err := ompadapter.New(ompadapter.Config{})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "liveserve: build omp adapter", err)
	}
	pool, err := agentsession.New(
		agentsession.Config{
			Routing: map[agentsession.RouteKey]agentsession.Route{
				liveRouteKey(): {Harness: configuration.Harness, Model: configuration.Model},
			},
		},
		agentsession.Deps{
			Adapters: map[string]agentsession.Adapter{
				"claude-code": claudeAdapter,
				"omp":         ompAdapter,
			},
			Secrets:    provider,
			Transcript: runLog,
			Clock:      clock,
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "liveserve: build agentsession pool", err)
	}

	// The record plane: a real orchestrator.Pool over in-memory fakes, seeded with the default
	// template so a create request's Spawn is admitted and recorded (no real pod is provisioned —
	// the live harness runs in-process via the Pool above).
	manager := orchestratortest.New(orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()))

	// The standing grant the live gateway opens both the chat session AND the propose session
	// under: a conservative read-only Read (the demo agent may Read but not Write/Bash without an
	// explicit per-call permission, 07 §3) — keeps an unattended live agent safe.
	grants := []agentsession.ToolGrant{{ID: "grant-read", Tool: "Read", ReadOnly: true}}

	gw, err := gateway.New(
		gateway.Config{
			Credential: secrets.Ref(configuration.CredentialReference),
			Routing:    liveRouteKey(),
			Workspace:  configuration.Workspace,
			Grants:     grants,
		},
		gateway.Deps{
			Manager:    manager,
			Sessions:   pool,
			Transcript: runLog,
			Clock:      clock,
			Logger:     configuration.Logger,
			// The create-flow wizard's propose seam: ONE real harness turn (claude-code | omp)
			// instructed to return ONLY ProductConfig JSON, opened on the SAME live Pool the chat
			// streams off (the harness under the Vault-resolved credential). A parse failure falls
			// back to the gateway's sane defaults; only an Open/stream fault surfaces as an error.
			Proposer: &harnessProposer{
				sessions: pool,
				spec: agentsession.Spec{
					Workspace:  configuration.Workspace,
					Routing:    liveRouteKey(),
					Grants:     grants,
					Credential: secrets.Ref(configuration.CredentialReference),
				},
				logger: configuration.Logger,
			},
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "liveserve: build gateway", err)
	}
	return gw, nil
}

// buildSecretsProvider builds the secrets Mediator over the REAL Vault backend (ModeUserpass —
// the local bootstrap, ADR-0022 #1). The bootstrap login is lazy (first Resolve), so New stays
// cheap and a Vault that is briefly unreachable at startup does not fail construction.
//
//nolint:ireturn // returns the secrets.Provider port the agentsession Pool holds (the frozen surface).
func buildSecretsProvider(configuration *Config) (secrets.Provider, error) {
	adapter, err := vaultadapter.New(
		vaultadapter.Config{Address: configuration.VaultAddress, Mode: vaultadapter.ModeUserpass},
		vaultadapter.Deps{Username: configuration.VaultUsername, Password: configuration.VaultPassword},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "liveserve: build vault backend", err)
	}
	mediator, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": adapter}},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "liveserve: build secrets mediator", err)
	}
	return mediator, nil
}

// DefaultCreateTemplate exposes the template Name/Version a create request must name so the seeded
// record plane's Spawn resolves the default template. The dev frontend (or a smoke test) posts
// these on POST /sessions (the UI's DEV_TENANCY names exactly this template).
func DefaultCreateTemplate() (name, version string) {
	template := orchestratortest.DefaultTemplate()
	return template.Ref.Name, template.Ref.Version
}

// liveRouteKey is the RouteKey the live gateway opens its session under (matched in the Pool's
// Routing). The gateway opens its OWN session on the live plane, independent of the orchestrator
// template's routing.
func liveRouteKey() agentsession.RouteKey {
	return agentsession.RouteKey{Role: "assistant"}
}

// validate checks the required configuration the command resolved from the environment, returning
// a wrapped KindInvalid error naming the missing field (never echoing a value).
func (c *Config) validate() error {
	switch {
	case c.VaultAddress == "":
		return errors.New(errors.KindInvalid, "liveserve: VaultAddress is required")
	case c.VaultUsername == "":
		return errors.New(errors.KindInvalid, "liveserve: VaultUsername is required")
	case c.VaultPassword == "":
		return errors.New(errors.KindInvalid, "liveserve: VaultPassword is required (the userpass bootstrap)")
	case c.CredentialReference == "":
		return errors.New(errors.KindInvalid, "liveserve: CredentialReference is required (the opaque vault:// ref)")
	case c.Workspace == "":
		return errors.New(errors.KindInvalid, "liveserve: Workspace is required (the harness CWD)")
	case c.Harness == "":
		return errors.New(errors.KindInvalid, "liveserve: Harness is required (claude-code|omp)")
	}
	return nil
}
