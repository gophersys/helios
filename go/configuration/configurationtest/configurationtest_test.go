package configurationtest_test

import (
	"context"
	"errors"
	"testing"

	cfg "github.com/gophersys/libs/go/configuration"
	cfgtest "github.com/gophersys/libs/go/configuration/configurationtest"
)

func TestDoc_BuildsTree(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{
		"engine": map[string]any{
			"models": []any{
				map[string]any{"auth": "tok"},
			},
		},
	})
	v, ok := doc.Lookup("engine.models[0].auth")
	if !ok {
		t.Fatal("Doc Lookup ok == false")
	}
	s, d := v.String()
	if d != nil || s != "tok" {
		t.Fatalf("Doc value = (%q, %v), want (tok, nil)", s, d)
	}
}

func TestDoc_WithOptions(t *testing.T) {
	doc := cfgtest.Doc(map[string]any{"a": 1},
		cfgtest.WithFormat(cfg.FormatYAML),
		cfgtest.WithOrigin("x.yaml"),
		cfgtest.WithPosition("a", cfg.Position{Source: "x.yaml", Line: 4, Column: 1}),
	)
	if doc.Format() != cfg.FormatYAML {
		t.Fatalf("Format = %q, want yaml", doc.Format())
	}
	if doc.Origin().Source != "x.yaml" {
		t.Fatalf("Origin = %q, want x.yaml", doc.Origin().Source)
	}
	v, _ := doc.Lookup("a")
	if v.At().Line != 4 {
		t.Fatalf("WithPosition not applied: At().Line = %d, want 4", v.At().Line)
	}
}

// --- scripted Parser ---

func TestFakeParser_StagedDoc(t *testing.T) {
	want := cfgtest.Doc(map[string]any{"k": "v"})
	p := &cfgtest.Parser{
		Documents: map[string]cfg.Document{"a.yaml": want},
	}
	doc, _, err := p.Parse(context.Background(), "a.yaml")
	if err != nil {
		t.Fatalf("Parse staged err = %v", err)
	}
	if v, ok := doc.Lookup("k"); !ok {
		t.Fatal("staged doc Lookup ok == false")
	} else if s, _ := v.String(); s != "v" {
		t.Fatalf("staged doc k = %q, want v", s)
	}
	if len(p.ParseCalls) != 1 || p.ParseCalls[0] != "a.yaml" {
		t.Fatalf("ParseCalls = %v, want [a.yaml]", p.ParseCalls)
	}
}

func TestFakeParser_UnstagedNameReturnsParseError(t *testing.T) {
	p := &cfgtest.Parser{}
	_, _, err := p.Parse(context.Background(), "missing.yaml")
	if err == nil {
		t.Fatal("unstaged name returned nil err, want *ParseError")
	}
	var pe *cfg.ParseError
	if !errors.As(err, &pe) {
		t.Fatalf("unstaged err is not *ParseError: %T", err)
	}
	if pe.Source != "missing.yaml" {
		t.Fatalf("ParseError.Source = %q, want missing.yaml", pe.Source)
	}
}

func TestFakeParser_StagedReadErr(t *testing.T) {
	boom := errors.New("io boom")
	p := &cfgtest.Parser{ReadErr: map[string]error{"x": boom}}
	_, _, err := p.Parse(context.Background(), "x")
	if !errors.Is(err, boom) {
		t.Fatalf("staged ReadErr not surfaced: %v", err)
	}
	var pe *cfg.ParseError
	if !errors.As(err, &pe) {
		t.Fatalf("staged ReadErr not wrapped as *ParseError: %T", err)
	}
}

func TestFakeParser_StagedDiagnostics(t *testing.T) {
	var staged cfg.Diagnostics
	staged.Append(cfg.Diagnostic{Severity: cfg.SeverityError, Path: "a", Summary: "bad"})
	p := &cfgtest.Parser{
		Documents:   map[string]cfg.Document{"a.yaml": cfgtest.Doc(map[string]any{"a": 1})},
		Diagnostics: map[string]cfg.Diagnostics{"a.yaml": staged},
	}
	_, diags, err := p.Parse(context.Background(), "a.yaml")
	if err != nil {
		t.Fatalf("Parse err = %v", err)
	}
	if !diags.HasError() {
		t.Fatal("staged Diagnostics not returned")
	}
}

func TestFakeParser_ZeroValueUsable(t *testing.T) {
	var p cfgtest.Parser // zero value: every name unstaged
	_, _, err := p.Parse(context.Background(), "anything")
	var pe *cfg.ParseError
	if !errors.As(err, &pe) {
		t.Fatalf("zero-value fake Parse err = %T, want *ParseError", err)
	}
}

func TestFakeParser_Merge(t *testing.T) {
	var p cfgtest.Parser
	base := cfgtest.Doc(map[string]any{"a": 1})
	overlay := cfgtest.Doc(map[string]any{"a": 2})
	merged, _, err := p.Merge(context.Background(), base, overlay)
	if err != nil {
		t.Fatalf("fake Merge err = %v", err)
	}
	if merged == nil {
		t.Fatal("fake Merge returned nil Document")
	}
}

// --- Source ---

func TestFakeSource_ReadsFiles(t *testing.T) {
	s := cfgtest.Source{Files: map[string][]byte{"f": []byte("data")}}
	b, err := s.Read(context.Background(), "f")
	if err != nil {
		t.Fatalf("Source.Read err = %v", err)
	}
	if string(b) != "data" {
		t.Fatalf("Source.Read = %q, want data", b)
	}
}

func TestFakeSource_MissingReturnsError(t *testing.T) {
	s := cfgtest.Source{}
	if _, err := s.Read(context.Background(), "nope"); err == nil {
		t.Fatal("missing file Read returned nil err")
	}
}

func TestFakeSource_StagedError(t *testing.T) {
	boom := errors.New("nope")
	s := cfgtest.Source{Err: map[string]error{"f": boom}}
	if _, err := s.Read(context.Background(), "f"); !errors.Is(err, boom) {
		t.Fatalf("staged Source error not surfaced: %v", err)
	}
}

// --- Diags helper ---

func TestDiags_FiltersUnderPath(t *testing.T) {
	var d cfg.Diagnostics
	d.Append(
		cfg.Diagnostic{Path: "engine.models[0].auth", Severity: cfg.SeverityError, Summary: "auth"},
		cfg.Diagnostic{Path: "engine.models[0]", Severity: cfg.SeverityWarning, Summary: "model"},
		cfg.Diagnostic{Path: "other", Severity: cfg.SeverityError, Summary: "other"},
	)
	got := cfgtest.Diags(d, "engine.models[0]")
	if len(got) != 2 {
		t.Fatalf("Diags under engine.models[0] = %d findings, want 2 (%v)", len(got), got)
	}
	exact := cfgtest.Diags(d, "engine.models[0].auth")
	if len(exact) != 1 || exact[0].Summary != "auth" {
		t.Fatalf("Diags exact path = %v, want [auth]", exact)
	}
}
