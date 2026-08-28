package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/gophersys/libs/go/errors"
)

// main is the go-first-emit CLI. With `-mode emit` it writes the contract from the route types; with
// `-mode verify` it re-emits and compares to the committed contract, exiting non-zero on drift (the
// route types changed but the contract was not regenerated). The output path defaults to the
// template's contract/openapi.yaml; ctl.sh sets it explicitly.
func main() {
	mode := flag.String("mode", "emit", "emit | verify")
	out := flag.String("out", "contract/openapi.yaml", "the contract path to write/verify")
	flag.Parse()

	document := emit(operations())

	switch *mode {
	case "emit":
		if err := writeFile(*out, document); err != nil {
			fail("emit: %v", err)
		}
		fmt.Printf("openapi: emitted %d operations -> %s\n", len(operations()), *out)
	case "verify":
		existing, err := os.ReadFile(*out) //nolint:gosec // a fixed, repo-relative contract path.
		if err != nil {
			fail("verify: read %s: %v (run `ctl.sh openapi` to emit it)", *out, err)
		}
		if string(existing) != document {
			fail("verify: %s is STALE vs the route types — run `bash ./ctl.sh openapi` and commit the result", *out)
		}
		fmt.Printf("openapi: %s is up to date with the route types\n", *out)
	default:
		fail("unknown -mode %q (emit | verify)", *mode)
	}
}

// writeFile writes content to path, creating the parent directory if needed.
func writeFile(path, content string) error {
	if dir := filepath.Dir(path); dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil { //nolint:gosec // standard dir perms for a repo path.
			return errors.Wrap(errors.KindInternal, "openapi: create contract directory", err)
		}
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil { //nolint:gosec // a contract is world-readable, not a secret.
		return errors.Wrap(errors.KindInternal, "openapi: write contract", err)
	}
	return nil
}

// fail prints a message to stderr and exits 1 (the gate-failure path).
func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "openapi: "+format+"\n", args...)
	os.Exit(1)
}
