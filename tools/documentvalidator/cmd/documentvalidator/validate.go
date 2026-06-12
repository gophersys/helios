package main

import (
	"encoding/json"
	"fmt"
	"io"
	"sort"

	"github.com/gophersys/eden/tools/documentvalidator/internal/corpus"
	"github.com/gophersys/eden/tools/documentvalidator/internal/projection"
)

// diagnostic is the wire form of a single diagnostic line for both text and JSON
// output. It carries enough to locate (file, id), classify (rule or schema
// pointer), and explain (message) a finding.
type diagnostic struct {
	File       string `json:"file"`
	DocumentID string `json:"documentId,omitempty"`
	Rule       string `json:"rule,omitempty"`
	Message    string `json:"message"`
}

// runValidate executes `documentvalidator validate <dir> [--schemas <dir>] [--json]`.
func runValidate(args []string, stdout, stderr io.Writer) int {
	opts, err := parseArgs(args)
	if err != nil {
		fmt.Fprintf(stderr, "documentvalidator: %v\n", err)
		usage(stderr)
		return exitUsage
	}

	schemaDir, err := resolveSchemaDir(opts.schemas, opts.dir)
	if err != nil {
		fmt.Fprintf(stderr, "documentvalidator: %v\n", err)
		return exitUsage
	}

	schemas, err := loadSchemas(schemaDir)
	if err != nil {
		fmt.Fprintf(stderr, "documentvalidator: loading schemas: %v\n", err)
		return exitUsage
	}

	paths, err := walkDocuments(opts.dir)
	if err != nil {
		fmt.Fprintf(stderr, "documentvalidator: %v\n", err)
		return exitUsage
	}

	var (
		diags []diagnostic
		docs  []*projection.Document
	)

	// PROJECTION + SHAPE, per document.
	for _, path := range paths {
		rel := relPath(opts.dir, path)
		doc, perr := projection.Project(path)
		if perr != nil {
			// A projection failure (bad YAML, missing frontmatter) is an I/O /
			// authoring error: surface it but keep going so the report is complete.
			diags = append(diags, diagnostic{File: rel, Rule: "projection", Message: perr.Error()})
			continue
		}
		docs = append(docs, doc)

		if doc.DocumentType == "" {
			diags = append(diags, diagnostic{
				File:    rel,
				Rule:    "shape",
				Message: "document has no meta.type; cannot select a schema",
			})
			continue
		}
		schema, ok := schemas[doc.DocumentType]
		if !ok {
			diags = append(diags, diagnostic{
				File:       rel,
				DocumentID: documentID(doc),
				Rule:       "shape",
				Message:    fmt.Sprintf("no schema registered for meta.type %q", doc.DocumentType),
			})
			continue
		}
		for _, d := range validateShape(schema, doc, rel) {
			diags = append(diags, d)
		}
	}

	// CORPUS rules T1-T5 + T6 report. Build over every projected document
	// (even those that failed shape — resolution still wants their ids).
	c := corpus.Build(docs)
	for _, d := range c.CheckAll() {
		diags = append(diags, fromCorpus(opts.dir, d))
	}
	coverage := make([]diagnostic, 0)
	for _, d := range c.CoverageReport() {
		coverage = append(coverage, fromCorpus(opts.dir, d))
	}

	sortDiagnostics(diags)

	// Violations are everything except the T6 coverage report.
	violation := len(diags) > 0

	if opts.json {
		emitJSON(stdout, diags, coverage)
	} else {
		emitText(stdout, diags, coverage)
	}

	if violation {
		return exitViolations
	}
	return exitClean
}

// validateShape validates a projected document against its schema and converts
// each JSON Schema error into a diagnostic carrying the failing schema pointer.
func validateShape(schema *compiledSchema, doc *projection.Document, rel string) []diagnostic {
	errs := schema.Validate(doc.Projection)
	out := make([]diagnostic, 0, len(errs))
	for _, e := range errs {
		out = append(out, diagnostic{
			File:       rel,
			DocumentID: documentID(doc),
			Rule:       e.Pointer,
			Message:    e.Message,
		})
	}
	return out
}

func fromCorpus(baseDir string, d corpus.Diagnostic) diagnostic {
	return diagnostic{
		File:       relPath(baseDir, d.File),
		DocumentID: d.DocumentID,
		Rule:       d.Rule,
		Message:    d.Message,
	}
}

func documentID(doc *projection.Document) string {
	if meta, ok := doc.Projection["meta"].(map[string]any); ok {
		if id, ok := meta["id"].(string); ok {
			return id
		}
	}
	return ""
}

// sortDiagnostics orders diagnostics deterministically: file, rule, id, message.
func sortDiagnostics(diags []diagnostic) {
	sort.SliceStable(diags, func(i, j int) bool {
		a, b := diags[i], diags[j]
		if a.File != b.File {
			return a.File < b.File
		}
		if a.Rule != b.Rule {
			return a.Rule < b.Rule
		}
		if a.DocumentID != b.DocumentID {
			return a.DocumentID < b.DocumentID
		}
		return a.Message < b.Message
	})
}

func emitText(w io.Writer, diags, coverage []diagnostic) {
	for _, d := range diags {
		fmt.Fprintln(w, formatLine(d))
	}
	if len(coverage) > 0 {
		fmt.Fprintln(w, "# coverage report (T6 — not a violation):")
		for _, d := range coverage {
			fmt.Fprintln(w, formatLine(d))
		}
	}
	if len(diags) == 0 {
		fmt.Fprintln(w, "ok: 0 violations")
	}
}

// formatLine renders one diagnostic as a single stable line:
// "<file>: [<rule>] <id> <message>".
func formatLine(d diagnostic) string {
	id := d.DocumentID
	if id != "" {
		id = " " + id
	}
	rule := d.Rule
	if rule == "" {
		rule = "-"
	}
	return fmt.Sprintf("%s: [%s]%s %s", d.File, rule, id, d.Message)
}

func emitJSON(w io.Writer, diags, coverage []diagnostic) {
	type report struct {
		Violations []diagnostic `json:"violations"`
		Coverage   []diagnostic `json:"coverage"`
		OK         bool         `json:"ok"`
	}
	if diags == nil {
		diags = []diagnostic{}
	}
	if coverage == nil {
		coverage = []diagnostic{}
	}
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	_ = enc.Encode(report{Violations: diags, Coverage: coverage, OK: len(diags) == 0})
}
