package configurationtest

import "testing"

// Run is a BARE conformance entrypoint — it does NOT match ^Run<Role>Suite$ and must
// be flagged (the entrypoint must be named Run<Role>Suite, 08 §2).
func Run(t *testing.T) { _ = t }
