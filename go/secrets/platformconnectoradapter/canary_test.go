package platformconnectoradapter_test

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/platformconnectoradapter"
)

// seededCanary is the redaction needle for the connector backend (ADR-0020 dimension (f)): a secret
// VALUE that, once sealed and resolved THROUGH THE WHOLE CHAIN (load → envelope.Unseal → mint), must
// appear in NO surfaced artifact — not any fmt verb, not Marshal*, not a slog record, not
// TelemetryValue, and never an error message. One leak fails the lane. High-entropy + self-labeling so
// a real gitleaks match would be unambiguous.
const seededCanary = "SEEDED-CANARY-connector-d34db33f-c0ffee-do-not-leak"

// TestCanary_ResolvedConnectorValueNeverLeaks resolves the canary THROUGH the adapter's full path
// (parse → load → envelope.Unseal → mint) and asserts every operator-facing projection of the resulting
// Secret redacts to the sentinel and never contains the canary — the "the type redacts but the
// resolution wiring leaks" gap closed for the connector backend, end-to-end through the real crypto.
func TestCanary_ResolvedConnectorValueNeverLeaks(t *testing.T) {
	t.Parallel()
	const id = "canary-connector"
	transport := seededTransport(t, id, seededCanary)
	adapter := newAdapter(t, transport)

	sec, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/"+id))
	if err != nil {
		t.Fatalf("Resolve err = %v", err)
	}
	defer sec.Zeroize()

	for name, rendered := range redactionSurfaces(t, sec) {
		if strings.Contains(rendered, seededCanary) {
			t.Fatalf("canary leaked through %s after a connector Resolve: %q", name, rendered)
		}
		if rendered != secrets.Redacted && !strings.Contains(rendered, secrets.Redacted) {
			t.Errorf("%s = %q, did not project to the Redacted sentinel", name, rendered)
		}
	}
}

// TestCanary_ConnectorErrorsNeverCarryValue forces the adapter's fault paths (a tampered record whose
// sealed blob holds the canary; a transport outage) and asserts no surfaced error message ever carries
// the canary, even though the sealed material encodes it — the error half of the redaction contract.
func TestCanary_ConnectorErrorsNeverCarryValue(t *testing.T) {
	t.Parallel()
	const id = "canary-error"
	ref := secrets.Ref("eden://connector/" + id)

	// A record sealing the canary, then tampered so Unseal fails — the sealed blob is present but the
	// error must not carry the canary.
	record := sealValue(t, newSealer(t), seededCanary)
	record.Ciphertext[len(record.Ciphertext)-1] ^= 0xFF
	tampered := &fakeTransport{records: map[string]platformconnectoradapter.SealedRecord{id: record}}

	outage := &fakeTransport{loadErr: errors.New(errors.KindUnavailable, "connectors store down")}

	for name, transport := range map[string]*fakeTransport{"tampered": tampered, "outage": outage} {
		adapter := newAdapter(t, transport)
		_, err := adapter.Resolve(context.Background(), ref)
		if err == nil {
			t.Fatalf("%s: expected an error", name)
		}
		surface := err.Error() + " | " + fmt.Sprintf("%v %+v", err, err)
		if strings.Contains(surface, seededCanary) {
			t.Fatalf("%s error path leaked the canary: %q", name, surface)
		}
	}
}

// redactionSurfaces renders every operator-facing projection of sec for the leak assertion. It routes
// %s/%v through fmt's verb machinery (not sec.String()) so the Format override is the code path under
// test.
func redactionSurfaces(t *testing.T, sec *secrets.Secret) map[string]string {
	t.Helper()
	tb, err := sec.MarshalText()
	if err != nil {
		t.Fatalf("MarshalText err = %v", err)
	}
	jb, err := sec.MarshalJSON()
	if err != nil {
		t.Fatalf("MarshalJSON err = %v", err)
	}
	enc, err := json.Marshal(sec)
	if err != nil {
		t.Fatalf("json.Marshal err = %v", err)
	}
	var logbuf bytes.Buffer
	slog.New(slog.NewJSONHandler(&logbuf, nil)).Info("connector resolve", "credential", sec)
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
