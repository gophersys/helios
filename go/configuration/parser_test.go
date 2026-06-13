package configuration_test

import (
	"context"
	"errors"
	"strings"
	"testing"

	cfg "github.com/gophersys/libs/go/configuration"
	cfgtest "github.com/gophersys/libs/go/configuration/configurationtest"
)

// panicSource panics on Read; used to prove New performs no I/O.
type panicSource struct{}

func (panicSource) Read(context.Context, string) ([]byte, error) {
	panic("New must not read from Source")
}

// --- New: purity & validation ---

func TestNew_DoesNotTouchSource(t *testing.T) {
	// Constructing with a panicking Source must not panic: New reads nothing.
	p, err := cfg.New(cfg.Config{Format: cfg.FormatJSON}, cfg.Deps{Source: panicSource{}})
	if err != nil {
		t.Fatalf("New returned err = %v, want nil", err)
	}
	if p == nil {
		t.Fatal("New returned nil Parser")
	}
}

func TestNew_RejectsUnknownFormat(t *testing.T) {
	_, err := cfg.New(cfg.Config{Format: cfg.Format("xml")}, cfg.Deps{Source: cfgtest.Source{}})
	if err == nil {
		t.Fatal("New with unknown Format returned nil err, want error")
	}
}

func TestNew_RejectsNegativeMaxSourceBytes(t *testing.T) {
	_, err := cfg.New(
		cfg.Config{Format: cfg.FormatJSON, MaxSourceBytes: -1},
		cfg.Deps{Source: cfgtest.Source{}},
	)
	if err == nil {
		t.Fatal("New with negative MaxSourceBytes returned nil err, want error")
	}
}

func TestNew_AllowsZeroMaxSourceBytes(t *testing.T) {
	// 0 means an internal sane cap, not an error.
	if _, err := cfg.New(cfg.Config{Format: cfg.FormatJSON}, cfg.Deps{Source: cfgtest.Source{}}); err != nil {
		t.Fatalf("New with zero MaxSourceBytes err = %v, want nil", err)
	}
}

// --- Parse: happy path ---

func TestParse_JSON(t *testing.T) {
	src := cfgtest.Source{Files: map[string][]byte{
		"backend.json": []byte(`{"engine":{"maxConcurrency":8,"name":"primary"}}`),
	}}
	p, err := cfg.New(cfg.Config{Format: cfg.FormatJSON}, cfg.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	doc, diags, err := p.Parse(context.Background(), "backend.json")
	if err != nil {
		t.Fatalf("Parse err = %v, want nil", err)
	}
	if diags.HasError() {
		t.Fatalf("clean JSON yielded errors: %v", summaries(diags.All()))
	}
	v, ok := doc.Lookup("engine.maxConcurrency")
	if !ok {
		t.Fatal("Lookup(engine.maxConcurrency) ok == false")
	}
	n, d := v.Int()
	if d != nil || n != 8 {
		t.Fatalf("maxConcurrency = (%d, %v), want (8, nil)", n, d)
	}
	if doc.Format() != cfg.FormatJSON {
		t.Fatalf("Format() = %q, want json", doc.Format())
	}
	if doc.Origin().Source != "backend.json" {
		t.Fatalf("Origin().Source = %q, want backend.json", doc.Origin().Source)
	}
}

func TestParse_Env(t *testing.T) {
	src := cfgtest.Source{Files: map[string][]byte{
		"app.env": []byte("ENGINE.MAXCONCURRENCY=8\nENGINE.NAME=primary\n# comment\n\n"),
	}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatEnv}, cfg.Deps{Source: src})
	doc, diags, err := p.Parse(context.Background(), "app.env")
	if err != nil {
		t.Fatalf("Parse err = %v", err)
	}
	if diags.HasError() {
		t.Fatalf("clean env yielded errors: %v", summaries(diags.All()))
	}
	// Dotted keys nest.
	v, ok := doc.Lookup("ENGINE.NAME")
	if !ok {
		t.Fatal("Lookup(ENGINE.NAME) ok == false; dotted env keys must nest")
	}
	s, _ := v.String()
	if s != "primary" {
		t.Fatalf("ENGINE.NAME = %q, want primary", s)
	}
}

// Env positions are truthful: line numbers point at the source line.
func TestParse_EnvPositionTruthful(t *testing.T) {
	src := cfgtest.Source{Files: map[string][]byte{
		"a.env": []byte("A=1\nB=2\n"),
	}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatEnv}, cfg.Deps{Source: src})
	doc, _, _ := p.Parse(context.Background(), "a.env")
	v, _ := doc.Lookup("B")
	if v.At().Line != 2 {
		t.Fatalf("B At().Line = %d, want 2", v.At().Line)
	}
	if v.At().Source != "a.env" {
		t.Fatalf("B At().Source = %q, want a.env", v.At().Source)
	}
}

// --- Strict by default ---

func TestParse_StrictRejectsDuplicateKeys(t *testing.T) {
	src := cfgtest.Source{Files: map[string][]byte{
		"d.json": []byte(`{"a":1,"a":2}`),
	}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatJSON}, cfg.Deps{Source: src})
	_, diags, err := p.Parse(context.Background(), "d.json")
	if err != nil {
		t.Fatalf("duplicate-key Parse err = %v, want nil (config-is-wrong is data)", err)
	}
	if !diags.HasError() {
		t.Fatal("strict parse of duplicate key did not produce SeverityError")
	}
}

func TestParse_AllowUnknownKeysDowngradesDuplicate(t *testing.T) {
	src := cfgtest.Source{Files: map[string][]byte{
		"d.json": []byte(`{"a":1,"a":2}`),
	}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatJSON, AllowUnknownKeys: true}, cfg.Deps{Source: src})
	_, diags, err := p.Parse(context.Background(), "d.json")
	if err != nil {
		t.Fatalf("Parse err = %v", err)
	}
	if diags.HasError() {
		t.Fatal("AllowUnknownKeys should downgrade duplicate to Warning, not Error")
	}
	// A warning should still be present (the finding is reported, just downgraded).
	found := false
	for _, dg := range diags.All() {
		if dg.Severity == cfg.SeverityWarning {
			found = true
		}
	}
	if !found {
		t.Fatal("AllowUnknownKeys produced no Warning for the duplicate key")
	}
}

// --- Diagnostics accumulate (no short-circuit) ---

func TestParse_AccumulatesMultipleProblems(t *testing.T) {
	// Three duplicate keys => three findings in ONE Parse.
	src := cfgtest.Source{Files: map[string][]byte{
		"m.json": []byte(`{"a":1,"a":2,"b":1,"b":2,"c":1,"c":2}`),
	}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatJSON}, cfg.Deps{Source: src})
	_, diags, _ := p.Parse(context.Background(), "m.json")
	errCount := 0
	for _, dg := range diags.All() {
		if dg.Severity == cfg.SeverityError {
			errCount++
		}
	}
	if errCount < 3 {
		t.Fatalf("accumulate-all: got %d errors, want >= 3 (one per duplicate)", errCount)
	}
}

// --- Error-channel discipline ---

func TestParse_IOFailureReturnsParseError(t *testing.T) {
	wantErr := errors.New("disk gone")
	src := cfgtest.Source{Err: map[string]error{"x.json": wantErr}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatJSON}, cfg.Deps{Source: src})
	doc, _, err := p.Parse(context.Background(), "x.json")
	if err == nil {
		t.Fatal("I/O failure returned nil err, want *ParseError")
	}
	var pe *cfg.ParseError
	if !errors.As(err, &pe) {
		t.Fatalf("err is not *ParseError: %T", err)
	}
	if pe.Source != "x.json" {
		t.Fatalf("ParseError.Source = %q, want x.json", pe.Source)
	}
	if !errors.Is(err, wantErr) {
		t.Fatal("ParseError does not Unwrap to the underlying Source error")
	}
	if doc != nil {
		// On I/O failure the document is not usable; contract returns no doc.
		if _, ok := doc.Lookup("a"); ok {
			t.Fatal("Lookup on I/O-failure document returned ok == true")
		}
	}
}

func TestParse_WrongButReadableSourceReturnsDiags(t *testing.T) {
	// Syntactically invalid JSON is readable => (doc, diags, nil) with HasError.
	src := cfgtest.Source{Files: map[string][]byte{
		"bad.json": []byte(`{"a": }`),
	}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatJSON}, cfg.Deps{Source: src})
	_, diags, err := p.Parse(context.Background(), "bad.json")
	if err != nil {
		t.Fatalf("syntactically-wrong-but-readable returned err = %v, want nil", err)
	}
	if !diags.HasError() {
		t.Fatal("invalid JSON syntax did not produce a SeverityError diagnostic")
	}
}

func TestParseError_ErrorString(t *testing.T) {
	pe := &cfg.ParseError{Source: "backend.yaml", Err: errors.New("boom")}
	if !strings.Contains(pe.Error(), "backend.yaml") {
		t.Fatalf("ParseError.Error() = %q, want it to contain the source name", pe.Error())
	}
}

// --- MaxSourceBytes cap ---

func TestParse_MaxSourceBytesCap(t *testing.T) {
	big := []byte(`{"k":"` + strings.Repeat("x", 1000) + `"}`)
	src := cfgtest.Source{Files: map[string][]byte{"big.json": big}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatJSON, MaxSourceBytes: 16}, cfg.Deps{Source: src})
	_, diags, err := p.Parse(context.Background(), "big.json")
	// Over-cap is a config/data problem, not an I/O error: report as Diagnostic.
	if err != nil {
		var pe *cfg.ParseError
		if !errors.As(err, &pe) {
			t.Fatalf("over-cap err is not *ParseError: %v", err)
		}
		return // acceptable: surfaced on the error channel as a ParseError
	}
	if !diags.HasError() {
		t.Fatal("source exceeding MaxSourceBytes produced neither err nor SeverityError diag")
	}
}

// --- Validators run as a phase ---

type recordingValidator struct {
	ran  *bool
	emit cfg.Diagnostic
}

func (v recordingValidator) Validate(doc cfg.Document, into *cfg.Diagnostics) {
	*v.ran = true
	into.Append(v.emit)
}

func TestParse_ValidatorsRunAfterParse(t *testing.T) {
	ran := false
	src := cfgtest.Source{Files: map[string][]byte{"v.json": []byte(`{"a":1}`)}}
	p, _ := cfg.New(cfg.Config{
		Format: cfg.FormatJSON,
		Validators: []cfg.Validator{
			recordingValidator{ran: &ran, emit: cfg.Diagnostic{
				Severity: cfg.SeverityError, Path: "a", Summary: "domain rule",
			}},
		},
	}, cfg.Deps{Source: src})
	_, diags, err := p.Parse(context.Background(), "v.json")
	if err != nil {
		t.Fatalf("Parse err = %v", err)
	}
	if !ran {
		t.Fatal("Validator did not run")
	}
	if !diags.HasError() {
		t.Fatal("Validator's SeverityError did not surface in Diagnostics")
	}
}

func TestParse_ValidatorErrorDoesNotChangeErrChannel(t *testing.T) {
	ran := false
	src := cfgtest.Source{Files: map[string][]byte{"v.json": []byte(`{"a":1}`)}}
	p, _ := cfg.New(cfg.Config{
		Format: cfg.FormatJSON,
		Validators: []cfg.Validator{
			recordingValidator{ran: &ran, emit: cfg.Diagnostic{Severity: cfg.SeverityError, Summary: "x"}},
		},
	}, cfg.Deps{Source: src})
	_, diags, err := p.Parse(context.Background(), "v.json")
	if err != nil {
		t.Fatal("Validator SeverityError must NOT populate the err channel")
	}
	if !diags.HasError() {
		t.Fatal("Validator SeverityError must populate Diagnostics")
	}
}

func TestParse_ValidatorsRunInOrder(t *testing.T) {
	var order []string
	mk := func(name string) cfg.Validator {
		return orderValidator{name: name, sink: &order}
	}
	src := cfgtest.Source{Files: map[string][]byte{"v.json": []byte(`{"a":1}`)}}
	p, _ := cfg.New(cfg.Config{
		Format:     cfg.FormatJSON,
		Validators: []cfg.Validator{mk("first"), mk("second"), mk("third")},
	}, cfg.Deps{Source: src})
	if _, _, err := p.Parse(context.Background(), "v.json"); err != nil {
		t.Fatalf("Parse err = %v", err)
	}
	want := []string{"first", "second", "third"}
	if strings.Join(order, ",") != strings.Join(want, ",") {
		t.Fatalf("validator order = %v, want %v", order, want)
	}
}

type orderValidator struct {
	name string
	sink *[]string
}

func (v orderValidator) Validate(cfg.Document, *cfg.Diagnostics) {
	*v.sink = append(*v.sink, v.name)
}

// --- Merge ---

func TestMerge_OverlayWins(t *testing.T) {
	src := cfgtest.Source{Files: map[string][]byte{
		"base.json":    []byte(`{"engine":{"maxConcurrency":4,"name":"base"}}`),
		"overlay.json": []byte(`{"engine":{"maxConcurrency":16}}`),
	}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatJSON}, cfg.Deps{Source: src})
	base, _, _ := p.Parse(context.Background(), "base.json")
	overlay, _, _ := p.Parse(context.Background(), "overlay.json")

	merged, _, err := p.Merge(context.Background(), base, overlay)
	if err != nil {
		t.Fatalf("Merge err = %v", err)
	}
	// overlay wins for maxConcurrency
	v, ok := merged.Lookup("engine.maxConcurrency")
	if !ok {
		t.Fatal("merged Lookup(engine.maxConcurrency) ok == false")
	}
	n, _ := v.Int()
	if n != 16 {
		t.Fatalf("merged maxConcurrency = %d, want 16 (overlay wins)", n)
	}
	// base-only key survives
	nv, ok := merged.Lookup("engine.name")
	if !ok {
		t.Fatal("base-only key engine.name lost in merge")
	}
	s, _ := nv.String()
	if s != "base" {
		t.Fatalf("engine.name = %q, want base", s)
	}
}

func TestMerge_PreservesOriginPosition(t *testing.T) {
	src := cfgtest.Source{Files: map[string][]byte{
		"base.env":    []byte("X=base\nY=base\n"),
		"overlay.env": []byte("X=over\n"),
	}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatEnv}, cfg.Deps{Source: src})
	base, _, _ := p.Parse(context.Background(), "base.env")
	overlay, _, _ := p.Parse(context.Background(), "overlay.env")
	merged, _, _ := p.Merge(context.Background(), base, overlay)

	// X comes from the overlay -> origin Source must be overlay.env
	x, _ := merged.Lookup("X")
	if x.At().Source != "overlay.env" {
		t.Fatalf("merged X origin = %q, want overlay.env (overlay leaf keeps its origin)", x.At().Source)
	}
	// Y comes from base only -> origin Source base.env
	y, _ := merged.Lookup("Y")
	if y.At().Source != "base.env" {
		t.Fatalf("merged Y origin = %q, want base.env (base leaf keeps its origin)", y.At().Source)
	}
}

func TestMerge_DoesNotMutateInputs(t *testing.T) {
	src := cfgtest.Source{Files: map[string][]byte{
		"base.json":    []byte(`{"k":1}`),
		"overlay.json": []byte(`{"k":2}`),
	}}
	p, _ := cfg.New(cfg.Config{Format: cfg.FormatJSON}, cfg.Deps{Source: src})
	base, _, _ := p.Parse(context.Background(), "base.json")
	overlay, _, _ := p.Parse(context.Background(), "overlay.json")
	_, _, _ = p.Merge(context.Background(), base, overlay)

	bv, _ := base.Lookup("k")
	bn, _ := bv.Int()
	if bn != 1 {
		t.Fatalf("Merge mutated base: k = %d, want 1", bn)
	}
	ov, _ := overlay.Lookup("k")
	on, _ := ov.Int()
	if on != 2 {
		t.Fatalf("Merge mutated overlay: k = %d, want 2", on)
	}
}
