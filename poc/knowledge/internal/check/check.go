// Package check implements the C1 oracles: deterministic static checkers,
// one per rule, over go/ast + go/types. This is the "rule → checker
// compilation" layer — every violation message carries the rule ID and, when
// requested, the rule's fix hint (the checker-feedback arm delivers knowledge
// exclusively through these messages).
package check

import (
	"fmt"
	"go/token"
	"path/filepath"
	"sort"
	"strings"

	"golang.org/x/tools/go/packages"
)

// Violation is one rule breach at one position.
type Violation struct {
	Rule    string `json:"rule"`
	Pos     string `json:"pos"` // path:line:col, path relative to the analyzed dir
	Message string `json:"message"`
}

// Checker is one compiled rule oracle.
type Checker struct {
	Rule string
	Run  func(ctx *Context) []Violation
}

// Options tunes checker strictness.
type Options struct {
	// TransitivePurity extends go/constructor-purity with a package-local
	// call-graph fixpoint: New* is impure if anything it (transitively)
	// calls within the package performs a forbidden call. v2 semantics —
	// keep OFF when scoring an experiment whose checker arm gated on v1.
	TransitivePurity bool
}

// Context hands a checker everything it needs for one package.
type Context struct {
	Pkg     *packages.Package
	Fset    *token.FileSet
	Dir     string // root dir under analysis, for relative positions
	Options Options
}

func (c *Context) pos(p token.Pos) string {
	position := c.Fset.Position(p)
	rel, err := filepath.Rel(c.Dir, position.Filename)
	if err != nil || strings.HasPrefix(rel, "..") {
		rel = position.Filename
	}
	return fmt.Sprintf("%s:%d:%d", rel, position.Line, position.Column)
}

func (c *Context) violation(rule string, p token.Pos, format string, args ...any) Violation {
	return Violation{Rule: rule, Pos: c.pos(p), Message: fmt.Sprintf(format, args...)}
}

// isTestFile reports whether pos lives in a _test.go file.
func (c *Context) isTestFile(p token.Pos) bool {
	return strings.HasSuffix(c.Fset.Position(p).Filename, "_test.go")
}

// isVerifyFile reports whether pos lives in an injected clean-room verify file
// (never agent-authored; excluded from scoring).
func (c *Context) isVerifyFile(p token.Pos) bool {
	return strings.HasPrefix(filepath.Base(c.Fset.Position(p).Filename), "zz_verify")
}

// Run loads the module at dir (including test files) and runs every checker
// with default (v1) options.
func Run(dir string, checkers []Checker) ([]Violation, error) {
	return RunWithOptions(dir, checkers, Options{})
}

// RunWithOptions is Run with explicit strictness options, returning
// violations sorted and deduplicated (Tests:true loads package variants which
// would otherwise duplicate findings).
func RunWithOptions(dir string, checkers []Checker, options Options) ([]Violation, error) {
	cfg := &packages.Config{
		Mode: packages.NeedName | packages.NeedFiles | packages.NeedSyntax |
			packages.NeedTypes | packages.NeedTypesInfo | packages.NeedImports |
			packages.NeedDeps | packages.NeedModule,
		Dir:   dir,
		Tests: true,
		Env:   nil, // inherit; tasks have no external deps so loads are hermetic
	}
	pkgs, err := packages.Load(cfg, "./...")
	if err != nil {
		return nil, fmt.Errorf("load %s: %w", dir, err)
	}
	var loadErrors []string
	packages.Visit(pkgs, nil, func(p *packages.Package) {
		for _, e := range p.Errors {
			loadErrors = append(loadErrors, e.Error())
		}
	})
	if len(loadErrors) > 0 {
		return nil, fmt.Errorf("packages did not compile:\n%s", strings.Join(loadErrors, "\n"))
	}

	seen := map[string]bool{}
	var all []Violation
	for _, p := range pkgs {
		ctx := &Context{Pkg: p, Fset: p.Fset, Dir: dir, Options: options}
		for _, ch := range checkers {
			for _, v := range ch.Run(ctx) {
				key := v.Rule + "|" + v.Pos + "|" + v.Message
				if !seen[key] {
					seen[key] = true
					all = append(all, v)
				}
			}
		}
	}
	sort.Slice(all, func(i, j int) bool {
		if all[i].Pos != all[j].Pos {
			return all[i].Pos < all[j].Pos
		}
		return all[i].Rule < all[j].Rule
	})
	return all, nil
}
