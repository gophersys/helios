package agentprofile_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/agentprofile/agentprofiletest"
)

// ADR-0020 dimension (g) — the performance lane. `ctl.sh bench` records these at -benchmem -count=10
// and `bench-guard` fails the gate when a hot path regresses more than +10% in time or allocations at
// benchstat p<0.05. EDEN_HOT_PATHS is "." for this lib, so every benchmark below is under guard.
//
// The sinks prevent the compiler from proving the measured work dead and eliding it. `any` keeps them
// off any typed sentinel path, and they are package-level so the optimizer cannot see across the
// benchmark boundary.
//
//nolint:gochecknoglobals // benchmark sinks must be package-level so the compiler cannot elide the measured work.
var (
	sink       any
	sinkDigest string
)

// benchDocument is the fixture every hot path is measured over: the conformance document with the
// full precedence chain in play, so the numbers reflect real composition work rather than a
// degenerate single-layer document.
//
//nolint:gochecknoglobals // one fixture shared by every benchmark, built once at init cost.
var benchDocument = agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)

// benchTarget is the cell every hot path addresses.
func benchTarget() agentprofile.Target {
	return agentprofile.Target{Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessClaudeCode}
}

// BenchmarkNew measures the constructor spine: parse, validate, select the overlay, bind the
// renderers. It is the cost a composition root pays once per profile document, and it is pure — no
// I/O, no clock — so a regression here is a real algorithmic change rather than environmental noise.
func BenchmarkNew(b *testing.B) {
	dependencies := agentprofile.Deps{
		Renderers: []agentprofile.Renderer{agentprofile.ClaudeRenderer{}},
		Tree:      agentprofiletest.NewTree(),
	}
	configuration := agentprofile.Config{Document: benchDocument, Repository: agentprofiletest.CanonicalOverlay}
	var (
		compiler *agentprofile.Compiler
		err      error
	)
	b.ReportAllocs()
	for b.Loop() {
		compiler, err = agentprofile.New(configuration, dependencies)
	}
	sink = compiler
	sink = err
}

// BenchmarkRender measures the emission spine: resolve the cell through the precedence chain, hand
// the projection to the bound renderer, sort the result, and enforce the emission invariants. This is
// the hottest end-to-end path a caller drives, and it runs once per cell of the matrix.
func BenchmarkRender(b *testing.B) {
	compiler := newBenchCompiler(b, agentprofiletest.NewTree())
	ctx := context.Background()
	target := benchTarget()
	var (
		files agentprofile.FileSet
		err   error
	)
	b.ReportAllocs()
	for b.Loop() {
		files, err = compiler.Render(ctx, target)
	}
	sink = files
	sink = err
}

// BenchmarkDigest measures the content-addressing hash over a real emission: the canonical
// serialization plus one SHA-256 pass. Every profileRef in the estate is produced here, and Digest
// allocates its canonical buffer exactly once, so an allocation regression is a visible design change.
func BenchmarkDigest(b *testing.B) {
	compiler := newBenchCompiler(b, agentprofiletest.NewTree())
	files, err := compiler.Render(context.Background(), benchTarget())
	if err != nil {
		b.Fatalf("Render: %v", err)
	}
	b.ReportAllocs()
	for b.Loop() {
		sinkDigest = files.Digest()
	}
}

// BenchmarkDrift measures the full drift spine over a tree that HOLDS the render — the clean-verdict
// path, which is the one a green CI gate takes on every run and therefore the one whose cost is paid
// most often. It is a fresh render plus one tree read and one byte comparison per emitted file.
func BenchmarkDrift(b *testing.B) {
	document := benchDocument
	seed := newBenchCompiler(b, agentprofiletest.NewTree())
	rendered, err := seed.Render(context.Background(), benchTarget())
	if err != nil {
		b.Fatalf("seed Render: %v", err)
	}
	compiler := newBenchCompiler(b, agentprofiletest.NewTree().WithFileSet(rendered))
	_ = document
	ctx := context.Background()
	target := benchTarget()
	var divergences []agentprofile.Divergence
	b.ReportAllocs()
	for b.Loop() {
		divergences, err = compiler.Drift(ctx, target)
	}
	sink = divergences
	sink = err
}

// BenchmarkDriftAllMissing measures the OTHER drift verdict: an empty tree, so every rendered file
// produces a divergence and the summary strings are all built. It is the worst case a first-run
// consumer hits, and it is the path that allocates the most.
func BenchmarkDriftAllMissing(b *testing.B) {
	compiler := newBenchCompiler(b, agentprofiletest.NewTree())
	ctx := context.Background()
	target := benchTarget()
	var (
		divergences []agentprofile.Divergence
		err         error
	)
	b.ReportAllocs()
	for b.Loop() {
		divergences, err = compiler.Drift(ctx, target)
	}
	sink = divergences
	sink = err
}

// newBenchCompiler builds a Compiler over the bench fixture with the real ClaudeRenderer.
func newBenchCompiler(b *testing.B, tree agentprofile.Tree) *agentprofile.Compiler {
	b.Helper()
	compiler, err := agentprofile.New(
		agentprofile.Config{Document: benchDocument, Repository: agentprofiletest.CanonicalOverlay},
		agentprofile.Deps{Renderers: []agentprofile.Renderer{agentprofile.ClaudeRenderer{}}, Tree: tree},
	)
	if err != nil {
		b.Fatalf("New: %v", err)
	}
	return compiler
}
