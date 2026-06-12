package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/gophersys/eden/tools/documentvalidator/internal/projection"
)

// projectOptions holds the parsed flags for the `project` verb.
type projectOptions struct {
	dir string
	// out, when non-empty, is the directory <document-id>.json files are written
	// to; empty means NDJSON to stdout.
	out string
	// schemas is accepted for signature symmetry with `validate`; projection does
	// not consult the schemas (it emits the {meta, data, sections} value verbatim).
	schemas string
}

// runProject executes `documentvalidator project <dir> [--schemas <dir>] [--out <dir>]`.
//
// It emits each document's JSON projection {meta, data, sections} in the
// canonical, byte-stable form (doc 11 §5 / ADR-0011: the projection is the UI
// contract). By default it writes NDJSON to stdout — one compact projection per
// line, documents sorted by document id, top-level keys in the contract order
// (meta, data, sections). With --out it instead writes one pretty-printed
// <document-id>.json file (two-space indent) per document into that directory.
func runProject(args []string, stdout, stderr io.Writer) int {
	opts, err := parseProjectArgs(args)
	if err != nil {
		fmt.Fprintf(stderr, "documentvalidator: %v\n", err)
		usage(stderr)
		return exitUsage
	}

	paths, err := walkDocuments(opts.dir)
	if err != nil {
		fmt.Fprintf(stderr, "documentvalidator: %v\n", err)
		return exitUsage
	}

	docs := make([]*projection.Document, 0, len(paths))
	for _, path := range paths {
		doc, perr := projection.Project(path)
		if perr != nil {
			fmt.Fprintf(stderr, "documentvalidator: %v\n", perr)
			return exitUsage
		}
		docs = append(docs, doc)
	}

	// Sort by document id (the stable identifier) so both NDJSON line order and
	// the on-disk file set are deterministic. Path order breaks ties when two
	// documents share (or lack) an id, keeping the output total-ordered.
	sort.SliceStable(docs, func(i, j int) bool {
		if a, b := docs[i].DocumentID(), docs[j].DocumentID(); a != b {
			return a < b
		}
		return docs[i].Path < docs[j].Path
	})

	if opts.out != "" {
		return projectToDirectory(docs, opts, stdout, stderr)
	}
	return projectToStdout(docs, stdout, stderr)
}

// projectToStdout writes one compact projection per line (NDJSON) to stdout. Each
// line is the canonical projection re-encoded compactly (the top-level key order
// is preserved; whitespace is stripped) so the stream is one document per line.
func projectToStdout(docs []*projection.Document, stdout, stderr io.Writer) int {
	for _, doc := range docs {
		indented, err := projection.Marshal(doc.Projection)
		if err != nil {
			fmt.Fprintf(stderr, "documentvalidator: projecting %s: %v\n", doc.Path, err)
			return exitUsage
		}
		compact, err := compactJSONLine(indented)
		if err != nil {
			fmt.Fprintf(stderr, "documentvalidator: projecting %s: %v\n", doc.Path, err)
			return exitUsage
		}
		if _, err := fmt.Fprintf(stdout, "%s\n", compact); err != nil {
			fmt.Fprintf(stderr, "documentvalidator: writing projection: %v\n", err)
			return exitUsage
		}
	}
	return exitClean
}

// projectToDirectory writes each document's pretty-printed projection to
// <out>/<document-id>.json. A document with no meta.id, or two documents that
// would write the same file, is a usage error (the projection set must be a
// well-formed, id-keyed map — that is what the dashboards consume).
func projectToDirectory(docs []*projection.Document, opts projectOptions, stdout, stderr io.Writer) int {
	if err := os.MkdirAll(opts.out, 0o755); err != nil { //nolint:gosec // operator-chosen output dir.
		fmt.Fprintf(stderr, "documentvalidator: creating --out dir %q: %v\n", opts.out, err)
		return exitUsage
	}

	written := map[string]string{}
	for _, doc := range docs {
		id := doc.DocumentID()
		if id == "" {
			fmt.Fprintf(stderr, "documentvalidator: %s has no meta.id; cannot name its projection file\n", doc.Path)
			return exitUsage
		}
		fileName := id + ".json"
		if prior, clash := written[fileName]; clash {
			fmt.Fprintf(stderr, "documentvalidator: documents %s and %s both project to %s\n", prior, doc.Path, fileName)
			return exitUsage
		}
		written[fileName] = doc.Path

		indented, err := projection.Marshal(doc.Projection)
		if err != nil {
			fmt.Fprintf(stderr, "documentvalidator: projecting %s: %v\n", doc.Path, err)
			return exitUsage
		}
		// A trailing newline makes the file a well-formed text file and matches the
		// golden fixtures.
		content := append(indented, '\n')
		outPath := filepath.Join(opts.out, fileName)
		if err := os.WriteFile(outPath, content, 0o644); err != nil { //nolint:gosec // operator-chosen output dir.
			fmt.Fprintf(stderr, "documentvalidator: writing %s: %v\n", outPath, err)
			return exitUsage
		}
		fmt.Fprintf(stdout, "wrote %s\n", outPath)
	}
	return exitClean
}

// compactJSONLine strips insignificant whitespace from canonical projection
// bytes to produce a single NDJSON line. json.Compact is a byte-level transform,
// so the contract top-level key order (already baked into the input by
// projection.Marshal) is preserved.
func compactJSONLine(indented []byte) (string, error) {
	var buf bytes.Buffer
	if err := json.Compact(&buf, indented); err != nil {
		return "", err
	}
	return buf.String(), nil
}

// parseProjectArgs parses the positional directory and the --out / --schemas
// flags for the project verb. Exactly one positional directory is required.
func parseProjectArgs(args []string) (projectOptions, error) {
	var (
		opts projectOptions
		dirs []string
	)
	for i := 0; i < len(args); i++ {
		a := args[i]
		switch {
		case a == "--out":
			if i+1 >= len(args) {
				return opts, fmt.Errorf("--out requires a directory argument")
			}
			i++
			opts.out = args[i]
		case strings.HasPrefix(a, "--out="):
			opts.out = strings.TrimPrefix(a, "--out=")
		case a == "--schemas":
			if i+1 >= len(args) {
				return opts, fmt.Errorf("--schemas requires a directory argument")
			}
			i++
			opts.schemas = args[i]
		case strings.HasPrefix(a, "--schemas="):
			opts.schemas = strings.TrimPrefix(a, "--schemas=")
		case strings.HasPrefix(a, "-"):
			return opts, fmt.Errorf("unknown flag %q", a)
		default:
			dirs = append(dirs, a)
		}
	}
	if len(dirs) != 1 {
		return opts, fmt.Errorf("expected exactly one target directory, got %d", len(dirs))
	}
	opts.dir = dirs[0]
	info, err := os.Stat(opts.dir)
	if err != nil {
		return opts, fmt.Errorf("target %q: %w", opts.dir, err)
	}
	if !info.IsDir() {
		return opts, fmt.Errorf("target %q is not a directory", opts.dir)
	}
	return opts, nil
}
