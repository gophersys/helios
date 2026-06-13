// Package docbuild is the unexported construction seam that lets the
// configurationtest fakes build the SAME concrete configuration.Document the
// real parser produces — without configuration exporting a production symbol
// outside its frozen contract surface (contracts/configuration.md §2).
//
// The concrete document/value adapters must live in package configuration (they
// return public configuration.Diagnostic/Position, so they cannot move to a
// leaf package). configurationtest, however, only constructs an internal
// tree.Node graph and needs a way to wrap it in that concrete Document. A direct
// exported configuration.NewTestDocument would add a symbol the §2 surface does
// not enumerate (an api-check/exported-diff gate, 10 §9, would flag it).
//
// Instead, configuration registers its (unexported) constructor into Build at
// package-init time, and configurationtest calls through Build. Both packages
// import this internal package; neither imports a configuration symbol outside
// §2, and the public surface stays EXACTLY the frozen set. Build's signature is
// expressed only in this package's internal vocabulary (a tree.Node root, a
// format string, a tree.Position origin, and an any-typed Document) so it has no
// import cycle with configuration.
package docbuild

import "github.com/gophersys/libs/go/configuration/internal/tree"

// Build wraps an internal tree root in the concrete configuration.Document.
// configuration registers the real implementation in its init; until then it is
// nil. The returned any is a configuration.Document (asserted by the caller),
// kept any-typed here so this leaf package takes no dependency on the public
// configuration surface that depends on it.
//
//nolint:gochecknoglobals // a single registration seam set once at init; the documented mechanism that keeps the public §2 surface frozen.
var Build func(root *tree.Node, format string, origin tree.Position) any
