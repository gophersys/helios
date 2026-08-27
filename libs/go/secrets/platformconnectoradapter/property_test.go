package platformconnectoradapter_test

import (
	"context"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/platformconnectoradapter"
)

// The `property` ctl.sh verb runs go test with RAPID_CHECKS set (default 1000 iterations/property,
// ADR-0020 dimension (a)); rapid reads it directly.

// drawID draws a well-formed connector id (a segment with no '/' or '#', non-empty, whitespace-free so
// secrets.Ref accepts it).
func drawID(rt *rapid.T) string {
	return rapid.StringMatching(`[A-Za-z0-9][A-Za-z0-9._-]{0,32}`).Draw(rt, "id")
}

// drawValue draws an arbitrary printable credential value.
func drawValue(rt *rapid.T) string {
	return rapid.StringMatching(`[ -~]{1,64}`).Draw(rt, "value")
}

// TestProperty_AnySealedConnectorResolvesToItsValue asserts the adapter's load-bearing round-trip over
// the whole (id, value) space: for any connector id sealed to any value, "eden://connector/<id>"
// resolves — through the REAL envelope crypto — to EXACTLY that value, and the resolved Secret still
// redacts totally. This is the parse → load → Unseal → mint fingerprint property of dimension (a),
// proven against the transport seam + the real cipher (the value flows through the real adapter code).
func TestProperty_AnySealedConnectorResolvesToItsValue(t *testing.T) {
	t.Parallel()
	sealer := newSealer(t)
	rapid.Check(t, func(rt *rapid.T) {
		id := drawID(rt)
		value := drawValue(rt)

		transport := &fakeTransport{records: map[string]platformconnectoradapter.SealedRecord{
			id: sealValue(rt, sealer, value),
		}}
		adapter := newAdapter(rt, transport)

		sec, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/"+id))
		if err != nil {
			rt.Fatalf("Resolve(eden://connector/%s) err = %v", id, err)
		}
		defer sec.Zeroize()

		got, uerr := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
		if uerr != nil {
			rt.Fatalf("Use1 err = %v", uerr)
		}
		if got != value {
			rt.Fatalf("resolved value = %q, want the sealed %q (id %q)", got, value, id)
		}
		if s := sec.String(); s != secrets.Redacted {
			rt.Fatalf("resolved Secret String() = %q, want Redacted", s)
		}
	})
}

// TestProperty_UnseededConnectorIsAlwaysNotFound asserts the negative: any well-formed connector id the
// transport does NOT hold resolves to a typed NotFoundError — never a panic, a wrong value, or a
// non-nil Secret. The store is empty, so every drawn id must miss.
func TestProperty_UnseededConnectorIsAlwaysNotFound(t *testing.T) {
	t.Parallel()
	empty := &fakeTransport{records: map[string]platformconnectoradapter.SealedRecord{}}
	adapter := newAdapter(t, empty)
	rapid.Check(t, func(rt *rapid.T) {
		id := drawID(rt)
		sec, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/"+id))
		if sec != nil {
			rt.Fatalf("Resolve(%q) returned a non-nil Secret for an unseeded id", id)
		}
		if !errors.IsType[secrets.NotFoundError](err) {
			rt.Fatalf("Resolve(%q) err = %v, want NotFoundError", id, err)
		}
	})
}
