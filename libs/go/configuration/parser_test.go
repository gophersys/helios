package configuration_test

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/configurationtest"
)

// panicSource panics on Read; used to prove New performs no I/O.
type panicSource struct{}

func (panicSource) Read(context.Context, string) ([]byte, error) {
	panic("New must not read from Source")
}

// newParser constructs a Parser and fails the test if New errors. Used by the
// happy-path cases whose Config is known-valid, so an error is a bug in the
// fixture, not the property under test.
//
//nolint:ireturn // configuration.Parser is an interface fixed by contracts/configuration.md §2; this helper forwards the contract surface.
func newParser(t *testing.T, c configuration.Config, src configuration.Source) configuration.Parser {
	t.Helper()
	p, err := configuration.New(c, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v, want nil", err)
	}
	return p
}

// mustParse parses name and fails the test on the I/O error channel, returning
// the (doc, diags) the property cares about. Config-is-wrong stays in diags.
//
//nolint:ireturn // configuration.Document is an interface fixed by contracts/configuration.md §2; this helper forwards the contract surface.
func mustParse(t *testing.T, p configuration.Parser, name string) (configuration.Document, configuration.Diagnostics) {
	t.Helper()
	doc, diags, err := p.Parse(context.Background(), name)
	if err != nil {
		t.Fatalf("Parse(%s) err = %v, want nil", name, err)
	}
	return doc, diags
}

// mustMerge folds base<-overlay and fails the test on the err channel.
//
//nolint:ireturn // configuration.Document is an interface fixed by contracts/configuration.md §2; this helper forwards the contract surface.
func mustMerge(t *testing.T, p configuration.Parser, base, overlay configuration.Document) configuration.Document {
	t.Helper()
	merged, _, err := p.Merge(context.Background(), base, overlay)
	if err != nil {
		t.Fatalf("Merge err = %v, want nil", err)
	}
	return merged
}

// Section: New: purity & validation.
func TestNew_DoesNotTouchSource(t *testing.T) {
	t.Parallel()
	// Constructing with a panicking Source must not panic: New reads nothing.
	p, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: panicSource{}})
	if err != nil {
		t.Fatalf("New returned err = %v, want nil", err)
	}
	if p == nil {
		t.Fatal("New returned nil Parser")
	}
}

func TestNew_RejectsUnknownFormat(t *testing.T) {
	t.Parallel()
	_, err := configuration.New(configuration.Config{Format: configuration.Format("xml")}, configuration.Deps{Source: configurationtest.Source{}})
	if err == nil {
		t.Fatal("New with unknown Format returned nil err, want error")
	}
}

func TestNew_RejectsNegativeMaxSourceBytes(t *testing.T) {
	t.Parallel()
	_, err := configuration.New(
		configuration.Config{Format: configuration.FormatJSON, MaxSourceBytes: -1},
		configuration.Deps{Source: configurationtest.Source{}},
	)
	if err == nil {
		t.Fatal("New with negative MaxSourceBytes returned nil err, want error")
	}
}

func TestNew_AllowsZeroMaxSourceBytes(t *testing.T) {
	t.Parallel()
	// 0 means an internal sane cap, not an error.
	if _, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: configurationtest.Source{}}); err != nil {
		t.Fatalf("New with zero MaxSourceBytes err = %v, want nil", err)
	}
}

// Section: Parse: happy path.
func TestParse_JSON(t *testing.T) {
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"backend.json": []byte(`{"engine":{"maxConcurrency":8,"name":"primary"}}`),
	}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
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
	if doc.Format() != configuration.FormatJSON {
		t.Fatalf("Format() = %q, want json", doc.Format())
	}
	if doc.Origin().Source != "backend.json" {
		t.Fatalf("Origin().Source = %q, want backend.json", doc.Origin().Source)
	}
}

func TestParse_Env(t *testing.T) {
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"app.env": []byte("ENGINE.MAXCONCURRENCY=8\nENGINE.NAME=primary\n# comment\n\n"),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatEnv}, src)
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
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"a.env": []byte("A=1\nB=2\n"),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatEnv}, src)
	doc, _ := mustParse(t, p, "a.env")
	v, _ := doc.Lookup("B")
	if v.At().Line != 2 {
		t.Fatalf("B At().Line = %d, want 2", v.At().Line)
	}
	if v.At().Source != "a.env" {
		t.Fatalf("B At().Source = %q, want a.env", v.At().Source)
	}
}

// Section: Strict by default.
func TestParse_StrictRejectsDuplicateKeys(t *testing.T) {
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"d.json": []byte(`{"a":1,"a":2}`),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatJSON}, src)
	_, diags, err := p.Parse(context.Background(), "d.json")
	if err != nil {
		t.Fatalf("duplicate-key Parse err = %v, want nil (config-is-wrong is data)", err)
	}
	if !diags.HasError() {
		t.Fatal("strict parse of duplicate key did not produce SeverityError")
	}
}

func TestParse_AllowUnknownKeysDowngradesDuplicate(t *testing.T) {
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"d.json": []byte(`{"a":1,"a":2}`),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatJSON, AllowUnknownKeys: true}, src)
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
		if dg.Severity == configuration.SeverityWarning {
			found = true
		}
	}
	if !found {
		t.Fatal("AllowUnknownKeys produced no Warning for the duplicate key")
	}
}

// Section: Diagnostics accumulate (no short-circuit).
func TestParse_AccumulatesMultipleProblems(t *testing.T) {
	t.Parallel()
	// Three duplicate keys => three findings in ONE Parse.
	src := configurationtest.Source{Files: map[string][]byte{
		"m.json": []byte(`{"a":1,"a":2,"b":1,"b":2,"c":1,"c":2}`),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatJSON}, src)
	_, diags := mustParse(t, p, "m.json")
	errCount := 0
	for _, dg := range diags.All() {
		if dg.Severity == configuration.SeverityError {
			errCount++
		}
	}
	if errCount < 3 {
		t.Fatalf("accumulate-all: got %d errors, want >= 3 (one per duplicate)", errCount)
	}
}

// Section: Error-channel discipline.
func TestParse_IOFailureReturnsParseError(t *testing.T) {
	t.Parallel()
	wantErr := errors.New("disk gone")
	src := configurationtest.Source{Err: map[string]error{"x.json": wantErr}}
	p := newParser(t, configuration.Config{Format: configuration.FormatJSON}, src)
	doc, _, err := p.Parse(context.Background(), "x.json")
	if err == nil {
		t.Fatal("I/O failure returned nil err, want *ParseError")
	}
	var pe *configuration.ParseError
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
	t.Parallel()
	// Syntactically invalid JSON is readable => (doc, diags, nil) with HasError.
	src := configurationtest.Source{Files: map[string][]byte{
		"bad.json": []byte(`{"a": }`),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatJSON}, src)
	_, diags, err := p.Parse(context.Background(), "bad.json")
	if err != nil {
		t.Fatalf("syntactically-wrong-but-readable returned err = %v, want nil", err)
	}
	if !diags.HasError() {
		t.Fatal("invalid JSON syntax did not produce a SeverityError diagnostic")
	}
}

func TestParseError_ErrorString(t *testing.T) {
	t.Parallel()
	pe := &configuration.ParseError{Source: "backend.yaml", Err: errors.New("boom")}
	if !strings.Contains(pe.Error(), "backend.yaml") {
		t.Fatalf("ParseError.Error() = %q, want it to contain the source name", pe.Error())
	}
}

// Section: MaxSourceBytes cap.
func TestParse_MaxSourceBytesCap(t *testing.T) {
	t.Parallel()
	big := []byte(`{"k":"` + strings.Repeat("x", 1000) + `"}`)
	src := configurationtest.Source{Files: map[string][]byte{"big.json": big}}
	p := newParser(t, configuration.Config{Format: configuration.FormatJSON, MaxSourceBytes: 16}, src)
	_, diags, err := p.Parse(context.Background(), "big.json")
	// Over-cap is a config/data problem, not an I/O error: report as Diagnostic.
	if err != nil {
		var pe *configuration.ParseError
		if !errors.As(err, &pe) {
			t.Fatalf("over-cap err is not *ParseError: %v", err)
		}
		return // acceptable: surfaced on the error channel as a ParseError
	}
	if !diags.HasError() {
		t.Fatal("source exceeding MaxSourceBytes produced neither err nor SeverityError diag")
	}
}

// Section: Validators run as a phase.
type recordingValidator struct {
	ran  *bool
	emit configuration.Diagnostic
}

func (v *recordingValidator) Validate(_ configuration.Document, into *configuration.Diagnostics) {
	*v.ran = true
	into.Append(v.emit)
}

func TestParse_ValidatorsRunAfterParse(t *testing.T) {
	t.Parallel()
	ran := false
	src := configurationtest.Source{Files: map[string][]byte{"v.json": []byte(`{"a":1}`)}}
	p, err := configuration.New(configuration.Config{
		Format: configuration.FormatJSON,
		Validators: []configuration.Validator{
			&recordingValidator{ran: &ran, emit: configuration.Diagnostic{
				Severity: configuration.SeverityError, Path: "a", Summary: "domain rule",
			}},
		},
	}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
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
	t.Parallel()
	ran := false
	src := configurationtest.Source{Files: map[string][]byte{"v.json": []byte(`{"a":1}`)}}
	p, err := configuration.New(configuration.Config{
		Format: configuration.FormatJSON,
		Validators: []configuration.Validator{
			&recordingValidator{ran: &ran, emit: configuration.Diagnostic{Severity: configuration.SeverityError, Summary: "x"}},
		},
	}, configuration.Deps{Source: src})
	if err != nil {
		t.Fatalf("New err = %v", err)
	}
	_, diags, err := p.Parse(context.Background(), "v.json")
	if err != nil {
		t.Fatal("Validator SeverityError must NOT populate the err channel")
	}
	if !diags.HasError() {
		t.Fatal("Validator SeverityError must populate Diagnostics")
	}
}

func TestParse_ValidatorsRunInOrder(t *testing.T) {
	t.Parallel()
	var order []string
	mk := func(name string) configuration.Validator {
		return orderValidator{name: name, sink: &order}
	}
	src := configurationtest.Source{Files: map[string][]byte{"v.json": []byte(`{"a":1}`)}}
	p := newParser(t, configuration.Config{
		Format:     configuration.FormatJSON,
		Validators: []configuration.Validator{mk("first"), mk("second"), mk("third")},
	}, src)
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

func (v orderValidator) Validate(configuration.Document, *configuration.Diagnostics) {
	*v.sink = append(*v.sink, v.name)
}

// Section: Merge.
func TestMerge_OverlayWins(t *testing.T) {
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"base.json":    []byte(`{"engine":{"maxConcurrency":4,"name":"base"}}`),
		"overlay.json": []byte(`{"engine":{"maxConcurrency":16}}`),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatJSON}, src)
	base, _ := mustParse(t, p, "base.json")
	overlay, _ := mustParse(t, p, "overlay.json")

	merged := mustMerge(t, p, base, overlay)
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
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"base.env":    []byte("X=base\nY=base\n"),
		"overlay.env": []byte("X=over\n"),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatEnv}, src)
	base, _ := mustParse(t, p, "base.env")
	overlay, _ := mustParse(t, p, "overlay.env")
	merged := mustMerge(t, p, base, overlay)

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
	t.Parallel()
	src := configurationtest.Source{Files: map[string][]byte{
		"base.json":    []byte(`{"k":1}`),
		"overlay.json": []byte(`{"k":2}`),
	}}
	p := newParser(t, configuration.Config{Format: configuration.FormatJSON}, src)
	base, _ := mustParse(t, p, "base.json")
	overlay, _ := mustParse(t, p, "overlay.json")
	_ = mustMerge(t, p, base, overlay) // result unused: this test asserts inputs are not mutated

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
