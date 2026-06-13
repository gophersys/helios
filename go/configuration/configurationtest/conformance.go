package configurationtest

import (
	"context"
	"errors"
	"testing"

	"github.com/gophersys/libs/go/configuration"
)

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
func NewParser(c configuration.Config, d configuration.Deps) (configuration.Parser, error) {
	return configuration.New(c, d)
}

// Run drives any configuration.Parser produced by newParser through the
// substitutability properties. The real adapter and configurationtest.Parser
// must both pass identically (08 §2).
func Run(t *testing.T, newParser func(configuration.Config, configuration.Deps) (configuration.Parser, error)) {
	t.Helper()

	t.Run("PurityOfNew", func(t *testing.T) {
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
	})

	t.Run("MalformedConfigIsTheOnlyNewError", func(t *testing.T) {
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
	})

	t.Run("StrictByDefault", func(t *testing.T) {
		src := Source{Files: map[string][]byte{"d.json": []byte(`{"a":1,"a":2}`)}}
		strict, _ := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
		_, diags, err := strict.Parse(context.Background(), "d.json")
		if err != nil {
			t.Fatalf("strict Parse err = %v, want nil", err)
		}
		if !diags.HasError() {
			t.Fatal("strict (zero Config) must flag duplicate keys as SeverityError")
		}

		lax, _ := newParser(configuration.Config{Format: configuration.FormatJSON, AllowUnknownKeys: true}, configuration.Deps{Source: src})
		_, laxDiags, _ := lax.Parse(context.Background(), "d.json")
		if laxDiags.HasError() {
			t.Fatal("AllowUnknownKeys must downgrade duplicate-key findings to Warning")
		}
	})

	t.Run("DiagnosticsAccumulate", func(t *testing.T) {
		src := Source{Files: map[string][]byte{"m.json": []byte(`{"a":1,"a":2,"b":1,"b":2}`)}}
		p, _ := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
		_, diags, _ := p.Parse(context.Background(), "m.json")
		n := 0
		for _, dg := range diags.All() {
			if dg.Severity == configuration.SeverityError {
				n++
			}
		}
		if n < 2 {
			t.Fatalf("accumulate-all: got %d errors in one Parse, want >= 2", n)
		}
	})

	t.Run("ErrorChannelDiscipline", func(t *testing.T) {
		// I/O failure -> *ParseError, Unwrap reaching the cause.
		cause := errors.New("device error")
		failSrc := Source{Err: map[string]error{"x.json": cause}}
		p, _ := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: failSrc})
		_, _, err := p.Parse(context.Background(), "x.json")
		var pe *configuration.ParseError
		if !errors.As(err, &pe) {
			t.Fatalf("read failure err = %T, want *ParseError", err)
		}
		if !errors.Is(err, cause) {
			t.Fatal("*ParseError must Unwrap to the Source cause")
		}

		// Wrong-but-readable -> (doc, diags, nil) with HasError.
		badSrc := Source{Files: map[string][]byte{"bad.json": []byte(`{"a":}`)}}
		p2, _ := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: badSrc})
		_, diags, err := p2.Parse(context.Background(), "bad.json")
		if err != nil {
			t.Fatalf("readable-but-wrong source err = %v, want nil", err)
		}
		if !diags.HasError() {
			t.Fatal("readable-but-wrong source must report a SeverityError diagnostic")
		}
	})

	t.Run("PositionTruthfulness", func(t *testing.T) {
		src := Source{Files: map[string][]byte{"p.env": []byte("A=1\nB=2\n")}}
		p, _ := newParser(configuration.Config{Format: configuration.FormatEnv}, configuration.Deps{Source: src})
		doc, _, _ := p.Parse(context.Background(), "p.env")
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
	})

	t.Run("TotalConversions", func(t *testing.T) {
		src := Source{Files: map[string][]byte{"t.json": []byte(`{"x":"hello"}`)}}
		p, _ := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
		doc, _, _ := p.Parse(context.Background(), "t.json")
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
	})

	t.Run("ZeroValueSafety", func(t *testing.T) {
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
	})

	t.Run("MergeSemantics", func(t *testing.T) {
		src := Source{Files: map[string][]byte{
			"base.json":    []byte(`{"k":1,"only":"base"}`),
			"overlay.json": []byte(`{"k":2}`),
		}}
		p, _ := newParser(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
		base, _, _ := p.Parse(context.Background(), "base.json")
		overlay, _, _ := p.Parse(context.Background(), "overlay.json")

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
	})
}

// panicSource panics on Read, proving New performs no I/O.
type panicSource struct{}

func (panicSource) Read(context.Context, string) ([]byte, error) {
	panic("conformance: New must not read Source")
}
