package edenhttp_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/edenhttptest"
	"github.com/gophersys/libs/go/errors"
)

// ── grant grammar ─────────────────────────────────────────────────────────────.

func TestParseGrant_Valid(t *testing.T) {
	t.Parallel()
	grant, err := edenhttp.ParseGrant("sessions:control")
	if err != nil {
		t.Fatalf("ParseGrant: %v", err)
	}
	if grant.Namespace != "sessions" || grant.Action != "control" {
		t.Errorf("grant = %+v, want {sessions control}", grant)
	}
	if grant.String() != "sessions:control" {
		t.Errorf("String() = %q, want sessions:control", grant.String())
	}
}

func TestParseGrant_Wildcard(t *testing.T) {
	t.Parallel()
	grant, err := edenhttp.ParseGrant("*")
	if err != nil {
		t.Fatalf("ParseGrant(*): %v", err)
	}
	if grant.String() != "*" {
		t.Errorf("String() = %q, want *", grant.String())
	}
	if !grant.Covers(edenhttp.NewGrant("anything", "atall")) {
		t.Error("* must cover any grant")
	}
}

func TestParseGrant_Malformed(t *testing.T) {
	t.Parallel()
	for _, raw := range []string{"", "  ", "noseparator", "a:b:c", ":action", "ns:"} {
		if _, err := edenhttp.ParseGrant(raw); errors.KindOf(err) != errors.KindInvalid {
			t.Errorf("ParseGrant(%q) kind = %s, want invalid", raw, errors.KindOf(err))
		}
	}
}

func TestGrant_Covers(t *testing.T) {
	t.Parallel()
	cases := []struct {
		held, required string
		want           bool
	}{
		{"sessions:control", "sessions:control", true},
		{"sessions:*", "sessions:control", true},
		{"*", "sessions:control", true},
		{"sessions:control", "sessions:read", false},
		{"sessions:control", "workspaces:control", false},
		{"workspaces:*", "sessions:control", false},
	}
	for _, c := range cases {
		held := mustGrant(t, c.held)
		required := mustGrant(t, c.required)
		if got := held.Covers(required); got != c.want {
			t.Errorf("%q.Covers(%q) = %v, want %v", c.held, c.required, got, c.want)
		}
	}
}

// ── the dev-JWT HMAC verifier ─────────────────────────────────────────────────.

func TestNewHMACVerifier_RejectsEmptySecret(t *testing.T) {
	t.Parallel()
	if _, err := edenhttp.NewHMACVerifier(""); errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("empty secret kind = %s, want invalid", errors.KindOf(err))
	}
}

func TestHMACVerifier_SignVerifyRoundTrip(t *testing.T) {
	t.Parallel()
	verifier := edenhttptest.NewVerifier()
	token := edenhttptest.MintToken("sessions:control", "sessions:read")
	identity, err := verifier.Verify(token, edenhttptest.FixedInstant)
	if err != nil {
		t.Fatalf("Verify: %v", err)
	}
	if identity.Subject != edenhttptest.Subject {
		t.Errorf("subject = %q, want %q", identity.Subject, edenhttptest.Subject)
	}
	if len(identity.Grants) != 2 {
		t.Errorf("grants = %d, want 2", len(identity.Grants))
	}
}

// TestHMACVerifier_RejectsTamperedClaims proves flipping a claims byte breaks the signature.
func TestHMACVerifier_RejectsTamperedClaims(t *testing.T) {
	t.Parallel()
	verifier := edenhttptest.NewVerifier()
	token := edenhttptest.MintToken("sessions:read")
	parts := strings.Split(token, ".")
	// Tamper the claims segment (swap a character) so the signature no longer matches.
	parts[1] = "X" + parts[1][1:]
	tampered := strings.Join(parts, ".")
	if _, err := verifier.Verify(tampered, edenhttptest.FixedInstant); errors.KindOf(err) != errors.KindUnauthenticated {
		t.Fatalf("tampered token kind = %s, want unauthenticated", errors.KindOf(err))
	}
}

// TestHMACVerifier_RejectsMalformedStructure proves a non-three-segment token is rejected.
func TestHMACVerifier_RejectsMalformedStructure(t *testing.T) {
	t.Parallel()
	verifier := edenhttptest.NewVerifier()
	for _, bad := range []string{"", "onlyone", "two.parts", "a.b.c.d", "..", "a..c"} {
		if _, err := verifier.Verify(bad, edenhttptest.FixedInstant); errors.KindOf(err) != errors.KindUnauthenticated {
			t.Errorf("Verify(%q) kind = %s, want unauthenticated", bad, errors.KindOf(err))
		}
	}
}

// ── the uniform envelope + Kind→status map ────────────────────────────────────.

func TestStatusForKind(t *testing.T) {
	t.Parallel()
	cases := map[errors.Kind]int{
		errors.KindInvalid:         http.StatusBadRequest,
		errors.KindNotFound:        http.StatusNotFound,
		errors.KindConflict:        http.StatusConflict,
		errors.KindExhausted:       http.StatusTooManyRequests,
		errors.KindUnavailable:     http.StatusServiceUnavailable,
		errors.KindDeadline:        http.StatusGatewayTimeout,
		errors.KindUnauthenticated: http.StatusUnauthorized,
		errors.KindPermission:      http.StatusForbidden,
		errors.KindInternal:        http.StatusInternalServerError,
		errors.KindUnknown:         http.StatusInternalServerError,
	}
	for kind, want := range cases {
		if got := edenhttp.StatusForKind(kind); got != want {
			t.Errorf("StatusForKind(%s) = %d, want %d", kind, got, want)
		}
	}
}

// TestWriteError_5xxHidesCause proves a 5xx body carries the generic message, never the internal cause.
func TestWriteError_5xxHidesCause(t *testing.T) {
	t.Parallel()
	recorder := httptest.NewRecorder()
	status := edenhttp.WriteError(recorder, errors.New(errors.KindInternal, "a secret-bearing internal detail"))
	if status != http.StatusInternalServerError {
		t.Fatalf("status = %d, want 500", status)
	}
	if strings.Contains(recorder.Body.String(), "secret-bearing internal detail") {
		t.Errorf("5xx body leaked the internal cause: %s", recorder.Body.String())
	}
	var envelope edenhttp.Envelope
	if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if envelope.Kind != "internal" || len(envelope.Errors) != 1 || envelope.Errors[0] != "internal error" {
		t.Errorf("5xx envelope = %+v, want kind=internal errors=[internal error]", envelope)
	}
}

// TestWriteData_Envelope proves the data path wraps in {data, errors:[]}.
func TestWriteData_Envelope(t *testing.T) {
	t.Parallel()
	recorder := httptest.NewRecorder()
	edenhttp.WriteData(recorder, http.StatusOK, map[string]string{"id": "agent-1"})
	var envelope edenhttp.Envelope
	if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if envelope.Kind != "" || len(envelope.Errors) != 0 {
		t.Errorf("data envelope = %+v, want empty kind + no errors", envelope)
	}
	data, isObject := envelope.Data.(map[string]any)
	if !isObject {
		t.Fatalf("envelope data is not an object: %#v", envelope.Data)
	}
	if data["id"] != "agent-1" {
		t.Errorf("data.id = %v, want agent-1", data["id"])
	}
}

func mustGrant(t *testing.T, raw string) edenhttp.Grant {
	t.Helper()
	grant, err := edenhttp.ParseGrant(raw)
	if err != nil {
		t.Fatalf("ParseGrant(%q): %v", raw, err)
	}
	return grant
}
