// Command documentvalidator validates a project's document corpus against the
// Eden document schemas (shape, JSON Schema 2020-12) and the traceability rules
// T1-T5 (cross-document), and reports T6 coverage. It is the deterministic
// enforcement entrypoint of doc 11 §8 — no model in the path.
//
// Usage:
//
//	documentvalidator validate <dir> [--schemas <dir>] [--against <git-ref>] [--json]
//	documentvalidator project  <dir> [--schemas <dir>] [--out <dir>]
//	documentvalidator links    <dir> [--json]
//
// Exit codes: 0 clean, 1 violations found, 2 usage or I/O error.
package main

import (
	"fmt"
	"io"
	"os"
)

const (
	exitClean      = 0
	exitViolations = 1
	exitUsage      = 2
)

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout, stderr io.Writer) int {
	if len(args) < 1 {
		usage(stderr)
		return exitUsage
	}
	switch args[0] {
	case "validate":
		return runValidate(args[1:], stdout, stderr)
	case "project":
		return runProject(args[1:], stdout, stderr)
	case "links":
		return runLinks(args[1:], stdout, stderr)
	case "help", "-h", "--help":
		usage(stdout)
		return exitClean
	default:
		fmt.Fprintf(stderr, "documentvalidator: unknown command %q\n", args[0])
		usage(stderr)
		return exitUsage
	}
}

func usage(w io.Writer) {
	fmt.Fprint(w, `documentvalidator — validate Eden project documents (shape + traceability)

Usage:
  documentvalidator validate <dir> [--schemas <dir>] [--against <git-ref>] [--json]
  documentvalidator project  <dir> [--schemas <dir>] [--out <dir>]
  documentvalidator links    <dir> [--json]

Commands:
  validate   Project every document under <dir>, validate its shape against the
             schema selected by meta.type, and enforce traceability rules T1-T5;
             report T6 coverage gaps. With --against <git-ref>, additionally
             enforce the T5 lifecycle transition check on every document changed
             relative to that ref (approved is immutable; version is monotonic;
             superseded is terminal). Exit 0 clean, 1 on violations, 2 on usage/IO.
  project    Emit each document's JSON projection {meta, data, sections} — the
             dashboard/UI contract (doc 11 §5). Default: byte-stable NDJSON to
             stdout, one document per line, sorted by document id. With --out,
             write one <document-id>.json file (two-space indent) per document.
  links      Emit the typed link-edge list (the corpus graph) under <dir>.

Flags:
  --schemas <dir>   Directory of *.schema.json (default: <repo>/schemas/document/v1).
  --against <ref>   (validate) git ref to diff against for the T5 transition check.
  --out <dir>       (project) write <document-id>.json files here instead of NDJSON.
  --json            Emit machine-readable JSON instead of one diagnostic per line.
`)
}
