package configurationtest_test

import (
	"context"
	"errors"
	"testing"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/configurationtest"
)

func TestDoc_BuildsTree(t *testing.T) {
	t.Parallel()
	doc := configurationtest.Doc(map[string]any{
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
	t.Parallel()
	doc := configurationtest.Doc(
		map[string]any{"a": 1},
		configurationtest.WithFormat(configuration.FormatYAML),
		configurationtest.WithOrigin("x.yaml"),
		configurationtest.WithPosition("a", configuration.Position{Source: "x.yaml", Line: 4, Column: 1}),
	)
	if doc.Format() != configuration.FormatYAML {
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

// Section: scripted Parser.
func TestFakeParser_StagedDoc(t *testing.T) {
	t.Parallel()
	want := configurationtest.Doc(map[string]any{"k": "v"})
	p := &configurationtest.Parser{
		Documents: map[string]configuration.Document{"a.yaml": want},
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
	t.Parallel()
	p := &configurationtest.Parser{}
	_, _, err := p.Parse(context.Background(), "missing.yaml")
	if err == nil {
		t.Fatal("unstaged name returned nil err, want *ParseError")
	}
	var pe *configuration.ParseError
	if !errors.As(err, &pe) {
		t.Fatalf("unstaged err is not *ParseError: %T", err)
	}
	if pe.Source != "missing.yaml" {
		t.Fatalf("ParseError.Source = %q, want missing.yaml", pe.Source)
	}
}

func TestFakeParser_StagedReadErr(t *testing.T) {
	t.Parallel()
	boom := errors.New("io boom")
	p := &configurationtest.Parser{ReadErr: map[string]error{"x": boom}}
	_, _, err := p.Parse(context.Background(), "x")
	if !errors.Is(err, boom) {
		t.Fatalf("staged ReadErr not surfaced: %v", err)
	}
	var pe *configuration.ParseError
	if !errors.As(err, &pe) {
		t.Fatalf("staged ReadErr not wrapped as *ParseError: %T", err)
	}
}

func TestFakeParser_StagedDiagnostics(t *testing.T) {
	t.Parallel()
	var staged configuration.Diagnostics
	staged.Append(configuration.Diagnostic{Severity: configuration.SeverityError, Path: "a", Summary: "bad"})
	p := &configurationtest.Parser{
		Documents:   map[string]configuration.Document{"a.yaml": configurationtest.Doc(map[string]any{"a": 1})},
		Diagnostics: map[string]configuration.Diagnostics{"a.yaml": staged},
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
	t.Parallel()
	var p configurationtest.Parser // zero value: every name unstaged
	_, _, err := p.Parse(context.Background(), "anything")
	var pe *configuration.ParseError
	if !errors.As(err, &pe) {
		t.Fatalf("zero-value fake Parse err = %T, want *ParseError", err)
	}
}

func TestFakeParser_Merge(t *testing.T) {
	t.Parallel()
	var p configurationtest.Parser
	base := configurationtest.Doc(map[string]any{"a": 1})
	overlay := configurationtest.Doc(map[string]any{"a": 2})
	merged, _, err := p.Merge(context.Background(), base, overlay)
	if err != nil {
		t.Fatalf("fake Merge err = %v", err)
	}
	if merged == nil {
		t.Fatal("fake Merge returned nil Document")
	}
}

// Section: Source.
func TestFakeSource_ReadsFiles(t *testing.T) {
	t.Parallel()
	s := configurationtest.Source{Files: map[string][]byte{"f": []byte("data")}}
	b, err := s.Read(context.Background(), "f")
	if err != nil {
		t.Fatalf("Source.Read err = %v", err)
	}
	if string(b) != "data" {
		t.Fatalf("Source.Read = %q, want data", b)
	}
}

func TestFakeSource_MissingReturnsError(t *testing.T) {
	t.Parallel()
	s := configurationtest.Source{}
	if _, err := s.Read(context.Background(), "nope"); err == nil {
		t.Fatal("missing file Read returned nil err")
	}
}

func TestFakeSource_StagedError(t *testing.T) {
	t.Parallel()
	boom := errors.New("nope")
	s := configurationtest.Source{Err: map[string]error{"f": boom}}
	if _, err := s.Read(context.Background(), "f"); !errors.Is(err, boom) {
		t.Fatalf("staged Source error not surfaced: %v", err)
	}
}

// Section: Diags helper.
func TestDiags_FiltersUnderPath(t *testing.T) {
	t.Parallel()
	var d configuration.Diagnostics
	d.Append(
		configuration.Diagnostic{Path: "engine.models[0].auth", Severity: configuration.SeverityError, Summary: "auth"},
		configuration.Diagnostic{Path: "engine.models[0]", Severity: configuration.SeverityWarning, Summary: "model"},
		configuration.Diagnostic{Path: "other", Severity: configuration.SeverityError, Summary: "other"},
	)
	got := configurationtest.Diags(d, "engine.models[0]")
	if len(got) != 2 {
		t.Fatalf("Diags under engine.models[0] = %d findings, want 2 (%v)", len(got), got)
	}
	exact := configurationtest.Diags(d, "engine.models[0].auth")
	if len(exact) != 1 || exact[0].Summary != "auth" {
		t.Fatalf("Diags exact path = %v, want [auth]", exact)
	}
}
