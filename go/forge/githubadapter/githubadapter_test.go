package githubadapter_test

import (
	"context"
	"io"
	"net/http"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/forge"
	"github.com/gophersys/libs/go/forge/githubadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// --- the fake HTTP transport -------------------------------------------------
//
// fakeTransport is a recording, scriptable githubadapter.HTTPDoer: it returns a
// scripted (status, body) per request in order, records every request it saw (so a
// test can assert the Authorization header and that the token never leaked into the
// URL/argv), and can be made to fail at the transport level. It never touches the
// network — the unit suite is hermetic. The REAL github.com transport is exercised
// by the integration-tagged suite.

type scriptedResponse struct {
	status int
	body   string
	// transportErr, when set, makes Do return it (the connection-refused/DNS/TLS class).
	transportErr error
}

type fakeTransport struct {
	responses []scriptedResponse
	calls     []*http.Request
	// authHeaders records the Authorization header value seen per call, so a test can
	// prove the resolved token reached the wire exactly once and was redacted nowhere.
	authHeaders []string
	urls        []string
}

func (f *fakeTransport) Do(request *http.Request) (*http.Response, error) {
	f.calls = append(f.calls, request)
	f.authHeaders = append(f.authHeaders, request.Header.Get("Authorization"))
	f.urls = append(f.urls, request.URL.String())
	if len(f.responses) == 0 {
		// An unscripted call is a test bug, not a forge fault — surface it loudly.
		return nil, io.ErrUnexpectedEOF
	}
	next := f.responses[0]
	f.responses = f.responses[1:]
	if next.transportErr != nil {
		return nil, next.transportErr
	}
	return &http.Response{
		StatusCode: next.status,
		Body:       io.NopCloser(strings.NewReader(next.body)),
		Header:     make(http.Header),
	}, nil
}

// --- fixtures ----------------------------------------------------------------.

const (
	tokenRef       = "vault://eden/connectors/github#token"  //nolint:gosec // a secrets REFERENCE (loggable), not a credential value.
	tokenPlaintext = "ghp_unit_test_token_value_do_not_leak" //nolint:gosec // a fixture token for the fake provider; never a real credential.
)

func newConnector(t *testing.T, transport *fakeTransport) *githubadapter.Connector {
	t.Helper()
	provider := secretstest.New(map[string]string{tokenRef: tokenPlaintext})
	connector, err := githubadapter.New(
		githubadapter.Config{},
		githubadapter.Deps{HTTP: transport, Secrets: provider},
	)
	if err != nil {
		t.Fatalf("New: unexpected error: %v", err)
	}
	return connector
}

func sampleRequest() forge.CreateRepoRequest {
	return forge.CreateRepoRequest{
		Owner:       "eden-org",
		Name:        "new-service",
		Private:     true,
		Description: "a fresh service repository",
		Credential:  secrets.Ref(tokenRef),
	}
}

const createdRepoBody = `{
  "name": "new-service",
  "clone_url": "https://github.com/eden-org/new-service.git",
  "default_branch": "main",
  "owner": {"login": "eden-org"}
}`

const alreadyExistsBody = `{
  "message": "Repository creation failed.",
  "errors": [
    {"resource": "Repository", "field": "name", "code": "custom",
     "message": "name already exists on this account"}
  ]
}`

const unauthorizedBody = `{"message": "Bad credentials"}`

// --- the table: create-ok, already-exists-422 -> get, 401 --------------------.

// createRepoCase is one row of the CreateRepo table: the scripted forge responses
// and the expected outcome (a success with a clone URL/branch, or a classified
// error). wantKind == KindUnknown together with wantErr == false means "expect
// success".
type createRepoCase struct {
	name        string
	responses   []scriptedResponse
	wantKind    errors.Kind
	wantErr     bool
	wantCalls   int
	wantClone   string
	wantBranch  string
	wantErrType func(error) bool // nil means skip the typed-error assertion
}

func TestCreateRepo(t *testing.T) {
	t.Parallel()

	tests := []createRepoCase{
		{
			name:       "create-ok",
			responses:  []scriptedResponse{{status: http.StatusCreated, body: createdRepoBody}},
			wantErr:    false,
			wantCalls:  1,
			wantClone:  "https://github.com/eden-org/new-service.git",
			wantBranch: "main",
		},
		{
			name: "already-exists-422-then-get",
			responses: []scriptedResponse{
				{status: http.StatusUnprocessableEntity, body: alreadyExistsBody},
				{status: http.StatusOK, body: createdRepoBody},
			},
			wantErr:    false,
			wantCalls:  2, // POST (422) then GET (200) — the idempotent read-back
			wantClone:  "https://github.com/eden-org/new-service.git",
			wantBranch: "main",
		},
		{
			name:        "unauthorized-401",
			responses:   []scriptedResponse{{status: http.StatusUnauthorized, body: unauthorizedBody}},
			wantErr:     true,
			wantKind:    errors.KindUnauthenticated,
			wantCalls:   1,
			wantErrType: errors.IsType[forge.UnauthenticatedError],
		},
		{
			name:        "forbidden-403-is-unauthenticated",
			responses:   []scriptedResponse{{status: http.StatusForbidden, body: unauthorizedBody}},
			wantErr:     true,
			wantKind:    errors.KindUnauthenticated,
			wantCalls:   1,
			wantErrType: errors.IsType[forge.UnauthenticatedError],
		},
		{
			name:        "server-500-is-unavailable",
			responses:   []scriptedResponse{{status: http.StatusInternalServerError, body: `{"message":"oops"}`}},
			wantErr:     true,
			wantKind:    errors.KindUnavailable,
			wantCalls:   1,
			wantErrType: errors.IsType[forge.UnavailableError],
		},
		{
			name:        "transport-error-is-unavailable",
			responses:   []scriptedResponse{{transportErr: io.ErrUnexpectedEOF}},
			wantErr:     true,
			wantKind:    errors.KindUnavailable,
			wantCalls:   1,
			wantErrType: errors.IsType[forge.UnavailableError],
		},
		{
			name: "already-exists-then-get-404-is-notfound",
			responses: []scriptedResponse{
				{status: http.StatusUnprocessableEntity, body: alreadyExistsBody},
				{status: http.StatusNotFound, body: `{"message":"Not Found"}`},
			},
			wantErr:     true,
			wantKind:    errors.KindNotFound,
			wantCalls:   2,
			wantErrType: errors.IsType[forge.NotFoundError],
		},
		{
			name:        "unprocessable-not-already-exists-is-conflict",
			responses:   []scriptedResponse{{status: http.StatusUnprocessableEntity, body: `{"message":"Validation Failed","errors":[{"resource":"Repository","field":"name","code":"invalid","message":"is too long"}]}`}},
			wantErr:     true,
			wantKind:    errors.KindConflict,
			wantCalls:   1,
			wantErrType: errors.IsType[forge.ConflictError],
		},
	}

	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			transport := &fakeTransport{responses: testCase.responses}
			connector := newConnector(t, transport)

			repository, err := connector.CreateRepo(context.Background(), sampleRequest())

			if testCase.wantErr {
				assertErrorCase(t, &testCase, repository, err)
			} else {
				assertSuccessCase(t, &testCase, repository, err)
			}

			if len(transport.calls) != testCase.wantCalls {
				t.Errorf("transport calls: got %d, want %d", len(transport.calls), testCase.wantCalls)
			}
		})
	}
}

// assertErrorCase verifies a classified-error row: a non-nil error, the expected
// Kind and taxonomy type, and a zero Repository.
func assertErrorCase(t *testing.T, testCase *createRepoCase, repository forge.Repository, err error) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected an error, got nil and repository %+v", repository)
	}
	if got := errors.KindOf(err); got != testCase.wantKind {
		t.Errorf("Kind: got %v, want %v (err: %v)", got, testCase.wantKind, err)
	}
	if testCase.wantErrType != nil && !testCase.wantErrType(err) {
		t.Errorf("error is not the expected taxonomy type: %v", err)
	}
	if !repository.IsZero() {
		t.Errorf("expected zero Repository on error, got %+v", repository)
	}
}

// assertSuccessCase verifies a happy-path row: no error and the expected resolved
// Repository identity, clone URL, and default branch.
func assertSuccessCase(t *testing.T, testCase *createRepoCase, repository forge.Repository, err error) {
	t.Helper()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if repository.CloneURL != testCase.wantClone {
		t.Errorf("CloneURL: got %q, want %q", repository.CloneURL, testCase.wantClone)
	}
	if repository.DefaultBranch != testCase.wantBranch {
		t.Errorf("DefaultBranch: got %q, want %q", repository.DefaultBranch, testCase.wantBranch)
	}
	if repository.Owner != "eden-org" || repository.Name != "new-service" {
		t.Errorf("identity: got %s/%s, want eden-org/new-service", repository.Owner, repository.Name)
	}
}

// TestCreateRepo_AuthHeaderCarriesResolvedTokenAndNeverLeaks proves the resolved
// token reaches the Authorization header (so the call authenticates) AND never
// appears in the request URL — the credential-confinement contract (07 §2).
func TestCreateRepo_AuthHeaderCarriesResolvedTokenAndNeverLeaks(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{responses: []scriptedResponse{{status: http.StatusCreated, body: createdRepoBody}}}
	connector := newConnector(t, transport)

	if _, err := connector.CreateRepo(context.Background(), sampleRequest()); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(transport.authHeaders) != 1 {
		t.Fatalf("expected exactly one request, saw %d", len(transport.authHeaders))
	}
	if want := "Bearer " + tokenPlaintext; transport.authHeaders[0] != want {
		t.Errorf("Authorization header: got %q, want %q", transport.authHeaders[0], want)
	}
	// The token must NEVER appear in the URL (no basic-auth-in-URL, no query param).
	for _, u := range transport.urls {
		if strings.Contains(u, tokenPlaintext) {
			t.Errorf("token leaked into request URL: %q", u)
		}
	}
}

// TestCreateRepo_CredentialResolutionFailureIsUnauthenticated proves that when the
// secrets provider rejects the reference, CreateRepo never reaches the transport and
// classifies the failure as Unauthenticated with the loggable reference (no value).
func TestCreateRepo_CredentialResolutionFailureIsUnauthenticated(t *testing.T) {
	t.Parallel()
	ref := secrets.Ref(tokenRef)
	provider := secretstest.New(nil).FailWith(tokenRef, secrets.DeniedError{Ref: ref})
	transport := &fakeTransport{}
	connector, err := githubadapter.New(
		githubadapter.Config{},
		githubadapter.Deps{HTTP: transport, Secrets: provider},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	_, err = connector.CreateRepo(context.Background(), sampleRequest())
	if err == nil {
		t.Fatal("expected an error when the credential cannot be resolved")
	}
	if got := errors.KindOf(err); got != errors.KindUnauthenticated {
		t.Errorf("Kind: got %v, want KindUnauthenticated", got)
	}
	if !errors.IsType[forge.UnauthenticatedError](err) {
		t.Errorf("expected a forge.UnauthenticatedError in the chain: %v", err)
	}
	if len(transport.calls) != 0 {
		t.Errorf("transport must not be called when the credential cannot resolve, saw %d calls", len(transport.calls))
	}
	// The error message must carry the loggable reference and NEVER the token value.
	if strings.Contains(err.Error(), tokenPlaintext) {
		t.Errorf("error message leaked the token value: %q", err.Error())
	}
	if !strings.Contains(err.Error(), tokenRef) {
		t.Errorf("error message should carry the loggable reference %q: %q", tokenRef, err.Error())
	}
}

// TestCreateRepo_UnavailableCredentialStoreStaysRetryable proves a transient
// secrets-store fault maps to KindUnavailable (retryable), not Unauthenticated.
func TestCreateRepo_UnavailableCredentialStoreStaysRetryable(t *testing.T) {
	t.Parallel()
	ref := secrets.Ref(tokenRef)
	provider := secretstest.New(nil).FailWith(tokenRef, secrets.UnavailableError{Ref: ref})
	transport := &fakeTransport{}
	connector, err := githubadapter.New(githubadapter.Config{}, githubadapter.Deps{HTTP: transport, Secrets: provider})
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	_, err = connector.CreateRepo(context.Background(), sampleRequest())
	if got := errors.KindOf(err); got != errors.KindUnavailable {
		t.Errorf("Kind: got %v, want KindUnavailable", got)
	}
}

// TestCreateRepo_InvalidRequestRejectedBeforeIO proves the port boundary rejects a
// malformed request with KindInvalid and never resolves a credential or dials.
func TestCreateRepo_InvalidRequestRejectedBeforeIO(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name    string
		request forge.CreateRepoRequest
	}{
		{"empty-owner", forge.CreateRepoRequest{Name: "x", Credential: secrets.Ref(tokenRef)}},
		{"empty-name", forge.CreateRepoRequest{Owner: "o", Credential: secrets.Ref(tokenRef)}},
		{"zero-credential", forge.CreateRepoRequest{Owner: "o", Name: "x"}},
		{"slash-in-name", forge.CreateRepoRequest{Owner: "o", Name: "a/b", Credential: secrets.Ref(tokenRef)}},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			transport := &fakeTransport{}
			connector := newConnector(t, transport)
			_, err := connector.CreateRepo(context.Background(), testCase.request)
			if err == nil {
				t.Fatal("expected an error for a malformed request")
			}
			if got := errors.KindOf(err); got != errors.KindInvalid {
				t.Errorf("Kind: got %v, want KindInvalid", got)
			}
			if !errors.IsType[forge.InvalidRequestError](err) {
				t.Errorf("expected a forge.InvalidRequestError: %v", err)
			}
			if len(transport.calls) != 0 {
				t.Errorf("no transport call expected for an invalid request, saw %d", len(transport.calls))
			}
		})
	}
}

// TestNew_Validation proves the pure constructor spine rejects a nil transport, a
// nil provider, and a malformed BaseURL — with KindInvalid — and accepts a good
// BaseURL override.
func TestNew_Validation(t *testing.T) {
	t.Parallel()
	provider := secretstest.New(nil)
	good := &fakeTransport{}

	if _, err := githubadapter.New(githubadapter.Config{}, githubadapter.Deps{Secrets: provider}); err == nil {
		t.Error("expected error for nil HTTP transport")
	} else if errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("nil HTTP: Kind got %v, want KindInvalid", errors.KindOf(err))
	}

	if _, err := githubadapter.New(githubadapter.Config{}, githubadapter.Deps{HTTP: good}); err == nil {
		t.Error("expected error for nil Secrets provider")
	} else if errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("nil Secrets: Kind got %v, want KindInvalid", errors.KindOf(err))
	}

	if _, err := githubadapter.New(githubadapter.Config{BaseURL: "not a url"}, githubadapter.Deps{HTTP: good, Secrets: provider}); err == nil {
		t.Error("expected error for a malformed BaseURL")
	} else if errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("bad BaseURL: Kind got %v, want KindInvalid", errors.KindOf(err))
	}

	if _, err := githubadapter.New(githubadapter.Config{BaseURL: "https://github.example.com/api/v3"}, githubadapter.Deps{HTTP: good, Secrets: provider}); err != nil {
		t.Errorf("a valid GitHub Enterprise BaseURL should be accepted: %v", err)
	}
}

// staticProvider is a minimal secrets.Provider asserting the adapter accepts the
// port interface (not just the secretstest concrete fake). Compile-time only here.
var _ secrets.Provider = (*secretstest.Provider)(nil)
