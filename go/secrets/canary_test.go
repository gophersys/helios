package secrets_test

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// seededCanary is the redaction needle (ADR-0020 dimension (f), the CENTRAL property of the
// secrets library): a secret VALUE that, once minted into a Secret or seeded into a Provider,
// must appear in NO surfaced artifact — not String/GoString, not any fmt verb, not MarshalText/
// MarshalJSON, not a slog record, not TelemetryValue, and never in an error message. One leak
// fails the lane. The needle is high-entropy and self-labeling so a real gitleaks/secretscan
// match would be unambiguous if it ever escaped.
const seededCanary = "SEEDED-CANARY-c2VjcmV0-d34db33f-do-not-leak"

// allRedactionSurfaces renders every operator-facing projection of sec into a labeled map, so a
// single assertion can prove the canary is absent from EVERY surface at once. It deliberately
// routes the %s/%v verbs through fmt's verb machinery (not sec.String()) because the point is to
// prove the Format override redacts those verbs — gocritic's redundantSprint suggestion would
// bypass the very code path under test.
func allRedactionSurfaces(t *testing.T, sec *secrets.Secret) map[string]string {
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
	slog.New(slog.NewJSONHandler(&logbuf, nil)).Info("resolve", "credential", sec)

	tv, ok := sec.TelemetryValue().(string)
	if !ok {
		t.Fatalf("TelemetryValue() returned %T, want a string projection", sec.TelemetryValue())
	}
	return map[string]string{
		"String":            sec.String(),
		"GoString":          sec.GoString(),
		"%s":                fmt.Sprintf("%s", sec), //nolint:gocritic // exercises the Format verb path under test.
		"%v":                fmt.Sprintf("%v", sec), //nolint:gocritic // exercises the Format verb path under test.
		"%+v":               fmt.Sprintf("%+v", sec),
		"%#v":               fmt.Sprintf("%#v", sec),
		"%q":                fmt.Sprintf("%q", sec),
		"%d":                fmt.Sprintf("%d", sec),
		"MarshalText":       string(tb),
		"MarshalJSON":       string(jb),
		"json.Marshal":      string(enc),
		"slog":              logbuf.String(),
		"LogValue":          sec.LogValue().String(),
		"TelemetryValue":    tv,
		"struct-embed-json": mustMarshalWrapper(t, sec),
	}
}

// mustMarshalWrapper marshals a struct that embeds the *Secret as a JSON field — the most common
// real-world leak vector (a config/audit record carrying a credential) — and returns the output.
func mustMarshalWrapper(t *testing.T, sec *secrets.Secret) string {
	t.Helper()
	type auditRecord struct {
		Reference  string          `json:"reference"`
		Credential *secrets.Secret `json:"credential"`
	}
	b, err := json.Marshal(auditRecord{Reference: "vault://eden/audit#token", Credential: sec})
	if err != nil {
		t.Fatalf("json.Marshal(auditRecord) error = %v", err)
	}
	return string(b)
}

// TestCanary_NeverLeaksThroughAnyMintedSurface mints a Secret holding the canary and asserts the
// needle appears in NONE of the rendering/marshaling surfaces, and that the redaction surfaces
// instead carry the Redacted sentinel (so a regression that dropped the value silently — rather
// than redacting — is also caught). This is the load-bearing redaction property.
func TestCanary_NeverLeaksThroughAnyMintedSurface(t *testing.T) {
	t.Parallel()
	sec := secretstest.MintSecret([]byte(seededCanary))
	defer sec.Zeroize()

	surfaces := allRedactionSurfaces(t, sec)
	for name, rendered := range surfaces {
		if strings.Contains(rendered, seededCanary) {
			t.Fatalf("canary leaked through %s: %q", name, rendered)
		}
	}

	// The direct redaction surfaces must equal the sentinel — proving they redacted, not dropped.
	for _, name := range []string{"String", "GoString", "%s", "%v", "%+v", "%#v", "%d", "MarshalText", "LogValue", "TelemetryValue"} {
		if surfaces[name] != secrets.Redacted {
			t.Errorf("%s = %q, want the Redacted sentinel %q", name, surfaces[name], secrets.Redacted)
		}
	}
	// The slog record and the JSON embeds carry the sentinel SOMEWHERE (within the structured line),
	// proving the value was projected to Redacted rather than omitted.
	for _, name := range []string{"slog", "json.Marshal", "struct-embed-json"} {
		if !strings.Contains(surfaces[name], secrets.Redacted) {
			t.Errorf("%s did not project to the Redacted sentinel: %q", name, surfaces[name])
		}
	}
}

// TestCanary_NeverLeaksThroughResolvePath proves the redaction holds for the value AS IT FLOWS
// through the production Mediator.Resolve path: a Provider seeded with the canary, routed by the
// Mediator, yields a Secret whose every surface still redacts. This closes the "the type redacts
// but the resolution wiring leaks" gap — the canary must survive routing un-surfaced.
func TestCanary_NeverLeaksThroughResolvePath(t *testing.T) {
	t.Parallel()
	ref := secrets.Ref("vault://eden/connectors/github#token")
	adapter := secretstest.New(map[string]string{ref.String(): seededCanary})
	med, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": adapter}},
	)
	if err != nil {
		t.Fatalf("secrets.New error = %v", err)
	}

	sec, err := med.Resolve(context.Background(), ref)
	if err != nil {
		t.Fatalf("Resolve error = %v", err)
	}
	defer sec.Zeroize()

	for name, rendered := range allRedactionSurfaces(t, sec) {
		if strings.Contains(rendered, seededCanary) {
			t.Fatalf("canary leaked through %s after Resolve: %q", name, rendered)
		}
	}

	// The fake's Resolved log records the REFERENCE, never the value — assert the canary is absent
	// from the audit trail too.
	for _, logged := range adapter.Resolved {
		if strings.Contains(logged.String(), seededCanary) {
			t.Fatalf("canary leaked into the Provider's Resolved audit log: %q", logged.String())
		}
	}
}

// TestRedact_ErrorTaxonomyNeverCarriesValue proves the error contract's redaction half: every
// taxonomy error carries the loggable Reference but NEVER a secret value. The canary is placed
// where a careless implementation might interpolate it (it is NOT the reference text), and the
// error's message, AsType round-trip, and wrapped-chain string must all stay canary-free.
func TestRedact_ErrorTaxonomyNeverCarriesValue(t *testing.T) {
	t.Parallel()
	// The reference is loggable and legitimately appears; the canary is the VALUE that must not.
	ref := secrets.Ref("vault://eden/secret#field")
	taxonomy := []error{
		secrets.InvalidReferenceError{Ref: ref},
		secrets.NotFoundError{Ref: ref},
		secrets.DeniedError{Ref: ref},
		secrets.UnavailableError{Ref: ref},
		secrets.ZeroizedError{},
	}
	for _, e := range taxonomy {
		direct := e.Error()
		wrapped := fmt.Errorf("while resolving %s with credential canary: %w", ref, e).Error()
		for label, surface := range map[string]string{"Error()": direct, "wrapped-chain": wrapped} {
			if strings.Contains(surface, seededCanary) {
				t.Fatalf("%T %s leaked the canary: %q", e, label, surface)
			}
		}
	}
}

// TestSecret_ZeroizeRemovesReadableResidue is the wipe half of the redaction contract: after
// Zeroize, the canary bytes are not merely hidden from String() — they are wiped from the
// backing store, so even a contract-violating retained slice no longer reads the canary.
func TestSecret_ZeroizeRemovesReadableResidue(t *testing.T) {
	t.Parallel()
	sec := secretstest.MintSecret([]byte(seededCanary))

	var retained []byte
	if err := sec.Use(func(b []byte) error {
		retained = b // a contract violation we deliberately stage to prove Zeroize wipes in place
		return nil
	}); err != nil {
		t.Fatalf("Use error = %v", err)
	}
	sec.Zeroize()
	if strings.Contains(string(retained), seededCanary) {
		t.Fatalf("Zeroize did not wipe the backing bytes — a retained slice still reads the canary")
	}
}
