package configuration

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"

	"github.com/gophersys/libs/go/configuration/internal/tree"
)

// errUnexpectedJSONToken is the sentinel for a JSON token the decoder cannot
// place (a stray delimiter or an unmodeled token type). It is wrapped with the
// offending value via %w; it never escapes the package — decodeJSON converts it
// into a SeverityError Diagnostic — but a static sentinel keeps the err113
// "no dynamic errors" discipline intact on the internal decode path.
var errUnexpectedJSONToken = errors.New("unexpected JSON token")

// errJSONKeyNotString is the sentinel for an object key that is not a string.
var errJSONKeyNotString = errors.New("object key is not a string")

// errJSONTooDeep is the sentinel for JSON nesting that exceeds maxJSONDepth. It
// halts recursion BEFORE the Go stack overflows — a stack overflow is a runtime
// FATAL (not a recoverable panic), so an unbounded recursive decoder would crash
// the whole process on adversarial input that is still under MaxSourceBytes,
// defeating both the "never a panic" guarantee and the MaxSourceBytes DoS guard.
// decodeJSON converts it into a SeverityError Diagnostic; it never escapes.
var errJSONTooDeep = errors.New("JSON nesting too deep")

// maxJSONDepth bounds object/array nesting. Real configuration is shallow; a few
// hundred levels is far beyond any legitimate document yet far below the depth
// at which the Go stack overflows, so the bound is a Diagnostic the operator can
// act on rather than a process-killing fatal error. It is intentionally well
// under the ~10^4-frame overflow threshold to keep a comfortable margin.
const maxJSONDepth = 256

// decodeJSON decodes JSON into the internal tree with truthful per-token
// positions and strict duplicate-key detection. It is total: malformed JSON is
// reported as a SeverityError Diagnostic and yields an empty tree, never a
// panic. dupSev is SeverityError under strict (the default) or SeverityWarning
// when AllowUnknownKeys downgrades it.
func decodeJSON(source string, raw []byte, dupSev Severity, diags *Diagnostics) *tree.Node {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	lines := newLineMap(raw)

	root, err := jsonValue(dec, source, raw, lines, dupSev, diags, "", 0)
	if err != nil {
		diags.Append(Diagnostic{
			Severity: SeverityError,
			At:       posAtOffset(source, raw, lines, dec.InputOffset()),
			Summary:  "invalid JSON: " + err.Error(),
		})
		if root == nil {
			return tree.Absent()
		}
		return root
	}
	// Reject trailing tokens (e.g. two top-level values) as malformed.
	if _, err := dec.Token(); !errors.Is(err, io.EOF) {
		diags.Append(Diagnostic{
			Severity: SeverityError,
			At:       posAtOffset(source, raw, lines, dec.InputOffset()),
			Summary:  "invalid JSON: trailing data after top-level value",
		})
	}
	if root == nil {
		return tree.Absent()
	}
	return root
}

// jsonValue reads exactly one JSON value from the decoder, recursing for
// objects/arrays. The position stamped on each node is the byte offset where
// that value's first token began. prefix is the FULL resolved-tree Path of this
// value (extended with .Child(key)/.Index(i) on descent) so a nested
// duplicate-key Diagnostic reports its complete dotted path, not a root-relative
// bare key. depth is the current container nesting level; it is bounded by
// maxJSONDepth so adversarial deep nesting becomes a Diagnostic rather than a
// fatal stack overflow.
func jsonValue(dec *json.Decoder, source string, raw []byte, lines *lineMap, dupSev Severity, diags *Diagnostics, prefix Path, depth int) (*tree.Node, error) {
	startOff := dec.InputOffset()
	tok, err := dec.Token()
	if err != nil {
		// Internal decode error: never escapes the package (decodeJSON converts
		// it into a SeverityError Diagnostic). Wrapped with stdlib %w because
		// configuration takes no errors-library dependency (rationale 5).
		return nil, fmt.Errorf("read JSON token: %w", err) //nolint:wrapcheck // internal-only; stdlib %w, no errors-library dep (rationale 5).
	}
	pos := posAtOffset(source, raw, lines, startOff)

	switch t := tok.(type) {
	case json.Delim:
		switch t {
		case '{':
			if depth >= maxJSONDepth {
				return tree.NewObject(toTreePos(pos)), fmt.Errorf("%w (> %d)", errJSONTooDeep, maxJSONDepth) //nolint:wrapcheck // internal-only; wraps own sentinel via stdlib %w (rationale 5).
			}
			return jsonObject(dec, source, raw, lines, pos, dupSev, diags, prefix, depth+1)
		case '[':
			if depth >= maxJSONDepth {
				return tree.NewArray(nil, toTreePos(pos)), fmt.Errorf("%w (> %d)", errJSONTooDeep, maxJSONDepth) //nolint:wrapcheck // internal-only; wraps own sentinel via stdlib %w (rationale 5).
			}
			return jsonArray(dec, source, raw, lines, pos, dupSev, diags, prefix, depth+1)
		default:
			return nil, fmt.Errorf("%w %q", errUnexpectedJSONToken, t) //nolint:wrapcheck // internal-only; wraps own sentinel via stdlib %w (rationale 5).
		}
	case string:
		return tree.NewString(t, toTreePos(pos)), nil
	case json.Number:
		return numberNode(string(t), toTreePos(pos)), nil
	case bool:
		return tree.NewBool(t, toTreePos(pos)), nil
	case nil:
		// JSON null is modeled as an absent leaf carrying its position.
		n := tree.Absent()
		n.Pos = toTreePos(pos)
		return n, nil
	default:
		return nil, fmt.Errorf("%w %T", errUnexpectedJSONToken, tok) //nolint:wrapcheck // internal-only; wraps own sentinel via stdlib %w (rationale 5).
	}
}

func jsonObject(dec *json.Decoder, source string, raw []byte, lines *lineMap, pos Position, dupSev Severity, diags *Diagnostics, prefix Path, depth int) (*tree.Node, error) {
	obj := tree.NewObject(toTreePos(pos))
	for dec.More() {
		keyOff := dec.InputOffset()
		keyTok, err := dec.Token()
		if err != nil {
			return obj, fmt.Errorf("read JSON object key token: %w", err) //nolint:wrapcheck // internal-only; stdlib %w, no errors-library dep (rationale 5).
		}
		key, ok := keyTok.(string)
		if !ok {
			return obj, errJSONKeyNotString
		}
		keyPos := posAtOffset(source, raw, lines, keyOff)
		childPath := prefix.Child(key)
		if obj.Has(key) {
			// Strict-by-default: a duplicate key is a finding (the silent
			// last-wins of encoding/json is exactly the typo footgun this
			// pattern exists to catch). The Path is the FULL dotted path to the
			// offending key (prefix.Child(key)), so a nested duplicate names its
			// parent chain, not just the bare leaf key.
			diags.Append(Diagnostic{
				Severity: dupSev,
				Path:     childPath,
				At:       keyPos,
				Summary:  fmt.Sprintf("duplicate key %q", key),
			})
		}
		child, err := jsonValue(dec, source, raw, lines, dupSev, diags, childPath, depth)
		if err != nil {
			return obj, err
		}
		obj.Set(key, child)
	}
	// consume closing '}'
	if _, err := dec.Token(); err != nil {
		return obj, fmt.Errorf("read JSON object close: %w", err) //nolint:wrapcheck // internal-only; stdlib %w, no errors-library dep (rationale 5).
	}
	return obj, nil
}

func jsonArray(dec *json.Decoder, source string, raw []byte, lines *lineMap, pos Position, dupSev Severity, diags *Diagnostics, prefix Path, depth int) (*tree.Node, error) {
	var elems []*tree.Node
	for dec.More() {
		el, err := jsonValue(dec, source, raw, lines, dupSev, diags, prefix.Index(len(elems)), depth)
		if err != nil {
			return tree.NewArray(elems, toTreePos(pos)), err
		}
		elems = append(elems, el)
	}
	if _, err := dec.Token(); err != nil { // closing ']'
		return tree.NewArray(elems, toTreePos(pos)), fmt.Errorf("read JSON array close: %w", err)
	}
	return tree.NewArray(elems, toTreePos(pos)), nil
}

// numberNode classifies a JSON number as int or float.
func numberNode(s string, pos tree.Position) *tree.Node {
	num := json.Number(s)
	if i, err := num.Int64(); err == nil {
		return tree.NewInt(i, pos)
	}
	if f, err := num.Float64(); err == nil {
		return tree.NewFloat(f, pos)
	}
	// Unparseable number: keep the raw text as a string leaf so it round-trips.
	return tree.NewString(s, pos)
}
