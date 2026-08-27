module github.com/gophersys/libs/go/envelope

go 1.26

require (
	github.com/gophersys/libs/go/errors v0.0.0
	github.com/gophersys/libs/go/secrets v0.0.0
)

// Test-only dependencies (the ADR-0020 test-taxonomy block): goleak (dimension b, leak), rapid
// (dimension a, property), and the secretstest fake Provider (the conformance two-binding's fake
// KEK source). depguard's `test-taxonomy` rule permits these in *_test.go only.
require (
	go.uber.org/goleak v1.3.0
	pgregory.net/rapid v1.3.0
)

replace (
	github.com/gophersys/libs/go/dependencies v0.0.0 => ../dependencies
	github.com/gophersys/libs/go/errors v0.0.0 => ../errors
	github.com/gophersys/libs/go/secrets v0.0.0 => ../secrets
	github.com/gophersys/libs/go/testing v0.0.0 => ../testing
)
