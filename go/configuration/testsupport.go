package configuration

import "github.com/gophersys/libs/go/configuration/internal/tree"

// NewTestDocument builds a Document directly from an internal tree root. It is
// the construction seam the configurationtest fakes use so that
// configurationtest.Doc returns the SAME concrete Document type the real Parser
// produces — without configurationtest reaching into unexported fields and
// without an import cycle (the concrete document/value adapters return public
// configuration.Diagnostic/Position, so they must live in this package).
//
// It is NOT part of the consumer-facing contract surface (section 2): consumers
// obtain a Document only through Parse/Merge. It exists solely to back the
// public fakes mandated by the testing pattern (10 §4); see the implementation
// report's note on this seam. Hidden from doc tooling by intent — keep callers
// limited to configurationtest.
func NewTestDocument(root *tree.Node, format Format, origin Position) Document {
	return newDocument(root, format, origin)
}
