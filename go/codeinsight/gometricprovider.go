package codeinsight

import (
	"go/ast"
	"go/parser"
	"go/scanner"
	"go/token"
	"math"
	"os"
	"strings"
)

// GoMetricProvider computes the static metrics for one Go source file natively from go/ast — no
// subprocess (OD-CI-4: the Go MetricProvider). It computes cyclomatic, cognitive, Halstead volume,
// and the maintainability index PER FUNCTION, then aggregates the maintainability index to the file
// as a LOC-weighted average (the design fix: a whole-file cyclomatic summed into one index saturates
// it to 0 on any large file, rating everything E; per-function aggregation makes the rating
// discriminate). File cyclomatic and cognitive stay sums. The zero value is usable; construct via
// NewGoMetricProvider for symmetry with the rest of the hexagon.
type GoMetricProvider struct{}

// compile-time assertion: *GoMetricProvider implements the MetricProvider port.
var _ MetricProvider = (*GoMetricProvider)(nil)

// NewGoMetricProvider returns the native-AST Go MetricProvider (the v1 default provider, contract
// §4). It is pure: it parses no file until Metrics is called.
func NewGoMetricProvider() *GoMetricProvider { return &GoMetricProvider{} }

// Supports reports whether language is Go (the only language this provider computes).
func (*GoMetricProvider) Supports(language string) bool { return language == "go" }

// Metrics computes the per-file static metrics for absolutePath, a Go source file. It returns
// ok=false (a skip, never fatal) for an unreadable, unparseable (e.g. build-tagged), or non-Go
// file, so one odd file never aborts a whole report. A `_test.go` file is intentionally skipped —
// test code is not the maintainability surface the rating measures.
func (p *GoMetricProvider) Metrics(language, absolutePath string) (FileMetrics, bool) {
	if !p.Supports(language) {
		return FileMetrics{}, false
	}
	if strings.HasSuffix(absolutePath, "_test.go") {
		return FileMetrics{}, false
	}
	source, err := os.ReadFile(absolutePath) // #nosec G304 -- absolutePath is a repository file joined from the bound repository path; reading the source the analyzer was pointed at IS the function.
	if err != nil {
		return FileMetrics{}, false
	}
	fileSet := token.NewFileSet()
	file, err := parser.ParseFile(fileSet, absolutePath, source, 0)
	if err != nil {
		return FileMetrics{}, false // unparseable (e.g. build-tagged) — skip, not fatal
	}
	return fileMetrics(fileSet, source, file), true
}

// fileMetrics computes the file-level metrics from the parsed AST and source: cyclomatic and
// cognitive as the per-function sums, and the maintainability index as the LOC-weighted average of
// the per-function maintainability index (the design fix). The Halstead volume that feeds each
// function's index is apportioned from the file's total volume by the function's share of the file's
// function-body lines (go/scanner has no per-function token stream without re-slicing source).
func fileMetrics(fileSet *token.FileSet, source []byte, file *ast.File) FileMetrics {
	lines := countLines(source)
	fileVolume := halsteadVolume(source)

	functions := functionMetrics(fileSet, file)
	cyclomatic, cognitive := 0, 0
	for i := range functions {
		cyclomatic += functions[i].cyclomatic
		cognitive += functions[i].cognitive
	}

	return FileMetrics{
		Lines:           lines,
		Cyclomatic:      cyclomatic,
		Cognitive:       cognitive,
		Maintainability: round(aggregateMaintainability(functions, fileVolume), 1),
	}
}

// functionStat is the per-function metric tuple the file aggregates from.
type functionStat struct {
	cyclomatic int
	cognitive  int
	lines      int // the function body's line span (the LOC weight)
}

// functionMetrics computes per-function cyclomatic, cognitive, and body line span for every function
// declaration in the file.
func functionMetrics(fileSet *token.FileSet, file *ast.File) []functionStat {
	functions := make([]functionStat, 0, len(file.Decls))
	for _, decl := range file.Decls {
		fn, ok := decl.(*ast.FuncDecl)
		if !ok || fn.Body == nil {
			continue
		}
		functions = append(functions, functionStat{
			cyclomatic: cyclomaticComplexity(fn),
			cognitive:  cognitiveComplexity(fn),
			lines:      functionLineSpan(fileSet, fn),
		})
	}
	return functions
}

// functionLineSpan returns the number of source lines the function declaration spans (at least 1) —
// the LOC weight for the maintainability aggregation.
func functionLineSpan(fileSet *token.FileSet, fn *ast.FuncDecl) int {
	start, end := fn.Pos(), fn.End()
	if !start.IsValid() || !end.IsValid() {
		return 1
	}
	span := fileSet.Position(end).Line - fileSet.Position(start).Line + 1
	if span < 1 {
		return 1
	}
	return span
}

// aggregateMaintainability is the design fix: compute the maintainability index PER FUNCTION (from
// the function's apportioned Halstead volume, its own cyclomatic, and its line span) and aggregate
// to the file as a LOC-weighted average. A file with no functions (e.g. only declarations) reports
// the trivial 100. The per-function volume is the file volume apportioned by the function's share of
// the total function line span — a transparent split that keeps a small simple function rating high
// even inside a large file, the discrimination the whole-file sum destroyed.
func aggregateMaintainability(functions []functionStat, fileVolume float64) float64 {
	totalLines := 0
	for i := range functions {
		totalLines += functions[i].lines
	}
	if len(functions) == 0 || totalLines == 0 {
		return 100
	}
	weighted, weight := 0.0, 0.0
	for i := range functions {
		share := float64(functions[i].lines) / float64(totalLines)
		functionVolume := fileVolume * share
		index := maintainabilityIndex(functionVolume, functions[i].cyclomatic, functions[i].lines)
		weighted += index * float64(functions[i].lines)
		weight += float64(functions[i].lines)
	}
	if weight == 0 {
		return 100
	}
	return weighted / weight
}

// cyclomaticComplexity = 1 + the number of decision points in the function body (research §2 F1).
func cyclomaticComplexity(fn *ast.FuncDecl) int {
	complexity := 1
	ast.Inspect(fn.Body, func(node ast.Node) bool {
		switch n := node.(type) {
		case *ast.IfStmt, *ast.ForStmt, *ast.RangeStmt, *ast.CaseClause, *ast.CommClause:
			complexity++
		case *ast.BinaryExpr:
			if n.Op == token.LAND || n.Op == token.LOR {
				complexity++
			}
		}
		return true
	})
	return complexity
}

// cognitiveComplexity is the nesting-aware readability proxy (research §R2): each control-flow break
// adds 1 plus the current nesting depth; a boolean operator sequence adds a flat 1. It deliberately
// does not reward shorthand, matching SonarSource's intent.
func cognitiveComplexity(fn *ast.FuncDecl) int {
	return cognitiveWalk(fn.Body, 0)
}

// cognitiveWalk accumulates the cognitive score of node at the given nesting depth.
func cognitiveWalk(node ast.Node, nesting int) int {
	switch n := node.(type) {
	case *ast.IfStmt:
		return cognitiveIf(n, nesting)
	case *ast.ForStmt:
		return 1 + nesting + cognitiveChildren(n.Body, nesting+1)
	case *ast.RangeStmt:
		return 1 + nesting + cognitiveChildren(n.Body, nesting+1)
	case *ast.SwitchStmt:
		return 1 + nesting + cognitiveChildren(n.Body, nesting+1)
	case *ast.TypeSwitchStmt:
		return 1 + nesting + cognitiveChildren(n.Body, nesting+1)
	case *ast.BinaryExpr:
		score := 0
		if n.Op == token.LAND || n.Op == token.LOR {
			score = 1
		}
		return score + cognitiveChildren(node, nesting)
	}
	return cognitiveChildren(node, nesting)
}

// cognitiveIf scores an if statement: a +1+nesting structural increment for the if, the else branch,
// and the recursive score of the condition, init, and both bodies.
func cognitiveIf(n *ast.IfStmt, nesting int) int {
	score := 1 + nesting
	score += cognitiveChildren(n.Body, nesting+1)
	if n.Else != nil {
		score++ // else / else-if structural increment
		score += cognitiveChildren(n.Else, nesting+1)
	}
	if n.Init != nil {
		score += cognitiveWalk(n.Init, nesting)
	}
	score += cognitiveWalk(n.Cond, nesting)
	return score
}

// cognitiveChildren sums the cognitive score of a node's immediate AST children at the given nesting.
func cognitiveChildren(node ast.Node, nesting int) int {
	score := 0
	for _, child := range childNodes(node) {
		score += cognitiveWalk(child, nesting)
	}
	return score
}

// childNodes returns the immediate AST children of a node (one level; the cognitive walker drives
// the recursion).
func childNodes(node ast.Node) []ast.Node {
	if node == nil {
		return nil
	}
	var children []ast.Node
	ast.Inspect(node, func(n ast.Node) bool {
		if n == node || n == nil {
			return true
		}
		children = append(children, n)
		return false // only the first level; recursion is driven by the cognitive walker
	})
	return children
}

// halsteadVolume = N * log2(n) where N is total tokens and n is distinct tokens, bucketed into
// operators and operands over the file's token stream (research §R2). It is an approximation
// sufficient to drive the maintainability index.
func halsteadVolume(source []byte) float64 {
	distinctOperators, distinctOperands := map[string]struct{}{}, map[string]struct{}{}
	totalOperators, totalOperands := scanHalstead(source, distinctOperators, distinctOperands)

	vocabulary := len(distinctOperators) + len(distinctOperands)
	length := totalOperators + totalOperands
	if vocabulary == 0 || length == 0 {
		return 0
	}
	return float64(length) * math.Log2(float64(vocabulary))
}

// scanHalstead tokenizes source and tallies operator/operand totals into the distinct-token sets,
// returning the running totals.
func scanHalstead(source []byte, distinctOperators, distinctOperands map[string]struct{}) (totalOperators, totalOperands int) {
	fileSet := token.NewFileSet()
	file := fileSet.AddFile("", fileSet.Base(), len(source))
	var s scanner.Scanner
	s.Init(file, source, nil, 0)

	for {
		_, tok, literal := s.Scan()
		if tok == token.EOF {
			break
		}
		switch {
		case tok.IsOperator() || tok.IsKeyword():
			totalOperators++
			distinctOperators[tok.String()] = struct{}{}
		case tok == token.IDENT || tok.IsLiteral():
			totalOperands++
			key := literal
			if key == "" {
				key = tok.String()
			}
			distinctOperands[key] = struct{}{}
		}
	}
	return totalOperators, totalOperands
}

// maintainabilityIndex is the Visual Studio rescaled formula, clamped to 0–100 (research §2 F2). The
// rescale (×100/171) maps the classic 0–171 index onto 0–100, but a trivially small Halstead volume
// (a tiny function) yields a raw value above 171, so the result is clamped at BOTH ends, not just
// floored at 0 — the contract's stated 0–100 range.
func maintainabilityIndex(volume float64, cyclomatic, lines int) float64 {
	if volume <= 0 || lines <= 0 {
		return 100
	}
	raw := 171.0 - 5.2*math.Log(volume) - 0.23*float64(cyclomatic) - 16.2*math.Log(float64(lines))
	rescaled := raw * 100.0 / 171.0
	if rescaled < 0 {
		return 0
	}
	if rescaled > 100 {
		return 100
	}
	return rescaled
}

// countLines counts the source lines (a trailing newline does not add a phantom line).
func countLines(source []byte) int {
	if len(source) == 0 {
		return 0
	}
	text := string(source)
	lines := strings.Count(text, "\n")
	if !strings.HasSuffix(text, "\n") {
		lines++
	}
	return lines
}
