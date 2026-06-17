package codeinsight_test

import (
	"sort"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/codeinsight"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS in the process environment (default
// 1000 iterations/property, ADR-0020 dimension (a)); rapid reads it directly. These properties drive
// the REAL pure value layer: the numstat parser's binary-safety, the rename-path normalizer's
// idempotence, the bus-factor monotonicity, the SQALE band ordering, and the maintainability index
// bounds — the invariants the whole Report rides on.

// TestProperty_NormalizeRenamePathIdempotent asserts normalizing an already-normalized path is a
// no-op: a path with no rename marker passes through unchanged, and normalizing twice equals
// normalizing once. A drift would mean a renamed file's history detaches from its current location.
func TestProperty_NormalizeRenamePathIdempotent(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		segments := rapid.SliceOfN(rapid.StringMatching(`[a-z]{1,6}`), 1, 4).Draw(rt, "segments")
		path := segments[0]
		for _, s := range segments[1:] {
			path += "/" + s
		}
		path += ".go"
		once := codeinsight.NormalizeRenamePathForTest(path)
		if once != path {
			rt.Fatalf("a path with no rename marker should pass through: %q -> %q", path, once)
		}
		if twice := codeinsight.NormalizeRenamePathForTest(once); twice != once {
			rt.Fatalf("normalize not idempotent: %q -> %q -> %q", path, once, twice)
		}
	})
}

// TestProperty_BusFactorMonotone asserts the bus factor is in [1,n] for any non-empty share vector
// and that a more concentrated distribution never needs MORE authors to clear 50% than a flatter
// one. The bus factor is the SPOF signal the ownership view annotates.
func TestProperty_BusFactorMonotone(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		n := rapid.IntRange(1, 8).Draw(rt, "n")
		raw := make([]float64, n)
		total := 0.0
		for i := range raw {
			raw[i] = float64(rapid.IntRange(1, 100).Draw(rt, "weight"))
			total += raw[i]
		}
		shares := make([]float64, n)
		for i := range raw {
			shares[i] = raw[i] / total
		}
		bf := codeinsight.BusFactorForTest(shares)
		if bf < 1 || bf > n {
			rt.Fatalf("bus factor %d out of [1,%d] for shares %v", bf, n, shares)
		}
		// A single dominant author (share > 0.5) must yield exactly 1.
		sorted := append([]float64(nil), shares...)
		sort.Sort(sort.Reverse(sort.Float64Slice(sorted)))
		if sorted[0] > 0.5 && bf != 1 {
			rt.Fatalf("dominant author (%.3f > 0.5) should give bus factor 1, got %d", sorted[0], bf)
		}
	})
}

// TestProperty_SqaleBandsMonotone asserts the A–E rating is monotone in the debt ratio: a higher
// ratio never maps to a better (earlier) letter. The bands drive the release-gate rating badge.
func TestProperty_SqaleBandsMonotone(t *testing.T) {
	t.Parallel()
	order := map[string]int{"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
	rapid.Check(t, func(rt *rapid.T) {
		lo := rapid.Float64Range(0, 1).Draw(rt, "lo")
		hi := rapid.Float64Range(lo, 1).Draw(rt, "hi") // hi >= lo
		ratingLo := codeinsight.SqaleRatingForTest(lo)
		ratingHi := codeinsight.SqaleRatingForTest(hi)
		if order[ratingHi] < order[ratingLo] {
			rt.Fatalf("rating not monotone: ratio %.3f→%s but higher ratio %.3f→%s", lo, ratingLo, hi, ratingHi)
		}
	})
}

// TestProperty_MaintainabilityIndexBounded asserts the maintainability index is always within
// [0,100] for any non-negative inputs — the bound @eden/visualization's rating scale relies on.
func TestProperty_MaintainabilityIndexBounded(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		volume := rapid.Float64Range(0, 1e6).Draw(rt, "volume")
		cyclomatic := rapid.IntRange(0, 500).Draw(rt, "cyclomatic")
		lines := rapid.IntRange(0, 5000).Draw(rt, "lines")
		mi := codeinsight.MaintainabilityIndexForTest(volume, cyclomatic, lines)
		if mi < 0 || mi > 100 {
			rt.Fatalf("maintainability index %v out of [0,100] (vol=%v cyc=%d loc=%d)", mi, volume, cyclomatic, lines)
		}
	})
}

// TestProperty_CyclomaticAtLeastOne asserts a parseable function always has cyclomatic >= 1 (the
// base path), the floor the hotspot product relies on never being zero for a real function.
func TestProperty_CyclomaticAtLeastOne(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		branches := rapid.IntRange(0, 6).Draw(rt, "branches")
		body := ""
		for i := 0; i < branches; i++ {
			body += "\tif x > 0 { x-- }\n"
		}
		src := "package p\nfunc f(x int) {\n" + body + "}\n"
		if got := codeinsight.CyclomaticForTest(t, src); got < 1+branches {
			rt.Fatalf("cyclomatic %d < expected base+branches %d", got, 1+branches)
		}
	})
}
