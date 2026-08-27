package configuration

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/configuration/internal/tree"
)

// Document is the frozen IR: immutable after Parse returns, safe to share
// across goroutines, zero-value-safe. The zero Document is an empty, valid
// tree whose Lookup misses cleanly. It is a READ surface only — there is no
// setter and no exported mutable field, forever; immutability is structural.
type Document interface {
	// Lookup resolves a Path to a value view. ok == false on a miss; it never
	// panics and never allocates a Diagnostic. An absent optional key yields
	// (_, false) so a library applies its default rather than crashing.
	Lookup(p Path) (Value, bool)

	// Format reports the encoding this Document was decoded from.
	Format() Format

	// Origin is the root Position (Source set, Line 0) for telemetry/audit.
	Origin() Position
}

// Value is a typed read of one resolved node. Conversions are TOTAL: on a
// type mismatch they return a *Diagnostic (never a Go error), stamped with the
// leaf's At() Position, so a library Config constructor accumulates problems
// into one report instead of failing on the first. A nil *Diagnostic means
// success. The zero Value is "absent": every conversion returns its type's
// zero plus a *Diagnostic, and Field/Len report ok == false.
//
// The frozen contract (contracts/configuration.md §2) fixes Value at exactly
// these six methods (At + the three total scalar conversions + Field + Len).
// The contract is law; widening the 5-method ceiling here would change the
// published surface, which is the cardinal sin (10 §9).
//
//nolint:interfacebloat // 6 methods fixed by contracts/configuration.md §2; see doc above.
type Value interface {
	// At is the source Position of this leaf, carried so a conversion failure
	// surfaces "backend.yaml:14:7", not "bad int somewhere."
	At() Position
	String() (string, *Diagnostic)
	Int() (int64, *Diagnostic)
	Bool() (bool, *Diagnostic)
	// Field walks into an object; ok == false past the edge.
	Field(key string) (Value, bool)
	// Len reports array arity; ok == false if this is not an array. Elements
	// are read via Lookup(path.Index(i)) or Field on the parent's view.
	Len() (int, bool)
}

// document is the single concrete Document. It wraps an immutable root tree
// node; the root carries the document Origin Position and Format.
type document struct {
	root   *tree.Node
	format Format
	origin Position
}

// newDocument adapts an internal tree root into a Document. Used by the parser
// and (via the internal package) the configurationtest fakes, so the real and
// fake read surfaces are structurally identical.
//
// Document is an interface BY CONTRACT (contracts/configuration.md §2):
// immutability is structural — no setter, no exported field — so the only way
// to hand one out is behind the interface. Returning the concrete *document
// would leak the unexported type and break the frozen surface.
//
//nolint:ireturn // Document is an interface fixed by contracts/configuration.md §2; see doc above.
func newDocument(root *tree.Node, format Format, origin Position) Document {
	if root == nil {
		root = tree.Absent()
	}
	return &document{root: root, format: format, origin: origin}
}

func (d *document) Format() Format   { return d.format }
func (d *document) Origin() Position { return d.origin }

// Lookup implements the contract's Document.Lookup verbatim. Value is an
// interface BY CONTRACT (contracts/configuration.md §2): the fake supplies its
// own view without exposing internal state, so the read surface must be the
// abstract Value, not a concrete type.
//
//nolint:ireturn // Value is an interface fixed by contracts/configuration.md §2; see doc above.
func (d *document) Lookup(p Path) (Value, bool) {
	node, ok := resolve(d.root, string(p))
	if !ok {
		return value{node: tree.Absent()}, false
	}
	return value{node: node}, true
}

// resolve walks a dotted/indexed path from a root node. It never panics; a miss
// returns (absent, false).
func resolve(root *tree.Node, path string) (*tree.Node, bool) {
	if path == "" {
		return root, true
	}
	cur := root
	for _, seg := range splitPath(path) {
		var ok bool
		if seg.index >= 0 {
			cur, ok = cur.Elem(seg.index)
		} else {
			cur, ok = cur.Child(seg.key)
		}
		if !ok {
			return tree.Absent(), false
		}
	}
	return cur, true
}

type segment struct {
	key   string // object key when index < 0
	index int    // array index, or -1 for an object key
}

// splitPath tokenises "engine.models[0].auth" into ordered segments.
func splitPath(p string) []segment {
	var segs []segment
	for _, part := range strings.Split(p, ".") {
		if part == "" {
			continue
		}
		segs = appendPartSegments(segs, part)
	}
	return segs
}

// appendPartSegments splits one dotted part (e.g. "models[0][1]") into its key
// segment followed by any bracketed index segments, appending them in order.
func appendPartSegments(segs []segment, part string) []segment {
	br := strings.IndexByte(part, '[')
	name := part
	if br >= 0 {
		name = part[:br]
	}
	if name != "" {
		segs = append(segs, segment{key: name, index: -1})
	}
	if br < 0 {
		return segs
	}
	for rest := part[br:]; rest != "" && rest[0] == '['; {
		end := strings.IndexByte(rest, ']')
		if end < 0 {
			break
		}
		if i, err := strconv.Atoi(rest[1:end]); err == nil {
			segs = append(segs, segment{index: i})
		}
		rest = rest[end+1:]
	}
	return segs
}

// value is the single concrete Value over an internal tree node.
type value struct {
	node *tree.Node
}

func (v value) At() Position { return fromTreePos(v.node.Pos) }

func (v value) String() (string, *Diagnostic) {
	if v.node.Kind == tree.KindString {
		return v.node.Str, nil
	}
	return "", v.mismatch("string")
}

func (v value) Int() (int64, *Diagnostic) {
	switch v.node.Kind {
	case tree.KindInt:
		return v.node.Int, nil
	case tree.KindFloat:
		// A whole-number float read as int is exact; a fractional one is a
		// mismatch, not a silent truncation.
		if v.node.Float == float64(int64(v.node.Float)) {
			return int64(v.node.Float), nil
		}
		return 0, v.mismatch("int")
	case tree.KindAbsent, tree.KindString, tree.KindBool, tree.KindObject, tree.KindArray:
		return 0, v.mismatch("int")
	default:
		return 0, v.mismatch("int")
	}
}

func (v value) Bool() (bool, *Diagnostic) {
	if v.node.Kind == tree.KindBool {
		return v.node.Bool, nil
	}
	return false, v.mismatch("bool")
}

// Field returns the same abstract Value so element/field walks stay behind the
// read surface. Value is an interface BY CONTRACT (contracts/configuration.md
// §2); the signature is fixed by the frozen contract.
//
//nolint:ireturn // Value is an interface fixed by contracts/configuration.md §2; see doc above.
func (v value) Field(key string) (Value, bool) {
	child, ok := v.node.Child(key)
	if !ok {
		return value{node: tree.Absent()}, false
	}
	return value{node: child}, true
}

func (v value) Len() (int, bool) { return v.node.Len() }

// mismatch builds the *Diagnostic for a failed total conversion, stamped with
// the leaf's own Position so the operator sees "backend.yaml:14:7".
func (v value) mismatch(want string) *Diagnostic {
	return &Diagnostic{
		Severity: SeverityError,
		At:       fromTreePos(v.node.Pos),
		Summary:  fmt.Sprintf("expected %s, found %s", want, kindName(v.node.Kind)),
	}
}

func kindName(k tree.Kind) string {
	switch k {
	case tree.KindString:
		return "string"
	case tree.KindInt:
		return "int"
	case tree.KindFloat:
		return "number"
	case tree.KindBool:
		return "bool"
	case tree.KindObject:
		return "object"
	case tree.KindArray:
		return "array"
	default:
		return "absent"
	}
}

func fromTreePos(p tree.Position) Position {
	return Position{Source: p.Source, Line: p.Line, Column: p.Column}
}

func toTreePos(p Position) tree.Position {
	return tree.Position{Source: p.Source, Line: p.Line, Column: p.Column}
}
