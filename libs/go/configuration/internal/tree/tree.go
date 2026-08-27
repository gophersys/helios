// Package tree is the unexported in-memory representation shared by the
// configuration parser and the configurationtest fakes. It is the single
// concrete shape behind the public configuration.Document and
// configuration.Value interfaces, so the real parser and the map-backed fake
// produce structurally identical read surfaces (the substitutability oracle,
// 08 §2).
//
// This package holds NO knowledge of the public interface types — it speaks in
// the primitive Kind/Node vocabulary. The configuration package adapts these
// nodes to its Document/Value interfaces; configurationtest builds nodes from a
// Go map. Both go through the same Node, so Lookup/Field/Len/conversions behave
// identically regardless of origin.
package tree

// Position is a 1-based source coordinate mirrored from configuration.Position.
// Line == 0 means "synthetic / no source" (an honest unknown, never fabricated).
// It is duplicated here (not imported) to keep this leaf package dependency-free
// of the public surface that depends on it.
type Position struct {
	Source string
	Line   int
	Column int
}

// Kind enumerates the resolved node shapes the IR models.
type Kind int

// The resolved node kinds. KindAbsent is the zero Node ("no value here") on
// which conversions yield the type zero plus a mismatch signal and Field/Len
// report not-ok; the remaining kinds are the scalar leaves and the two
// containers, each mapping to one Value conversion or container accessor.
const (
	KindAbsent Kind = iota
	KindString
	KindInt
	KindBool
	KindFloat
	KindObject
	KindArray
)

// Node is one resolved node in the frozen tree. After construction it is never
// mutated: the parser and the fake both build a complete tree and hand back a
// read-only root. Sharing across goroutines is safe precisely because no method
// writes.
type Node struct {
	Kind Kind
	Pos  Position

	// Scalar payloads. Only the field matching Kind is meaningful.
	Str   string
	Int   int64
	Float float64
	Bool  bool

	// Object payload: insertion-ordered keys plus the lookup map. Keys preserve
	// declaration order so All()/iteration is deterministic.
	keys     []string
	children map[string]*Node

	// Array payload.
	elems []*Node
}

// Absent is the canonical zero/absent node. It is returned (never nil) so every
// accessor is total and panic-free.
func Absent() *Node { return &Node{Kind: KindAbsent} }

// NewString builds a string leaf.
func NewString(s string, pos Position) *Node {
	return &Node{Kind: KindString, Str: s, Pos: pos}
}

// NewInt builds an integer leaf.
func NewInt(i int64, pos Position) *Node { return &Node{Kind: KindInt, Int: i, Pos: pos} }

// NewFloat builds a float leaf.
func NewFloat(f float64, pos Position) *Node { return &Node{Kind: KindFloat, Float: f, Pos: pos} }

// NewBool builds a boolean leaf.
func NewBool(b bool, pos Position) *Node { return &Node{Kind: KindBool, Bool: b, Pos: pos} }

// NewObject builds an empty object node.
func NewObject(pos Position) *Node {
	return &Node{Kind: KindObject, Pos: pos, children: map[string]*Node{}}
}

// NewArray builds an array node from elements.
func NewArray(elems []*Node, pos Position) *Node {
	return &Node{Kind: KindArray, Pos: pos, elems: elems}
}

// Set inserts or replaces a child on an object node, preserving first-seen key
// order. Used only during construction.
func (n *Node) Set(key string, child *Node) {
	if n.Kind != KindObject {
		return
	}
	if n.children == nil {
		n.children = map[string]*Node{}
	}
	if _, seen := n.children[key]; !seen {
		n.keys = append(n.keys, key)
	}
	n.children[key] = child
}

// Has reports whether an object node already declares key (duplicate detection).
func (n *Node) Has(key string) bool {
	if n.Kind != KindObject || n.children == nil {
		return false
	}
	_, ok := n.children[key]
	return ok
}

// Keys returns object keys in first-seen order.
func (n *Node) Keys() []string {
	if n.Kind != KindObject {
		return nil
	}
	return n.keys
}

// Child returns the named child of an object node; ok == false past the edge.
func (n *Node) Child(key string) (*Node, bool) {
	if n.Kind != KindObject || n.children == nil {
		return Absent(), false
	}
	c, ok := n.children[key]
	if !ok {
		return Absent(), false
	}
	return c, true
}

// Elem returns the i-th array element; ok == false out of range or non-array.
func (n *Node) Elem(i int) (*Node, bool) {
	if n.Kind != KindArray || i < 0 || i >= len(n.elems) {
		return Absent(), false
	}
	return n.elems[i], true
}

// Len reports array arity; ok == false if this is not an array.
func (n *Node) Len() (int, bool) {
	if n.Kind != KindArray {
		return 0, false
	}
	return len(n.elems), true
}
