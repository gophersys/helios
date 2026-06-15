package configurationtest

import (
	"context"
	"errors"
	"testing"

	"github.com/gophersys/libs/go/configuration"
)

// errDeviceFailure is a static sentinel standing in for an I/O fault from a
// Source, used by the error-channel conformance property. A package-level
// sentinel (rather than an inline errors.New) keeps the err113 "no dynamic
// errors" discipline intact even on this exercise path.
var errDeviceFailure = errors.New("device error")

// NewParser adapts the canonical fakes to the (Config, Deps) -> (Parser, error)
// constructor shape the conformance suite drives. It returns a Parser that
// honors the SAME observable contract as the real configuration.New across the
// substitutability properties (08 §2): New purity/validation, the read-failure
// error channel, accumulate-all diagnostics, total/zero-value conversions, and
// position-preserving Merge.
//
// The adapter is backed by the same decoding engine the real parser uses,
// reading the injected Deps.Source — this is deliberate: the conformance suite
// proves the fakes' TYPES (Source, Document, Diagnostics, ParseError) and error
// discipline interoperate with the engine identically to the real path. The
// hand-scripted Parser struct is the separate fake for consumer-side tests
// (stage a doc/diag/error per name) and is exercised directly elsewhere.
//
// It returns the configuration.Parser INTERFACE by contract
// (contracts/configuration.md §2): this adapter exists precisely to feed a
// Parser into RunParserSuite, and it forwards configuration.New's error verbatim so the
// conformance suite observes the real constructor's error channel unaltered
// (wrapping it here would hide the *ParseError discipline under test).
//
//nolint:ireturn,wrapcheck // Parser interface + verbatim New error, both fixed by contracts/configuration.md §2; see doc above.
func NewParser(c configuration.Config, d configuration.Deps) (configuration.Parser, error) {
	return configuration.New(c, d)
}

// RunParserSuite drives any configuration.Parser produced by newParser through
// the substitutability properties. The real adapter and configurationtest.Parser
// must both pass identically (08 §2).
func RunParserSuite(t *testing.T, newParser parserFactory) {
	t.Helper()
	t.Run("PurityOfNew", func(t *testing.T) { assertPurityOfNew(t, newParser) })
	t.Run("MalformedConfigIsTheOnlyNewError", func(t *testing.T) { assertMalformedConfigIsOnlyNewError(t, newParser) })
	t.Run("StrictByDefault", func(t *testing.T) { assertStrictByDefault(t, newParser) })
	t.Run("DiagnosticsAccumulate", func(t *testing.T) { assertDiagnosticsAccumulate(t, newParser) })
	t.Run("ErrorChannelDiscipline", func(t *testing.T) { assertErrorChannelDiscipline(t, newParser) })
	t.Run("PositionTruthfulness", func(t *testing.T) { assertPositionTruthfulness(t, newParser) })
	t.Run("TotalConversions", func(t *testing.T) { assertTotalConversions(t, newParser) })
	t.Run("ZeroValueSafety", func(t *testing.T) { assertZeroValueSafety(t) })
	t.Run("MergeSemantics", func(t *testing.T) { assertMergeSemantics(t, newParser) })
	t.Run("NestedDuplicatePathIsFull", func(t *testing.T) { assertNestedDuplicatePathIsFull(t, newParser) })
	t.Run("CrossFormatValueEquivalence", func(t *testing.T) { assertCrossFormatValueEquivalence(t, newParser) })
}

// formatFixture pins one logical configuration expressed in each of the four
// Formats, so a single conformance property can assert decoder uniformity
// (a contract no single-format two-binding can see — it only proves fake≡real
// for ONE Format at a time, never format-A≡format-B for the same value).
type formatFixture struct {
	format configuration.Format
	name   string
	body   string
}

// assertNestedDuplicatePathIsFull pins the cross-decoder Path contract: a
// duplicate key NESTED under a parent must be reported at its FULL dotted Path
// (engine.name), never a root-relative bare key (name). Every Format's decoder
// is held to it, so a decoder that emits a parent-losing Path fails the suite.
func assertNestedDuplicatePathIsFull(t *testing.T, newParser parserFactory) {
	t.Helper()
	const wantPath = configuration.Path("engine.name")
	fixtures := []formatFixture{
		{configuration.FormatJSON, "dup.json", `{"engine":{"name":1,"name":2}}`},
		{configuration.FormatYAML, "dup.yaml", "engine:\n  name: 1\n  name: 2\n"},
		{configuration.FormatTOML, "dup.toml", "[engine]\nname = 1\nname = 2\n"},
		{configuration.FormatEnv, "dup.env", "engine.name=1\nengine.name=2\n"},
	}
	for _, fx := range fixtures {
		t.Run(string(fx.format), func(t *testing.T) {
			src := Source{Files: map[string][]byte{fx.name: []byte(fx.body)}}
			p, err := newParser(configuration.Config{Format: fx.format}, configuration.Deps{Source: src})
			if err != nil {
				t.Fatalf("New(%s) err = %v, want nil", fx.format, err)
			}
			_, diags, err := p.Parse(context.Background(), fx.name)
			if err != nil {
				t.Fatalf("Parse(%s) err = %v, want nil", fx.format, err)
			}
			var dup *configuration.Diagnostic
			for _, dg := range diags.All() {
				if dg.Severity == configuration.SeverityError && dg.Path == wantPath {
					d := dg
					dup = &d
					break
				}
			}
			if dup == nil {
				t.Fatalf("%s: no duplicate-key SeverityError at full Path %q; got %+v",
					fx.format, wantPath, pathsOf(diags))
			}
		})
	}
}

// assertCrossFormatValueEquivalence pins decoder uniformity: the SAME logical
// value at the SAME Path, expressed in each Format (including a surrounding
// quote pair), must resolve to the SAME string Value across all four decoders.
// This is the only layer that can catch a per-decoder value divergence such as
// env taking a quoted value verbatim while YAML/TOML strip the quotes.
func assertCrossFormatValueEquivalence(t *testing.T, newParser parserFactory) {
	t.Helper()
	const wantValue = "prod"
	const path = configuration.Path("engine.name")
	fixtures := []formatFixture{
		{configuration.FormatJSON, "eq.json", `{"engine":{"name":"prod"}}`},
		{configuration.FormatYAML, "eq.yaml", "engine:\n  name: \"prod\"\n"},
		{configuration.FormatTOML, "eq.toml", "[engine]\nname = \"prod\"\n"},
		{configuration.FormatEnv, "eq.env", "engine.name=\"prod\"\n"},
	}
	for _, fx := range fixtures {
		t.Run(string(fx.format), func(t *testing.T) {
			src := Source{Files: map[string][]byte{fx.name: []byte(fx.body)}}
			p, err := newParser(configuration.Config{Format: fx.format}, configuration.Deps{Source: src})
			if err != nil {
				t.Fatalf("New(%s) err = %v, want nil", fx.format, err)
			}
			doc, diags, err := p.Parse(context.Background(), fx.name)
			if err != nil {
				t.Fatalf("Parse(%s) err = %v, want nil", fx.format, err)
			}
			if diags.HasError() {
				t.Fatalf("%s: clean fixture produced a SeverityError: %+v", fx.format, pathsOf(diags))
			}
			v, ok := doc.Lookup(path)
			if !ok {
				t.Fatalf("%s: Lookup(%q) ok == false", fx.format, path)
			}
			got, d := v.String()
			if d != nil {
				t.Fatalf("%s: String() at %q returned a mismatch Diagnostic %+v, want a string", fx.format, path, d)
			}
			if got != wantValue {
				t.Fatalf("%s: %q resolved to %q, want %q (decoders diverged — a quoted scalar must strip identically)",
					fx.format, path, got, wantValue)
			}
		})
	}
}

// pathsOf renders the Paths of every finding for a readable assertion failure.
func pathsOf(d configuration.Diagnostics) []configuration.Path {
	all := d.All()
	out := make([]configuration.Path, 0, len(all))
	for _, dg := range all {
		out = append(out, dg.Path)
	}
	return out
}

// parserFactory is the constructor shape every conformance property drives.
type parserFactory func(configuration.Config, configuration.Deps) (configuration.Parser, error)

func assertPurityOfNew(t *testing.T, newParser parserFactory) {
	t.Helper()
	// New must not read Source: a panicking Source must not panic New.
	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("New panicked, must perform no I/O: %v", r)
		}
	}()
	p, err := newParser(
		configuration.Config{Format: configuration.FormatJSON},
		configuration.Deps{Source: panicSource{}},
	)
	if err != nil {
		t.Fatalf("New with valid Config err = %v, want nil", err)
	}
	if p == nil {
		t.Fatal("New returned nil Parser")
	}
}

func assertMalformedConfigIsOnlyNewError(t *testing.T, newParser parserFactory) {
	t.Helper()
	if _, err := newParser(
		configuration.Config{Format: configuration.Format("xml")},
		configuration.Deps{Source: Source{}},
	); err == nil {
		t.Fatal("unknown Format must be a New error")
	}
	if _, err := newParser(
		configuration.Config{Format: configuration.FormatJSON, MaxSourceBytes: -1},
		configuration.Deps{Source: Source{}},
	); err == nil {
		t.Fatal("negative MaxSourceBytes must be a New error")
	}
	if _, err := newParser(
		configuration.Config{Format: configuration.FormatJSON},
		configuration.Deps{Source: Source{}},
	); err != nil {
		t.Fatalf("valid Config must NOT be a New error: %v", err)
	}
}

func assertStrictByDefault(t *testing.T, newParser parserFactory) {
	t.Helper()
	src := Source{Files: map[string][]byte{"d.json": []byte(`{"a":1,"a":2}`)}}
	strict, err := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New(strict) err = %v, want nil", err)
	}
	_, diags, err := strict.Parse(context.Background(), "d.json")
	if err != nil {
		t.Fatalf("strict Parse err = %v, want nil", err)
	}
	if !diags.HasError() {
		t.Fatal("strict (zero Config) must flag duplicate keys as SeverityError")
	}

	lax, err := newParser(configuration.Config{Format: configuration.FormatJSON, AllowUnknownKeys: true}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New(lax) err = %v, want nil", err)
	}
	_, laxDiags, err := lax.Parse(context.Background(), "d.json")
	if err != nil {
		t.Fatalf("lax Parse err = %v, want nil", err)
	}
	if laxDiags.HasError() {
		t.Fatal("AllowUnknownKeys must downgrade duplicate-key findings to Warning")
	}
}

func assertDiagnosticsAccumulate(t *testing.T, newParser parserFactory) {
	t.Helper()
	src := Source{Files: map[string][]byte{"m.json": []byte(`{"a":1,"a":2,"b":1,"b":2}`)}}
	p, err := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v, want nil", err)
	}
	_, diags, err := p.Parse(context.Background(), "m.json")
	if err != nil {
		t.Fatalf("Parse err = %v, want nil", err)
	}
	n := 0
	for _, dg := range diags.All() {
		if dg.Severity == configuration.SeverityError {
			n++
		}
	}
	if n < 2 {
		t.Fatalf("accumulate-all: got %d errors in one Parse, want >= 2", n)
	}
}

func assertErrorChannelDiscipline(t *testing.T, newParser parserFactory) {
	t.Helper()
	// I/O failure -> *ParseError, Unwrap reaching the cause.
	failSrc := Source{Err: map[string]error{"x.json": errDeviceFailure}}
	p, err := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: failSrc})
	if err != nil {
		t.Fatalf("New err = %v, want nil", err)
	}
	_, _, err = p.Parse(context.Background(), "x.json")
	var pe *configuration.ParseError
	if !errors.As(err, &pe) {
		t.Fatalf("read failure err = %T, want *ParseError", err)
	}
	if !errors.Is(err, errDeviceFailure) {
		t.Fatal("*ParseError must Unwrap to the Source cause")
	}

	// Wrong-but-readable -> (doc, diags, nil) with HasError.
	badSrc := Source{Files: map[string][]byte{"bad.json": []byte(`{"a":}`)}}
	p2, err := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: badSrc})
	if err != nil {
		t.Fatalf("New err = %v, want nil", err)
	}
	_, diags, err := p2.Parse(context.Background(), "bad.json")
	if err != nil {
		t.Fatalf("readable-but-wrong source err = %v, want nil", err)
	}
	if !diags.HasError() {
		t.Fatal("readable-but-wrong source must report a SeverityError diagnostic")
	}
}

func assertPositionTruthfulness(t *testing.T, newParser parserFactory) {
	t.Helper()
	src := Source{Files: map[string][]byte{"p.env": []byte("A=1\nB=2\n")}}
	p, err := newParser(configuration.Config{Format: configuration.FormatEnv}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v, want nil", err)
	}
	doc, _, err := p.Parse(context.Background(), "p.env")
	if err != nil {
		t.Fatalf("Parse err = %v, want nil", err)
	}
	v, ok := doc.Lookup("B")
	if !ok {
		t.Fatal("Lookup(B) ok == false")
	}
	if v.At().Line == 0 {
		t.Fatal("parse-derived finding must carry a non-zero Position line")
	}
	if v.At().Line != 2 {
		t.Fatalf("B At().Line = %d, want 2 (truthful)", v.At().Line)
	}
}

func assertTotalConversions(t *testing.T, newParser parserFactory) {
	t.Helper()
	src := Source{Files: map[string][]byte{"t.json": []byte(`{"x":"hello"}`)}}
	p, err := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v, want nil", err)
	}
	doc, _, err := p.Parse(context.Background(), "t.json")
	if err != nil {
		t.Fatalf("Parse err = %v, want nil", err)
	}
	v, _ := doc.Lookup("x")
	n, diag := v.Int()
	if diag == nil {
		t.Fatal("Int() on a string must return a *Diagnostic, not a Go error")
	}
	if n != 0 {
		t.Fatalf("mismatch Int() value = %d, want 0", n)
	}
	if diag.At != v.At() {
		t.Fatalf("mismatch diag At = %+v, want the leaf At %+v", diag.At, v.At())
	}
}

func assertZeroValueSafety(t *testing.T) {
	t.Helper()
	// Zero Document Lookups miss cleanly; zero Value conversions are total.
	empty := Doc(map[string]any{})
	if _, ok := empty.Lookup("nope"); ok {
		t.Fatal("empty Document Lookup must miss")
	}
	parent := Doc(map[string]any{"o": map[string]any{}})
	obj, _ := parent.Lookup("o")
	absent, ok := obj.Field("missing")
	if ok {
		t.Fatal("Field past the edge must report ok == false")
	}
	if _, diag := absent.Int(); diag == nil {
		t.Fatal("absent Value.Int() must return a *Diagnostic")
	}
	if _, ok := absent.Len(); ok {
		t.Fatal("absent Value.Len() must report ok == false")
	}
	_ = absent.At() // must not panic
}

func assertMergeSemantics(t *testing.T, newParser parserFactory) {
	t.Helper()
	src := Source{Files: map[string][]byte{
		"base.json":    []byte(`{"k":1,"only":"base"}`),
		"overlay.json": []byte(`{"k":2}`),
	}}
	p, err := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v, want nil", err)
	}
	base, _, err := p.Parse(context.Background(), "base.json")
	if err != nil {
		t.Fatalf("Parse(base) err = %v, want nil", err)
	}
	overlay, _, err := p.Parse(context.Background(), "overlay.json")
	if err != nil {
		t.Fatalf("Parse(overlay) err = %v, want nil", err)
	}

	merged, _, err := p.Merge(context.Background(), base, overlay)
	if err != nil {
		t.Fatalf("Merge err = %v", err)
	}
	v, ok := merged.Lookup("k")
	if !ok {
		t.Fatal("merged Lookup(k) ok == false")
	}
	if n, _ := v.Int(); n != 2 {
		t.Fatalf("overlay must win: k = %d, want 2", n)
	}
	if _, ok := merged.Lookup("only"); !ok {
		t.Fatal("base-only key must survive merge")
	}

	// Inputs not mutated.
	bv, _ := base.Lookup("k")
	if n, _ := bv.Int(); n != 1 {
		t.Fatalf("Merge mutated base: k = %d, want 1", n)
	}
}

// panicSource panics on Read, proving New performs no I/O.
type panicSource struct{}

func (panicSource) Read(context.Context, string) ([]byte, error) {
	panic("conformance: New must not read Source")
}
