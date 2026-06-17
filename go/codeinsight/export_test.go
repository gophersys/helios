package codeinsight

// export_test.go is the white-box seam: it re-exports the pure, unexported helpers so the black-box
// (package codeinsight_test) unit suite can table-test them directly without widening the public API
// surface (these are implementation details the contract does not freeze). This is the house idiom
// for unit-testing internals while keeping tests in package x_test (the testpackage rule).

import (
	"go/ast"
	"go/parser"
	"go/token"
	"testing"
)

// ParseLogForTest exposes parseLog (the git-log stream parser) to the unit suite.
func ParseLogForTest(raw []byte) []Commit { return parseLog(raw) }

// NormalizeRenamePathForTest exposes normalizeRenamePath (git rename collapsing) to the unit suite.
func NormalizeRenamePathForTest(raw string) string { return normalizeRenamePath(raw) }

// MaintainabilityIndexForTest exposes the per-function maintainability index to the unit suite.
func MaintainabilityIndexForTest(volume float64, cyclomatic, lines int) float64 {
	return maintainabilityIndex(volume, cyclomatic, lines)
}

// SqaleRatingForTest exposes the SQALE A–E band mapping to the unit suite.
func SqaleRatingForTest(ratio float64) string { return sqaleRating(ratio) }

// BusFactorForTest exposes the >50%-ownership bus-factor computation to the unit suite.
func BusFactorForTest(shares []float64) int { return busFactor(shares) }

// CyclomaticForTest parses src, finds its first function, and returns its cyclomatic complexity.
func CyclomaticForTest(t *testing.T, src string) int {
	t.Helper()
	return cyclomaticComplexity(firstFuncForTest(t, src))
}

// CognitiveForTest parses src, finds its first function, and returns its cognitive complexity.
func CognitiveForTest(t *testing.T, src string) int {
	t.Helper()
	return cognitiveComplexity(firstFuncForTest(t, src))
}

// RecordCoChangesForTest exposes recordCoChanges (and the symmetric pair count) to the unit suite,
// returning the number of distinct pairs recorded and the count for the (a,b) pair.
func RecordCoChangesForTest(touched []string, a, b string) (pairCount, abCount int) {
	pairs := map[pairKey]int{}
	recordCoChanges(touched, pairs)
	return len(pairs), pairs[makePairKey(a, b)]
}

// firstFuncForTest parses src and returns its first function declaration.
func firstFuncForTest(t *testing.T, src string) *ast.FuncDecl {
	t.Helper()
	fileSet := token.NewFileSet()
	file, err := parser.ParseFile(fileSet, "x.go", src, 0)
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	for _, decl := range file.Decls {
		if fn, ok := decl.(*ast.FuncDecl); ok && fn.Body != nil {
			return fn
		}
	}
	t.Fatal("no function found")
	return nil
}
