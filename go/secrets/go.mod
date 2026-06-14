module github.com/gophersys/libs/go/secrets

go 1.26

require github.com/gophersys/libs/go/errors v0.0.0

require github.com/gophersys/libs/go/dependencies v0.0.0 // indirect

// Test-only dependencies (the ADR-0020 test-taxonomy block): goleak (dimension b, leak),
// rapid (dimension a, property), and the testing pattern lib (dimension c, AssertLifecycle /
// LifecycleProbe). depguard's `test-taxonomy` rule permits these in *_test.go only.
require (
	github.com/gophersys/libs/go/testing v0.0.0
	go.uber.org/goleak v1.3.0
	pgregory.net/rapid v1.3.0
)

replace (
	github.com/gophersys/libs/go/dependencies v0.0.0 => ../dependencies
	github.com/gophersys/libs/go/errors v0.0.0 => ../errors
	github.com/gophersys/libs/go/testing v0.0.0 => ../testing
)
