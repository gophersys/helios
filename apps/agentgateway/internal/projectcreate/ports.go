package projectcreate

import (
	"context"

	"github.com/gophersys/libs/go/secrets"
)

// This file holds the saga's CONSUMER-DEFINED ports — the shape of exactly what the saga needs from
// the forge and the git plumbing, expressed where it is used (10 §9 "consumer-defined"). The saga does
// NOT import the heavy gitrepository.Provisioner/Author/Inspector triad or hand the forge its full REST
// surface; each port below is the minimal seam the corresponding step drives, so a fake binds it in a
// unit test and the real library adapter binds it at composition (accept-interface, return-concrete).
// Neither port carries a secret value: the gh PAT rides an opaque secrets.Reference resolved
// server-side by the real adapter, never by the saga.

// RepositoryCoordinates is the saga's record of where a project's repository landed — the result of
// step 1, folded onto the project's saga scratch (GitHubOwner/GitHubRepo/RepoURL/DefaultBranch) and read
// by step 2 (the seed pushes into RepoURL). It is a plain value (copyable, loggable); RepoURL is the
// PUBLIC clone URL and never embeds a credential (the credential rides the helper seam at push time).
type RepositoryCoordinates struct {
	// Owner is the account/organization that owns the repository.
	Owner string
	// Name is the repository name under Owner (the derived HNS-1 slug).
	Name string
	// CloneURL is the public HTTPS clone URL the seed step pushes into; never a credential.
	CloneURL string
	// DefaultBranch is the default branch the forge initialized (e.g. "main").
	DefaultBranch string
}

// ProjectForge is the saga's narrow seam over the source-code forge: create (idempotently) the
// project's repository and return where it landed. It is a ONE-method port — the shape of step 1's need
// — that the production forge.Forge (githubadapter) binds through a thin adapter, and a fake binds in a
// unit test. The credential is named by CreateRepositoryInput.Credential (an opaque secrets.Reference)
// and resolved at the call by the bound forge, never by the saga.
type ProjectForge interface {
	// CreateRepository creates the repository named by input under input.Owner and returns its resolved
	// coordinates. It MUST be IDEMPOTENT: a repository that already exists is read back and returned
	// rather than erroring (the githubadapter's 422->GET path) so a saga replay of step 1 converges. On
	// failure it returns a wrapped *errors.Error whose Kind the saga branches on; it never returns
	// non-zero coordinates together with a non-nil error.
	CreateRepository(ctx context.Context, input CreateRepositoryInput) (RepositoryCoordinates, error)
}

// CreateRepositoryInput is the validated, credential-FREE description of the repository step 1 creates.
// It carries the opaque secrets.Reference that NAMES the gh-token, never the token value (07 §2). The
// bound adapter maps it onto forge.CreateRepoRequest.
type CreateRepositoryInput struct {
	// Owner is the account/organization the repository is created under.
	Owner string
	// Name is the derived, unique HNS-1 slug to create.
	Name string
	// Private requests a private repository; false creates a public one.
	Private bool
	// Description is the optional repository description (free text; "" for none); never a credential.
	Description string
	// Credential is the OPAQUE gh-token reference, resolved server-side by the bound forge at the call.
	Credential secrets.Reference
}

// TemplateSeeder is the saga's narrow seam over the git plumbing for step 2: take a freshly-created,
// EMPTY repository and seed it from the template in one idempotent act — clone the template, flatten its
// history to a single "seed from template" root commit, re-point origin at the new repository, and push
// the seed into its unborn main (a fast-forward into an empty branch, so gitrepository's ff-only Push
// contract holds). It is a ONE-method port the real gitrepository.Repository binds through an adapter
// (Clone -> Flatten -> SetRemote -> Push), and a fake binds in a unit test. The push credential rides
// SeedInput.Credential (opaque), resolved by the bound adapter at the push, never by the saga.
type TemplateSeeder interface {
	// SeedRepository seeds the repository at input.RepositoryURL from input.TemplateURL and returns the
	// seeded SeedResult (the default branch + the seed commit id). It MUST be IDEMPOTENT: when the new
	// repository's origin/main already carries the seed, it is a no-op that returns the existing seed
	// rather than re-pushing (so a saga replay of step 2 converges). On failure it returns a wrapped
	// *errors.Error whose Kind the saga branches on.
	SeedRepository(ctx context.Context, input SeedInput) (SeedResult, error)
}

// SeedInput is the validated, credential-FREE description of step 2's seed. The credential is the opaque
// gh-token reference resolved at the push by the bound adapter.
type SeedInput struct {
	// ProjectID scopes the working directory the seed adapter clones into, so concurrent saga runs never
	// collide on a shared checkout. Required.
	ProjectID string
	// TemplateURL is the seed template's clone URL (gophersys/template).
	TemplateURL string
	// RepositoryURL is the public clone URL of the new, empty repository the seed is pushed into.
	RepositoryURL string
	// Credential is the OPAQUE gh-token reference, resolved server-side by the bound adapter at the push.
	Credential secrets.Reference
}

// SeedResult is the saga's record of the seed — folded onto the project (DefaultBranch) and the step's
// ledger Output. CommitID is the seed commit's full hex id (loggable; never a credential).
type SeedResult struct {
	// DefaultBranch is the branch the seed was pushed onto (e.g. "main").
	DefaultBranch string
	// CommitID is the full hex id of the seed commit (loggable provenance; "" when the seed was a
	// no-op idempotent skip and the adapter did not re-resolve it).
	CommitID string
}
