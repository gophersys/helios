package configuration_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/configurationtest"
)

// The sinks keep the compiler from eliding the benchmarked work and keep return values consumed.
// `any` keeps them off any sentinel/errname path. They must be package-level so the compiler
// cannot prove the result dead and elide the work being measured (ADR-0020 §g).
//
//nolint:gochecknoglobals // benchmark sinks; see comment above.
var (
	sink     any
	sinkBool bool
)

// benchJSONText is the representative parse fixture: a small nested object with an array and mixed
// scalar leaves — the shape a service config takes at the edge.
const benchJSONText = `{"engine":{"models":[{"name":"a","weight":1},{"name":"b","weight":2}]},"port":8080,"flags":{"debug":true,"trace":false}}`

// BenchmarkParse measures the parse spine — the hottest path (every composition-root boot parses
// each source once). The performance lane (`ctl.sh bench` / `bench-guard`, ADR-0020 dimension (g))
// records this at -benchmem -count=10 and benchstat guards HEAD vs the .benchbaseline so a
// regression > +10% allocs/bytes fails.
func BenchmarkParse(b *testing.B) {
	src := configurationtest.Source{Files: map[string][]byte{"c.json": []byte(benchJSONText)}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		b.Fatalf("New err = %v", err)
	}
	ctx := context.Background()
	var (
		doc  configuration.Document
		perr error
	)
	b.ReportAllocs()
	for b.Loop() {
		doc, _, perr = p.Parse(ctx, "c.json")
	}
	if perr != nil {
		b.Fatalf("Parse err = %v", perr)
	}
	sink = doc
}

// BenchmarkLookup measures the read spine — a typed library Config reads each leaf it needs by
// Path. The Document is parsed once outside the loop; only the resolve+convert is measured.
func BenchmarkLookup(b *testing.B) {
	src := configurationtest.Source{Files: map[string][]byte{"c.json": []byte(benchJSONText)}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		b.Fatalf("New err = %v", err)
	}
	doc, _, err := p.Parse(context.Background(), "c.json")
	if err != nil {
		b.Fatalf("seed Parse err = %v", err)
	}
	var name string
	b.ReportAllocs()
	for b.Loop() {
		v, _ := doc.Lookup("engine.models[1].name")
		name, _ = v.String()
	}
	sink = name
}

// BenchmarkMerge measures the stage-overlay fold — the env-override / staging layering path.
func BenchmarkMerge(b *testing.B) {
	src := configurationtest.Source{Files: map[string][]byte{
		"base.json":    []byte(`{"port":8080,"flags":{"debug":false,"trace":false},"name":"svc"}`),
		"overlay.json": []byte(`{"port":9090,"flags":{"debug":true}}`),
	}}
	p, err := configuration.New(configuration.Config{Format: configuration.FormatJSON}, configuration.Deps{Source: src})
	if err != nil {
		b.Fatalf("New err = %v", err)
	}
	base, _, berr := p.Parse(context.Background(), "base.json")
	if berr != nil {
		b.Fatalf("Parse(base) err = %v", berr)
	}
	overlay, _, oerr := p.Parse(context.Background(), "overlay.json")
	if oerr != nil {
		b.Fatalf("Parse(overlay) err = %v", oerr)
	}
	ctx := context.Background()
	var (
		merged configuration.Document
		merr   error
	)
	b.ReportAllocs()
	for b.Loop() {
		merged, _, merr = p.Merge(ctx, base, overlay)
	}
	if merr != nil {
		b.Fatalf("Merge err = %v", merr)
	}
	sink = merged
}

// appendManyN is the scale at which BenchmarkAppendMany accumulates findings one at a time. It is
// large enough that a quadratic Append (clone-the-whole-backing-array per call) shows up as
// O(n^2) allocs in the benchstat baseline, so bench-guard pins the accumulate-all complexity:
// amortized append is ~n allocs/op, a re-clone-per-call regression is ~n^2.
const appendManyN = 10000

// BenchmarkAppendMany measures the accumulate-all hot path: a parse/validation pass appends every
// finding into one Diagnostics sink one Append at a time. Append must be amortized O(1) growth
// (ordinary append into spare capacity), not an O(n) clone of the whole backing slice on every
// call — the latter makes the whole accumulation O(n^2). Recorded in .benchbaseline so a
// regression-to-quadratic trips the allocs/op ceiling (ADR-0020 §g; the configuration performance
// finding). The single Diagnostic is hoisted so only the append growth is measured.
func BenchmarkAppendMany(b *testing.B) {
	one := configuration.Diagnostic{Severity: configuration.SeverityError, Path: "k", Summary: "dup"}
	var d configuration.Diagnostics
	b.ReportAllocs()
	for b.Loop() {
		var acc configuration.Diagnostics
		for range appendManyN {
			acc.Append(one)
		}
		d = acc
	}
	sink = d.All()
}

// BenchmarkConvertMismatch measures the total-conversion failure path (the diagnostic-building
// spine a validation pass exercises heavily). sinkBool keeps the bool result live.
func BenchmarkConvertMismatch(b *testing.B) {
	doc := configurationtest.Doc(map[string]any{"s": "not-a-number"})
	v, _ := doc.Lookup("s")
	var hadDiag bool
	b.ReportAllocs()
	for b.Loop() {
		_, d := v.Int()
		hadDiag = d != nil
	}
	sinkBool = hadDiag
}
