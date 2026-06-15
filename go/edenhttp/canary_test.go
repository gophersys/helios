package edenhttp_test

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/edenhttptest"
	"github.com/gophersys/libs/go/errors"
)

// seededCanary is the needle the no-leak property feeds into the token/secret/error paths; it must
// appear in NO surfaced artifact (a response body, a header echoed to the client, a log line).
const seededCanary = "SEEDED-CANARY-edenhttp-do-not-leak"

// TestCanary_TokenNeverInResponseOrLog proves that a request carrying the canary as its bearer token
// leaks the token into NEITHER the 401 response body NOR a log line. The token value is attacker-
// supplied; the redaction contract is that it never echoes back.
func TestCanary_TokenNeverInResponseOrLog(t *testing.T) {
	t.Parallel()
	logger := &edenhttptest.RecordingLogger{}
	spine, err := edenhttp.New(
		edenhttp.Config{},
		edenhttp.Deps{Verifier: edenhttptest.NewVerifier(), Clock: edenhttptest.FixedClock{}, Logger: logger},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	handler := spine.MiddlewareFunc(func(http.ResponseWriter, *http.Request) {})

	request := httptest.NewRequest(http.MethodGet, "/sessions/x/events", http.NoBody)
	request.Header.Set("Authorization", "Bearer "+seededCanary) // the canary as a (malformed) token.
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, request)

	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", recorder.Code)
	}
	if strings.Contains(recorder.Body.String(), seededCanary) {
		t.Fatalf("the canary token leaked into the response body: %s", recorder.Body.String())
	}
	for header, values := range recorder.Header() {
		for _, value := range values {
			if strings.Contains(value, seededCanary) {
				t.Fatalf("the canary token leaked into header %q: %q", header, value)
			}
		}
	}
	for _, line := range append(logger.Infos(), logger.Errors()...) {
		if strings.Contains(line, seededCanary) {
			t.Fatalf("the canary token leaked into a log line: %q", line)
		}
	}
}

// TestCanary_LogFieldScanHasTeeth proves the token-no-leak canary is NON-VACUOUS: the RecordingLogger
// it scans retains structured field VALUES, so a token reaching a logged field IS caught. It plants
// the needle into a log FIELD (not the message) and asserts the same scan TestCanary_TokenNeverInResponse
// OrLog runs over the production log now surfaces it. WEAKEN-TO-CONFIRM: if RecordingLogger reverted to
// dropping fields (storing only `message`), the needle would vanish from Infos()/Errors() and this test
// would FAIL on the "want the scan to catch it" assertion — i.e. it certifies the redaction property is
// actually being exercised, not silently bypassed.
func TestCanary_LogFieldScanHasTeeth(t *testing.T) {
	t.Parallel()
	logger := &edenhttptest.RecordingLogger{}
	// A token value reaching a logged field is the exact leak the canary guards against. Plant it in a
	// FIELD on both the info and the error path (the two surfaces the production middleware/pipeline use).
	logger.Info("edenhttp: request rejected", "token", seededCanary)
	logger.Error("edenhttp: request failed", "offending-token", seededCanary)

	caught := false
	for _, line := range append(logger.Infos(), logger.Errors()...) {
		if strings.Contains(line, seededCanary) {
			caught = true
		}
	}
	if !caught {
		t.Fatal("the canary scan is VACUOUS: a token planted in a log FIELD was not surfaced by " +
			"Infos()/Errors() — the recorder is dropping fields, so the no-leak property proves nothing")
	}
}

// TestCanary_SecretNeverInSignedTokenOrError proves the HMAC SECRET never appears in a signed token
// (the secret signs, it is not embedded) nor in a verify error.
func TestCanary_SecretNeverInSignedTokenOrError(t *testing.T) {
	t.Parallel()
	verifier, err := edenhttp.NewHMACVerifier(seededCanary) // the canary as the SECRET.
	if err != nil {
		t.Fatalf("NewHMACVerifier: %v", err)
	}
	token, err := verifier.Sign("user-1", []edenhttp.Grant{edenhttp.NewGrant("sessions", "read")}, edenhttptest.FixedInstant.Add(time.Hour))
	if err != nil {
		t.Fatalf("Sign: %v", err)
	}
	if strings.Contains(token, seededCanary) {
		t.Fatalf("the HMAC secret leaked into the signed token: %s", token)
	}
	// A verify fault on a tampered token must not embed the secret either.
	_, verifyErr := verifier.Verify(token+"tamper", edenhttptest.FixedInstant)
	if verifyErr != nil && strings.Contains(verifyErr.Error(), seededCanary) {
		t.Fatalf("the HMAC secret leaked into a verify error: %v", verifyErr)
	}
}

// TestCanary_5xxErrorNeverLeaksCause proves WriteError on a 5xx carrying the canary in its cause
// returns only the generic message — the internal cause (and any secret in it) stays server-side.
func TestCanary_5xxErrorNeverLeaksCause(t *testing.T) {
	t.Parallel()
	recorder := httptest.NewRecorder()
	edenhttp.WriteError(recorder, errors.New(errors.KindInternal, "internal detail "+seededCanary))
	if strings.Contains(recorder.Body.String(), seededCanary) {
		t.Fatalf("a 5xx body leaked the internal cause: %s", recorder.Body.String())
	}
}
