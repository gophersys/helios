package platformconnectoradapter_test

import (
	"context"
	"sync"
	"testing"

	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/platformconnectoradapter"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// kekReference is the loggable KEK reference the test envelope.Sealer resolves through the seeded fake
// secrets.Provider — the SAME reference shape the production platform Vault holds
// (vault://eden/production#connectors-kek). The fake resolves it to a 32-byte AES-256 key.
const kekReference = "vault://eden/production#connectors-kek"

// kekPlaintext is the 32-byte (AES-256) fake KEK the seeded secretstest.Provider returns for
// kekReference. A real KEK is minted by the platform Vault seed; this fixture is a valid-length key so
// envelope's Seal/Unseal round-trips exactly as it does in production.
const kekPlaintext = "0123456789abcdef0123456789abcdef" // exactly 32 bytes

// fakeTransport is an in-memory platformconnectoradapter.SealedRowLoader for the UNIT lane: it exercises the
// adapter's parse → load → unseal → mint mapping WITHOUT a database. The REAL-Postgres proof is the
// integration lane (//go:build integration), never this fake (ADR-0016 §2). It records the ids loaded
// so a test can assert exactly one lookup per Resolve, and can force a typed load fault.
type fakeTransport struct {
	mu sync.Mutex

	// records maps a connector id to its envelope-sealed material (already sealed with the fake KEK, so
	// the adapter's real envelope.Unseal round-trips it).
	records map[string]platformconnectoradapter.SealedRecord
	// loadErr forces LoadSealed to return err (a typed errors.Error to drive the taxonomy mapping).
	loadErr error

	idsLoaded []string
}

func (f *fakeTransport) LoadSealed(_ context.Context, id string) (platformconnectoradapter.SealedRecord, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.idsLoaded = append(f.idsLoaded, id)
	if f.loadErr != nil {
		return platformconnectoradapter.SealedRecord{}, f.loadErr
	}
	record, ok := f.records[id]
	if !ok {
		// The documented "no such connector" sentinel: the zero SealedRecord (empty blobs), which the
		// adapter maps to NotFound. Mirrors the real transport returning the tenant-scoped-miss zero value.
		return platformconnectoradapter.SealedRecord{}, nil
	}
	return record, nil
}

// newKEKProvider returns a secrets.Provider seeded so the KEK reference resolves to the 32-byte fake
// KEK. It is the fake KEK SOURCE the test envelope.Sealer + the adapter share (the crypto is real; only
// the KEK bytes are a fixture).
func newKEKProvider() *secretstest.Provider {
	return secretstest.New(map[string]string{kekReference: kekPlaintext})
}

// newSealer builds a REAL envelope.Sealer over the fake KEK provider — the same crypto the platform
// gateway seals connectors with. Sealing a record with THIS sealer and unsealing it through the adapter
// (which shares the same KEK) is the round-trip the unit lane proves.
//
//nolint:ireturn // returns the envelope.Sealer port the adapter's Deps.Sealer holds (the frozen seam).
func newSealer(tb fatalReporter) envelope.Sealer {
	tb.Helper()
	sealer, err := envelope.New(
		envelope.Config{KEK: secrets.Ref(kekReference), KEKVersion: 1},
		envelope.Deps{Secrets: newKEKProvider()},
	)
	if err != nil {
		tb.Fatalf("envelope.New: %v", err)
	}
	return sealer
}

// sealValue seals plaintext with a real envelope.Sealer and returns the SealedRecord shape the
// transport hands back — so a seeded connector row is genuine envelope material, not a hand-rolled blob.
func sealValue(tb fatalReporter, sealer envelope.Sealer, plaintext string) platformconnectoradapter.SealedRecord {
	tb.Helper()
	sealed, err := sealer.Seal(context.Background(), []byte(plaintext))
	if err != nil {
		tb.Fatalf("Seal(%q): %v", plaintext, err)
	}
	return platformconnectoradapter.SealedRecord{
		Ciphertext:      sealed.Ciphertext,
		WrappedDEK:      sealed.WrappedDEK,
		NonceCiphertext: sealed.NonceCiphertext,
		NonceDEK:        sealed.NonceDEK,
		KEKVersion:      sealed.KEKVersion,
	}
}

// fatalReporter is the minimal failure surface the helpers need, satisfied by BOTH *testing.T and
// *rapid.T — so the property body and the table tests build the fixtures the same way.
type fatalReporter interface {
	Helper()
	Fatalf(format string, args ...any)
}

// newAdapter builds an adapter over the fake transport, injecting a pre-built (Deps.Sealer) envelope
// Sealer that shares the fake KEK — the construction the unit + conformance lanes share.
func newAdapter(tb fatalReporter, transport platformconnectoradapter.SealedRowLoader) *platformconnectoradapter.Adapter {
	tb.Helper()
	adapter, err := platformconnectoradapter.New(
		platformconnectoradapter.Config{},
		platformconnectoradapter.Deps{Loader: transport, Sealer: newSealer(tb)},
	)
	if err != nil {
		tb.Fatalf("platformconnectoradapter.New: %v", err)
	}
	return adapter
}

// seededTransport returns a fake transport holding one connector id sealed to plaintext.
func seededTransport(tb fatalReporter, id, plaintext string) *fakeTransport {
	tb.Helper()
	return &fakeTransport{records: map[string]platformconnectoradapter.SealedRecord{
		id: sealValue(tb, newSealer(tb), plaintext),
	}}
}

// ── Construction: New purity + validation ───────────────────────────────────────────────────────.

func TestNew_RejectsNilTransport(t *testing.T) {
	t.Parallel()
	_, err := platformconnectoradapter.New(
		platformconnectoradapter.Config{},
		platformconnectoradapter.Deps{Sealer: newSealer(t)},
	)
	if !errors.IsType[*errors.Error](err) || errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("New(nil transport) err = %v, want KindInvalid", err)
	}
}

func TestNew_BuildsSealerFromConfigWhenNotInjected(t *testing.T) {
	t.Parallel()
	// No Deps.Sealer: New must build one from Config.KEK + Deps.Secrets.
	adapter, err := platformconnectoradapter.New(
		platformconnectoradapter.Config{KEK: secrets.Ref(kekReference), KEKVersion: 1},
		platformconnectoradapter.Deps{
			Loader:  seededTransport(t, "abc", secretstest.SeededPlaintext),
			Secrets: newKEKProvider(),
		},
	)
	if err != nil {
		t.Fatalf("New(built sealer) err = %v", err)
	}
	sec, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/abc"))
	if err != nil {
		t.Fatalf("Resolve err = %v", err)
	}
	defer sec.Zeroize()
	got, useErr := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
	if useErr != nil {
		t.Fatalf("Use1 err = %v", useErr)
	}
	if got != secretstest.SeededPlaintext {
		t.Errorf("resolved value = %q, want the seeded plaintext", got)
	}
}

func TestNew_RejectsBuiltSealerWithoutSecrets(t *testing.T) {
	t.Parallel()
	_, err := platformconnectoradapter.New(
		platformconnectoradapter.Config{KEK: secrets.Ref(kekReference)},
		platformconnectoradapter.Deps{Loader: &fakeTransport{}}, // no Sealer, no Secrets
	)
	if errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("New(no sealer, no secrets) err = %v, want KindInvalid", err)
	}
}

func TestNew_RejectsBuiltSealerWithZeroKEK(t *testing.T) {
	t.Parallel()
	_, err := platformconnectoradapter.New(
		platformconnectoradapter.Config{}, // zero KEK
		platformconnectoradapter.Deps{Loader: &fakeTransport{}, Secrets: newKEKProvider()},
	)
	if errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("New(no sealer, zero KEK) err = %v, want KindInvalid", err)
	}
}

// ── Happy-path resolve ──────────────────────────────────────────────────────────────────────────.

func TestResolve_LoadsSealedRowAndMintsSecret(t *testing.T) {
	t.Parallel()
	const id = "11111111-2222-3333-4444-555555555555"
	transport := seededTransport(t, id, secretstest.SeededPlaintext)
	adapter := newAdapter(t, transport)

	sec, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/"+id))
	if err != nil {
		t.Fatalf("Resolve err = %v", err)
	}
	defer sec.Zeroize()

	got, err := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
	if err != nil {
		t.Fatalf("Use1 err = %v", err)
	}
	if got != secretstest.SeededPlaintext {
		t.Errorf("resolved value = %q, want %q", got, secretstest.SeededPlaintext)
	}
	if len(transport.idsLoaded) != 1 || transport.idsLoaded[0] != id {
		t.Errorf("ids loaded = %v, want exactly [%q]", transport.idsLoaded, id)
	}
}

// ── Reference parsing → typed InvalidReferenceError ─────────────────────────────────────────────.

func TestResolve_MalformedReferenceIsInvalid(t *testing.T) {
	t.Parallel()
	adapter := newAdapter(t, &fakeTransport{})
	for _, raw := range []string{
		"vault://eden/connectors/x#token", // wrong scheme
		"eden://connector/",               // empty id
		"eden://connector",                // no resource slash
		"eden://other/abc",                // wrong resource
		"eden://connector/abc/def",        // id has a path segment
		"eden://connector/abc#frag",       // id has a fragment
		"eden://",                         // nothing after scheme
	} {
		_, err := adapter.Resolve(context.Background(), secrets.Ref(raw))
		if !errors.IsType[secrets.InvalidReferenceError](err) {
			t.Errorf("Resolve(%q) err = %v, want InvalidReferenceError", raw, err)
		}
	}
}

func TestResolve_ZeroReferenceIsInvalid(t *testing.T) {
	t.Parallel()
	adapter := newAdapter(t, &fakeTransport{})
	_, err := adapter.Resolve(context.Background(), secrets.Reference{})
	if !errors.IsType[secrets.InvalidReferenceError](err) {
		t.Errorf("Resolve(zero ref) err = %v, want InvalidReferenceError", err)
	}
}

// ── Not-found mapping ───────────────────────────────────────────────────────────────────────────.

func TestResolve_AbsentConnectorIsNotFound(t *testing.T) {
	t.Parallel()
	adapter := newAdapter(t, &fakeTransport{records: map[string]platformconnectoradapter.SealedRecord{}})
	_, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/missing"))
	if !errors.IsType[secrets.NotFoundError](err) {
		t.Errorf("Resolve(absent) err = %v, want NotFoundError", err)
	}
}

func TestResolve_TransportNotFoundIsNotFound(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{loadErr: errors.New(errors.KindNotFound, "connector not found")}
	adapter := newAdapter(t, transport)
	_, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/abc"))
	if !errors.IsType[secrets.NotFoundError](err) {
		t.Errorf("Resolve(transport 404) err = %v, want NotFoundError", err)
	}
}

// ── Transport-fault → taxonomy mapping ──────────────────────────────────────────────────────────.

func TestResolve_TransportPermissionIsDenied(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{loadErr: errors.New(errors.KindPermission, "cross-tenant")}
	adapter := newAdapter(t, transport)
	_, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/abc"))
	if !errors.IsType[secrets.DeniedError](err) {
		t.Errorf("Resolve(denied) err = %v, want DeniedError", err)
	}
}

func TestResolve_TransportOutageIsUnavailable(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{loadErr: errors.New(errors.KindUnavailable, "database down")}
	adapter := newAdapter(t, transport)
	_, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/abc"))
	if !errors.IsType[secrets.UnavailableError](err) {
		t.Errorf("Resolve(outage) err = %v, want UnavailableError", err)
	}
}

func TestResolve_TransportUnclassifiedIsUnavailable(t *testing.T) {
	t.Parallel()
	transport := &fakeTransport{loadErr: errors.New(errors.KindInternal, "boom")}
	adapter := newAdapter(t, transport)
	_, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/abc"))
	if !errors.IsType[secrets.UnavailableError](err) {
		t.Errorf("Resolve(unclassified) err = %v, want UnavailableError", err)
	}
}

// ── Tampered / wrong-KEK record → InvalidReferenceError (GCM authenticity via envelope) ─────────.

func TestResolve_TamperedCiphertextIsInvalid(t *testing.T) {
	t.Parallel()
	const id = "tampered"
	record := sealValue(t, newSealer(t), secretstest.SeededPlaintext)
	// Flip a ciphertext byte — GCM authentication must reject it inside envelope.Unseal.
	record.Ciphertext[0] ^= 0xFF
	transport := &fakeTransport{records: map[string]platformconnectoradapter.SealedRecord{id: record}}
	adapter := newAdapter(t, transport)
	_, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/"+id))
	if !errors.IsType[secrets.InvalidReferenceError](err) {
		t.Errorf("Resolve(tampered) err = %v, want InvalidReferenceError", err)
	}
}

func TestResolve_WrongKEKIsInvalid(t *testing.T) {
	t.Parallel()
	const id = "wrong-kek"
	// Seal under one KEK, unseal through an adapter whose Sealer holds a DIFFERENT KEK → GCM rejects.
	otherKEK := "0000000000000000000000000000000000000000000000000000000000000000"[:32]
	otherSealer, err := envelope.New(
		envelope.Config{KEK: secrets.Ref(kekReference), KEKVersion: 1},
		envelope.Deps{Secrets: secretstest.New(map[string]string{kekReference: otherKEK})},
	)
	if err != nil {
		t.Fatalf("envelope.New(other KEK): %v", err)
	}
	record := sealValue(t, newSealer(t), secretstest.SeededPlaintext) // sealed under the CANONICAL fake KEK
	transport := &fakeTransport{records: map[string]platformconnectoradapter.SealedRecord{id: record}}
	adapter, err := platformconnectoradapter.New(
		platformconnectoradapter.Config{},
		platformconnectoradapter.Deps{Loader: transport, Sealer: otherSealer},
	)
	if err != nil {
		t.Fatalf("New(other-KEK adapter): %v", err)
	}
	_, err = adapter.Resolve(context.Background(), secrets.Ref("eden://connector/"+id))
	if !errors.IsType[secrets.InvalidReferenceError](err) {
		t.Errorf("Resolve(wrong KEK) err = %v, want InvalidReferenceError", err)
	}
}
