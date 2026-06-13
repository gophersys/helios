package configuration_test

import (
	"sync"
	"testing"

	cfg "github.com/gophersys/libs/go/configuration"
	cfgtest "github.com/gophersys/libs/go/configuration/configurationtest"
)

// --- Zero Document ---

func TestZeroDocument_LookupMissesCleanly(t *testing.T) {
	var doc cfg.Document // zero value of the interface is nil; the contract's
	// "zero Document" refers to a constructed empty tree. The fake supplies it.
	if doc != nil {
		t.Skip("nil interface is not the zero-tree; covered by emptyDoc test")
	}
	empty := cfgtest.Doc(map[string]any{})
	if _, ok := empty.Lookup("anything"); ok {
		t.Fatal("empty Document Lookup returned ok == true, want false")
	}
	if _, ok := empty.Lookup(""); ok {
		// root of an empty tree: an object exists at root, but it is empty;
		// Lookup of the empty path may return the root object. We only require
		// it not panic — assert child miss instead.
		_ = ok
	}
}

// --- Lookup ---

func TestDocument_LookupScalar(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{
		"engine": map[string]any{"maxConcurrency": 8},
	})
	v, ok := doc.Lookup("engine.maxConcurrency")
	if !ok {
		t.Fatal("Lookup(engine.maxConcurrency) ok == false, want true")
	}
	n, diag := v.Int()
	if diag != nil {
		t.Fatalf("Int() diag = %+v, want nil", diag)
	}
	if n != 8 {
		t.Fatalf("Int() = %d, want 8", n)
	}
}

func TestDocument_LookupMissReturnsFalse(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{"a": 1})
	if _, ok := doc.Lookup("a.b.c"); ok {
		t.Fatal("Lookup of absent deep path ok == true, want false")
	}
	if _, ok := doc.Lookup("nope"); ok {
		t.Fatal("Lookup of absent key ok == true, want false")
	}
}

func TestDocument_LookupIntoArray(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{
		"engine": map[string]any{
			"models": []any{
				map[string]any{"auth": "tokenA"},
				map[string]any{"auth": "tokenB"},
			},
		},
	})
	v, ok := doc.Lookup("engine.models[1].auth")
	if !ok {
		t.Fatal("Lookup(engine.models[1].auth) ok == false, want true")
	}
	s, diag := v.String()
	if diag != nil {
		t.Fatalf("String() diag = %+v, want nil", diag)
	}
	if s != "tokenB" {
		t.Fatalf("String() = %q, want %q", s, "tokenB")
	}
}

func TestDocument_FormatAndOrigin(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{"a": 1},
		cfgtest.WithFormat(cfg.FormatTOML),
		cfgtest.WithOrigin("backend.toml"),
	)
	if doc.Format() != cfg.FormatTOML {
		t.Fatalf("Format() = %q, want %q", doc.Format(), cfg.FormatTOML)
	}
	o := doc.Origin()
	if o.Source != "backend.toml" {
		t.Fatalf("Origin().Source = %q, want %q", o.Source, "backend.toml")
	}
	if o.Line != 0 {
		t.Fatalf("Origin().Line = %d, want 0 (root position)", o.Line)
	}
}

// --- Value ---

func TestValue_FieldWalksObject(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{
		"engine": map[string]any{"name": "primary"},
	})
	v, ok := doc.Lookup("engine")
	if !ok {
		t.Fatal("Lookup(engine) ok == false")
	}
	f, ok := v.Field("name")
	if !ok {
		t.Fatal("Field(name) ok == false, want true")
	}
	s, diag := f.String()
	if diag != nil || s != "primary" {
		t.Fatalf("Field(name).String() = (%q, %v), want (primary, nil)", s, diag)
	}
	if _, ok := v.Field("missing"); ok {
		t.Fatal("Field(missing) ok == true, want false past the edge")
	}
}

func TestValue_Len(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{
		"items": []any{1, 2, 3},
	})
	v, _ := doc.Lookup("items")
	n, ok := v.Len()
	if !ok {
		t.Fatal("Len() ok == false on an array, want true")
	}
	if n != 3 {
		t.Fatalf("Len() = %d, want 3", n)
	}
	// Len on a non-array reports ok == false.
	scalar, _ := doc.Lookup("items[0]")
	if _, ok := scalar.Len(); ok {
		t.Fatal("Len() on a scalar ok == true, want false")
	}
}

func TestValue_AtCarriesPosition(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{
		"engine": map[string]any{"maxConcurrency": "oops"},
	},
		cfgtest.WithPosition("engine.maxConcurrency", cfg.Position{Source: "backend.yaml", Line: 14, Column: 7}),
	)
	v, _ := doc.Lookup("engine.maxConcurrency")
	at := v.At()
	if at.Source != "backend.yaml" || at.Line != 14 || at.Column != 7 {
		t.Fatalf("At() = %+v, want backend.yaml:14:7", at)
	}
}

// --- Total conversions: mismatch returns *Diagnostic stamped with At() ---

func TestValue_TotalConversion_IntMismatch(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{"x": "not-an-int"},
		cfgtest.WithPosition("x", cfg.Position{Source: "s.yaml", Line: 3, Column: 2}),
	)
	v, _ := doc.Lookup("x")
	n, diag := v.Int()
	if diag == nil {
		t.Fatal("Int() on a string returned nil *Diagnostic, want a mismatch diagnostic")
	}
	if n != 0 {
		t.Fatalf("Int() value on mismatch = %d, want 0 (type zero)", n)
	}
	if diag.At.Line != 3 || diag.At.Source != "s.yaml" {
		t.Fatalf("mismatch diag At = %+v, want s.yaml:3:_", diag.At)
	}
	if diag.Severity != cfg.SeverityError {
		t.Fatalf("mismatch diag Severity = %v, want SeverityError", diag.Severity)
	}
}

func TestValue_TotalConversion_BoolMismatch(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{"x": 5})
	v, _ := doc.Lookup("x")
	b, diag := v.Bool()
	if diag == nil {
		t.Fatal("Bool() on an int returned nil, want mismatch diagnostic")
	}
	if b != false {
		t.Fatalf("Bool() on mismatch = %v, want false", b)
	}
}

func TestValue_StringConversion_FromString(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{"x": "hello"})
	v, _ := doc.Lookup("x")
	s, diag := v.String()
	if diag != nil || s != "hello" {
		t.Fatalf("String() = (%q, %v), want (hello, nil)", s, diag)
	}
}

func TestValue_BoolConversion(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{"x": true})
	v, _ := doc.Lookup("x")
	b, diag := v.Bool()
	if diag != nil || b != true {
		t.Fatalf("Bool() = (%v, %v), want (true, nil)", b, diag)
	}
}

// --- Zero Value safety ---

func TestZeroValue_IsAbsent(t *testing.T) {
	// A miss yields a zero Value; the contract: zero Value conversions return
	// zero+*Diagnostic and Field/Len report ok == false. Obtain a zero value
	// via the fake's miss-path: Field past the edge returns (nil-ish, false),
	// but we exercise the documented zero Value semantics through an explicit
	// absent node: Lookup of an object's missing field via Field.
	doc := cfgtest.Doc(map[string]any{"obj": map[string]any{}})
	parent, _ := doc.Lookup("obj")
	v, ok := parent.Field("missing")
	if ok {
		t.Fatal("Field(missing) ok == true, want false")
	}
	// v is the zero/absent Value: every conversion is total and non-panicking.
	if _, diag := v.Int(); diag == nil {
		t.Fatal("absent Value.Int() returned nil diag, want mismatch")
	}
	if _, diag := v.String(); diag == nil {
		t.Fatal("absent Value.String() returned nil diag, want mismatch")
	}
	if _, diag := v.Bool(); diag == nil {
		t.Fatal("absent Value.Bool() returned nil diag, want mismatch")
	}
	if _, ok := v.Field("z"); ok {
		t.Fatal("absent Value.Field() ok == true, want false")
	}
	if _, ok := v.Len(); ok {
		t.Fatal("absent Value.Len() ok == true, want false")
	}
	// At() on an absent value must not panic.
	_ = v.At()
}

// --- Immutability / concurrency ---

func TestDocument_ConcurrentLookupRaceFree(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{
		"engine": map[string]any{
			"models": []any{
				map[string]any{"auth": "a"},
				map[string]any{"auth": "b"},
			},
			"maxConcurrency": 16,
		},
	})
	var wg sync.WaitGroup
	for i := 0; i < 64; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if v, ok := doc.Lookup("engine.maxConcurrency"); ok {
				_, _ = v.Int()
			}
			if v, ok := doc.Lookup("engine.models[1].auth"); ok {
				_, _ = v.String()
			}
		}()
	}
	wg.Wait()
}
