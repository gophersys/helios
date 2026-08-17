// Package smoke is the fixture the image compiles, vets, formats, lints and
// traces. It has no dependency, so every one of those runs with GOPROXY=off
// and reaches no network.
package smoke

// Greeting is the function the debugger sets its tracepoint on.
func Greeting(name string) string {
	return "hello, " + name
}
