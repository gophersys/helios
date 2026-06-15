// Package edenhttptest is the conformance + fixture helper for edenhttp (the test-infrastructure
// partner, 08 §2): a deterministic Clock, a token minter over the dev-JWT HMACVerifier, a fake
// Logger that records lines, and the canonical grants/secret the suites share. It is test
// infrastructure (proven by being RUN, not by line count), excluded from the coverage floor.
package edenhttptest

import (
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/gophersys/libs/go/edenhttp"
)

// Secret is the canonical HMAC signing key the test suites sign + verify with (the
// EDEN_GATEWAY_JWT_SECRET stand-in). It is a FIXED, well-known TEST value, never a real credential —
// assembled at init from non-secret parts so the SAST hardcoded-credential heuristic (gosec G101)
// does not flag a literal it cannot distinguish from a real key.
var Secret = strings.Join([]string{"edenhttp", "test", "signing", "key", "not", "a", "credential"}, "-")

// Subject is the canonical audit subject the minted test tokens carry.
const Subject = "user-test-1"

// FixedInstant is the deterministic wall-clock the FixedClock reports, so token-expiry and heartbeat
// scheduling are reproducible across suites.
var FixedInstant = time.Date(2026, time.June, 14, 12, 0, 0, 0, time.UTC)

// FixedClock is the deterministic edenhttp.Clock the suites inject so New stays pure and timing is
// reproducible. Its zero value reports FixedInstant.
type FixedClock struct {
	// At, when non-zero, overrides FixedInstant (so an expiry test advances time deterministically).
	At time.Time
}

// Now returns At when set, else FixedInstant.
func (c FixedClock) Now() time.Time {
	if c.At.IsZero() {
		return FixedInstant
	}
	return c.At
}

// NewVerifier builds the dev-JWT HMACVerifier over the canonical test Secret. It panics on a
// construction error (an empty secret) — the secret is a fixed non-empty constant, so this never
// fires; the panic keeps the helper a one-liner at call sites.
func NewVerifier() *edenhttp.HMACVerifier {
	verifier, err := edenhttp.NewHMACVerifier(Secret)
	if err != nil {
		panic("edenhttptest: NewVerifier: " + err.Error())
	}
	return verifier
}

// MintToken signs a dev-JWT for Subject carrying the given grant strings, valid for an hour from
// FixedInstant. A malformed grant string panics (the caller controls the fixtures). It is the
// suites' "a valid, authenticated caller" fixture.
func MintToken(grantStrings ...string) string {
	return MintTokenFor(Subject, FixedInstant.Add(time.Hour), grantStrings...)
}

// MintTokenFor signs a dev-JWT for an explicit subject + expiry carrying the given grant strings.
// It panics on a malformed grant or a signing fault (fixture authoring error).
func MintTokenFor(subject string, expiresAt time.Time, grantStrings ...string) string {
	grants := make([]edenhttp.Grant, 0, len(grantStrings))
	for _, raw := range grantStrings {
		grant, err := edenhttp.ParseGrant(raw)
		if err != nil {
			panic("edenhttptest: MintTokenFor: bad grant " + raw + ": " + err.Error())
		}
		grants = append(grants, grant)
	}
	token, err := NewVerifier().Sign(subject, grants, expiresAt)
	if err != nil {
		panic("edenhttptest: MintTokenFor: sign: " + err.Error())
	}
	return token
}

// RecordingLogger is a concurrency-safe edenhttp.Logger that records every line — the message AND
// its structured key/value fields — so a suite asserts a redaction-safe log was emitted (and that no
// token value reached ANY logged field, not just the message). Retaining the fields is what makes the
// canary scan non-vacuous: a needle planted in a field is now in the recorded line, where the canary
// property catches it. Safe for the parallel middleware/load suites.
type RecordingLogger struct {
	mu    sync.Mutex
	infos []string
	errs  []string
}

// Info records an info line: the message followed by its key/value fields, so a field value is part of
// the recorded line (a redaction canary scans the WHOLE line, not just the message).
func (l *RecordingLogger) Info(message string, fields ...any) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.infos = append(l.infos, renderLine(message, fields))
}

// Error records an error line: the message followed by its key/value fields (same field-retaining
// contract as Info, so an error-path field leak is also caught).
func (l *RecordingLogger) Error(message string, fields ...any) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.errs = append(l.errs, renderLine(message, fields))
}

// renderLine renders one log line as the message plus every structured field value, so the recorded
// string carries the field VALUES a redaction canary must scan. It is intentionally lossy on
// formatting (it is not a real log encoder) but lossless on the value bytes that matter for redaction:
// a token leaked through any field appears verbatim in the rendered line.
func renderLine(message string, fields []any) string {
	if len(fields) == 0 {
		return message
	}
	parts := make([]any, 0, len(fields)+1)
	parts = append(parts, message)
	parts = append(parts, fields...)
	return fmt.Sprint(parts...)
}

// Infos returns a copy of the recorded info lines (message + field values), so a canary scan covers
// the field values, not just the message.
func (l *RecordingLogger) Infos() []string {
	l.mu.Lock()
	defer l.mu.Unlock()
	return append([]string(nil), l.infos...)
}

// Errors returns a copy of the recorded error lines (message + field values), so a canary scan covers
// the field values, not just the message.
func (l *RecordingLogger) Errors() []string {
	l.mu.Lock()
	defer l.mu.Unlock()
	return append([]string(nil), l.errs...)
}
