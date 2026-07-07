package githubadapter

import (
	"context"
	"io"
	"net/http"
	"strings"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/forge"
	"github.com/gophersys/libs/go/secrets"
)

// DeleteRepository PERMANENTLY deletes the repository named by request — but ONLY after
// forge.GuardDelete passes (the name is an ephemeral `eden-it-*` test repository AND not in the
// protected denylist). The guard runs BEFORE the credential is even resolved, so a protected or
// non-ephemeral name is refused with ForbiddenDeletionError and NO HTTP request is ever issued —
// a real repository (eden / libs / template / …) cannot be deleted through this adapter, by any
// caller, regardless of the credential's scopes. Idempotent: a 204 (deleted) and a 404 (already
// gone) are both success. The credential must carry the delete_repo scope.
func (c *Connector) DeleteRepository(ctx context.Context, request forge.DeleteRepositoryRequest) error {
	if err := errors.FromContext(ctx); err != nil {
		return err
	}
	// WALL 1 — capability off by default: a connector not explicitly constructed with
	// EnableEphemeralDelete cannot delete ANY repository (production never enables it).
	if !c.ephemeralDeleteEnabled {
		return forge.Wrap(forge.ForbiddenDeletionError{
			Owner:  request.Owner,
			Name:   request.Name,
			Reason: "ephemeral-delete capability is disabled on this connector (EnableEphemeralDelete=false)",
		})
	}
	if err := validateDeleteRequest(request); err != nil {
		return forge.Wrap(err)
	}
	// WALL 2 — the name fence, before any credential resolution or network call. There is no
	// DeleteRepository path that does not pass through GuardDelete first.
	if err := forge.GuardDelete(request.Owner, request.Name); err != nil {
		return forge.Wrap(err)
	}

	secret, err := c.secrets.Resolve(ctx, request.Credential)
	if err != nil {
		if errors.IsType[secrets.UnavailableError](err) {
			return forge.Wrap(forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: "credential store unavailable", Cause: err})
		}
		return forge.Wrap(forge.UnauthenticatedError{Owner: request.Owner, Name: request.Name, Credential: request.Credential, Cause: err})
	}
	defer secret.Zeroize()

	status, err := c.deleteRepository(ctx, request, secret)
	if err != nil {
		return forge.Wrap(err)
	}
	switch {
	case status == http.StatusNoContent || status == http.StatusNotFound:
		return nil // 204 deleted; 404 already gone — both idempotent success.
	case status == http.StatusUnauthorized || status == http.StatusForbidden:
		return forge.Wrap(forge.UnauthenticatedError{Owner: request.Owner, Name: request.Name, Credential: request.Credential})
	case status >= 500:
		return forge.Wrap(forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: "github responded with status " + itoa(status)})
	default:
		return forge.Wrap(forge.ConflictError{Owner: request.Owner, Name: request.Name, Reason: "github responded with status " + itoa(status)})
	}
}

// validateDeleteRequest enforces the delete port boundary (non-empty Owner/Name, non-zero
// Credential) before the guard and any I/O.
func validateDeleteRequest(request forge.DeleteRepositoryRequest) error {
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

// deleteRepository issues DELETE <base>/repos/{owner}/{name} with the auth header built inside
// Secret.Use (the token never escapes the closure), returning the status. The body is drained +
// closed for connection reuse; it carries no data the caller needs.
func (c *Connector) deleteRepository(ctx context.Context, request forge.DeleteRepositoryRequest, secret *secrets.Secret) (int, error) {
	path := c.baseURL + "/repos/" + request.Owner + "/" + request.Name
	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodDelete, path, http.NoBody)
	if err != nil {
		return 0, forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: "building request failed"}
	}
	httpRequest.Header.Set("Accept", "application/vnd.github+json")
	httpRequest.Header.Set("X-GitHub-Api-Version", defaultAPIVersion)
	httpRequest.Header.Set("User-Agent", c.userAgent)
	if err := secret.Use(func(plaintext []byte) error {
		httpRequest.Header.Set("Authorization", "Bearer "+string(plaintext))
		return nil
	}); err != nil {
		return 0, forge.UnauthenticatedError{Owner: request.Owner, Name: request.Name, Credential: request.Credential}
	}
	response, err := c.http.Do(httpRequest)
	if err != nil {
		return 0, forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: "transport error"}
	}
	defer func() {
		_, _ = io.Copy(io.Discard, response.Body) //nolint:errcheck // drain is best-effort for connection reuse.
		_ = response.Body.Close()                 //nolint:errcheck // close error is unactionable after the read.
	}()
	_, _ = io.Copy(io.Discard, io.LimitReader(response.Body, readBodyLimit)) //nolint:errcheck // delete body is unused.
	return response.StatusCode, nil
}
