package checker

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

// suiteEntrypointRe is the required name shape for the ONE conformance-suite
// entrypoint a <lib>test package exposes: Run<Role>Suite (08 §2 — the two-binding
// conformance suite is driven through a single, discoverably-named entrypoint).
// e.g. RunParserSuite, RunManagerSuite, RunProviderSuite.
var suiteEntrypointRe = regexp.MustCompile(`^Run[A-Z][A-Za-z]*Suite$`)

// suiteFakeVariantRe is the ONE sanctioned second entrypoint: the same Run<Role>Suite
// stem with a trailing fake-only qualifier (e.g. RunProviderSuiteWithFake), which runs
// the suite over the in-tree fake without a real-substrate factory. Exactly one such
// variant is permitted in addition to the primary Run<Role>Suite.
var suiteFakeVariantRe = regexp.MustCompile(`^Run[A-Z][A-Za-z]*Suite[A-Z][A-Za-z]*$`)

// checkConformanceEntrypoint enforces the conformance-suite-entrypoint rule on a
// <lib>test package: when the package exposes any exported Run* function (i.e. it
// claims to drive a conformance suite), it MUST expose exactly ONE primary entrypoint
// matching ^Run[A-Z][A-Za-z]*Suite$, optionally plus ONE fake-only variant
// (Run<Role>SuiteWithFake). A bare Run/RunConformance, zero valid Suite entrypoints
// among present Run* funcs, or an ambiguous set FAILS.
//
// A <lib>test package that exports NO Run* function at all is a pure fixtures/helpers
// package (fakes, harness, mint helpers — e.g. agentruntimetest, edenhttptest,
// testingtest) and is intentionally out of scope: it makes no conformance-suite claim.
//
// slug is the library's canonical slug; the fakes package is slug+"test".
func checkConformanceEntrypoint(dir, slug string) []Diagnostic {
	wantPkg := slug + "test"
	testDir := filepath.Join(dir, wantPkg)
	info, err := os.Stat(testDir)
	if err != nil || !info.IsDir() {
		return nil // no <lib>test package; nothing to assert.
	}

	runFuncs, scanErr := exportedRunFuncs(testDir)
	if scanErr != nil {
		return []Diagnostic{{
			Path:    testDir,
			Message: fmt.Sprintf("scanning conformance entrypoints: %v", scanErr),
		}}
	}
	if len(runFuncs) == 0 {
		// Pure fixtures package — no conformance-suite claim.
		return nil
	}

	var primary, variants, malformed []string
	for _, name := range runFuncs {
		switch {
		case suiteEntrypointRe.MatchString(name):
			primary = append(primary, name)
		case suiteFakeVariantRe.MatchString(name):
			variants = append(variants, name)
		default:
			malformed = append(malformed, name)
		}
	}
	sort.Strings(primary)
	sort.Strings(variants)
	sort.Strings(malformed)

	var diags []Diagnostic
	add := func(msg string) {
		diags = append(diags, Diagnostic{Path: testDir, Message: msg})
	}

	switch len(primary) {
	case 0:
		add(fmt.Sprintf(
			"conformance package %q exposes Run* entrypoint(s) %v but none match the required ^Run<Role>Suite$ shape; name the single suite entrypoint Run<Role>Suite (08 §2), not a bare Run/RunConformance",
			wantPkg, runFuncs,
		))
	case 1:
		// Exactly one primary — the conformant case. Any malformed Run* still fails.
		if len(malformed) > 0 {
			add(fmt.Sprintf(
				"conformance package %q has the suite entrypoint %q but also exposes off-pattern Run* func(s) %v; the only permitted second entrypoint is a fake-only Run<Role>SuiteWithFake variant",
				wantPkg, primary[0], malformed,
			))
		}
	default:
		add(fmt.Sprintf(
			"conformance package %q exposes %d ambiguous suite entrypoints %v; expose exactly ONE Run<Role>Suite (08 §2)",
			wantPkg, len(primary), primary,
		))
	}

	if len(variants) > 1 {
		add(fmt.Sprintf(
			"conformance package %q exposes %d fake-only variants %v; only ONE Run<Role>SuiteWithFake is permitted",
			wantPkg, len(variants), variants,
		))
	}

	sort.Slice(diags, func(i, j int) bool { return diags[i].Message < diags[j].Message })
	return diags
}

// exportedRunFuncs returns the names of every exported, Run-prefixed top-level
// function declared in the package directory testDir (the directory itself, not its
// children — a Go package is one directory). Method declarations (a non-nil receiver)
// are excluded: an entrypoint is a package-level func. Both production source and
// in-package test files are scanned, because a conformance entrypoint may live in
// either.
func exportedRunFuncs(testDir string) ([]string, error) {
	entries, err := os.ReadDir(testDir)
	if err != nil {
		return nil, err
	}
	fset := token.NewFileSet()
	var names []string
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".go") {
			continue
		}
		path := filepath.Join(testDir, e.Name())
		f, perr := parser.ParseFile(fset, path, nil, parser.SkipObjectResolution)
		if perr != nil {
			continue // parse failures are out of scope for naming.
		}
		for _, decl := range f.Decls {
			fn, ok := decl.(*ast.FuncDecl)
			if !ok || fn.Recv != nil || !fn.Name.IsExported() {
				continue
			}
			if strings.HasPrefix(fn.Name.Name, "Run") {
				names = append(names, fn.Name.Name)
			}
		}
	}
	sort.Strings(names)
	return names, nil
}
