// Command hnslint enforces the structural HNS-1 naming rules that
// golangci-lint's forbidigo cannot express, for one or more libs/go/<slug>
// module directories: module path, primary package name, fakes package name,
// and the no-banned-token rule on directories and packages (10 §5, ADR-0018).
//
// Usage:
//
//	hnslint <dir>...
//
// It prints one diagnostic per line as "path: message" and exits 0 when every
// directory conforms, 1 when any violation is found, and 2 on a usage error.
package main

import (
	"fmt"
	"io"
	"os"
)

func main() {
	code, err := run(os.Args[1:], os.Stdout)
	if err != nil {
		fmt.Fprintf(os.Stderr, "hnslint: %v\n", err)
	}
	os.Exit(code)
}

// run is the testable entry point: it returns the process exit code and any
// terminal error (a write failure or usage error), writing diagnostics to out.
// The code is 0 when every directory conforms, 1 on any violation, and 2 on a
// usage error.
func run(args []string, out io.Writer) (int, error) {
	if len(args) == 0 {
		return 2, errUsage
	}

	lines, violations := collect(args)
	for _, line := range lines {
		if _, err := fmt.Fprintln(out, line); err != nil {
			return 1, fmt.Errorf("writing output: %w", err)
		}
	}

	if violations > 0 {
		return 1, nil
	}
	return 0, nil
}
