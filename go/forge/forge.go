package forge

import (
	"context"

	"github.com/gophersys/libs/go/secrets"
)

// Forge is the consumer-defined port for a remote source-code forge's management
// API. It is the narrow seam a provisioning caller depends on; the concrete GitHub
// REST adapter (githubadapter) implements it and is bound at the composition root
// (accept this interface, return the concrete adapter — 10 §9). Wave 1 exposes the
// single create-repository verb; the surface grows (webhooks, branch protection,
// pull requests) within the 5-method interface ceiling, splitting into composed
// ports before it would exceed it.
//
// Implementations MUST be idempotent on CreateRepo (a duplicate is read back, not
// an error) and MUST be safe for concurrent use by multiple goroutines.
type Forge interface {
	// CreateRepo creates the repository named by request under request.Owner and
	// returns its resolved Repository (clone URL + default branch the forge chose).
	// It is IDEMPOTENT: if the repository already exists, the existing repository is
	// read back and returned rather than erroring. The credential is named by
	// request.Credential (an opaque secrets.Reference) and resolved at the call,
	// never carried in the request, a log, or the returned error. On failure it
	// returns a wrapped *errors.Error whose Kind the caller branches on
	// (KindConflict / KindUnauthenticated / KindUnavailable / KindInvalid /
	// KindNotFound); it never returns a non-zero Repository together with a non-nil
	// error.
	CreateRepo(ctx context.Context, request CreateRepoRequest) (Repository, error)

	// DeleteRepo PERMANENTLY deletes the repository named by request — a DESTRUCTIVE,
	// IRREVERSIBLE operation that exists ONLY to reap ephemeral test repositories. It is
	// fenced by a HARD GUARD (GuardDelete, guard.go) applied BEFORE any network call: it
	// refuses unless request.Name matches the reserved ephemeral pattern (EphemeralRepoName,
	// `eden-it-*`) AND is not in the protected denylist (ProtectedRepoNames). A request for a
	// real repository — eden / libs / template / infrastructure / .devcontainer / any
	// non-`eden-it-*` name — is REFUSED with KindInvalid and NO HTTP call is made, by a test
	// or production code, regardless of the credential. There is no unguarded delete path.
	// Idempotent: a 404 (already gone) is success. The credential is resolved per call.
	DeleteRepo(ctx context.Context, request DeleteRepoRequest) error
}

// DeleteRepoRequest names a repository to delete. The zero value is invalid. Even a fully-formed
// request is REFUSED unless Name passes GuardDelete (ephemeral + not protected) — the request
// shape is necessary but never sufficient to delete.
type DeleteRepoRequest struct {
	// Owner is the account/organization that owns the repository. Required.
	Owner string
	// Name is the repository name. Required, and MUST be an ephemeral `eden-it-*` test name
	// (EphemeralRepoName) that is not protected (ProtectedRepoNames) or DeleteRepo refuses it.
	Name string
	// Credential is the opaque secrets.Reference to the forge PAT (needs the delete_repo scope),
	// resolved at the call. Required. The token never enters this struct, a log, or an error.
	Credential secrets.Reference
}

// IsZero reports whether r is the unconstructed delete request.
func (r DeleteRepoRequest) IsZero() bool {
	return r.Owner == "" && r.Name == "" && r.Credential.IsZero()
}

// CreateRepoRequest is the validated, credential-free description of a repository
// to create. It carries the opaque secrets.Reference that NAMES the credential —
// never the token value (07 §2). DATA, not code; the zero value is invalid (Owner
// and Name are required, Credential must be non-zero), rejected at the port
// boundary before any I/O.
type CreateRepoRequest struct {
	// Owner is the account or organization that will own the repository (a GitHub
	// user login or organization slug). Required.
	Owner string

	// Name is the repository name to create under Owner. Required.
	Name string

	// Private requests a private repository; false creates a public one.
	Private bool

	// Description is the optional repository description (free text, "" for none).
	Description string

	// Credential is the opaque, loggable reference to the forge credential — a
	// GitHub Personal Access Token with the "repo" scope — resolved through the
	// injected secrets.Provider at the moment of the call. Required: a zero
	// Reference is rejected with KindInvalid (a forge create always authenticates).
	// The value never enters this struct, a log, or an error.
	Credential secrets.Reference
}

// IsZero reports whether r is the zero request (no Owner, Name, or Credential set).
// It lets a caller and the adapter guard the unconstructed value before any I/O.
func (r CreateRepoRequest) IsZero() bool {
	return r.Owner == "" && r.Name == "" && !r.Private && r.Description == "" && r.Credential.IsZero()
}

// Repository is the resolved remote repository the forge returns. DATA, not code:
// it carries the identity the caller needs to clone and work the repository (the
// gitrepository hand-off) and nothing the forge keeps private. The zero value is
// the "no repository" result, returned only alongside a non-nil error.
type Repository struct {
	// Owner is the account or organization that owns the repository.
	Owner string

	// Name is the repository name under Owner.
	Name string

	// CloneURL is the HTTPS clone URL the forge published for the repository — the
	// remote a gitrepository.Clone consumes. It NEVER embeds a credential; the
	// credential rides the credential-helper seam at clone time, not the URL.
	CloneURL string

	// DefaultBranch is the default branch the forge initialized (e.g. "main").
	DefaultBranch string
}

// IsZero reports whether the repository is the zero value (no Owner and no Name) —
// the "no result" sentinel returned only with a non-nil error.
func (r Repository) IsZero() bool {
	return r.Owner == "" && r.Name == ""
}
