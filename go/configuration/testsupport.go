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
//
// It returns the Document INTERFACE deliberately: this is the seam that lets
// configurationtest.Doc hand back the SAME concrete Document the real Parser
// produces (contracts/configuration.md §2 — immutability is structural).
// Returning the unexported concrete type is impossible across the package
// boundary; the interface is the point.
//
//nolint:ireturn // Document is an interface fixed by contracts/configuration.md §2; see doc above.
func NewTestDocument(root *tree.Node, format Format, origin Position) Document {
	return newDocument(root, format, origin)
}
