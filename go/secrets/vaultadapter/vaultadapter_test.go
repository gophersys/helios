package vaultadapter_test

import (
	"context"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"testing"

	vaultapi "github.com/hashicorp/vault/api"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
	"github.com/gophersys/libs/go/secrets/vaultadapter"
)

// is reports whether err's chain carries a value of type E (errors.AsType[E]). The whole error
// taxonomy is inspected by TYPE, never by string (the errors contract, secrets.md §6.6).
func is[E error](err error) bool {
	_, ok := errors.AsType[E](err)
	return ok
}

// fakeTransport is an in-memory vaultadapter.Transport for the UNIT lane: it exercises the
// adapter's parse → token → KV-unwrap → mint mapping WITHOUT a Vault daemon. The REAL-Vault proof
// is the integration lane (//go:build integration), never this fake (ADR-0016 §2). It records the
// login and the api paths read so a test can assert the dual-mode bootstrap fired exactly once.
type fakeTransport struct {
	mu sync.Mutex

	// kv maps a KV v2 api path ("<mount>/data/<path>") to its raw response Data map (already in
	// the KV v2 "data" envelope shape, mirroring what the real SDK returns).
	kv map[string]map[string]any
	// loginErr / readErr force a transport error on the respective call (a *vaultapi.ResponseError
	// to drive the status-code mapping, or any error to drive the Unavailable fallback).
	loginErr error
	readErr  error
	// token is the token Login issues; SetToken records what the adapter installed.
	issuedToken string

	loginCount  int
	setToken    string
	pathsRead   []string
	loginCalled bool
}

func (f *fakeTransport) Login(_ context.Context, _ string, _ map[string]any) (string, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.loginCount++
	f.loginCalled = true
	if f.loginErr != nil {
		return "", f.loginErr
	}
	if f.issuedToken == "" {
		return "fake-login-token", nil
	}
	return f.issuedToken, nil
}

func (f *fakeTransport) SetToken(token string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.setToken = token
}

func (f *fakeTransport) ReadKeyValue(_ context.Context, apiPath string) (map[string]any, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.pathsRead = append(f.pathsRead, apiPath)
	if f.readErr != nil {
		return nil, f.readErr
	}
	data, ok := f.kv[apiPath]
	if !ok {
		return nil, nil //nolint:nilnil // the documented "no such secret" sentinel the adapter maps to NotFound.
	}
	return data, nil
}

// kvEnvelope wraps user fields in the KV v2 "data" sub-map the real SDK returns.
func kvEnvelope(fields map[string]any) map[string]any {
	return map[string]any{"data": fields}
}

// newUserpassAdapter builds a ModeUserpass adapter over a fake transport seeded with kv. It
// delegates to newAdapterTB (property_test.go) so the unit and property lanes construct identically.
func newUserpassAdapter(t *testing.T, transport vaultadapter.Transport) *vaultadapter.Adapter {
	t.Helper()
	return newAdapterTB(t, transport)
}

// Construction: New purity + validation.

func TestNew_RejectsMissingAddress(t *testing.T) {
	t.Parallel()
	_, err := vaultadapter.New(
		vaultadapter.Config{Mode: vaultadapter.ModeUserpass},
		vaultadapter.Dependencies{Username: "u", Password: "p", Transport: &fakeTransport{}},
	)
	if err == nil {
		t.Fatal("New with no Address should error")
	}
	if k := errors.KindOf(err); k != errors.KindInvalid {
		t.Errorf("New(no address) Kind = %v, want KindInvalid", k)
	}
}

func TestNew_RejectsUserpassWithoutCredential(t *testing.T) {
	t.Parallel()
	for name, dependencies := range map[string]vaultadapter.Dependencies{
		"no username": {Password: "p", Transport: &fakeTransport{}},
		"no password": {Username: "u", Transport: &fakeTransport{}},
	} {
		_, err := vaultadapter.New(
			vaultadapter.Config{Address: "http://x:8200", Mode: vaultadapter.ModeUserpass}, dependencies,
		)
		if err == nil {
			t.Errorf("%s: New should error", name)
		}
	}
}

func TestNew_RejectsTokenFileModeWithoutPath(t *testing.T) {
	t.Parallel()
	_, err := vaultadapter.New(
		vaultadapter.Config{Address: "http://x:8200", Mode: vaultadapter.ModeTokenFile},
		vaultadapter.Dependencies{Transport: &fakeTransport{}},
	)
	if err == nil {
		t.Fatal("ModeTokenFile with no TokenFilePath should error")
	}
}

// Happy-path resolve over the userpass bootstrap.

func TestResolve_UserpassReadsKVAndMintsSecret(t *testing.T) {
	t.Parallel()
	const apiPath = "eden/data/connectors/github"
	transport := &fakeTransport{kv: map[string]map[string]any{
		apiPath: kvEnvelope(map[string]any{"token": secretstest.SeededPlaintext}),
	}}
	adapter := newUserpassAdapter(t, transport)

	ref := secrets.Ref("vault://eden/connectors/github#token")
	sec, err := adapter.Resolve(context.Background(), ref)
	if err != nil {
		t.Fatalf("Resolve error = %v", err)
	}
	defer sec.Zeroize()

	got, err := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
	if err != nil {
		t.Fatalf("Use1 error = %v", err)
	}
	if got != secretstest.SeededPlaintext {
		t.Errorf("resolved value = %q, want %q", got, secretstest.SeededPlaintext)
	}
	if transport.setToken != "fake-login-token" {
		t.Errorf("adapter installed token %q, want the login token", transport.setToken)
	}
	if len(transport.pathsRead) != 1 || transport.pathsRead[0] != apiPath {
		t.Errorf("read paths = %v, want exactly [%q]", transport.pathsRead, apiPath)
	}
}

// TestResolve_UserpassLoginHappensExactlyOnce proves the once-guarded bootstrap: many Resolves
// drive exactly one login (the sticky token is reused), the local-mode invariant.
func TestResolve_UserpassLoginHappensExactlyOnce(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{kv: map[string]map[string]any{
		"eden/data/a": kvEnvelope(map[string]any{"k": "v1"}),
		"eden/data/b": kvEnvelope(map[string]any{"k": "v2"}),
	}}
	adapter := newUserpassAdapter(t, transport)
	for _, p := range []string{"vault://eden/a#k", "vault://eden/b#k", "vault://eden/a#k"} {
		sec, err := adapter.Resolve(context.Background(), secrets.Ref(p))
		if err != nil {
			t.Fatalf("Resolve(%q) error = %v", p, err)
		}
		sec.Zeroize()
	}
	if transport.loginCount != 1 {
		t.Errorf("login count = %d, want exactly 1 (sticky bootstrap)", transport.loginCount)
	}
}

// Token-file mode (the production bootstrap).

func TestResolve_TokenFileModeReadsTokenEachResolve(t *testing.T) {
	t.Parallel()
	const apiPath = "eden/data/runtime/key"
	transport := &fakeTransport{kv: map[string]map[string]any{
		apiPath: kvEnvelope(map[string]any{"value": "prod-secret"}),
	}}
	var reads int
	adapter, err := vaultadapter.New(
		vaultadapter.Config{
			Address:       "http://127.0.0.1:8200",
			Mode:          vaultadapter.ModeTokenFile,
			TokenFilePath: "/vault/secrets/token",
		},
		vaultadapter.Dependencies{
			Transport: transport,
			ReadTokenFile: func(path string) ([]byte, error) {
				reads++
				if path != "/vault/secrets/token" {
					t.Errorf("ReadTokenFile path = %q, want /vault/secrets/token", path)
				}
				return []byte("  sidecar-token-" + strconv.Itoa(reads) + "  \n"), nil
			},
		},
	)
	if err != nil {
		t.Fatalf("New(ModeTokenFile) error = %v", err)
	}

	ref := secrets.Ref("vault://eden/runtime/key#value")
	for range 2 {
		sec, rerr := adapter.Resolve(context.Background(), ref)
		if rerr != nil {
			t.Fatalf("Resolve error = %v", rerr)
		}
		sec.Zeroize()
	}
	if reads != 2 {
		t.Errorf("token-file reads = %d, want 2 (re-read each Resolve so a sidecar refresh is honored)", reads)
	}
	if transport.loginCalled {
		t.Error("ModeTokenFile must not call Login (the sidecar token is already minted)")
	}
	if !strings.HasPrefix(transport.setToken, "sidecar-token-") {
		t.Errorf("installed token = %q, want the trimmed sidecar token", transport.setToken)
	}
}

func TestResolve_TokenFileModeEmptyTokenIsUnavailable(t *testing.T) {
	t.Parallel()
	adapter, err := vaultadapter.New(
		vaultadapter.Config{Address: "http://x:8200", Mode: vaultadapter.ModeTokenFile, TokenFilePath: "/t"},
		vaultadapter.Dependencies{
			Transport:     &fakeTransport{},
			ReadTokenFile: func(string) ([]byte, error) { return []byte("   \n"), nil },
		},
	)
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	_, rerr := adapter.Resolve(context.Background(), secrets.Ref("vault://eden/a#k"))
	if !is[secrets.UnavailableError](rerr) {
		t.Errorf("empty token-file Resolve error = %v, want UnavailableError", rerr)
	}
}

// Reference parsing yields the typed InvalidReferenceError.

func TestResolve_MalformedReferenceIsInvalid(t *testing.T) {
	t.Parallel()
	adapter := newUserpassAdapter(t, &fakeTransport{})
	for _, raw := range []string{
		"vault://eden/path",   // no #key fragment
		"vault://eden/path#",  // empty key
		"vault://eden#key",    // mount but no path
		"vault://#key",        // no mount, no path
		"notvault://eden/p#k", // wrong scheme
		"vault://eden//#k",    // empty path after trim
	} {
		_, err := adapter.Resolve(context.Background(), secrets.Ref(raw))
		if !is[secrets.InvalidReferenceError](err) {
			t.Errorf("Resolve(%q) error = %v, want InvalidReferenceError", raw, err)
		}
	}
}

func TestResolve_ZeroReferenceIsInvalid(t *testing.T) {
	t.Parallel()
	adapter := newUserpassAdapter(t, &fakeTransport{})
	_, err := adapter.Resolve(context.Background(), secrets.Reference{})
	if !is[secrets.InvalidReferenceError](err) {
		t.Errorf("Resolve(zero ref) error = %v, want InvalidReferenceError", err)
	}
}

// Not-found mapping for missing secrets/fields.

func TestResolve_MissingSecretIsNotFound(t *testing.T) {
	t.Parallel()
	adapter := newUserpassAdapter(t, &fakeTransport{kv: map[string]map[string]any{}})
	_, err := adapter.Resolve(context.Background(), secrets.Ref("vault://eden/missing#k"))
	if !is[secrets.NotFoundError](err) {
		t.Errorf("Resolve(missing) error = %v, want NotFoundError", err)
	}
}

func TestResolve_MissingFieldIsNotFound(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{kv: map[string]map[string]any{
		"eden/data/p": kvEnvelope(map[string]any{"present": "v"}),
	}}
	adapter := newUserpassAdapter(t, transport)
	_, err := adapter.Resolve(context.Background(), secrets.Ref("vault://eden/p#absent"))
	if !is[secrets.NotFoundError](err) {
		t.Errorf("Resolve(missing field) error = %v, want NotFoundError", err)
	}
}

func TestResolve_NonStringFieldIsNotFound(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{kv: map[string]map[string]any{
		"eden/data/p": kvEnvelope(map[string]any{"k": 42}),
	}}
	adapter := newUserpassAdapter(t, transport)
	_, err := adapter.Resolve(context.Background(), secrets.Ref("vault://eden/p#k"))
	if !is[secrets.NotFoundError](err) {
		t.Errorf("Resolve(non-string field) error = %v, want NotFoundError", err)
	}
}

// Transport-error to taxonomy mapping.

func TestResolve_ForbiddenIsDenied(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{readErr: &vaultapi.ResponseError{StatusCode: http.StatusForbidden}}
	adapter := newUserpassAdapter(t, transport)
	_, err := adapter.Resolve(context.Background(), secrets.Ref("vault://eden/p#k"))
	if !is[secrets.DeniedError](err) {
		t.Errorf("Resolve(403) error = %v, want DeniedError", err)
	}
}

func TestResolve_Response404IsNotFound(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{readErr: &vaultapi.ResponseError{StatusCode: http.StatusNotFound}}
	adapter := newUserpassAdapter(t, transport)
	_, err := adapter.Resolve(context.Background(), secrets.Ref("vault://eden/p#k"))
	if !is[secrets.NotFoundError](err) {
		t.Errorf("Resolve(404) error = %v, want NotFoundError", err)
	}
}

func TestResolve_ServerErrorIsUnavailable(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{readErr: &vaultapi.ResponseError{StatusCode: http.StatusBadGateway}}
	adapter := newUserpassAdapter(t, transport)
	_, err := adapter.Resolve(context.Background(), secrets.Ref("vault://eden/p#k"))
	if !is[secrets.UnavailableError](err) {
		t.Errorf("Resolve(502) error = %v, want UnavailableError", err)
	}
}

func TestResolve_DialErrorIsUnavailable(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{readErr: errors.New(errors.KindUnavailable, "connection refused")}
	adapter := newUserpassAdapter(t, transport)
	_, err := adapter.Resolve(context.Background(), secrets.Ref("vault://eden/p#k"))
	if !is[secrets.UnavailableError](err) {
		t.Errorf("Resolve(dial error) error = %v, want UnavailableError", err)
	}
}

func TestResolve_LoginFailureIsMappedAndSticky(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{loginErr: &vaultapi.ResponseError{StatusCode: http.StatusForbidden}}
	adapter := newUserpassAdapter(t, transport)
	for range 3 {
		_, err := adapter.Resolve(context.Background(), secrets.Ref("vault://eden/p#k"))
		if !is[secrets.DeniedError](err) {
			t.Errorf("Resolve after login-403 error = %v, want DeniedError", err)
		}
	}
	if transport.loginCount != 1 {
		t.Errorf("login attempted %d times, want exactly 1 (sticky bootstrap error)", transport.loginCount)
	}
}

// KV v1 (unwrapped) tolerance.

func TestResolve_KVv1RawMapIsAccepted(t *testing.T) {
	t.Parallel()
	// A KV v1 mount returns the fields WITHOUT the "data" envelope.
	transport := &fakeTransport{kv: map[string]map[string]any{
		"kv/data/legacy": {"password": "v1-secret"},
	}}
	adapter := newUserpassAdapter(t, transport)
	sec, err := adapter.Resolve(context.Background(), secrets.Ref("vault://kv/legacy#password"))
	if err != nil {
		t.Fatalf("Resolve(KV v1) error = %v", err)
	}
	defer sec.Zeroize()
	got, uerr := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
	if uerr != nil {
		t.Fatalf("Use1 error = %v", uerr)
	}
	if got != "v1-secret" {
		t.Errorf("KV v1 resolved value = %q, want v1-secret", got)
	}
}
