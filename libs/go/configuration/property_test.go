package configuration_test

import (
	"context"
	"encoding/json"
	"strconv"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/configurationtest"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS set in the process environment
// (default 1000 iterations/property, ADR-0020 dimension (a) threshold); rapid reads it directly.
// These properties exercise the configuration invariants that the example-based suite asserts at
// fixed points: parse→read round-trips over the whole scalar space, Merge overlay-wins/no-mutate
// over arbitrary key sets, Diagnostics value-semantics-on-copy, and Path construction round-trips.

func mustMarshalProp(rt *rapid.T, v any) []byte {
	body, err := json.Marshal(v)
	if err != nil {
		rt.Fatalf("fixture marshal failed: %v", err)
	}
	return body
}

//nolint:ireturn // configuration.Document is an interface fixed by contracts/configuration.md §2.
func mustParseProp(rt *rapid.T, p configuration.Parser, name string) configuration.Document {
	doc, diags, err := p.Parse(context.Background(), name)
	if err != nil {
		rt.Fatalf("Parse(%q) I/O err = %v, want nil", name, err)
	}
	if diags.HasError() {
		rt.Fatalf("clean source %q produced SeverityError diagnostics: %v", name, diags.All())
	}
	return doc
}

//nolint:ireturn // configuration.Parser is an interface fixed by contracts/configuration.md §2.
func newJSONParser(rt *rapid.T, src configuration.Source) configuration.Parser {
	p, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		rt.Fatalf("New err = %v", err)
	}
	return p
}

// TestProperty_JSONStringRoundTrip asserts the IR round-trip for the string axis: a string encoded
// into a JSON source, parsed at the edge, and read back via String() reproduces the original with
// no diagnostic; reading the same leaf as the WRONG type is total (zero + diagnostic, never a
// panic) and the diagnostic is stamped at the leaf's Position (ADR-0020 §a, rapid).
func TestProperty_JSONStringRoundTrip(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		key := rapid.StringMatching(`[a-z][a-z0-9_]{0,15}`).Draw(rt, "key")
		want := rapid.StringMatching(`[a-zA-Z0-9 _.@-]{0,32}`).Draw(rt, "value")

		src := configurationtest.Source{Files: map[string][]byte{"r.json": mustMarshalProp(rt, map[string]any{key: want})}}
		doc := mustParseProp(rt, newJSONParser(rt, src), "r.json")

		v, ok := doc.Lookup(configuration.Path(key))
		if !ok {
			rt.Fatalf("Lookup(%q) missed a present key", key)
		}
		got, d := v.String()
		if d != nil {
			rt.Fatalf("String() on a string leaf = diagnostic %v, want nil", d)
		}
		if got != want {
			rt.Fatalf("String() round-trip drifted: got %q want %q", got, want)
		}
		// Mismatch path: Int() on a string is total (0, diagnostic) stamped at the leaf.
		n, mismatch := v.Int()
		if mismatch == nil || n != 0 {
			rt.Fatalf("Int() on a string must be (0, diagnostic), got (%d, %v)", n, mismatch)
		}
		if mismatch.At != v.At() {
			rt.Fatalf("mismatch diagnostic At = %+v, want leaf At %+v", mismatch.At, v.At())
		}
	})
}

// TestProperty_JSONIntRoundTrip asserts the IR round-trip for the integer axis.
func TestProperty_JSONIntRoundTrip(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		key := rapid.StringMatching(`[a-z][a-z0-9_]{0,15}`).Draw(rt, "key")
		want := rapid.Int64Range(-1<<40, 1<<40).Draw(rt, "value")

		src := configurationtest.Source{Files: map[string][]byte{"r.json": mustMarshalProp(rt, map[string]any{key: want})}}
		doc := mustParseProp(rt, newJSONParser(rt, src), "r.json")

		v, ok := doc.Lookup(configuration.Path(key))
		if !ok {
			rt.Fatalf("Lookup(%q) missed a present key", key)
		}
		got, d := v.Int()
		if d != nil {
			rt.Fatalf("Int() on an int leaf = diagnostic %v, want nil", d)
		}
		if got != want {
			rt.Fatalf("Int() round-trip drifted: got %d want %d", got, want)
		}
		if b, mismatch := v.Bool(); mismatch == nil || b {
			rt.Fatalf("Bool() on an int must be (false, diagnostic), got (%v, %v)", b, mismatch)
		}
	})
}

// TestProperty_JSONBoolRoundTrip asserts the IR round-trip for the boolean axis.
func TestProperty_JSONBoolRoundTrip(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		key := rapid.StringMatching(`[a-z][a-z0-9_]{0,15}`).Draw(rt, "key")
		want := rapid.Bool().Draw(rt, "value")

		src := configurationtest.Source{Files: map[string][]byte{"r.json": mustMarshalProp(rt, map[string]any{key: want})}}
		doc := mustParseProp(rt, newJSONParser(rt, src), "r.json")

		v, ok := doc.Lookup(configuration.Path(key))
		if !ok {
			rt.Fatalf("Lookup(%q) missed a present key", key)
		}
		got, d := v.Bool()
		if d != nil {
			rt.Fatalf("Bool() on a bool leaf = diagnostic %v, want nil", d)
		}
		if got != want {
			rt.Fatalf("Bool() round-trip drifted: got %v want %v", got, want)
		}
		if s, mismatch := v.String(); mismatch == nil || s != "" {
			rt.Fatalf("String() on a bool must be (\"\", diagnostic), got (%q, %v)", s, mismatch)
		}
	})
}

// TestProperty_MergeOverlayWinsAndNoMutate asserts the stage-overlay fold invariant over an
// arbitrary set of integer keys: every overlay key wins per Path, every base-only key survives,
// and NEITHER input Document is mutated by the fold (the inputs-are-frozen guarantee, ADR-0020 §a).
func TestProperty_MergeOverlayWinsAndNoMutate(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		keys := rapid.SliceOfNDistinct(
			rapid.StringMatching(`[a-z][a-z0-9]{0,7}`), 1, 6,
			func(s string) string { return s },
		).Draw(rt, "keys")

		base := map[string]any{}
		overlay := map[string]any{}
		overlaid := map[string]bool{}
		for i, k := range keys {
			base[k] = int64(i)
			if rapid.Bool().Draw(rt, "overlay_"+k) {
				overlay[k] = int64(1000 + i)
				overlaid[k] = true
			}
		}

		src := configurationtest.Source{Files: map[string][]byte{
			"base.json":    mustMarshalProp(rt, base),
			"overlay.json": mustMarshalProp(rt, overlay),
		}}
		p := newJSONParser(rt, src)
		baseDoc := mustParseProp(rt, p, "base.json")
		overlayDoc := mustParseProp(rt, p, "overlay.json")

		merged, _, err := p.Merge(context.Background(), baseDoc, overlayDoc)
		if err != nil {
			rt.Fatalf("Merge err = %v", err)
		}

		assertMergeWinners(rt, merged, keys, overlaid)

		// Inputs not mutated: base still reads its own values after the fold.
		for i, k := range keys {
			bv, _ := baseDoc.Lookup(configuration.Path(k))
			if n, _ := bv.Int(); n != int64(i) {
				rt.Fatalf("Merge mutated base at %q: got %d want %d", k, n, i)
			}
		}
	})
}

// assertMergeWinners checks each merged key resolves to the overlay value where overlaid, else the
// base value (factored out to keep the property body under the cognitive-complexity floor).
func assertMergeWinners(rt *rapid.T, merged configuration.Document, keys []string, overlaid map[string]bool) {
	for i, k := range keys {
		v, ok := merged.Lookup(configuration.Path(k))
		if !ok {
			rt.Fatalf("merged dropped key %q", k)
		}
		n, d := v.Int()
		if d != nil {
			rt.Fatalf("merged %q Int() diagnostic = %v", k, d)
		}
		want := int64(i)
		if overlaid[k] {
			want = int64(1000 + i)
		}
		if n != want {
			rt.Fatalf("merge winner wrong at %q: got %d want %d", k, n, want)
		}
	}
}

// TestProperty_DiagnosticsValueSemanticsOnCopy asserts the Diagnostics copy invariant: appending
// to a COPY of a Diagnostics never reaches back into the original's finding set, for an arbitrary
// pair of finding counts (the value-semantics contract — appending to a copy must not alias).
func TestProperty_DiagnosticsValueSemanticsOnCopy(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		nBase := rapid.IntRange(0, 8).Draw(rt, "nBase")
		nExtra := rapid.IntRange(1, 8).Draw(rt, "nExtra")

		var original configuration.Diagnostics
		for i := range nBase {
			original.Append(configuration.Diagnostic{
				Severity: configuration.SeverityWarning,
				Path:     configuration.Path("k" + strconv.Itoa(i)),
				Summary:  "base",
			})
		}
		clone := original
		for i := range nExtra {
			clone.Append(configuration.Diagnostic{
				Severity: configuration.SeverityError,
				Path:     configuration.Path("x" + strconv.Itoa(i)),
				Summary:  "extra",
			})
		}
		if got := len(original.All()); got != nBase {
			rt.Fatalf("append to copy mutated original: original len = %d, want %d", got, nBase)
		}
		if got := len(clone.All()); got != nBase+nExtra {
			rt.Fatalf("copy len = %d, want %d", got, nBase+nExtra)
		}
		if nBase == 0 && original.HasError() {
			rt.Fatal("empty original must not report HasError after copy was appended to")
		}
	})
}

// TestProperty_PathRoundTrip asserts Path construction is a faithful, total round-trip: building a
// dotted/indexed Path with Child/Index and resolving it back through Lookup reaches exactly the
// value placed there, for arbitrary nesting (the join-key invariant — ADR-0020 §a).
func TestProperty_PathRoundTrip(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		key := rapid.StringMatching(`[a-z][a-z0-9]{0,7}`).Draw(rt, "key")
		idx := rapid.IntRange(0, 4).Draw(rt, "idx")
		leaf := rapid.StringMatching(`[a-z][a-z0-9]{0,7}`).Draw(rt, "leaf")
		want := rapid.StringMatching(`[a-zA-Z0-9 ._-]{0,16}`).Draw(rt, "want")

		// Build {key: [ ...idx-1 fillers..., {leaf: want} ]}.
		arr := make([]any, idx+1)
		for i := range arr {
			arr[i] = map[string]any{leaf: "filler" + strconv.Itoa(i)}
		}
		arr[idx] = map[string]any{leaf: want}
		doc := configurationtest.Doc(map[string]any{key: arr})

		path := configuration.Path("").Child(key).Index(idx).Child(leaf)
		v, ok := doc.Lookup(path)
		if !ok {
			rt.Fatalf("Lookup(%q) missed the constructed leaf", path)
		}
		got, d := v.String()
		if d != nil {
			rt.Fatalf("Lookup(%q) String() diagnostic = %v", path, d)
		}
		if got != want {
			rt.Fatalf("Path round-trip drifted at %q: got %q want %q", path, got, want)
		}
	})
}
