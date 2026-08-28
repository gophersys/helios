package vaultadapter_test

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"testing"

	vaultapi "github.com/hashicorp/vault/api"

	"github.com/gophersys/libs/go/secrets"
)

// seededCanary is the redaction needle for the Vault backend (ADR-0020 dimension (f)): a secret
// VALUE that, once read from Vault into a Secret, must appear in NO surfaced artifact — not any
// fmt verb, not Marshal*, not a slog record, not TelemetryValue, and never an error message. One
// leak fails the lane. High-entropy + self-labeling so a real gitleaks match would be unambiguous.
const seededCanary = "SEEDED-CANARY-vault-d34db33f-c0ffee-do-not-leak"

// TestCanary_VaultResolvedValueNeverLeaks resolves the canary THROUGH the Vault adapter's full
// path (parse → token → KV read → mint) and asserts every operator-facing projection of the
// resulting Secret redacts to the sentinel and never contains the canary — the "the type redacts
// but the resolution wiring leaks" gap closed for the real backend.
func TestCanary_VaultResolvedValueNeverLeaks(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{kv: map[string]map[string]any{
		"eden/data/connectors/github": kvEnvelope(map[string]any{"token": seededCanary}),
	}}
	adapter := newUserpassAdapter(t, transport)

	ref := secrets.Ref("vault://eden/connectors/github#token")
	sec, err := adapter.Resolve(context.Background(), ref)
	if err != nil {
		t.Fatalf("Resolve error = %v", err)
	}
	defer sec.Zeroize()

	for name, rendered := range vaultRedactionSurfaces(t, sec) {
		if strings.Contains(rendered, seededCanary) {
			t.Fatalf("canary leaked through %s after a Vault Resolve: %q", name, rendered)
		}
		if rendered != secrets.Redacted && !strings.Contains(rendered, secrets.Redacted) {
			t.Errorf("%s = %q, did not project to the Redacted sentinel", name, rendered)
		}
	}
}

// TestCanary_VaultErrorsNeverCarryValue forces the adapter's transport-error paths (403/404/5xx/
// dial) and asserts no surfaced error message ever carries the canary, even though the seeded KV
// holds it — the error half of the redaction contract for the backend.
func TestCanary_VaultErrorsNeverCarryValue(t *testing.T) {
	t.Parallel()
	ref := secrets.Ref("vault://eden/connectors/github#token")
	for name, transport := range map[string]*fakeTransport{
		"403":  {readErr: &vaultapi.ResponseError{StatusCode: http.StatusForbidden}, kv: canaryKV()},
		"404":  {readErr: &vaultapi.ResponseError{StatusCode: http.StatusNotFound}, kv: canaryKV()},
		"5xx":  {readErr: &vaultapi.ResponseError{StatusCode: http.StatusBadGateway}, kv: canaryKV()},
		"miss": {kv: map[string]map[string]any{}},
	} {
		adapter := newUserpassAdapter(t, transport)
		_, err := adapter.Resolve(context.Background(), ref)
		if err == nil {
			continue
		}
		surface := err.Error() + " | " + fmt.Sprintf("%v %+v", err, err)
		if strings.Contains(surface, seededCanary) {
			t.Fatalf("%s error path leaked the canary: %q", name, surface)
		}
		// The loggable Reference legitimately appears in the typed errors that carry it.
		_ = ref
	}
}

// vaultRedactionSurfaces renders every operator-facing projection of sec for the leak assertion.
// It routes %s/%v through fmt's verb machinery (not sec.String()) so the Format override is the
// code path under test.
func vaultRedactionSurfaces(t *testing.T, sec *secrets.Secret) map[string]string {
	t.Helper()
	tb, err := sec.MarshalText()
	if err != nil {
		t.Fatalf("MarshalText error = %v", err)
	}
	jb, err := sec.MarshalJSON()
	if err != nil {
		t.Fatalf("MarshalJSON error = %v", err)
	}
	enc, err := json.Marshal(sec)
	if err != nil {
		t.Fatalf("json.Marshal error = %v", err)
	}
	var logbuf bytes.Buffer
	slog.New(slog.NewJSONHandler(&logbuf, nil)).Info("vault resolve", "credential", sec)
	tv, ok := sec.TelemetryValue().(string)
	if !ok {
		t.Fatalf("TelemetryValue() returned %T, want a string projection", sec.TelemetryValue())
	}
	return map[string]string{
		"String":         sec.String(),
		"GoString":       sec.GoString(),
		"%s":             fmt.Sprintf("%s", sec), //nolint:gocritic // exercises the Format verb path under test.
		"%v":             fmt.Sprintf("%v", sec), //nolint:gocritic // exercises the Format verb path under test.
		"%+v":            fmt.Sprintf("%+v", sec),
		"%#v":            fmt.Sprintf("%#v", sec),
		"%q":             fmt.Sprintf("%q", sec),
		"MarshalText":    string(tb),
		"MarshalJSON":    string(jb),
		"json.Marshal":   string(enc),
		"slog":           logbuf.String(),
		"LogValue":       sec.LogValue().String(),
		"TelemetryValue": tv,
	}
}

// canaryKV seeds the canary at the github connector path so the error-path tests prove the value
// is present in the store yet never reaches an error surface.
func canaryKV() map[string]map[string]any {
	return map[string]map[string]any{
		"eden/data/connectors/github": kvEnvelope(map[string]any{"token": seededCanary}),
	}
}
