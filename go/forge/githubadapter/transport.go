package githubadapter

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/forge"
	"github.com/gophersys/libs/go/secrets"
)

// createRepoBody is the GitHub "create a repository for the authenticated user"
// request payload (POST /user/repos). Only the fields the forge port exposes are
// sent; GitHub defaults the rest.
type createRepoBody struct {
	Name        string `json:"name"`
	Private     bool   `json:"private"`
	Description string `json:"description,omitempty"`
	AutoInit    bool   `json:"auto_init"`
}

// repositoryResponse is the subset of GitHub's repository JSON the forge port
// surfaces. GitHub returns far more; the adapter decodes only what Repository needs,
// so an upstream additive field cannot break the parse.
type repositoryResponse struct {
	Name          string `json:"name"`
	CloneURL      string `json:"clone_url"`
	DefaultBranch string `json:"default_branch"`
	Owner         struct {
		Login string `json:"login"`
	} `json:"owner"`
}

// githubErrorResponse is the subset of GitHub's error JSON the adapter inspects:
// the top-level message and the per-field validation errors (whose "code" carries
// the "already_exists" signal that drives the idempotent read-back).
type githubErrorResponse struct {
	Message string `json:"message"`
	Errors  []struct {
		Resource string `json:"resource"`
		Field    string `json:"field"`
		Code     string `json:"code"`
		Message  string `json:"message"`
	} `json:"errors"`
}

// httpResult is the captured outcome of one forge HTTP call: the status code and
// the bounded, drained response body. It is the named return the transport methods
// hand back so a caller reads result.status / result.body rather than a bare triple.
type httpResult struct {
	status int
	body   []byte
}

// postCreateRepo issues POST <base>/user/repos with the create payload and the
// authenticated header set, returning the captured result, or a transport-level
// error mapped into the forge taxonomy (Unavailable). The body is always drained
// and closed.
func (c *Connector) postCreateRepo(ctx context.Context, request forge.CreateRepoRequest, secret *secrets.Secret) (httpResult, error) {
	payload := createRepoBody{
		Name:        request.Name,
		Private:     request.Private,
		Description: request.Description,
		AutoInit:    true, // initialize with a default branch so DefaultBranch is populated
	}
	encoded, err := json.Marshal(payload)
	if err != nil {
		// A struct of strings/bools always marshals; a failure here is an Eden-side
		// invariant break, not a forge fault — classify Unavailable so it never
		// masquerades as the caller's malformed request.
		return httpResult{}, forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: "encoding request body failed"}
	}

	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/user/repos", bytes.NewReader(encoded))
	if err != nil {
		return httpResult{}, forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: "building request failed"}
	}
	httpRequest.Header.Set("Content-Type", "application/json")

	return c.do(httpRequest, request, secret)
}

// getRepo issues GET <base>/repos/{owner}/{name} for the idempotent read-back,
// returning the captured result or a transport error mapped to the forge taxonomy.
// The body is always drained and closed.
func (c *Connector) getRepo(ctx context.Context, request forge.CreateRepoRequest, secret *secrets.Secret) (httpResult, error) {
	path := c.baseURL + "/repos/" + request.Owner + "/" + request.Name
	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodGet, path, http.NoBody)
	if err != nil {
		return httpResult{}, forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: "building request failed"}
	}
	return c.do(httpRequest, request, secret)
}

// do stamps the common GitHub headers + the Authorization header (built inside
// secrets.Secret.Use so the token never escapes the closure into a retained string),
// runs the request through the injected transport, and returns the captured status +
// bounded, drained body. A transport error classifies as Unavailable (retryable).
func (c *Connector) do(httpRequest *http.Request, request forge.CreateRepoRequest, secret *secrets.Secret) (httpResult, error) {
	httpRequest.Header.Set("Accept", "application/vnd.github+json")
	httpRequest.Header.Set("X-GitHub-Api-Version", defaultAPIVersion)
	httpRequest.Header.Set("User-Agent", c.userAgent)

	// Build the Authorization header value inside Use: the plaintext is read only for
	// the duration of the closure, the assembled "Bearer <token>" header is the single
	// derived value out, and it lives only on this request — never a log, never argv.
	if err := secret.Use(func(plaintext []byte) error {
		httpRequest.Header.Set("Authorization", "Bearer "+string(plaintext))
		return nil
	}); err != nil {
		// A Use on an already-zeroized secret (a misuse) classifies as auth failure
		// rather than leaking the spent-secret error semantics to the caller.
		return httpResult{}, forge.UnauthenticatedError{Owner: request.Owner, Name: request.Name, Credential: request.Credential}
	}

	response, err := c.http.Do(httpRequest)
	if err != nil {
		// A transport error (DNS, connection refused, TLS, a tripped context) is the
		// retryable class. A context cancellation/deadline is reported as such via the
		// errors model upstream; here it classifies Unavailable with an operator-safe
		// reason that never carries the token.
		return httpResult{}, forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: "transport error"}
	}
	defer func() {
		// Drain then close so the connection can be reused; both errors are
		// unactionable here (the status/body are already captured).
		_, _ = io.Copy(io.Discard, response.Body) //nolint:errcheck // drain is best-effort for connection reuse.
		_ = response.Body.Close()                 //nolint:errcheck // close error is unactionable after a successful read.
	}()

	// Read at most readBodyLimit bytes so a hostile or runaway forge cannot exhaust
	// memory through an unbounded body. The raw read error is unactionable to the
	// caller (the body is the diagnostic), so it is re-classified as a retryable
	// Unavailable fault rather than surfaced bare.
	body, err := io.ReadAll(io.LimitReader(response.Body, readBodyLimit))
	if err != nil {
		return httpResult{status: response.StatusCode}, forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: "reading response body failed"}
	}
	return httpResult{status: response.StatusCode, body: body}, nil
}

// decodeRepository decodes a GitHub repository JSON response into a forge.Repository,
// falling back to the request's Owner/Name when the response omits them (a defensive
// guard; GitHub always populates them). A body that does not decode is an Unavailable
// fault (a malformed/garbled response the caller may retry).
func decodeRepository(request forge.CreateRepoRequest, body []byte) (forge.Repository, error) {
	var raw repositoryResponse
	if err := json.Unmarshal(body, &raw); err != nil {
		return forge.Repository{}, forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: "decoding repository response failed"}
	}
	owner := raw.Owner.Login
	if owner == "" {
		owner = request.Owner
	}
	name := raw.Name
	if name == "" {
		name = request.Name
	}
	repository := forge.Repository{
		Owner:         owner,
		Name:          name,
		CloneURL:      raw.CloneURL,
		DefaultBranch: raw.DefaultBranch,
	}
	// A 2xx that decodes but carries no clone URL is a malformed contract the caller
	// cannot act on — surface it as Unavailable rather than a half-populated success.
	if strings.TrimSpace(repository.CloneURL) == "" {
		return forge.Repository{}, forge.UnavailableError{Owner: request.Owner, Name: request.Name, Reason: "repository response missing clone_url"}
	}
	return repository, nil
}

// bodyIsAlreadyExists reports whether a 422 body is GitHub's idempotent
// "name already exists on this account" validation error — the signal to read the
// existing repository back rather than fail. It inspects the structured "code"
// field ("custom"/"already_exists") and the field name, not a brittle message
// substring.
func bodyIsAlreadyExists(body []byte) bool {
	var parsed githubErrorResponse
	if err := json.Unmarshal(body, &parsed); err != nil {
		return false
	}
	for _, item := range parsed.Errors {
		code := strings.ToLower(item.Code)
		if code == "already_exists" {
			return true
		}
		// GitHub's create-repo duplicate uses code "custom" with a message naming the
		// existing-name case; match on the structured field+message, never the
		// top-level free-text alone.
		if code == "custom" && item.Field == "name" &&
			strings.Contains(strings.ToLower(item.Message), "already exists") {
			return true
		}
	}
	return false
}

// decodeErrorMessage extracts GitHub's operator-safe top-level error message from an
// error body, or "" when the body does not decode. Used only for a Reason string;
// it is never a token (a request header is never echoed in an error body).
func decodeErrorMessage(body []byte) string {
	var parsed githubErrorResponse
	if err := json.Unmarshal(body, &parsed); err != nil {
		return ""
	}
	return strings.TrimSpace(parsed.Message)
}

// itoa renders an HTTP status for an operator-safe Reason without pulling fmt onto
// the hot classification path.
func itoa(n int) string { return strconv.Itoa(n) }
