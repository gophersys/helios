package get

// export_test.go is the idiomatic Go test seam: it exposes the unexported pipeline stages to the
// external _test package without widening the production surface.

// Execute is the test alias for the execute-stage constructor.
var Execute = execute
