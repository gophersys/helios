// Command documentvalidator validates a project's document corpus against the
// Eden document schemas (shape, JSON Schema 2020-12) and the traceability rules
// T1-T5 (cross-document), and reports T6 coverage. It is the deterministic
// enforcement entrypoint of doc 11 §8 — no model in the path.
//
// Usage:
//
//	documentvalidator validate <dir> [--schemas <dir>] [--json]
//	documentvalidator links <dir> [--json]
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
  documentvalidator validate <dir> [--schemas <dir>] [--json]
  documentvalidator links <dir> [--json]

Commands:
  validate   Project every document under <dir>, validate its shape against the
             schema selected by meta.type, and enforce traceability rules T1-T5;
             report T6 coverage gaps. Exit 0 clean, 1 on violations, 2 on usage/IO.
  links      Emit the typed link-edge list (the corpus graph) under <dir>.

Flags:
  --schemas <dir>   Directory of *.schema.json (default: <repo>/schemas/document/v1).
  --json            Emit machine-readable JSON instead of one diagnostic per line.
`)
}
