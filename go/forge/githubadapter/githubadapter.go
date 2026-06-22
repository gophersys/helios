// Package githubadapter is the concrete GitHub REST implementation of the
// forge.Forge port. It speaks the GitHub REST API v3 over an injected HTTP
// transport, resolving the credential named by each request through the injected
// secrets.Provider at the moment of the call (never holding a token in the struct,
// the request, a log, or an error — 07 §2).
//
// Module: github.com/gophersys/libs/go/forge/githubadapter  (go 1.26)
//
// The transport is the HTTPDoer interface so the wire behavior is exercised against
// a fake in unit tests (table: create-ok, already-exists-422→get, 401) and against
// the REAL github.com under the integration build tag. New is the pure constructor
// spine: it validates Config + Deps and wires; the first network call is the first
// CreateRepo.
package githubadapter

import (
	"net/http"
	"net/url"
	"strings"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/forge"
	"github.com/gophersys/libs/go/secrets"
)

// defaultBaseURL is GitHub's public REST API root. A self-hosted GitHub Enterprise
// instance overrides it via Config.BaseURL (e.g. "https://github.example.com/api/v3").
const defaultBaseURL = "https://api.github.com"

// defaultAPIVersion is the GitHub REST API version pin sent in the
// X-GitHub-Api-Version header so a future default-version bump on GitHub's side
// cannot silently change the wire shape this adapter parses.
const defaultAPIVersion = "2022-11-28"

// readBodyLimit caps how many bytes of a response body the adapter reads, so a
// hostile or runaway forge cannot exhaust memory through an unbounded error body.
const readBodyLimit = 1 << 20 // 1 MiB

// HTTPDoer is the injected HTTP transport — the single seam over the network. It is
// the consumer-defined narrowing of *http.Client to the one method this adapter
// needs (accept the interface; *http.Client satisfies it). A fake HTTPDoer drives
// the unit suite; *http.Client drives the integration suite and production.
type HTTPDoer interface {
	Do(request *http.Request) (*http.Response, error)
}

// Config is the immutable, fully-resolved construction input. It is credential-free
// by construction: the token is never configured, only NAMED per request by a
// secrets.Reference and resolved through Deps.Secrets at call time (07 §2).
type Config struct {
	// BaseURL overrides the GitHub REST API root for a GitHub Enterprise host. Empty
	// selects the public api.github.com. A non-empty value must be an absolute http(s)
	// URL; New rejects a malformed one.
	BaseURL string

	// UserAgent is the User-Agent header GitHub requires on every request. Empty
	// selects a stable default identifying the Eden forge connector.
	UserAgent string

	// EnableEphemeralDelete OPTS IN to the destructive DeleteRepo capability. It is FALSE by
	// default, so a PRODUCTION composition root (the saga, the orchestrator) cannot delete a
	// repository at all — DeleteRepo refuses every call before touching the network. ONLY an
	// integration-test composition sets it true; and even then GuardDelete still confines deletion
	// to ephemeral `eden-it-*` repositories that are not on the protected denylist. Two walls
	// (capability-off + name-guard) so a real repository can never be deleted.
	//
	// TODO(eden, REMOVE THIS): DeleteRepo + this opt-in exist ONLY to reap throwaway
	// integration-test repositories under MateoSegura while the delete_repo PAT scope is live.
	// Remove DeleteRepo, this flag, and the delete_repo scope once test repos are reaped by a
	// safer mechanism (a dedicated disposable GitHub org / sandbox account with automated TTL
	// cleanup, or repo auto-expiry) — so NO Eden code path can delete a repository on a real
	// account, by construction. This is a deliberate, temporary, clearly-marked affordance.
	EnableEphemeralDelete bool
}

// Deps is the injected hexagon: the HTTP transport and the secrets provider. Both
// are REQUIRED — a create always authenticates and always crosses the network.
// Accepting the interfaces here is the accept-interfaces rule; New returns the
// concrete *Connector.
type Deps struct {
	// HTTP is the transport every request rides. Required (*http.Client in production,
	// a fake in unit tests).
	HTTP HTTPDoer

	// Secrets resolves a request's Credential Reference to a short-lived Secret at the
	// moment of the call. Required: a forge create always authenticates.
	Secrets secrets.Provider
}

// defaultUserAgent identifies the connector to GitHub when Config.UserAgent is empty.
const defaultUserAgent = "eden-forge-connector"

// errInvalidConfig is the construction-time wiring sentinel (a nil transport, a nil
// provider, or a malformed BaseURL). It carries KindInvalid because Deps/Config are
// malformed; the composition root can branch on it via errors.Is.
var errInvalidConfig = errors.New(errors.KindInvalid, "githubadapter.New: invalid configuration or dependencies")

// Connector is the concrete forge.Forge returned by New. It holds the immutable
// resolved base URL, the headers, and the injected ports. Safe for concurrent use
// iff the injected transport is (*http.Client is). Zero value is not usable;
// construct via New.
type Connector struct {
	baseURL   string
	userAgent string
	http      HTTPDoer
	secrets   secrets.Provider
	// ephemeralDeleteEnabled gates the destructive DeleteRepo: false (the default) refuses every
	// delete before any network call, so production connectors cannot delete a repository at all.
	ephemeralDeleteEnabled bool
}

// compile-time assertion: *Connector implements the forge.Forge port.
var _ forge.Forge = (*Connector)(nil)

// New is the pure constructor spine (10 §9). PURE: no I/O, no env reads, no clock,
// no network dial. It validates Deps + Config, defaults the knobs, and returns the
// concrete *Connector. The first network call is the first CreateRepo.
//
//nolint:gocritic // contract: New(configuration, dependencies) is the canon spine; Config/Deps pass by value (the frozen, copyable inputs).
func New(configuration Config, dependencies Deps) (*Connector, error) {
	if dependencies.HTTP == nil {
		return nil, errors.Wrap(errors.KindInvalid, "githubadapter.New: Deps.HTTP is required", errInvalidConfig)
	}
	if dependencies.Secrets == nil {
		return nil, errors.Wrap(errors.KindInvalid, "githubadapter.New: Deps.Secrets is required", errInvalidConfig)
	}

	base := strings.TrimRight(strings.TrimSpace(configuration.BaseURL), "/")
	if base == "" {
		base = defaultBaseURL
	} else if err := validateBaseURL(base); err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "githubadapter.New: invalid Config.BaseURL", err)
	}

	userAgent := strings.TrimSpace(configuration.UserAgent)
	if userAgent == "" {
		userAgent = defaultUserAgent
	}

	return &Connector{
		baseURL:                base,
		userAgent:              userAgent,
		http:                   dependencies.HTTP,
		secrets:                dependencies.Secrets,
		ephemeralDeleteEnabled: configuration.EnableEphemeralDelete,
	}, nil
}

// The BaseURL validation sentinels are declared (not invented inline) so a caller
// could branch on them via errors.Is and err113 stays satisfied (no dynamic error
// at a throw site). New wraps the matching one with %w when a Config.BaseURL is
// malformed.
var (
	errBaseURLUnparseable = errors.New(errors.KindInvalid, "Config.BaseURL is not a valid URL")
	errBaseURLNotHTTP     = errors.New(errors.KindInvalid, "Config.BaseURL must use the http or https scheme")
	errBaseURLNoHost      = errors.New(errors.KindInvalid, "Config.BaseURL has no host")
)

// validateBaseURL ensures an overridden BaseURL is an absolute http(s) URL with a
// host, so a malformed override fails at construction, not on the first request. It
// returns one of the declared sentinels (never a dynamic error) so the throw site
// stays static and a caller may branch on the cause with errors.Is.
func validateBaseURL(raw string) error {
	parsed, err := url.Parse(raw)
	if err != nil {
		return errBaseURLUnparseable
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return errBaseURLNotHTTP
	}
	if parsed.Host == "" {
		return errBaseURLNoHost
	}
	return nil
}
