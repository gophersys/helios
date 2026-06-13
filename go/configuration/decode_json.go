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

// decodeJSON decodes JSON into the internal tree with truthful per-token
// positions and strict duplicate-key detection. It is total: malformed JSON is
// reported as a SeverityError Diagnostic and yields an empty tree, never a
// panic. dupSev is SeverityError under strict (the default) or SeverityWarning
// when AllowUnknownKeys downgrades it.
func decodeJSON(source string, raw []byte, dupSev Severity, diags *Diagnostics) *tree.Node {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	lines := newLineMap(raw)

	root, err := jsonValue(dec, source, raw, lines, dupSev, diags)
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
// that value's first token began.
func jsonValue(dec *json.Decoder, source string, raw []byte, lines *lineMap, dupSev Severity, diags *Diagnostics) (*tree.Node, error) {
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
			return jsonObject(dec, source, raw, lines, pos, dupSev, diags)
		case '[':
			return jsonArray(dec, source, raw, lines, pos, dupSev, diags)
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

func jsonObject(dec *json.Decoder, source string, raw []byte, lines *lineMap, pos Position, dupSev Severity, diags *Diagnostics) (*tree.Node, error) {
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
		if obj.Has(key) {
			// Strict-by-default: a duplicate key is a finding (the silent
			// last-wins of encoding/json is exactly the typo footgun this
			// pattern exists to catch).
			diags.Append(Diagnostic{
				Severity: dupSev,
				Path:     pathForKeyAt(obj, key, pos),
				At:       keyPos,
				Summary:  fmt.Sprintf("duplicate key %q", key),
			})
		}
		child, err := jsonValue(dec, source, raw, lines, dupSev, diags)
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

func jsonArray(dec *json.Decoder, source string, raw []byte, lines *lineMap, pos Position, dupSev Severity, diags *Diagnostics) (*tree.Node, error) {
	var elems []*tree.Node
	for dec.More() {
		el, err := jsonValue(dec, source, raw, lines, dupSev, diags)
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

// pathForKeyAt is a best-effort Path for a duplicate-key diagnostic. The object
// position is known but not its full path; the key alone is the operator-facing
// signal, so the Path is the bare key (root-relative).
func pathForKeyAt(_ *tree.Node, key string, _ Position) Path {
	return Path("").Child(key)
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
