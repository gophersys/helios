package create

// export_test.go exposes the unexported pipeline stages to the package's external test (the _test
// package) WITHOUT widening the production surface — the idiomatic Go test seam. The stages stay
// unexported in the build; only the test binary sees these aliases.

// Validate is the test alias for the validate stage.
var Validate = validate

// Execute is the test alias for the execute-stage constructor.
var Execute = execute
