package checker

import (
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// goPackage is the resolved name of the Go package living directly in a single
// directory (one directory holds at most one non-test package, by Go's rules).
type goPackage struct {
	dir  string // directory holding the package, relative to the library root
	name string // the package clause, e.g. "configuration"
}

// scanPackages walks root and returns, for every directory that contains
// buildable (non-_test) Go source, the package name declared there. The walk
// skips dot-directories and any "testdata" tree (mirroring the go tool), so the
// result is the set of real packages the library publishes plus its internals.
//
// Directories holding only *_test.go files are reported under the base package
// name (the external "<pkg>_test" suffix is stripped) so an all-tests directory
// still surfaces for the banned-token check.
func scanPackages(root string) ([]goPackage, error) {
	byDir := map[string]string{}
	fset := token.NewFileSet()

	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			name := d.Name()
			if path != root && (strings.HasPrefix(name, ".") || name == "testdata") {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(path, ".go") {
			return nil
		}
		f, perr := parser.ParseFile(fset, path, nil, parser.PackageClauseOnly)
		if perr != nil {
			// A file we cannot parse is not a naming violation; ignore it here.
			// (gofmt/go vet own syntax correctness.)
			return nil //nolint:nilerr // parse failures are out of scope for naming
		}
		dir := filepath.Dir(path)
		pkg := strings.TrimSuffix(f.Name.Name, "_test")
		// Prefer a non-test package name if both an in-package test file and a
		// real source file live in the same directory.
		if existing, ok := byDir[dir]; ok {
			if existing != "" && !strings.HasSuffix(f.Name.Name, "_test") {
				byDir[dir] = pkg
			}
			return nil
		}
		byDir[dir] = pkg
		return nil
	})
	if err != nil {
		return nil, err
	}

	pkgs := make([]goPackage, 0, len(byDir))
	for dir, name := range byDir {
		rel, rerr := filepath.Rel(root, dir)
		if rerr != nil {
			rel = dir
		}
		pkgs = append(pkgs, goPackage{dir: rel, name: name})
	}
	sort.Slice(pkgs, func(i, j int) bool { return pkgs[i].dir < pkgs[j].dir })
	return pkgs, nil
}
