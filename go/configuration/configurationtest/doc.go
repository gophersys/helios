// Package configurationtest provides the canonical public fakes for the
// configuration pattern (the testing discipline, 10 §4). It is the
// substitutability oracle: the conformance suite asserts the real Parser and
// these fakes agree on the same fixtures.
package configurationtest

import (
	"sort"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/configuration/internal/docbuild"
	"github.com/gophersys/libs/go/configuration/internal/tree"
)

// docState accumulates options applied to a Doc before it is built.
type docState struct {
	format    configuration.Format
	origin    string
	positions map[configuration.Path]configuration.Position
}

// DocOption customizes a Doc.
type DocOption func(*docState)

// WithFormat stamps the Document's reported Format.
func WithFormat(f configuration.Format) DocOption {
	return func(s *docState) { s.format = f }
}

// WithOrigin sets the Document's root Position source name.
func WithOrigin(src string) DocOption {
	return func(s *docState) { s.origin = src }
}

// WithPosition stamps a synthetic Position on a Path so diagnostic line/column
// assertions are exercisable without real source text.
func WithPosition(p configuration.Path, pos configuration.Position) DocOption {
	return func(s *docState) {
		if s.positions == nil {
			s.positions = map[configuration.Path]configuration.Position{}
		}
		s.positions[p] = pos
	}
}

// Doc builds an in-memory Document from a Go map — no parser, no source. The
// composition-root-side workhorse: a library Config test constructs the exact
// resolved tree it needs and asserts its Validator/ConfigFrom against it.
//
// The Document it returns is the SAME concrete type the real parser yields
// (built through configuration's internal tree), so the fake and the adapter
// share one read surface — the substitutability oracle (08 §2).
//
// It returns the configuration.Document INTERFACE by contract
// (contracts/configuration.md §2): Doc is the public fake that hands callers the
// frozen read surface, identical to what Parse produces — that interface IS the
// deliverable of the testing pattern (10 §4).
//
//nolint:ireturn // Document is an interface fixed by contracts/configuration.md §2; see doc above.
func Doc(treeMap map[string]any, opts ...DocOption) configuration.Document {
	st := &docState{positions: map[configuration.Path]configuration.Position{}}
	for _, o := range opts {
		o(st)
	}
	origin := tree.Position{Source: st.origin}
	root := buildObject(treeMap, "", origin, st.positions)
	// Build through the internal docbuild seam (registered by configuration's
	// init) so this fake returns the SAME concrete Document the real Parser
	// yields, while keeping the public configuration surface exactly the frozen
	// §2 set — no exported test-only constructor (see internal/docbuild).
	built := docbuild.Build(root, string(st.format), tree.Position{Source: st.origin})
	doc, ok := built.(configuration.Document)
	if !ok {
		// Unreachable: configuration's init registers a Build that returns a
		// configuration.Document. A miss means the registration seam is broken —
		// a programming error in this module, not runtime config data, so it is
		// a hard failure rather than a swallowed nil that would mask the bug.
		panic("configurationtest: docbuild.Build did not return a configuration.Document (seam not registered)")
	}
	return doc
}

// buildObject converts a Go map into an object node, recursing for nested maps
// and slices. Synthetic positions from WithPosition are applied by Path.
func buildObject(m map[string]any, prefix configuration.Path, defPos tree.Position, positions map[configuration.Path]configuration.Position) *tree.Node {
	obj := tree.NewObject(posFor(prefix, defPos, positions))
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys) // deterministic order from an unordered Go map
	for _, k := range keys {
		child := buildNode(m[k], prefix.Child(k), defPos, positions)
		obj.Set(k, child)
	}
	return obj
}

func buildNode(v any, path configuration.Path, defPos tree.Position, positions map[configuration.Path]configuration.Position) *tree.Node {
	pos := posFor(path, defPos, positions)
	switch x := v.(type) {
	case map[string]any:
		return buildObject(x, path, defPos, positions)
	case []any:
		elems := make([]*tree.Node, len(x))
		for i, e := range x {
			elems[i] = buildNode(e, path.Index(i), defPos, positions)
		}
		return tree.NewArray(elems, pos)
	case string:
		return tree.NewString(x, pos)
	case bool:
		return tree.NewBool(x, pos)
	case int:
		return tree.NewInt(int64(x), pos)
	case int64:
		return tree.NewInt(x, pos)
	case float64:
		// A whole-number float from a literal is stored as float; Value.Int
		// still reads it when integral (mirrors JSON number handling).
		return tree.NewFloat(x, pos)
	case nil:
		n := tree.Absent()
		n.Pos = pos
		return n
	default:
		// Unknown Go type: model as absent rather than panic — total by design.
		n := tree.Absent()
		n.Pos = pos
		return n
	}
}

func posFor(path configuration.Path, def tree.Position, positions map[configuration.Path]configuration.Position) tree.Position {
	if p, ok := positions[path]; ok {
		return tree.Position{Source: p.Source, Line: p.Line, Column: p.Column}
	}
	return def
}
