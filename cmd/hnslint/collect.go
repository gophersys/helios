package main

import (
	"errors"
	"os"

	"github.com/gophersys/hnslint/internal/checker"
)

// errUsage is returned when hnslint is invoked with no directory arguments.
var errUsage = errors.New("no directories given; usage: hnslint <dir> [dir...]")

// collect runs the HNS-1 checks over every directory in args and returns the
// rendered diagnostic lines plus the total violation count. A path that is not
// a directory is itself one violation.
func collect(args []string) (lines []string, violations int) {
	for _, dir := range args {
		info, err := os.Stat(dir)
		if err != nil || !info.IsDir() {
			lines = append(lines, dir+": not a directory")
			violations++
			continue
		}
		for _, d := range checker.Check(dir) {
			lines = append(lines, d.String())
			violations++
		}
	}
	return lines, violations
}
