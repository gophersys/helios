package configuration_test

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/configurationtest"
)

//nolint:ireturn // configuration.Document is an interface fixed by contracts/configuration.md §2; this helper forwards the contract surface.
func parse(t *testing.T, format configuration.Format, name, body string) (configuration.Document, configuration.Diagnostics) {
	t.Helper()
	src := configurationtest.Source{Files: map[string][]byte{name: []byte(body)}}
	p, err := configuration.New(configuration.Config{Format: format}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New(%s) err = %v", format, err)
	}
	doc, diags, err := p.Parse(context.Background(), name)
	if err != nil {
		t.Fatalf("Parse err = %v", err)
	}
	return doc, diags
}

// Section: YAML subset.
func TestYAML_NestedMappingAndScalars(t *testing.T) {
	t.Parallel()
	doc, diags := parse(t, configuration.FormatYAML, "c.yaml",
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
	t.Parallel()
	_, diags := parse(t, configuration.FormatYAML, "s.yaml", "items:\n  - a\n  - b\n")
	if !diags.HasError() {
		t.Fatal("unsupported YAML block sequence must be a SeverityError, not a panic")
	}
}

func TestYAML_MalformedLineIsDiagnostic(t *testing.T) {
	t.Parallel()
	_, diags := parse(t, configuration.FormatYAML, "m.yaml", "no colon here\n")
	if !diags.HasError() {
		t.Fatal("malformed YAML line must be a SeverityError")
	}
}

func TestYAML_DuplicateKeyStrict(t *testing.T) {
	t.Parallel()
	_, diags := parse(t, configuration.FormatYAML, "d.yaml", "a: 1\na: 2\n")
	if !diags.HasError() {
		t.Fatal("duplicate YAML key must be SeverityError under strict default")
	}
}

// Section: TOML subset.
func TestTOML_TablesAndScalars(t *testing.T) {
	t.Parallel()
	doc, diags := parse(t, configuration.FormatTOML, "c.toml",
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
	t.Parallel()
	_, diags := parse(t, configuration.FormatTOML, "a.toml", "[[products]]\nname = \"x\"\n")
	if !diags.HasError() {
		t.Fatal("unsupported [[array-of-tables]] must be a SeverityError, not a panic")
	}
}

func TestTOML_MalformedHeaderIsDiagnostic(t *testing.T) {
	t.Parallel()
	_, diags := parse(t, configuration.FormatTOML, "h.toml", "[unterminated\n")
	if !diags.HasError() {
		t.Fatal("malformed TOML table header must be a SeverityError")
	}
}

func TestTOML_DuplicateKeyStrict(t *testing.T) {
	t.Parallel()
	_, diags := parse(t, configuration.FormatTOML, "d.toml", "a = 1\na = 2\n")
	if !diags.HasError() {
		t.Fatal("duplicate TOML key must be SeverityError under strict default")
	}
}

// Section: JSON arrays, floats, nulls.
func TestJSON_ArrayLenAndIndexedReads(t *testing.T) {
	t.Parallel()
	doc, diags := parse(t, configuration.FormatJSON, "a.json", `{"xs":[10,20,30]}`)
	if diags.HasError() {
		t.Fatalf("clean JSON had errors: %v", summaries(diags.All()))
	}
	v, _ := doc.Lookup("xs")
	n, ok := v.Len()
	if !ok || n != 3 {
		t.Fatalf("xs Len = (%d,%v), want (3,true)", n, ok)
	}
	for i, want := range []int64{10, 20, 30} {
		ev, ok := doc.Lookup(configuration.Path("xs").Index(i))
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
	t.Parallel()
	doc, _ := parse(t, configuration.FormatJSON, "f.json", `{"a":2.0,"b":2.5}`)
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
	t.Parallel()
	doc, diags := parse(t, configuration.FormatJSON, "n.json", `{"a":null}`)
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
	t.Parallel()
	_, diags := parse(t, configuration.FormatJSON, "t.json", `{"a":1} {"b":2}`)
	if !diags.HasError() {
		t.Fatal("trailing top-level data must be a SeverityError")
	}
}

// Section: env malformed lines.
func TestEnv_MalformedLineIsDiagnostic(t *testing.T) {
	t.Parallel()
	_, diags := parse(t, configuration.FormatEnv, "m.env", "GOOD=1\nNOEQUALS\n=emptykey\n")
	errs := 0
	for _, d := range diags.All() {
		if d.Severity == configuration.SeverityError {
			errs++
		}
	}
	if errs < 2 {
		t.Fatalf("expected >= 2 malformed-env errors (missing '=' and empty key), got %d", errs)
	}
}

func TestEnv_TypedInference(t *testing.T) {
	t.Parallel()
	doc, _ := parse(t, configuration.FormatEnv, "i.env", "N=42\nB=true\nS=hello\n")
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

// Section: Merge type-conflict path.
func TestMerge_TypeConflictIsDiagnosticNotFatal(t *testing.T) {
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"base.json":    []byte(`{"k":{"nested":1}}`),
		"overlay.json": []byte(`{"k":"scalar"}`),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatJSON}, src)
	base, _ := mustParse(t, p, "base.json")
	overlay, _ := mustParse(t, p, "overlay.json")
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
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{"o.json": []byte(`{"k":1}`)}}
	p := newParser(t, configuration.Config{Format: configuration.FormatJSON}, src)
	overlay, _ := mustParse(t, p, "o.json")
	// base is an empty document.
	base := configurationtest.Doc(map[string]any{})
	merged := mustMerge(t, p, base, overlay)
	if v, ok := merged.Lookup("k"); !ok {
		t.Fatal("overlay key lost when merging over empty base")
	} else if n, _ := v.Int(); n != 1 {
		t.Fatalf("merged k = %d, want 1", n)
	}
}

// Section: JSON nesting is bounded (the contract's "never a panic" guarantee).
//
// Deeply-nested JSON must NOT recurse into a Go stack overflow — a stack
// overflow is a runtime FATAL that recover() cannot catch, so it would kill the
// whole process on adversarial input under MaxSourceBytes. The decoder bounds
// nesting and surfaces a SeverityError Diagnostic instead.
func TestJSON_DeeplyNestedIsDiagnosticNotStackOverflow(t *testing.T) {
	t.Parallel()
	// Far beyond the depth bound but tiny in bytes: pure-recursion adversarial
	// input. A wrong decoder would crash the test binary here, not fail it.
	const depth = 5000
	body := strings.Repeat("[", depth) + strings.Repeat("]", depth)
	doc, diags := parse(t, configuration.FormatJSON, "deep.json", body)
	if !diags.HasError() {
		t.Fatal("deeply-nested JSON must produce a SeverityError diagnostic (depth bound), got none")
	}
	if doc == nil {
		t.Fatal("deeply-nested JSON must still return a (partial) Document, not nil")
	}
	// The Document must remain usable: a Lookup miss must be clean, not a panic.
	if _, ok := doc.Lookup("anything"); ok {
		t.Fatal("Lookup into a depth-bounded partial doc returned ok == true")
	}
}

// A large but shallow JSON document (well within the depth bound) parses
// cleanly — the depth guard must not reject legitimate input.
func TestJSON_WideShallowDocumentParsesCleanly(t *testing.T) {
	t.Parallel()
	var b strings.Builder
	b.WriteByte('{')
	for i := 0; i < 1000; i++ {
		if i > 0 {
			b.WriteByte(',')
		}
		b.WriteString(`"k`)
		b.WriteString(strings.Repeat("x", 1)) // distinct-ish keys
		b.WriteString(itoa(i))
		b.WriteString(`":`)
		b.WriteString(itoa(i))
	}
	b.WriteByte('}')
	_, diags := parse(t, configuration.FormatJSON, "wide.json", b.String())
	if diags.HasError() {
		t.Fatalf("wide shallow JSON wrongly flagged: %v", summaries(diags.All()))
	}
}

// itoa is a tiny dependency-free int->string for the wide-doc fixture.
func itoa(i int) string {
	if i == 0 {
		return "0"
	}
	var buf [20]byte
	pos := len(buf)
	for i > 0 {
		pos--
		buf[pos] = byte('0' + i%10)
		i /= 10
	}
	return string(buf[pos:])
}

// Section: strict-by-default intermediate-path / table conflicts.
//
// A scalar already occupying a path that a later dotted key (env) or table
// header (TOML) needs as a container must be a SeverityError under the strict
// default — silently clobbering it is exactly the typo footgun this pattern
// exists to prevent, and the JSON duplicate-key path already diagnoses it.
func TestEnv_ScalarThenDottedKeyConflictIsDiagnostic(t *testing.T) {
	t.Parallel()
	// LOG=info then LOG.LEVEL=debug: a real typo that silently lost LOG before.
	_, diags := parse(t, configuration.FormatEnv, "c.env", "LOG=info\nLOG.LEVEL=debug\n")
	if !diags.HasError() {
		t.Fatal("env scalar-then-object intermediate conflict must be a SeverityError, got none")
	}
	if got := errorDiagAt(diags, "LOG"); got == nil {
		t.Fatalf("expected a SeverityError at path LOG, got: %v", summaries(diags.All()))
	}
}

func TestTOML_ScalarThenTableHeaderConflictIsDiagnostic(t *testing.T) {
	t.Parallel()
	// server = 1 then [server]: silently discarded server = 1 before.
	_, diags := parse(t, configuration.FormatTOML, "c.toml", "server = 1\n[server]\nport = 8080\n")
	if !diags.HasError() {
		t.Fatal("TOML scalar-then-table intermediate conflict must be a SeverityError, got none")
	}
	if got := errorDiagAt(diags, "server"); got == nil {
		t.Fatalf("expected a SeverityError at path server, got: %v", summaries(diags.All()))
	}
}

// The intermediate conflict is wired to the strictness toggle, not hard-coded:
// AllowUnknownKeys downgrades it from Error to Warning, like every other
// strict-by-default finding.
func TestEnv_IntermediateConflictDowngradedByAllowUnknownKeys(t *testing.T) {
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"c.env": []byte("LOG=info\nLOG.LEVEL=debug\n"),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatEnv, AllowUnknownKeys: true}, src)
	_, diags := mustParse(t, p, "c.env")
	if diags.HasError() {
		t.Fatal("AllowUnknownKeys must downgrade the intermediate conflict to a Warning, not Error")
	}
	warned := false
	for _, d := range diags.All() {
		if d.Severity == configuration.SeverityWarning && d.Path == "LOG" {
			warned = true
		}
	}
	if !warned {
		t.Fatalf("expected a Warning at LOG under AllowUnknownKeys, got: %v", summaries(diags.All()))
	}
}

func TestTOML_IntermediateConflictDowngradedByAllowUnknownKeys(t *testing.T) {
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"c.toml": []byte("server = 1\n[server]\nport = 8080\n"),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatTOML, AllowUnknownKeys: true}, src)
	_, diags := mustParse(t, p, "c.toml")
	if diags.HasError() {
		t.Fatal("AllowUnknownKeys must downgrade the table-over-scalar conflict to a Warning, not Error")
	}
	warned := false
	for _, d := range diags.All() {
		if d.Severity == configuration.SeverityWarning && d.Path == "server" {
			warned = true
		}
	}
	if !warned {
		t.Fatalf("expected a Warning at server under AllowUnknownKeys, got: %v", summaries(diags.All()))
	}
}

// errorDiagAt returns the first SeverityError diagnostic at exactly path, or nil.
func errorDiagAt(diags configuration.Diagnostics, path configuration.Path) *configuration.Diagnostic {
	for _, d := range diags.All() {
		if d.Severity == configuration.SeverityError && d.Path == path {
			dd := d
			return &dd
		}
	}
	return nil
}
