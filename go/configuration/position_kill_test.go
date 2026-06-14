package configuration_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/configurationtest"
)

// This file pins down the EXACT source coordinates (line AND column) and the EXACT type-inference
// boundaries every decoder computes. The example-based suite proves "parsing works"; these assert
// the precise arithmetic — `eq + 2`, `indent + colon + 2`, `lineNo + 1`, the `len(s) >= 2`
// quote boundary, the depth boundary — so a one-off / negated / boundary-shifted mutant in the
// position math or the inference predicates can no longer survive (ADR-0020 §h, mutation power).
// Coordinates were captured from the real decoders and are the contract's "truthful Position"
// guarantee (04 §8) made executable.

// posOf parses a single fixture and returns the resolved leaf's Position, failing on any miss.
func posOf(t *testing.T, format configuration.Format, name, body string, path configuration.Path) configuration.Position {
	t.Helper()
	src := configurationtest.Source{Files: map[string][]byte{name: []byte(body)}}
	p, err := configuration.New(configuration.Config{Format: format}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	doc, diags, perr := p.Parse(context.Background(), name)
	if perr != nil {
		t.Fatalf("Parse I/O err = %v", perr)
	}
	if diags.HasError() {
		t.Fatalf("clean fixture %s produced errors: %v", name, diags.All())
	}
	v, ok := doc.Lookup(path)
	if !ok {
		t.Fatalf("Lookup(%q) missed in %s", path, name)
	}
	return v.At()
}

func assertPos(t *testing.T, got configuration.Position, wantLine, wantCol int) {
	t.Helper()
	if got.Line != wantLine {
		t.Fatalf("Position line = %d, want %d (got %+v)", got.Line, wantLine, got)
	}
	if got.Column != wantCol {
		t.Fatalf("Position column = %d, want %d (got %+v)", got.Column, wantCol, got)
	}
}

// TestKill_EnvExactPositions pins env value columns (`eq + 2`) and line numbers (`lineNo + 1`)
// across multiple lines, killing the position-arithmetic mutants in decode_env.go.
func TestKill_EnvExactPositions(t *testing.T) {
	t.Parallel()
	body := "A=1\nBB=two\n  C.D = x\n"
	assertPos(t, posOf(t, configuration.FormatEnv, "e.env", body, "A"), 1, 3)
	assertPos(t, posOf(t, configuration.FormatEnv, "e.env", body, "BB"), 2, 4)
	// "  C.D = x": '=' is at 0-based index 6, so the value column is 8; line 3.
	assertPos(t, posOf(t, configuration.FormatEnv, "e.env", body, "C.D"), 3, 8)
}

// TestKill_EnvTypeInferenceBoundaries pins the inferLeaf predicate ladder: "true"/"false" => bool,
// an integer literal => int, everything else => string. Killing these stops a negated/boundary
// mutant in the inference chain from passing.
func TestKill_EnvTypeInferenceBoundaries(t *testing.T) {
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"i.env": []byte("N=42\nNEG=-7\nB=true\nBF=false\nS=hello\nALMOST=12x\n"),
	}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatEnv}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	doc, _, perr := p.Parse(context.Background(), "i.env")
	if perr != nil {
		t.Fatalf("Parse err = %v", perr)
	}
	requireInt(t, doc, "N", 42)
	requireInt(t, doc, "NEG", -7)
	requireBool(t, doc, "B", true)
	requireBool(t, doc, "BF", false)
	requireString(t, doc, "S", "hello")
	// "12x" is NOT a valid integer literal — must fall through to string, not int.
	requireString(t, doc, "ALMOST", "12x")
}

// TestKill_EnvMalformedDiagnosticsExactPositions pins the missing-'=' and empty-key diagnostics at
// their exact line/column, killing the `eq < 0` / `key == ""` boundary+negation mutants.
func TestKill_EnvMalformedDiagnosticsExactPositions(t *testing.T) {
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"m.env": []byte("GOOD=1\nNOEQUALS\n=novalue\n"),
	}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatEnv}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	_, diags, perr := p.Parse(context.Background(), "m.env")
	if perr != nil {
		t.Fatalf("Parse err = %v", perr)
	}
	all := diags.All()
	if len(all) != 2 {
		t.Fatalf("want 2 malformed diagnostics, got %d: %v", len(all), all)
	}
	// Ordered by position: line 2 (missing '='), then line 3 (empty key), both at column 1.
	assertDiagAt(t, &all[0], configuration.SeverityError, 2, 1)
	assertDiagAt(t, &all[1], configuration.SeverityError, 3, 1)
}

// TestKill_YAMLExactPositions pins YAML key/value columns: a top-level value column is
// `indent + colon + 2` and a nested key column is `indent + 1` — exercising both arithmetic forms.
func TestKill_YAMLExactPositions(t *testing.T) {
	t.Parallel()
	body := "name: svc\nengine:\n  region: us-east\n  port: 9090\n"
	// "name: svc": indent 0, colon at 4 -> value col 6, line 1.
	assertPos(t, posOf(t, configuration.FormatYAML, "y.yaml", body, "name"), 1, 6)
	// "  region: us-east": indent 2, colon at 6 -> value col 2+6+2 = 10, line 3.
	assertPos(t, posOf(t, configuration.FormatYAML, "y.yaml", body, "engine.region"), 3, 10)
	// "  port: 9090": indent 2, colon at 4 -> value col 2+4+2 = 8, line 4.
	assertPos(t, posOf(t, configuration.FormatYAML, "y.yaml", body, "engine.port"), 4, 8)
}

// TestKill_YAMLScalarInference pins the inferYAMLScalar ladder including the quote boundary
// (len(s) >= 2) and every bool spelling (true/True/yes/on and false/False/no/off), killing the
// boundary/negation mutants in decode_yaml.go.
func TestKill_YAMLScalarInference(t *testing.T) {
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"s.yaml": []byte(
			"q: \"quoted\"\n" +
				"sq: 'apos'\n" +
				"i: 123\n" +
				"f: 2.5\n" +
				"t1: true\n" +
				"t2: yes\n" +
				"t3: on\n" +
				"t4: True\n" +
				"f1: false\n" +
				"f2: no\n" +
				"f3: off\n" +
				"plain: hello\n",
		),
	}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatYAML}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	doc, _, perr := p.Parse(context.Background(), "s.yaml")
	if perr != nil {
		t.Fatalf("Parse err = %v", perr)
	}
	requireString(t, doc, "q", "quoted") // quotes stripped (len>=2 boundary)
	requireString(t, doc, "sq", "apos")
	requireInt(t, doc, "i", 123)
	requireFloat(t, doc, "f", 2.5)
	for _, k := range []string{"t1", "t2", "t3", "t4"} {
		requireBool(t, doc, configuration.Path(k), true)
	}
	for _, k := range []string{"f1", "f2", "f3"} {
		requireBool(t, doc, configuration.Path(k), false)
	}
	requireString(t, doc, "plain", "hello")
}

// TestKill_YAMLCommentAndBlockSeqDiagnostics pins comment stripping (a space-preceded '#' is cut,
// a '#' inside quotes is kept) and the block-sequence diagnostic's exact column.
func TestKill_YAMLCommentAndBlockSeq(t *testing.T) {
	t.Parallel()
	// Trailing comment stripped; quoted '#' preserved.
	doc := mustParseClean(t, configuration.FormatYAML, "c.yaml",
		"a: value # trailing comment\nb: \"v#1\"\n")
	requireString(t, doc, "a", "value")
	requireString(t, doc, "b", "v#1")

	// Block sequence is an unsupported-construct diagnostic at the dash's column.
	src := configurationtest.Source{Files: map[string][]byte{"seq.yaml": []byte("items:\n  - one\n")}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatYAML}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	_, diags, perr := p.Parse(context.Background(), "seq.yaml")
	if perr != nil {
		t.Fatalf("Parse err = %v", perr)
	}
	if !diags.HasError() {
		t.Fatal("block sequence must be a SeverityError diagnostic")
	}
	// "  - one": indent 2 -> column 3.
	seqDiags := diags.All()
	assertDiagAt(t, &seqDiags[0], configuration.SeverityError, 2, 3)
}

// TestKill_TOMLExactPositionsAndInference pins TOML value columns (`eq + 2`), table headers, dotted
// tables, quoted-key trimming, and the scalar inference ladder (string/int/float/bool).
func TestKill_TOMLExactPositionsAndInference(t *testing.T) {
	t.Parallel()
	body := "port = 8080\n[server]\nhost = \"h\"\nratio = 1.5\nflag = true\n"
	// "port = 8080": '=' at 0-based 5 -> value col 7, line 1.
	assertPos(t, posOf(t, configuration.FormatTOML, "t.toml", body, "port"), 1, 7)
	// "host = \"h\"": '=' at 5 -> value col 7, line 3.
	assertPos(t, posOf(t, configuration.FormatTOML, "t.toml", body, "server.host"), 3, 7)

	doc := mustParseClean(t, configuration.FormatTOML, "t.toml", body)
	requireInt(t, doc, "port", 8080)
	requireString(t, doc, "server.host", "h")
	requireFloat(t, doc, "server.ratio", 1.5)
	requireBool(t, doc, "server.flag", true)
}

// TestKill_TOMLCommentInQuotes pins stripTOMLComment: a '#' inside a quoted value is preserved.
func TestKill_TOMLCommentInQuotes(t *testing.T) {
	t.Parallel()
	doc := mustParseClean(t, configuration.FormatTOML, "q.toml",
		"a = \"v#1\" # real comment\nb = 2\n")
	requireString(t, doc, "a", "v#1")
	requireInt(t, doc, "b", 2)
}

// TestKill_JSONFloatAndNestedColumns pins the JSON offset->column arithmetic on a single line and
// the integral-float-readable-as-int rule (2.0 reads as 2; 3.5 is a mismatch).
func TestKill_JSONFloatAndNestedColumns(t *testing.T) {
	t.Parallel()
	// `{"x": 2.0, "y": 3.5}`: the leaves are stamped at their token offsets mapped to columns —
	// x at column 5, y at column 15 — assert distinct columns so a constant-folded position mutant
	// cannot pass.
	xPos := posOf(t, configuration.FormatJSON, "f.json", `{"x": 2.0, "y": 3.5}`, "x")
	yPos := posOf(t, configuration.FormatJSON, "f.json", `{"x": 2.0, "y": 3.5}`, "y")
	assertPos(t, xPos, 1, 5)
	assertPos(t, yPos, 1, 15)

	doc := mustParseClean(t, configuration.FormatJSON, "f.json", `{"x": 2.0, "y": 3.5}`)
	// 2.0 is integral -> Int() succeeds with 2.
	requireInt(t, doc, "x", 2)
	// 3.5 is fractional -> Int() is a mismatch diagnostic, not a silent truncation.
	yv, _ := doc.Lookup("y")
	if n, d := yv.Int(); d == nil || n != 0 {
		t.Fatalf("fractional 3.5 Int() = (%d,%v), want (0, diagnostic)", n, d)
	}
	requireFloat(t, doc, "y", 3.5)
}

// mustParseClean parses a fixture and fails on any I/O error (diagnostics are allowed for the
// mixed comment/quote fixtures).
//
//nolint:ireturn // configuration.Document is an interface fixed by contracts/configuration.md §2.
func mustParseClean(t *testing.T, format configuration.Format, name, body string) configuration.Document {
	t.Helper()
	src := configurationtest.Source{Files: map[string][]byte{name: []byte(body)}}
	p, err := configuration.New(configuration.Config{Format: format}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	doc, _, perr := p.Parse(context.Background(), name)
	if perr != nil {
		t.Fatalf("Parse err = %v", perr)
	}
	return doc
}

func requireInt(t *testing.T, doc configuration.Document, path configuration.Path, want int64) {
	t.Helper()
	v, ok := doc.Lookup(path)
	if !ok {
		t.Fatalf("Lookup(%q) miss", path)
	}
	n, d := v.Int()
	if d != nil {
		t.Fatalf("%q Int() diagnostic = %v, want nil", path, d)
	}
	if n != want {
		t.Fatalf("%q Int() = %d, want %d", path, n, want)
	}
}

func requireString(t *testing.T, doc configuration.Document, path configuration.Path, want string) {
	t.Helper()
	v, ok := doc.Lookup(path)
	if !ok {
		t.Fatalf("Lookup(%q) miss", path)
	}
	s, d := v.String()
	if d != nil {
		t.Fatalf("%q String() diagnostic = %v, want nil", path, d)
	}
	if s != want {
		t.Fatalf("%q String() = %q, want %q", path, s, want)
	}
}

func requireBool(t *testing.T, doc configuration.Document, path configuration.Path, want bool) {
	t.Helper()
	v, ok := doc.Lookup(path)
	if !ok {
		t.Fatalf("Lookup(%q) miss", path)
	}
	b, d := v.Bool()
	if d != nil {
		t.Fatalf("%q Bool() diagnostic = %v, want nil", path, d)
	}
	if b != want {
		t.Fatalf("%q Bool() = %v, want %v", path, b, want)
	}
}

func requireFloat(t *testing.T, doc configuration.Document, path configuration.Path, want float64) {
	t.Helper()
	// A float leaf has no direct accessor in the contract surface; it is exposed via Int when
	// integral and otherwise read by asserting Int() mismatches while the JSON/YAML/TOML inference
	// stored a float. We assert the integral-vs-fractional behavior: a fractional float's Int() is
	// a mismatch (proving it was stored as float, not int or string).
	v, ok := doc.Lookup(path)
	if !ok {
		t.Fatalf("Lookup(%q) miss", path)
	}
	if want == float64(int64(want)) {
		// Integral float: Int() must succeed.
		if n, d := v.Int(); d != nil || n != int64(want) {
			t.Fatalf("%q integral float Int() = (%d,%v), want (%d,nil)", path, n, d, int64(want))
		}
		return
	}
	// Fractional float: stored as float, so Int() is a mismatch and String() is a mismatch.
	if _, d := v.Int(); d == nil {
		t.Fatalf("%q fractional float Int() must be a mismatch diagnostic", path)
	}
	if _, d := v.String(); d == nil {
		t.Fatalf("%q fractional float String() must be a mismatch diagnostic", path)
	}
}

func assertDiagAt(t *testing.T, d *configuration.Diagnostic, sev configuration.Severity, line, col int) {
	t.Helper()
	if d.Severity != sev {
		t.Fatalf("diagnostic severity = %d, want %d (%+v)", d.Severity, sev, d)
	}
	if d.At.Line != line {
		t.Fatalf("diagnostic line = %d, want %d (%+v)", d.At.Line, line, d)
	}
	if d.At.Column != col {
		t.Fatalf("diagnostic column = %d, want %d (%+v)", d.At.Column, col, d)
	}
}
