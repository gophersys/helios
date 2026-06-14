module github.com/gophersys/libs/go/testing

go 1.26

require github.com/gophersys/libs/go/dependencies v0.0.0

// Test-only dependencies (the ADR-0020 test-taxonomy block): goleak (dimension b,
// leak) and rapid (dimension a, property). depguard's `test-taxonomy` rule permits
// these in *_test.go only — they never enter a production import graph.
require (
	go.uber.org/goleak v1.3.0
	pgregory.net/rapid v1.3.0
)

// Pin the unpublished v0.0.0 dependencies sibling to its in-repo source so the module
// builds/tidies/mutates standalone (GOWORK=off) as well as under the workspace go.work.
replace github.com/gophersys/libs/go/dependencies v0.0.0 => ../dependencies
