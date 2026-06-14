package vaultadapter_test

import (
	"context"
	"strings"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/vaultadapter"
)

// The `property` ctl.sh verb runs go test with RAPID_CHECKS set (default 1000 iterations/property,
// ADR-0020 dimension (a)); rapid reads it directly.

// drawMount / drawPath / drawKey draw the components of a well-formed vault Reference so every
// shape the parser accepts is exercised. They avoid '/' '#' inside a component so the drawn
// reference is unambiguous, and avoid whitespace so secrets.Ref accepts it.
func drawMount(rt *rapid.T) string {
	return rapid.StringMatching(`[a-z][a-z0-9-]{0,12}`).Draw(rt, "mount")
}

func drawPath(rt *rapid.T) string {
	return rapid.StringMatching(`[a-z0-9][a-z0-9/_-]{0,24}[a-z0-9]`).Draw(rt, "path")
}

func drawKey(rt *rapid.T) string {
	return rapid.StringMatching(`[A-Za-z0-9][A-Za-z0-9._-]{0,16}`).Draw(rt, "key")
}

// drawValue draws an arbitrary printable credential value.
func drawValue(rt *rapid.T) string {
	return rapid.StringMatching(`[ -~]{1,48}`).Draw(rt, "value")
}

// TestProperty_AnyWellFormedReferenceResolvesToItsSeededValue asserts the adapter's load-bearing
// mapping invariant over the whole reference shape space: for any (mount, path, key, value), a
// "vault://<mount>/<path>#<key>" reference seeded at the corresponding KV v2 api path resolves to
// EXACTLY that value, and the resolved Secret still redacts totally. This is the parse→apiPath→
// KV-unwrap→mint fingerprint property of dimension (a) — proven against the transport seam, not a
// mock of the contract (the value flows through the real adapter code).
func TestProperty_AnyWellFormedReferenceResolvesToItsSeededValue(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		mount := drawMount(rt)
		path := normalizePath(drawPath(rt))
		key := drawKey(rt)
		value := drawValue(rt)

		ref := secrets.Ref("vault://" + mount + "/" + path + "#" + key)
		apiPath := mount + "/data/" + path
		transport := &fakeTransport{kv: map[string]map[string]any{
			apiPath: kvEnvelope(map[string]any{key: value}),
		}}
		adapter := newAdapterTB(rt, transport)

		sec, err := adapter.Resolve(context.Background(), ref)
		if err != nil {
			rt.Fatalf("Resolve(%q -> %q) error = %v", ref, apiPath, err)
		}
		defer sec.Zeroize()

		got, uerr := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
		if uerr != nil {
			rt.Fatalf("Use1 error = %v", uerr)
		}
		if got != value {
			rt.Fatalf("resolved value = %q, want the seeded %q (ref %q -> apiPath %q)", got, value, ref, apiPath)
		}
		// Redaction is a property of the type: the resolved Secret never renders the value.
		if s := sec.String(); s != secrets.Redacted {
			rt.Fatalf("resolved Secret String() = %q, want Redacted", s)
		}
	})
}

// TestProperty_UnseededReferenceIsAlwaysNotFound asserts the negative: any well-formed reference
// whose KV path the transport does NOT hold resolves to a typed NotFoundError — never a panic, a
// wrong value, or a non-nil Secret. The store is empty, so every drawn reference must miss.
func TestProperty_UnseededReferenceIsAlwaysNotFound(t *testing.T) {
	t.Parallel()
	empty := &fakeTransport{kv: map[string]map[string]any{}}
	rapid.Check(t, func(rt *rapid.T) {
		mount := drawMount(rt)
		path := normalizePath(drawPath(rt))
		key := drawKey(rt)
		ref := secrets.Ref("vault://" + mount + "/" + path + "#" + key)

		adapter := newAdapterTB(rt, empty)
		sec, err := adapter.Resolve(context.Background(), ref)
		if sec != nil {
			rt.Fatalf("Resolve(%q) returned a non-nil Secret for an unseeded reference", ref)
		}
		if !is[secrets.NotFoundError](err) {
			rt.Fatalf("Resolve(%q) error = %v, want NotFoundError", ref, err)
		}
	})
}

// normalizePath collapses any "//" the path generator may produce (the parser Trims surrounding
// slashes but an INTERIOR "//" would change the api path) so the drawn path matches the seeded
// api path exactly. It also strips leading/trailing slashes the way parseReference does.
func normalizePath(p string) string {
	for strings.Contains(p, "//") {
		p = strings.ReplaceAll(p, "//", "/")
	}
	s := strings.Trim(p, "/")
	if s == "" {
		return "p"
	}
	return s
}

// fatalReporter is the minimal failure surface newAdapterTB needs, satisfied by BOTH *testing.T
// and *rapid.T — so the property body and the table tests build the adapter the same way.
type fatalReporter interface {
	Helper()
	Fatalf(format string, args ...any)
}

// newAdapterTB builds a ModeUserpass adapter over transport, failing through tb (a *testing.T or a
// *rapid.T). It is the construction the property body shares with the unit lane.
func newAdapterTB(tb fatalReporter, transport vaultadapter.Transport) *vaultadapter.Adapter {
	tb.Helper()
	adapter, err := vaultadapter.New(
		vaultadapter.Config{Address: "http://127.0.0.1:8200", Mode: vaultadapter.ModeUserpass},
		vaultadapter.Dependencies{Username: "eden", Password: "passw0rd", Transport: transport},
	)
	if err != nil {
		tb.Fatalf("vaultadapter.New(ModeUserpass) error = %v", err)
	}
	return adapter
}
