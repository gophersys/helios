package configuration_test

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/configurationtest"
)

// This file kills the remaining surviving mutants outside the decoders: the line/column mapping
// arithmetic (position.go), the dotted/indexed path tokeniser (document.go splitPath), the
// diagnostic ordering comparator (diagnostics.go lessByPosition), the ParseError nil-cause branch
// (parseerror.go), the over-cap boundary (parser.go), and the tree container accessors. Each
// assertion pins an exact observable so a boundary/negation/off-by-one mutant cannot survive.

// TestKill_LineMapColumnsAcrossLines pins the byte-offset -> (line, column) arithmetic: a leaf on a
// later line has its column computed relative to that line's start (`off - lineStart + 1`), not the
// file start. JSON is offset-based, so a multi-line fixture exercises the lineMap directly.
func TestKill_LineMapColumnsAcrossLines(t *testing.T) {
	t.Parallel()
	// Each value sits at a known column on its own line; the column must reset per line. The JSON
	// decoder stamps the leaf at its token's byte offset mapped through the lineMap, so the column
	// is computed relative to THAT line's start — a per-line column that grows by one as the key
	// widens by one character.
	body := "{\n" +
		`  "a": 1,` + "\n" + // line 2
		`  "bb": 22,` + "\n" + // line 3
		`  "ccc": 333` + "\n" + // line 4
		"}"
	assertPos(t, posOf(t, configuration.FormatJSON, "m.json", body, "a"), 2, 6)
	assertPos(t, posOf(t, configuration.FormatJSON, "m.json", body, "bb"), 3, 7)
	assertPos(t, posOf(t, configuration.FormatJSON, "m.json", body, "ccc"), 4, 8)
}

// TestKill_PathTokeniserIndices pins splitPath/appendPartSegments: dotted keys, a single [i] index,
// and chained [i][j] indices all resolve to the right leaf — killing the index-parsing arithmetic.
func TestKill_PathTokeniserIndices(t *testing.T) {
	t.Parallel()
	doc := configurationtest.Doc(map[string]any{
		"engine": map[string]any{
			"models": []any{
				map[string]any{"name": "m0"},
				map[string]any{"name": "m1"},
			},
		},
		"grid": []any{
			[]any{"r0c0", "r0c1"},
			[]any{"r1c0", "r1c1"},
		},
	})
	requireString(t, doc, "engine.models[0].name", "m0")
	requireString(t, doc, "engine.models[1].name", "m1")
	requireString(t, doc, "grid[0][1]", "r0c1")
	requireString(t, doc, "grid[1][0]", "r1c0")

	// An out-of-range index misses cleanly (no panic), exercising the Elem bound.
	if _, ok := doc.Lookup("engine.models[2].name"); ok {
		t.Fatal("out-of-range index must miss")
	}
}

// TestKill_DiagnosticsOrdering pins lessByPosition: All() sorts by Source, then Line, then Column.
// Findings are appended out of order and must come back in the exact (source,line,column) order.
func TestKill_DiagnosticsOrdering(t *testing.T) {
	t.Parallel()
	var d configuration.Diagnostics
	d.Append(
		configuration.Diagnostic{Summary: "b-l2-c5", At: configuration.Position{Source: "b", Line: 2, Column: 5}},
		configuration.Diagnostic{Summary: "a-l9-c9", At: configuration.Position{Source: "a", Line: 9, Column: 9}},
		configuration.Diagnostic{Summary: "b-l2-c1", At: configuration.Position{Source: "b", Line: 2, Column: 1}},
		configuration.Diagnostic{Summary: "b-l1-c9", At: configuration.Position{Source: "b", Line: 1, Column: 9}},
	)
	got := d.All()
	want := []string{"a-l9-c9", "b-l1-c9", "b-l2-c1", "b-l2-c5"}
	if len(got) != len(want) {
		t.Fatalf("All() len = %d, want %d", len(got), len(want))
	}
	for i, w := range want {
		if got[i].Summary != w {
			t.Fatalf("All()[%d] = %q, want %q (full order: %v)", i, got[i].Summary, w, summariesOf(got))
		}
	}
}

func summariesOf(ds []configuration.Diagnostic) []string {
	out := make([]string, len(ds))
	for i, d := range ds {
		out[i] = d.Summary
	}
	return out
}

// TestKill_DiagnosticsHasError pins HasError: true iff at least one finding is SeverityError. A
// warnings-only set must be false; adding one error flips it.
func TestKill_DiagnosticsHasError(t *testing.T) {
	t.Parallel()
	var d configuration.Diagnostics
	d.Append(configuration.Diagnostic{Severity: configuration.SeverityWarning, Summary: "w"})
	if d.HasError() {
		t.Fatal("warnings-only Diagnostics must not report HasError")
	}
	d.Append(configuration.Diagnostic{Severity: configuration.SeverityError, Summary: "e"})
	if !d.HasError() {
		t.Fatal("a SeverityError finding must make HasError true")
	}
}

// TestKill_ParseErrorNilCauseBranch pins ParseError.Error() in both branches: with a wrapped cause
// it renders "<source>: <cause>"; with a nil cause it renders "<source>: read failed".
func TestKill_ParseErrorNilCauseBranch(t *testing.T) {
	t.Parallel()
	withCause := &configuration.ParseError{Source: "x.json", Err: errReadDenied}
	if got, want := withCause.Error(), "x.json: read denied"; got != want {
		t.Fatalf("ParseError(with cause).Error() = %q, want %q", got, want)
	}
	nilCause := &configuration.ParseError{Source: "y.json"}
	if got, want := nilCause.Error(), "y.json: read failed"; got != want {
		t.Fatalf("ParseError(nil cause).Error() = %q, want %q", got, want)
	}
	// Unwrap reaches the cause (errors.Is), and is nil when there is none.
	if !errors.Is(withCause, errReadDenied) {
		t.Fatal("ParseError must Unwrap to its cause")
	}
	if nilCause.Unwrap() != nil {
		t.Fatal("ParseError with no cause must Unwrap to nil")
	}
}

// TestKill_MaxSourceBytesBoundary pins the over-cap boundary in parser.go: a source EQUAL to the
// cap parses cleanly; a source one byte OVER the cap is a SeverityError diagnostic (`> cap`, not
// `>= cap`). This is the exact `len(raw) > p.maxSourceBytes` boundary.
func TestKill_MaxSourceBytesBoundary(t *testing.T) {
	t.Parallel()
	// Exactly at the cap: "{}" is 2 bytes, cap 2 -> clean.
	atCap := configurationtest.Source{Files: map[string][]byte{"c.json": []byte(`{}`)}}
	p, err := configuration.New(
		configuration.Config{Format: configuration.FormatJSON, MaxSourceBytes: 2},
		configuration.Deps{Source: atCap},
	)
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	_, diags, perr := p.Parse(context.Background(), "c.json")
	if perr != nil {
		t.Fatalf("at-cap Parse I/O err = %v", perr)
	}
	if diags.HasError() {
		t.Fatalf("a source EQUAL to the cap must parse cleanly, got: %v", diags.All())
	}

	// One byte over the cap: "{ }" is 3 bytes, cap 2 -> over-cap diagnostic.
	overCap := configurationtest.Source{Files: map[string][]byte{"o.json": []byte(`{ }`)}}
	p2, err := configuration.New(
		configuration.Config{Format: configuration.FormatJSON, MaxSourceBytes: 2},
		configuration.Deps{Source: overCap},
	)
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	_, diags2, perr2 := p2.Parse(context.Background(), "o.json")
	if perr2 != nil {
		t.Fatalf("over-cap is a Diagnostic, not an I/O error: %v", perr2)
	}
	if !diags2.HasError() {
		t.Fatal("a source one byte OVER the cap must be a SeverityError diagnostic")
	}
}

// TestKill_JSONDepthBoundary pins the EXACT depth boundary (`depth >= maxJSONDepth`, 256): nesting
// up to the bound parses cleanly, and one level past it is a too-deep SeverityError — killing the
// boundary mutant that the existing 512-level test (which only kills the negation) leaves alive.
func TestKill_JSONDepthBoundary(t *testing.T) {
	t.Parallel()
	// 256 nested arrays: at the bound, decoded cleanly (no too-deep finding).
	atBound := strings.Repeat("[", 256) + strings.Repeat("]", 256)
	_, diagsOK := parseKill(t, configuration.FormatJSON, "ok.json", atBound)
	for _, d := range diagsOK.All() {
		if strings.Contains(d.Summary, "deep") {
			t.Fatalf("256 levels is AT the bound and must NOT be too-deep, got: %v", diagsOK.All())
		}
	}
	// 257 nested arrays: one past the bound -> too-deep SeverityError.
	overBound := strings.Repeat("[", 257) + strings.Repeat("]", 257)
	_, diagsBad := parseKill(t, configuration.FormatJSON, "bad.json", overBound)
	if !diagsBad.HasError() {
		t.Fatal("257 levels is one PAST the bound and must be a too-deep SeverityError")
	}
}

// TestKill_YAMLQuoteBoundaries pins the unquoteYAML / inferYAMLScalar quote predicate at its edges:
// a 2-char "" is the minimum balanced quote (len(s) >= 2 boundary), a single unbalanced quote is
// NOT stripped, and a 1-char string is left as-is. Killing these stops the boundary/negation
// mutants in the quote-detection conditionals.
func TestKill_YAMLQuoteBoundaries(t *testing.T) {
	t.Parallel()
	doc := mustParseClean(t, configuration.FormatYAML, "q.yaml",
		"empty: \"\"\n"+ // balanced 2-char -> empty string after strip
			"one: \"\n"+ // single quote, unbalanced -> kept literally
			"bare: x\n"+ // 1-char unquoted -> kept
			"mixed: \"a'\n") // leading double, trailing apostrophe: NOT a matched pair -> kept
	requireString(t, doc, "empty", "")
	requireString(t, doc, "one", `"`)
	requireString(t, doc, "bare", "x")
	requireString(t, doc, "mixed", `"a'`)
}

// TestKill_YAMLCommentAtLineStart pins indexUnquotedHash: a '#' at column 0 (line start) is a
// comment (the `i == 0` arm), and a '#' immediately after a non-space char is NOT a comment.
func TestKill_YAMLCommentAtLineStart(t *testing.T) {
	t.Parallel()
	doc := mustParseClean(t, configuration.FormatYAML, "h.yaml",
		"# whole line comment\n"+
			"a: 1\n"+
			"b: val#notcomment\n") // '#' preceded by a non-space char -> part of the value
	requireInt(t, doc, "a", 1)
	requireString(t, doc, "b", "val#notcomment")
	// The whole-line comment produced no 'a'-shadowing key and no diagnostic.
	if _, ok := doc.Lookup("#"); ok {
		t.Fatal("a whole-line comment must not become a key")
	}
}

// TestKill_YAMLNestedStackPop pins the frame-pop arithmetic (`indent <= parent.indent`): a value
// dedented back to a shallower level attaches to the correct ancestor, not the deepest open frame.
func TestKill_YAMLNestedStackPop(t *testing.T) {
	t.Parallel()
	body := "a:\n" +
		"  b:\n" +
		"    c: deep\n" +
		"  d: shallow\n" + // dedent: sibling of b under a, NOT under b
		"e: top\n" // dedent to root
	doc := mustParseClean(t, configuration.FormatYAML, "n.yaml", body)
	requireString(t, doc, "a.b.c", "deep")
	requireString(t, doc, "a.d", "shallow")
	requireString(t, doc, "e", "top")
	// d must be under a, not under a.b.
	if _, ok := doc.Lookup("a.b.d"); ok {
		t.Fatal("dedented key must NOT attach to the deeper frame")
	}
}

// TestKill_DiagnosticsOrderingTieBreaks pins lessByPosition at each comparison boundary: equal
// Source falls through to Line; equal Line falls through to Column. Each tie-break is exercised so
// a boundary mutant on any of the three comparisons is caught.
func TestKill_DiagnosticsOrderingTieBreaks(t *testing.T) {
	t.Parallel()
	var d configuration.Diagnostics
	d.Append(
		// same source "s", same line 5, columns out of order
		configuration.Diagnostic{Summary: "s5c9", At: configuration.Position{Source: "s", Line: 5, Column: 9}},
		configuration.Diagnostic{Summary: "s5c2", At: configuration.Position{Source: "s", Line: 5, Column: 2}},
		// same source "s", different line
		configuration.Diagnostic{Summary: "s4c9", At: configuration.Position{Source: "s", Line: 4, Column: 9}},
	)
	got := summariesOf(d.All())
	want := []string{"s4c9", "s5c2", "s5c9"}
	for i, w := range want {
		if got[i] != w {
			t.Fatalf("tie-break order[%d] = %q, want %q (full: %v)", i, got[i], w, got)
		}
	}
}

// TestKill_TOMLTableHeaderLinesAndConflict pins the TOML table-header / malformed-line diagnostics
// at their exact line (`lineNo + 1`), the missing-'=' branch, and the scalar-then-table conflict.
func TestKill_TOMLTableHeaderLinesAndConflict(t *testing.T) {
	t.Parallel()
	// A bare key with no '=' on line 2 is a malformed-line diagnostic at line 2, column 1.
	src := configurationtest.Source{Files: map[string][]byte{
		"m.toml": []byte("ok = 1\nNOEQUALS\n"),
	}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatTOML}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	_, diags, perr := p.Parse(context.Background(), "m.toml")
	if perr != nil {
		t.Fatalf("Parse err = %v", perr)
	}
	all := diags.All()
	if len(all) != 1 {
		t.Fatalf("want 1 malformed-line diagnostic, got %d: %v", len(all), all)
	}
	assertDiagAt(t, &all[0], configuration.SeverityError, 2, 1)

	// scalar set, then a [table] header needing it as a table -> a strict conflict diagnostic.
	conflictSrc := configurationtest.Source{Files: map[string][]byte{
		"c.toml": []byte("server = 1\n[server]\nhost = \"h\"\n"),
	}}
	p2, err := configuration.New(configuration.Config{Format: configuration.FormatTOML}, configuration.Deps{Source: conflictSrc})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	_, cdiags, cperr := p2.Parse(context.Background(), "c.toml")
	if cperr != nil {
		t.Fatalf("Parse(conflict) err = %v", cperr)
	}
	if !cdiags.HasError() {
		t.Fatal("scalar-then-table-header must be a strict SeverityError conflict")
	}
}

// parseKill is a local parse helper for the depth fixtures (diagnostics allowed).
//
//nolint:ireturn // configuration.Document is an interface fixed by contracts/configuration.md §2.
func parseKill(t *testing.T, format configuration.Format, name, body string) (configuration.Document, configuration.Diagnostics) {
	t.Helper()
	src := configurationtest.Source{Files: map[string][]byte{name: []byte(body)}}
	p, err := configuration.New(configuration.Config{Format: format}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	doc, diags, perr := p.Parse(context.Background(), name)
	if perr != nil {
		t.Fatalf("Parse err = %v", perr)
	}
	return doc, diags
}
