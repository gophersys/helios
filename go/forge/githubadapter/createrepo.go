package githubadapter

import (
	"context"
	"net/http"
	"strings"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/forge"
	"github.com/gophersys/libs/go/secrets"
)

// CreateRepo creates the repository named by request and returns its resolved
// forge.Repository. It is IDEMPOTENT: a GitHub 422 whose validation error is the
// "name already exists" case is reconciled by reading the existing repository back
// via GET, so a retried provision converges rather than erroring. Every other
// non-2xx status classifies into the forge taxonomy (401/403 → Unauthenticated,
// 404 → NotFound, 5xx/transport → Unavailable, other 4xx → Conflict/Invalid). The
// credential is resolved at the call and zeroized immediately; its value never
// enters argv, the URL, a log, or the returned error.
func (c *Connector) CreateRepo(ctx context.Context, request forge.CreateRepoRequest) (forge.Repository, error) {
	if err := errors.FromContext(ctx); err != nil {
		return forge.Repository{}, err
	}
	if err := validateRequest(request); err != nil {
		return forge.Repository{}, forge.Wrap(err)
	}

	secret, err := c.resolveCredential(ctx, request)
	if err != nil {
		return forge.Repository{}, err
	}
	defer secret.Zeroize()

	result, err := c.postCreateRepo(ctx, request, secret)
	if err != nil {
		return forge.Repository{}, forge.Wrap(err)
	}

	switch {
	case result.status == http.StatusCreated || result.status == http.StatusOK:
		repository, decodeErr := decodeRepository(request, result.body)
		if decodeErr != nil {
			return forge.Repository{}, forge.Wrap(decodeErr)
		}
		return repository, nil

	case result.status == http.StatusUnprocessableEntity && bodyIsAlreadyExists(result.body):
		// IDEMPOTENT path: the repository already exists. Read it back and succeed,
		// so a retried provision converges on the same Repository.
		return c.getRepository(ctx, request, secret)

	default:
		return forge.Repository{}, forge.Wrap(classifyStatus(request, result.status, result.body))
	}
}

// resolveCredential resolves request.Credential to a short-lived Secret through the
// injected provider, classifying a resolution failure as Unauthenticated with the
// loggable Reference (never the value). It never returns (nil, nil): a successful
// resolution returns a non-nil Secret the caller owns and must Zeroize.
func (c *Connector) resolveCredential(ctx context.Context, request forge.CreateRepoRequest) (*secrets.Secret, error) {
	secret, err := c.secrets.Resolve(ctx, request.Credential)
	if err != nil {
		// The forge-typed boundary error carries the loggable Reference and WRAPS the
		// secrets error (Cause), so a caller inspects either the forge type or the
		// underlying secrets type. A transient secrets.UnavailableError stays retryable
		// (KindUnavailable); any other resolution failure is an auth failure. forge.Wrap
		// is the single classification seam.
		if errors.IsType[secrets.UnavailableError](err) {
			return nil, forge.Wrap(forge.UnavailableError{
				Owner:  request.Owner,
				Name:   request.Name,
				Reason: "credential store unavailable",
				Cause:  err,
			})
		}
		return nil, forge.Wrap(forge.UnauthenticatedError{
			Owner:      request.Owner,
			Name:       request.Name,
			Credential: request.Credential,
			Cause:      err,
		})
	}
	return secret, nil
}

// getRepository reads an existing repository back via GET (the idempotent
// read-back). A 200 decodes the repository; a 404 is a NotFound (a race where the
// repository vanished between the 422 and the read); anything else classifies via
// the shared status mapper.
func (c *Connector) getRepository(ctx context.Context, request forge.CreateRepoRequest, secret *secrets.Secret) (forge.Repository, error) {
	result, err := c.getRepo(ctx, request, secret)
	if err != nil {
		return forge.Repository{}, forge.Wrap(err)
	}
	switch result.status {
	case http.StatusOK:
		repository, decodeErr := decodeRepository(request, result.body)
		if decodeErr != nil {
			return forge.Repository{}, forge.Wrap(decodeErr)
		}
		return repository, nil
	case http.StatusNotFound:
		return forge.Repository{}, forge.Wrap(forge.NotFoundError{Owner: request.Owner, Name: request.Name})
	default:
		return forge.Repository{}, forge.Wrap(classifyStatus(request, result.status, result.body))
	}
}

// validateRequest enforces the port boundary: a non-empty Owner and Name and a
// non-zero Credential Reference, before any I/O. A malformed request is an
// InvalidRequestError (KindInvalid).
func validateRequest(request forge.CreateRepoRequest) error {
	switch {
	case strings.TrimSpace(request.Owner) == "":
		return forge.InvalidRequestError{Owner: request.Owner, Name: request.Name, Reason: "Owner is required"}
	case strings.TrimSpace(request.Name) == "":
		return forge.InvalidRequestError{Owner: request.Owner, Name: request.Name, Reason: "Name is required"}
	case strings.ContainsAny(request.Owner, "/ \t\n"):
		return forge.InvalidRequestError{Owner: request.Owner, Name: request.Name, Reason: "Owner contains an invalid character"}
	case strings.ContainsAny(request.Name, "/ \t\n"):
		return forge.InvalidRequestError{Owner: request.Owner, Name: request.Name, Reason: "Name contains an invalid character"}
	case request.Credential.IsZero():
		return forge.InvalidRequestError{Owner: request.Owner, Name: request.Name, Reason: "Credential reference is required"}
	}
	return nil
}

// classifyStatus maps a non-idempotent, non-2xx HTTP status to the forge taxonomy.
// 401/403 → Unauthenticated; 404 → NotFound; 5xx → Unavailable (retryable); 422 →
// Conflict (a validation error that is NOT the already-exists case); any other 4xx
// → Conflict as the closest stable client-side classification. The forge's error
// message (operator-safe; never a token) rides the Reason for diagnosis.
func classifyStatus(request forge.CreateRepoRequest, status int, body []byte) error {
	reason := summarizeBody(status, body)
	switch {
	case status == http.StatusUnauthorized || status == http.StatusForbidden:
		return forge.UnauthenticatedError{Owner: request.Owner, Name: request.Name, Credential: request.Credential}
	case status == http.StatusNotFound:
		return forge.NotFoundError{Owner: request.Owner, Name: request.Name}
	case status >= 500:
		return forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: reason}
	default:
		return forge.ConflictError{Owner: request.Owner, Name: request.Name, Reason: reason}
	}
}

// summarizeBody renders an operator-safe one-line summary of a GitHub error body
// for an error Reason — the API "message" field when present, else the bare status.
// It never surfaces a credential (the request body is the only place a token-bearing
// header would be, and headers are not echoed in a GitHub error body).
func summarizeBody(status int, body []byte) string {
	if message := decodeErrorMessage(body); message != "" {
		return message
	}
	return "github responded with status " + itoa(status)
}
