// Command smoke is the binary the debugger runs.
package main

import (
	"os"

	"github.com/gophersys/libs/go/smoke"
)

func main() {
	if smoke.Greeting("gophersys") == "" {
		os.Exit(1)
	}
}
