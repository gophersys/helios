package configuration

import (
	"github.com/gophersys/libs/go/configuration/internal/docbuild"
	"github.com/gophersys/libs/go/configuration/internal/tree"
)

// init registers the construction seam the configurationtest fakes use so that
// configurationtest.Doc returns the SAME concrete Document type the real Parser
// produces — without configurationtest reaching into unexported fields and
// without an import cycle. The concrete document/value adapters return public
// configuration.Diagnostic/Position, so they MUST live in this package; the
// docbuild hook is how the fake reaches them.
//
// This is deliberately NOT an exported configuration symbol: the public surface
// stays EXACTLY the frozen contract set (contracts/configuration.md §2), with no
// extra exported test seam an api-check/exported-diff gate (10 §9) would flag.
// See internal/docbuild for the full rationale.
//
//nolint:gochecknoinits // single registration of the internal construction seam; the documented mechanism that keeps the public §2 surface frozen.
func init() {
	docbuild.Build = func(root *tree.Node, format string, origin tree.Position) any {
		return newDocument(root, Format(format), fromTreePos(origin))
	}
}
