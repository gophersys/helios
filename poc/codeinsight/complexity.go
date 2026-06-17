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

// staticMetrics are the per-file numbers computed natively from the Go AST — no
// subprocess (OD-CI-4: the Go MetricProvider). Non-Go files yield a zero value and are
// reported with their line count only.
type staticMetrics struct {
	lines           int
	cyclomatic      int
	cognitive       int
	maintainability float64
}

// analyzeGoFile computes the static metrics for one Go source file. Cyclomatic follows the
// verified definition (research §2 F1: 1 + each branch, summed per function). Cognitive is
// the SonarSource nesting-aware approximation (structural increment + a nesting penalty).
// Maintainability is the Visual Studio rescaled index from Halstead volume, cyclomatic, and
// LOC (research §2 F2).
func analyzeGoFile(path string) (staticMetrics, bool) {
	source, err := os.ReadFile(path)
	if err != nil {
		return staticMetrics{}, false
	}
	fileSet := token.NewFileSet()
	file, err := parser.ParseFile(fileSet, path, source, 0)
	if err != nil {
		return staticMetrics{}, false // unparseable (e.g. build-tagged) — skip, not fatal
	}

	lines := countLines(source)
	cyclomatic, cognitive := 0, 0
	for _, decl := range file.Decls {
		fn, ok := decl.(*ast.FuncDecl)
		if !ok || fn.Body == nil {
			continue
		}
		cyclomatic += cyclomaticComplexity(fn)
		cognitive += cognitiveComplexity(fn)
	}

	volume := halsteadVolume(source)
	return staticMetrics{
		lines:           lines,
		cyclomatic:      cyclomatic,
		cognitive:       cognitive,
		maintainability: maintainabilityIndex(volume, cyclomatic, lines),
	}, true
}

// cyclomaticComplexity = 1 + the number of decision points in the function body.
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

// cognitiveComplexity is the nesting-aware readability proxy (research §R2): each
// control-flow break adds 1 plus the current nesting depth; boolean operator sequences add
// a flat 1. It deliberately does not reward shorthand, matching SonarSource's intent.
func cognitiveComplexity(fn *ast.FuncDecl) int {
	var walk func(node ast.Node, nesting int) int
	walk = func(node ast.Node, nesting int) int {
		score := 0
		switch n := node.(type) {
		case *ast.IfStmt:
			score += 1 + nesting
			score += walkChildren(n.Body, nesting+1, walk)
			if n.Else != nil {
				score++ // else / else-if structural increment
				score += walkChildren(n.Else, nesting+1, walk)
			}
			if n.Init != nil {
				score += walk(n.Init, nesting)
			}
			score += walk(n.Cond, nesting)
			return score
		case *ast.ForStmt:
			score += 1 + nesting
			score += walkChildren(n.Body, nesting+1, walk)
			return score
		case *ast.RangeStmt:
			score += 1 + nesting
			score += walkChildren(n.Body, nesting+1, walk)
			return score
		case *ast.SwitchStmt:
			score += 1 + nesting
			score += walkChildren(n.Body, nesting+1, walk)
			return score
		case *ast.TypeSwitchStmt:
			score += 1 + nesting
			score += walkChildren(n.Body, nesting+1, walk)
			return score
		case *ast.BinaryExpr:
			if n.Op == token.LAND || n.Op == token.LOR {
				score++
			}
		}
		for _, child := range childNodes(node) {
			score += walk(child, nesting)
		}
		return score
	}
	return walk(fn.Body, 0)
}

// halsteadVolume = N * log2(n) where N is total tokens and n is distinct tokens, bucketed
// into operators and operands over the file's token stream (research §R2). It is an
// approximation sufficient to drive the maintainability index; the gated library refines it.
func halsteadVolume(source []byte) float64 {
	fileSet := token.NewFileSet()
	file := fileSet.AddFile("", fileSet.Base(), len(source))
	var s scanner.Scanner
	s.Init(file, source, nil, 0)

	distinctOperators := map[string]struct{}{}
	distinctOperands := map[string]struct{}{}
	totalOperators, totalOperands := 0, 0
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

	vocabulary := len(distinctOperators) + len(distinctOperands)
	length := totalOperators + totalOperands
	if vocabulary == 0 || length == 0 {
		return 0
	}
	return float64(length) * math.Log2(float64(vocabulary))
}

// maintainabilityIndex is the Visual Studio rescaled formula, clamped to 0–100 (research §2 F2).
func maintainabilityIndex(volume float64, cyclomatic, lines int) float64 {
	if volume <= 0 || lines <= 0 {
		return 100
	}
	raw := 171.0 - 5.2*math.Log(volume) - 0.23*float64(cyclomatic) - 16.2*math.Log(float64(lines))
	return math.Max(0, raw*100.0/171.0)
}

func countLines(source []byte) int {
	if len(source) == 0 {
		return 0
	}
	lines := strings.Count(string(source), "\n")
	if !strings.HasSuffix(string(source), "\n") {
		lines++
	}
	return lines
}

// walkChildren sums the cognitive score of a node's direct children at the given nesting.
func walkChildren(node ast.Node, nesting int, walk func(ast.Node, int) int) int {
	score := 0
	for _, child := range childNodes(node) {
		score += walk(child, nesting)
	}
	return score
}

// childNodes returns the immediate AST children of a node.
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
