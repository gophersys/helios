package checker

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// bareBannedIdentifiers is the set of HNS-1 banned tokens checked against a WHOLE
// exported Go identifier (10 §5; ADR-0018 Layer 1). forbidigo matches these as
// lowercase words in source text; hnslint additionally rejects them as *exported
// declared identifiers* (type/field/func/method names) — the surface forbidigo's
// `\bauth\b`-style lowercase patterns cannot see on a capitalized type name.
//
// The match is against the WHOLE identifier, never a substring: a meaningful
// compound that merely CONTAINS a banned word — ObjectStore, DesiredStore,
// TemplateStore, PostgresStore, Author, OAuth — is allowed and MUST NOT flag. The
// banned form is the bare token standing alone as the identifier's full name.
//
// The required full spelling is carried for the diagnostic. The full-spelled spine
// type outliers (Configuration/Dependencies) are handled separately by
// bannedExportedTypeNames, because they are banned ONLY as a type name (the founder
// ruling: Config/Deps are the idiomatic exported spine types; a struct field named
// Configuration mirroring an external wire shape is a different judgement).
var bareBannedIdentifiers = map[string]string{
	"Auth":  "Identity",
	"Store": "(a meaningful compound, e.g. ObjectStore/DesiredStore/PostgresStore)",
	"Db":    "Persistence",
	"DB":    "Persistence",
	"Repo":  "Repository",
}

// bannedExportedTypeNames is the set of identifiers banned specifically as a
// declared TYPE name (10 §5; the founder ruling, 2026-06-15). Config/Deps are the
// sanctioned idiomatic spine type names (the rule-11 exemption), so the full-spelled
// forms used AS A TYPE NAME are the outliers the ruling forbids: a `type
// Configuration struct` / `type Dependencies struct` must be Config/Deps.
//
// These are checked ONLY on type declarations, never on fields or funcs, because the
// ban is on the type vocabulary — a `type Configuration` is the outlier; a struct
// FIELD named Configuration (rare, and usually a wire mirror) is out of scope here.
var bannedExportedTypeNames = map[string]string{
	"Configuration": "Config",
	"Dependencies":  "Deps",
}

// checkExportedIdentifiers enforces the banned-exported-identifier rule: no exported
// Go identifier (type, struct field, interface-method, func, or method name) may be
// a bare banned token, and no declared TYPE name may be a full-spelled spine outlier
// (Configuration/Dependencies). It parses the full AST of every buildable Go file
// under dir (skipping dot-dirs and testdata, matching the package scan), so it sees
// the capitalized declarations forbidigo's lowercase patterns cannot.
func checkExportedIdentifiers(dir string) []Diagnostic {
	var diags []Diagnostic
	fset := token.NewFileSet()

	err := filepath.WalkDir(dir, func(path string, d os.DirEntry, werr error) error {
		if werr != nil {
			return werr
		}
		if d.IsDir() {
			name := d.Name()
			if path != dir && (strings.HasPrefix(name, ".") || name == "testdata") {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(path, ".go") {
			return nil
		}
		f, perr := parser.ParseFile(fset, path, nil, parser.SkipObjectResolution)
		if perr != nil {
			// A file we cannot parse is not a naming violation; gofmt/go vet own
			// syntax correctness.
			return nil //nolint:nilerr // parse failures are out of scope for naming
		}
		diags = append(diags, exportedIdentifierDiags(path, f)...)
		return nil
	})
	if err != nil {
		diags = append(diags, Diagnostic{
			Path:    dir,
			Message: fmt.Sprintf("scanning exported identifiers: %v", err),
		})
	}

	sort.Slice(diags, func(i, j int) bool {
		if diags[i].Path != diags[j].Path {
			return diags[i].Path < diags[j].Path
		}
		return diags[i].Message < diags[j].Message
	})
	return diags
}

// exportedIdentifierDiags walks one parsed file's top-level declarations and reports
// every exported identifier whose whole name is a bare banned token, plus every
// declared type name that is a banned full-spelled spine outlier.
func exportedIdentifierDiags(path string, f *ast.File) []Diagnostic {
	var diags []Diagnostic

	report := func(name, kind string) {
		if required, bad := bareBannedIdentifier(name); bad {
			diags = append(diags, Diagnostic{
				Path:    path,
				Message: fmt.Sprintf("exported %s %q is a bare banned HNS-1 token; use %s (10 §5)", kind, name, required),
			})
		}
	}

	for _, decl := range f.Decls {
		switch d := decl.(type) {
		case *ast.GenDecl:
			for _, spec := range d.Specs {
				switch s := spec.(type) {
				case *ast.TypeSpec:
					if !s.Name.IsExported() {
						continue
					}
					// Type name: both the bare-token ban and the spine-outlier ban apply.
					report(s.Name.Name, "type")
					if required, bad := bannedExportedTypeName(s.Name.Name); bad {
						diags = append(diags, Diagnostic{
							Path:    path,
							Message: fmt.Sprintf("exported type %q is a full-spelled spine outlier; use %s as the type name (10 §5 founder ruling — Config/Deps are the idiomatic spine types)", s.Name.Name, required),
						})
					}
					diags = append(diags, typeMemberDiags(path, s.Type, report)...)
				case *ast.ValueSpec:
					// Exported package-level const/var names.
					for _, n := range s.Names {
						if n.IsExported() {
							report(n.Name, "identifier")
						}
					}
				}
			}
		case *ast.FuncDecl:
			if d.Name.IsExported() {
				kind := "func"
				if d.Recv != nil {
					kind = "method"
				}
				report(d.Name.Name, kind)
			}
		}
	}
	return diags
}

// typeMemberDiags reports banned exported member names inside a type expression: the
// exported field names of a struct and the explicit method names of an interface.
// report does the bare-token match-and-append; only the names are walked here.
func typeMemberDiags(path string, expr ast.Expr, report func(name, kind string)) []Diagnostic {
	switch t := expr.(type) {
	case *ast.StructType:
		if t.Fields == nil {
			return nil
		}
		for _, field := range t.Fields.List {
			for _, n := range field.Names {
				if n.IsExported() {
					report(n.Name, "struct field")
				}
			}
		}
	case *ast.InterfaceType:
		if t.Methods == nil {
			return nil
		}
		for _, m := range t.Methods.List {
			for _, n := range m.Names {
				if n.IsExported() {
					report(n.Name, "interface method")
				}
			}
		}
	}
	return nil
}

// bareBannedIdentifier reports whether name is, in WHOLE, a bare banned HNS-1 token
// (Auth/Store/Db/DB/Repo) — never a substring — and returns the required form. A
// meaningful compound (ObjectStore, Author, OAuth) is not matched because the lookup
// keys on the entire identifier, not a contained word.
func bareBannedIdentifier(name string) (string, bool) {
	required, ok := bareBannedIdentifiers[name]
	return required, ok
}

// bannedExportedTypeName reports whether name is a full-spelled spine type outlier
// (Configuration/Dependencies) banned AS A TYPE NAME, returning the required spine
// type name (Config/Deps).
func bannedExportedTypeName(name string) (string, bool) {
	required, ok := bannedExportedTypeNames[name]
	return required, ok
}
