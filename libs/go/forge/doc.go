// Package forge is the remote SOURCE-CODE-FORGE connector port: it owns the
// remote forge's MANAGEMENT API (create a repository, and — as the surface grows
// — webhooks, branch protection, pull requests). It is the F2 SCM connector seam,
// the network boundary between Eden and a hosted forge (GitHub first).
//
// Module: github.com/gophersys/libs/go/forge  (go 1.26)
//
// It is NOT gitrepository. gitrepository is local PLUMBING over a worked checkout
// (clone/fetch/branch/worktree/commit/push) and never touches a forge's HTTP API;
// forge never shells git or touches a working tree. The split is deliberate: one
// concept, one home. A caller that needs both wires both — forge creates the remote
// repository, gitrepository clones and works it.
//
// AUTHENTICATION (07 §2): a Forge never carries a token in its arguments, its
// Config, or a log. The caller names the credential by an opaque, loggable
// secrets.Reference (a GitHub Personal Access Token with the "repo" scope); the
// adapter resolves it to a short-lived secrets.Secret at the moment of the call,
// confined to secrets.Secret.Use, zeroized immediately after, and presented to the
// forge only through the Authorization header — never argv, never the URL, never a
// log line.
//
// IDEMPOTENCY: CreateRepository is idempotent. A forge that rejects a duplicate create
// (GitHub answers HTTP 422 with a "name already exists" validation error) is not a
// failure here — the connector reads the existing repository back and returns it,
// so a retried provision converges on the same Repository rather than erroring.
//
// ERRORS: every failure is an *errors.Error carrying a stable errors.Kind the
// caller branches on (never a string match): KindConflict for a genuine
// name/state conflict the read-back could not reconcile, KindUnauthenticated for a
// rejected or missing credential, KindUnavailable for a transient transport/5xx
// fault the caller may retry, KindInvalid for a malformed request, KindNotFound
// for a missing resource. The token value never enters an error message.
//
// HEXAGON: the port (Forge) and its value types live here; the concrete GitHub
// REST adapter lives in the githubadapter subpackage, behind an injected HTTP
// transport (githubadapter.HTTPDoer) so the wire behavior is exercised against a
// fake transport in unit tests and against the REAL github.com under the
// integration build tag. New is the pure constructor spine
// (New(configuration, dependencies)): it validates and wires, performs no I/O.
//
// Concurrency: a Forge implementation is safe for concurrent use by multiple
// goroutines iff its injected transport is (net/http.Client is).
package forge
