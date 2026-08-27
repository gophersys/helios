package agentsession

import (
	"context"

	"github.com/gophersys/libs/go/errors"
)

// Pool is the concrete Factory returned by New: it routes each Open to the Adapter
// named by the resolved Route, manages spawned sessions, assigns Seq against the
// Transcript, fans out to viewers, and reaps sessions on Close. Safe for concurrent
// use. Zero value unusable.
type Pool struct {
	configuration Config
	dependencies  Deps
}

// compile-time assertion: *Pool is the Factory.
var _ Factory = (*Pool)(nil)

// New is the pure constructor spine: no I/O, no clock read, no env read, no process
// spawn. It validates Config + Deps and returns the concrete *Pool. The first process
// spawn happens only at Pool.Open. It returns a wrapped ConfigError (errors.AsType) on
// a missing dependency.
//
//nolint:gocritic // hugeParam: Deps is the injected hexagon taken BY VALUE per the constructor spine (rule 10 §9); a pointer would break the spine.
func New(configuration Config, dependencies Deps) (*Pool, error) {
	if len(dependencies.Adapters) == 0 {
		return nil, errors.Wrap(errors.KindInvalid, "agentsession: New",
			ConfigError{Field: "Adapters", Message: "at least one harness adapter is required"})
	}
	for harness, adapter := range dependencies.Adapters {
		if adapter == nil {
			return nil, errors.Wrap(errors.KindInvalid, "agentsession: New",
				ConfigError{Field: "Adapters", Message: "adapter for harness " + harness + " is nil"})
		}
	}
	if dependencies.Secrets == nil {
		return nil, errors.Wrap(errors.KindInvalid, "agentsession: New",
			ConfigError{Field: "Secrets", Message: "a secrets.Provider is required to resolve the credential at Open"})
	}
	if dependencies.Transcript == nil {
		return nil, errors.Wrap(errors.KindInvalid, "agentsession: New",
			ConfigError{Field: "Transcript", Message: "a durable Transcript is required (Seq == transcript offset)"})
	}
	if dependencies.Clock == nil {
		return nil, errors.Wrap(errors.KindInvalid, "agentsession: New",
			ConfigError{Field: "Clock", Message: "an injected Clock is required so the library stamps Event.Time deterministically"})
	}
	return &Pool{configuration: configuration, dependencies: dependencies}, nil
}

// Open binds the credential, invokes the harness in the already-provisioned pod, and
// returns a live Session once the StateReady handshake is confirmed — or an error.
// It resolves the opaque Credential reference SERVER-SIDE here (never the value into
// the Spec or any Event); a missing init/ready handshake converts to AuthError (the
// silent-bad-token trap). Errors: RouteError (no route/adapter), AuthError, SpawnError.
//
//nolint:gocritic,ireturn // contract §2: Spec is the frozen copyable session input (configuration pattern) and Open returns the Session port — both the frozen surface.
func (p *Pool) Open(ctx context.Context, spec Spec) (Session, error) {
	// The peer contract is validated FIRST, before any I/O: a session that believes it is
	// reachable and is not, or a name that would mangle an argv/socket filename, is a
	// ConfigError at Open — never a silent non-membership.
	if err := validatePeerSpec(spec, p.dependencies.Peer != nil); err != nil {
		return nil, err
	}

	route, adapter, err := p.resolveRoute(spec.Routing)
	if err != nil {
		return nil, err
	}

	cred, err := p.injectCredential(ctx, spec, route)
	if err != nil {
		return nil, err
	}
	// The Secret is owned by the session for the harness lifetime (the adapter places
	// it at Spawn via Secret.Use); it is zeroized on session Close. We must NOT zeroize
	// here on the happy path.

	// The peer host tools are the LIBRARY's, injected here because an Adapter cannot reach
	// the plane. They must be in the Spec the adapter is SPAWNED with, and Spawn necessarily
	// precedes joinPeer below — so the toolset is handed its link afterwards, and until then
	// every handler answers KindUnavailable.
	peerTools := newPeerToolset(spec.Name, p.dependencies.Peer, nil)
	spec.HostTools = p.injectPeerHostTools(spec.HostTools, peerTools, adapter)

	conn, err := adapter.Spawn(ctx, spec, route, cred)
	if err != nil {
		cred.zeroize()
		if authErr, ok := errors.AsType[AuthError](err); ok {
			// An adapter that diagnoses a bad credential at spawn surfaces AuthError
			// directly (the setup-token precondition); pass it through, classified.
			return nil, errors.Wrap(errors.KindUnauthenticated, "agentsession: spawn harness", authErr)
		}
		return nil, errors.Wrap(errors.KindUnavailable, "agentsession: spawn harness",
			SpawnError{Harness: route.Harness})
	}

	// Register on the injected peer plane (nil,nil when there is no plane): the session's link
	// is the wire the pump corroborates delivery over and the deliver goroutine drains.
	link, err := p.joinPeer(ctx, spec)
	if err != nil {
		cred.zeroize()
		_ = conn.Close(ctx) //nolint:errcheck // best-effort reap; the join error is the actionable outcome.
		return nil, err
	}
	peerTools.bind(link)

	session, err := newSession(ctx, spec, route, conn, cred, p.dependencies, link)
	if err != nil {
		// newSession reaps the conn and zeroizes the credential on a failed handshake; leave
		// the plane too so the name does not linger in the roster.
		if link != nil {
			_ = link.Close(context.Background()) //nolint:errcheck // best-effort leave on a failed handshake.
		}
		return nil, err
	}
	return session, nil
}

// injectPeerHostTools returns the host-tool set the adapter is spawned with. The gate is the
// adapter's OWN declared CapPeerMessaging status, never a hard-coded harness name: a harness
// whose model drives Eden's host tools gets them, and one whose peer messaging is only partial
// (claude, whose model uses its NATIVE send) gets NEITHER — offering a model a tool its harness
// cannot honor is the "declared but unproven" lie the manifest exists to prevent, and widening
// that harness's allowlist to make it work is not the adapter's authority.
func (p *Pool) injectPeerHostTools(callerTools []HostTool, peerTools *peerToolset, adapter Adapter) []HostTool {
	if adapter.Manifest().Status(CapPeerMessaging) != CapFull {
		return callerTools
	}
	injected := peerTools.hostTools()
	if len(injected) == 0 {
		return callerTools
	}
	return withPeerHostTools(callerTools, injected)
}

// resolveRoute looks up the (harness, model) Route for a RouteKey and the Adapter
// registered for that harness. It returns a RouteError when either is missing.
//
//nolint:ireturn // Adapter is the lower harness PORT (contract §2); resolveRoute selects one by key — returning the port is the design.
func (p *Pool) resolveRoute(key RouteKey) (Route, Adapter, error) {
	route, ok := p.configuration.Routing[key]
	if !ok {
		return Route{}, nil, errors.Wrap(errors.KindInvalid, "agentsession: resolve route",
			RouteError{Phase: key.Phase, Role: key.Role})
	}
	adapter, ok := p.dependencies.Adapters[route.Harness]
	if !ok {
		return Route{}, nil, errors.Wrap(errors.KindInvalid, "agentsession: resolve adapter",
			RouteError{Harness: route.Harness})
	}
	return route, adapter, nil
}

// injectCredential resolves the opaque Credential reference to a short-lived Secret
// SERVER-SIDE and wraps it as an InjectedCredential. The value never enters the Spec
// or any Event; only the loggable Reference does. A zero reference or a resolution
// failure converts to AuthError carrying the Reference (never the value). The chosen
// vehicle defaults to VehicleEnv with the harness's expected env var name.
//
//nolint:gocritic // contract §2: Spec is the frozen, copyable session input (the configuration pattern); the port takes it by value.
func (p *Pool) injectCredential(ctx context.Context, spec Spec, route Route) (InjectedCredential, error) {
	if spec.Credential.IsZero() {
		return InjectedCredential{}, errors.Wrap(errors.KindUnauthenticated, "agentsession: resolve credential",
			AuthError{Reference: spec.Credential})
	}
	secret, err := p.dependencies.Secrets.Resolve(ctx, spec.Credential)
	if err != nil {
		return InjectedCredential{}, errors.Wrap(errors.KindUnauthenticated, "agentsession: resolve credential",
			AuthError{Reference: spec.Credential})
	}
	return InjectedCredential{
		Secret:  secret,
		Vehicle: VehicleEnv,
		EnvName: envNameFor(route.Harness),
	}, nil
}

// envNameFor maps a harness key to the child-process env var its CLI reads the
// credential from. Unknown harnesses default to the Claude name (the v1 entry).
func envNameFor(harness string) string {
	switch harness {
	case "claude-code":
		return "CLAUDE_CODE_OAUTH_TOKEN"
	case "omp":
		return "OMP_AUTH_TOKEN"
	case "codex":
		return "CODEX_AUTH_TOKEN"
	default:
		return "CLAUDE_CODE_OAUTH_TOKEN"
	}
}

// zeroize best-effort wipes the resolved Secret. Called when a session is reaped or a
// spawn/handshake fails, so the plaintext does not outlive the harness.
func (c InjectedCredential) zeroize() {
	if c.Secret != nil {
		c.Secret.Zeroize()
	}
}
