// Package checker implements the structural HNS-1 naming checks that
// golangci-lint's forbidigo cannot express: it verifies, for a single
// libs/go/<slug> module directory, the module path, the primary package name,
// the fakes-package name, and that no directory or package uses a banned
// abbreviation (10 §5, ADR-0018 Layer 1 "hnslint").
//
// The slug is the directory basename. Per HNS-1 the Go disk path is the
// separator-free rendering of the canonical slug, so the on-disk directory name
// *is* the canonical join key: the expected module path is
// github.com/gophersys/libs/go/<basename>, the expected primary package is
// <basename>, and the expected fakes package is <basename>+"test". (v1 slugs are
// single-word; a hypothetical multi-word slug "workspace-provider" lands as the
// directory "workspaceprovider" with package "workspaceprovider", which this
// basename rule renders identically.)
package checker

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"golang.org/x/mod/modfile"
)

// modulePrefix is the required Go-ecosystem module root for every pattern
// library (10 §5).
const modulePrefix = "github.com/gophersys/libs/go/"

// Diagnostic is a single HNS-1 violation: a path and a human-readable message.
type Diagnostic struct {
	Path    string
	Message string
}

// String renders the diagnostic as "path: message" — one violation per line.
func (d Diagnostic) String() string {
	return d.Path + ": " + d.Message
}

// Check runs every structural HNS-1 rule against the library directory dir and
// returns the violations found, sorted deterministically. An empty slice means
// the library conforms. dir is the library root (the directory that holds
// go.mod), e.g. libs/go/configuration.
func Check(dir string) []Diagnostic {
	var diags []Diagnostic

	// Derive the slug from the absolute path so a relative argument (notably the
	// idiomatic ".", run from the library root) yields the real directory name
	// rather than "." — filepath.Base(".") is "." and would otherwise be compared
	// against the module path as the expected slug. Falling back to dir keeps the
	// behavior unchanged when the path cannot be resolved.
	slugDir := dir
	if abs, err := filepath.Abs(dir); err == nil {
		slugDir = abs
	}
	slug := filepath.Base(filepath.Clean(slugDir))

	// Rule 4 (slug): the directory basename itself must not be a banned token.
	if IsBanned(slug) {
		diags = append(diags, Diagnostic{
			Path:    dir,
			Message: fmt.Sprintf("directory name %q is a banned HNS-1 token; use %s", slug, requiredFor(slug)),
		})
	}

	// Rule 1: module path == github.com/gophersys/libs/go/<slug>.
	diags = append(diags, checkModulePath(dir, slug)...)

	// Scan packages once for rules 2, 3, and 4 (package-name half).
	pkgs, err := scanPackages(dir)
	if err != nil {
		diags = append(diags, Diagnostic{
			Path:    dir,
			Message: fmt.Sprintf("scanning packages: %v", err),
		})
		return sortDiagnostics(diags)
	}

	diags = append(diags, checkPackageNames(dir, slug, pkgs)...)

	// Rule 5 (banned exported identifiers): no exported type/field/func/method may
	// be a bare banned token, and no declared type name may be a full-spelled spine
	// outlier (Configuration/Dependencies) — the surface forbidigo cannot see on a
	// capitalized identifier (10 §5; founder ruling 2026-06-15).
	diags = append(diags, checkExportedIdentifiers(dir)...)

	// Rule 6 (conformance-suite entrypoint): a <lib>test package that drives a
	// conformance suite exposes exactly one Run<Role>Suite entrypoint (08 §2).
	diags = append(diags, checkConformanceEntrypoint(dir, slug)...)

	return sortDiagnostics(diags)
}

// sortDiagnostics returns diags ordered by path then message, so Check is
// deterministic regardless of filesystem walk order.
func sortDiagnostics(diags []Diagnostic) []Diagnostic {
	sort.Slice(diags, func(i, j int) bool {
		if diags[i].Path != diags[j].Path {
			return diags[i].Path < diags[j].Path
		}
		return diags[i].Message < diags[j].Message
	})
	return diags
}

// checkModulePath enforces rule 1.
func checkModulePath(dir, slug string) []Diagnostic {
	want := modulePrefix + slug
	goModPath := filepath.Join(dir, "go.mod")

	data, err := os.ReadFile(goModPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return []Diagnostic{{
				Path:    goModPath,
				Message: "go.mod not found; a libs/go library is one Go module per directory (10 §6.1)",
			}}
		}
		return []Diagnostic{{
			Path:    goModPath,
			Message: fmt.Sprintf("reading go.mod: %v", err),
		}}
	}

	got := modfile.ModulePath(data)
	if got == "" {
		return []Diagnostic{{
			Path:    goModPath,
			Message: "go.mod has no module declaration",
		}}
	}
	if got != want {
		return []Diagnostic{{
			Path:    goModPath,
			Message: fmt.Sprintf("module path is %q, want %q", got, want),
		}}
	}
	return nil
}

// checkPackageNames enforces rules 2 (primary package), 3 (fakes package), and
// the package-name half of rule 4 (no banned package or directory names below
// the root).
func checkPackageNames(dir, slug string, pkgs []goPackage) []Diagnostic {
	var diags []Diagnostic

	wantPrimary := slug        // separator-free lowercase rendering of the slug
	wantFakes := slug + "test" // the testing pattern's public fakes package
	foundPrimary := false
	foundFakes := false

	for _, p := range pkgs {
		full := filepath.Join(dir, p.dir)

		// Rule 4 (directory/package half): no directory segment below the root
		// and no package name may be a banned token, nor a fakes-style name
		// composed on a banned abbreviation (the "cfgtest" break, ADR-0018).
		for _, seg := range strings.Split(filepath.ToSlash(p.dir), "/") {
			if seg == "." || seg == "" {
				continue
			}
			if IsBanned(seg) {
				diags = append(diags, Diagnostic{
					Path:    full,
					Message: fmt.Sprintf("directory segment %q is a banned HNS-1 token; use %s", seg, requiredFor(seg)),
				})
			} else if stem, bad := bannedFakesStem(seg); bad {
				diags = append(diags, Diagnostic{
					Path:    full,
					Message: fmt.Sprintf("directory %q is a fakes package built on the banned abbreviation %q; use %s+\"test\"", seg, stem, requiredFor(stem)),
				})
			}
		}
		if IsBanned(p.name) {
			diags = append(diags, Diagnostic{
				Path:    full,
				Message: fmt.Sprintf("package name %q is a banned HNS-1 token; use %s", p.name, requiredFor(p.name)),
			})
		} else if stem, bad := bannedFakesStem(p.name); bad {
			diags = append(diags, Diagnostic{
				Path:    full,
				Message: fmt.Sprintf("package %q is a fakes package built on the banned abbreviation %q; use %s+\"test\"", p.name, stem, requiredFor(stem)),
			})
		}

		switch p.dir {
		case ".":
			// Rule 2: the root directory holds the primary package.
			foundPrimary = true
			if p.name != wantPrimary {
				diags = append(diags, Diagnostic{
					Path:    full,
					Message: fmt.Sprintf("primary package is %q, want %q (the separator-free rendering of slug %q)", p.name, wantPrimary, slug),
				})
			}
		case wantFakes:
			// Rule 3: the <slug>test directory holds the fakes package.
			foundFakes = true
			if p.name != wantFakes {
				diags = append(diags, Diagnostic{
					Path:    full,
					Message: fmt.Sprintf("fakes package is %q, want %q (slug + \"test\")", p.name, wantFakes),
				})
			}
		}
	}

	if !foundPrimary {
		diags = append(diags, Diagnostic{
			Path:    dir,
			Message: fmt.Sprintf("no primary package found in the library root; expected package %q", wantPrimary),
		})
	}
	// A missing fakes package is not flagged here: not every library must ship a
	// <slug>test package (the testing pattern's own fakes live elsewhere, and
	// some libraries expose fakes differently). When the directory exists, its
	// package name is enforced above.
	_ = foundFakes

	return diags
}
