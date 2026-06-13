package configuration_test

import (
	"context"
	"testing"

	cfg "github.com/gophersys/libs/go/configuration"
	cfgtest "github.com/gophersys/libs/go/configuration/configurationtest"
)

func parse(t *testing.T, format cfg.Format, name, body string) (cfg.Document, cfg.Diagnostics) {
	t.Helper()
	src := cfgtest.Source{Files: map[string][]byte{name: []byte(body)}}
	p, err := cfg.New(cfg.Config{Format: format}, cfg.Deps{Source: src})
	if err != nil {
		t.Fatalf("New(%s) err = %v", format, err)
	}
	doc, diags, err := p.Parse(context.Background(), name)
	if err != nil {
		t.Fatalf("Parse err = %v", err)
	}
	return doc, diags
}

// --- YAML subset ---

func TestYAML_NestedMappingAndScalars(t *testing.T) {
	doc, diags := parse(t, cfg.FormatYAML, "c.yaml",
		"engine:\n  maxConcurrency: 8\n  name: \"primary\"\n  enabled: true\n  ratio: 1.5\n# trailing comment\n")
	if diags.HasError() {
		t.Fatalf("clean YAML had errors: %v", summaries(diags.All()))
	}
	v, ok := doc.Lookup("engine.maxConcurrency")
	if !ok {
		t.Fatal("Lookup(engine.maxConcurrency) ok == false")
	}
	if n, d := v.Int(); d != nil || n != 8 {
		t.Fatalf("maxConcurrency = (%d,%v), want (8,nil)", n, d)
	}
	nm, _ := doc.Lookup("engine.name")
	if s, _ := nm.String(); s != "primary" {
		t.Fatalf("name = %q, want primary (quotes stripped)", s)
	}
	en, _ := doc.Lookup("engine.enabled")
	if b, d := en.Bool(); d != nil || !b {
		t.Fatalf("enabled = (%v,%v), want (true,nil)", b, d)
	}
	if v.At().Line != 2 {
		t.Fatalf("maxConcurrency At().Line = %d, want 2", v.At().Line)
	}
}

func TestYAML_BlockSequenceIsDiagnostic(t *testing.T) {
	_, diags := parse(t, cfg.FormatYAML, "s.yaml", "items:\n  - a\n  - b\n")
	if !diags.HasError() {
		t.Fatal("unsupported YAML block sequence must be a SeverityError, not a panic")
	}
}

func TestYAML_MalformedLineIsDiagnostic(t *testing.T) {
	_, diags := parse(t, cfg.FormatYAML, "m.yaml", "no colon here\n")
	if !diags.HasError() {
		t.Fatal("malformed YAML line must be a SeverityError")
	}
}

func TestYAML_DuplicateKeyStrict(t *testing.T) {
	_, diags := parse(t, cfg.FormatYAML, "d.yaml", "a: 1\na: 2\n")
	if !diags.HasError() {
		t.Fatal("duplicate YAML key must be SeverityError under strict default")
	}
}

// --- TOML subset ---

func TestTOML_TablesAndScalars(t *testing.T) {
	doc, diags := parse(t, cfg.FormatTOML, "c.toml",
		"name = \"root\"\n[engine]\nmaxConcurrency = 8\nenabled = true\nratio = 2.5\n[engine.nested]\nkey = \"deep\"\n")
	if diags.HasError() {
		t.Fatalf("clean TOML had errors: %v", summaries(diags.All()))
	}
	if v, ok := doc.Lookup("engine.maxConcurrency"); !ok {
		t.Fatal("Lookup(engine.maxConcurrency) ok == false")
	} else if n, _ := v.Int(); n != 8 {
		t.Fatalf("maxConcurrency = %d, want 8", n)
	}
	if v, ok := doc.Lookup("engine.nested.key"); !ok {
		t.Fatal("dotted table [engine.nested] did not nest")
	} else if s, _ := v.String(); s != "deep" {
		t.Fatalf("nested.key = %q, want deep", s)
	}
	if v, ok := doc.Lookup("name"); !ok {
		t.Fatal("top-level key lost")
	} else if s, _ := v.String(); s != "root" {
		t.Fatalf("name = %q, want root", s)
	}
}

func TestTOML_ArrayOfTablesIsDiagnostic(t *testing.T) {
	_, diags := parse(t, cfg.FormatTOML, "a.toml", "[[products]]\nname = \"x\"\n")
	if !diags.HasError() {
		t.Fatal("unsupported [[array-of-tables]] must be a SeverityError, not a panic")
	}
}

func TestTOML_MalformedHeaderIsDiagnostic(t *testing.T) {
	_, diags := parse(t, cfg.FormatTOML, "h.toml", "[unterminated\n")
	if !diags.HasError() {
		t.Fatal("malformed TOML table header must be a SeverityError")
	}
}

func TestTOML_DuplicateKeyStrict(t *testing.T) {
	_, diags := parse(t, cfg.FormatTOML, "d.toml", "a = 1\na = 2\n")
	if !diags.HasError() {
		t.Fatal("duplicate TOML key must be SeverityError under strict default")
	}
}

// --- JSON arrays, floats, nulls ---

func TestJSON_ArrayLenAndIndexedReads(t *testing.T) {
	doc, diags := parse(t, cfg.FormatJSON, "a.json", `{"xs":[10,20,30]}`)
	if diags.HasError() {
		t.Fatalf("clean JSON had errors: %v", summaries(diags.All()))
	}
	v, _ := doc.Lookup("xs")
	n, ok := v.Len()
	if !ok || n != 3 {
		t.Fatalf("xs Len = (%d,%v), want (3,true)", n, ok)
	}
	for i, want := range []int64{10, 20, 30} {
		ev, ok := doc.Lookup(cfg.Path("xs").Index(i))
		if !ok {
			t.Fatalf("Lookup(xs[%d]) ok == false", i)
		}
		got, _ := ev.Int()
		if got != want {
			t.Fatalf("xs[%d] = %d, want %d", i, got, want)
		}
	}
}

func TestJSON_FloatReadableAsIntWhenIntegral(t *testing.T) {
	doc, _ := parse(t, cfg.FormatJSON, "f.json", `{"a":2.0,"b":2.5}`)
	a, _ := doc.Lookup("a")
	if n, d := a.Int(); d != nil || n != 2 {
		t.Fatalf("integral float a.Int() = (%d,%v), want (2,nil)", n, d)
	}
	b, _ := doc.Lookup("b")
	if _, d := b.Int(); d == nil {
		t.Fatal("fractional float b.Int() must be a mismatch *Diagnostic, not silent truncation")
	}
}

func TestJSON_NullIsAbsentLeaf(t *testing.T) {
	doc, diags := parse(t, cfg.FormatJSON, "n.json", `{"a":null}`)
	if diags.HasError() {
		t.Fatalf("null value should not error: %v", summaries(diags.All()))
	}
	v, ok := doc.Lookup("a")
	if !ok {
		t.Fatal("Lookup(a) for null ok == false; null leaf should resolve")
	}
	// Conversions on a null/absent leaf are total mismatches.
	if _, d := v.String(); d == nil {
		t.Fatal("null leaf String() must return a mismatch *Diagnostic")
	}
}

func TestJSON_TrailingDataIsDiagnostic(t *testing.T) {
	_, diags := parse(t, cfg.FormatJSON, "t.json", `{"a":1} {"b":2}`)
	if !diags.HasError() {
		t.Fatal("trailing top-level data must be a SeverityError")
	}
}

// --- env malformed lines ---

func TestEnv_MalformedLineIsDiagnostic(t *testing.T) {
	_, diags := parse(t, cfg.FormatEnv, "m.env", "GOOD=1\nNOEQUALS\n=emptykey\n")
	errs := 0
	for _, d := range diags.All() {
		if d.Severity == cfg.SeverityError {
			errs++
		}
	}
	if errs < 2 {
		t.Fatalf("expected >= 2 malformed-env errors (missing '=' and empty key), got %d", errs)
	}
}

func TestEnv_TypedInference(t *testing.T) {
	doc, _ := parse(t, cfg.FormatEnv, "i.env", "N=42\nB=true\nS=hello\n")
	if v, _ := doc.Lookup("N"); func() int64 { n, _ := v.Int(); return n }() != 42 {
		t.Fatal("env int inference failed")
	}
	if v, _ := doc.Lookup("B"); func() bool { b, _ := v.Bool(); return b }() != true {
		t.Fatal("env bool inference failed")
	}
	if v, _ := doc.Lookup("S"); func() string { s, _ := v.String(); return s }() != "hello" {
		t.Fatal("env string inference failed")
	}
}

// --- Merge type-conflict path ---

func TestMerge_TypeConflictIsDiagnosticNotFatal(t *testing.T) {
	src := cfgtest.Source{Files: map[string][]byte{
		"base.json":    []byte(`{"k":{"nested":1}}`),
		"overlay.json": []byte(`{"k":"scalar"}`),
	}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatJSON}, cfg.Deps{Source: src})
	base, _, _ := p.Parse(context.Background(), "base.json")
	overlay, _, _ := p.Parse(context.Background(), "overlay.json")
	merged, diags, err := p.Merge(context.Background(), base, overlay)
	if err != nil {
		t.Fatalf("Merge err = %v, want nil (type conflict is a Diagnostic)", err)
	}
	// overlay wins: k is now the scalar.
	v, ok := merged.Lookup("k")
	if !ok {
		t.Fatal("merged Lookup(k) ok == false")
	}
	if s, d := v.String(); d != nil || s != "scalar" {
		t.Fatalf("merged k = (%q,%v), want (scalar,nil) — overlay wins", s, d)
	}
	// A warning-level conflict finding is recorded.
	if len(diags.All()) == 0 {
		t.Fatal("merge type conflict produced no diagnostic")
	}
}

func TestMerge_AgainstZeroDocument(t *testing.T) {
	src := cfgtest.Source{Files: map[string][]byte{"o.json": []byte(`{"k":1}`)}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatJSON}, cfg.Deps{Source: src})
	overlay, _, _ := p.Parse(context.Background(), "o.json")
	// base is an empty document.
	base := cfgtest.Doc(map[string]any{})
	merged, _, err := p.Merge(context.Background(), base, overlay)
	if err != nil {
		t.Fatalf("Merge err = %v", err)
	}
	if v, ok := merged.Lookup("k"); !ok {
		t.Fatal("overlay key lost when merging over empty base")
	} else if n, _ := v.Int(); n != 1 {
		t.Fatalf("merged k = %d, want 1", n)
	}
}
