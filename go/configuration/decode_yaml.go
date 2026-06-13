package configuration

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/configuration/internal/tree"
)

// decodeYAML decodes the indentation-nested "key: value" subset of YAML using
// only the standard library (the contract names no YAML dependency, and Go's
// stdlib has no YAML parser). It handles nested mappings via two-space (or any
// consistent) indentation and scalar leaves with type inference; it does NOT
// implement flow collections, anchors/aliases, multi-document streams, or block
// scalars. Bytes outside this subset produce a SeverityError Diagnostic, never
// a panic — honoring "a source whose bytes don't match Format is a Diagnostic."
//
// This is the pragmatic v1 surface for FormatYAML: enough to keep the closed
// Format set honest (New accepts FormatYAML, Parse decodes the common subset)
// without taking a third-party dependency. Richer YAML is an additive,
// non-breaking decoder upgrade later (10 §4).
func decodeYAML(source string, raw []byte, dupSev Severity, diags *Diagnostics) *tree.Node {
	root := tree.NewObject(tree.Position{Source: source})
	// indentStack tracks (indentWidth, node) frames; root is depth -1.
	type frame struct {
		indent int
		node   *tree.Node
	}
	stack := []frame{{indent: -1, node: root}}

	for lineNo, line := range strings.Split(string(raw), "\n") {
		raw := line
		// Strip trailing comments (only when '#' starts a token; conservative:
		// a space-preceded '#').
		if i := indexUnquotedHash(raw); i >= 0 {
			raw = raw[:i]
		}
		if strings.TrimSpace(raw) == "" {
			continue
		}
		indent := countIndent(raw)
		content := strings.TrimSpace(raw)

		if strings.HasPrefix(content, "- ") || content == "-" {
			diags.Append(Diagnostic{
				Severity: SeverityError,
				At:       Position{Source: source, Line: lineNo + 1, Column: indent + 1},
				Summary:  "unsupported YAML construct: block sequences are not decoded in v1",
			})
			continue
		}

		colon := strings.IndexByte(content, ':')
		if colon < 0 {
			diags.Append(Diagnostic{
				Severity: SeverityError,
				At:       Position{Source: source, Line: lineNo + 1, Column: indent + 1},
				Summary:  fmt.Sprintf("malformed YAML line: expected 'key: value', got %q", content),
			})
			continue
		}

		// Pop frames until the parent is shallower than this line.
		for len(stack) > 1 && indent <= stack[len(stack)-1].indent {
			stack = stack[:len(stack)-1]
		}
		parent := stack[len(stack)-1].node

		key := strings.TrimSpace(content[:colon])
		valStr := strings.TrimSpace(content[colon+1:])
		key = unquoteYAML(key)
		pos := tree.Position{Source: source, Line: lineNo + 1, Column: indent + 1}

		if parent.Has(key) {
			diags.Append(Diagnostic{
				Severity: dupSev,
				Path:     Path("").Child(key),
				At:       fromTreePos(pos),
				Summary:  fmt.Sprintf("duplicate key %q", key),
			})
		}

		if valStr == "" {
			// A nested mapping opens here.
			child := tree.NewObject(pos)
			parent.Set(key, child)
			stack = append(stack, frame{indent: indent, node: child})
			continue
		}
		valPos := tree.Position{Source: source, Line: lineNo + 1, Column: indent + colon + 2}
		parent.Set(key, inferYAMLScalar(valStr, valPos))
	}
	return root
}

func countIndent(line string) int {
	n := 0
	for _, r := range line {
		if r == ' ' {
			n++
		} else if r == '\t' {
			n += 1
		} else {
			break
		}
	}
	return n
}

// indexUnquotedHash returns the index of a comment '#' (preceded by whitespace
// or at line start) outside of quotes, or -1.
func indexUnquotedHash(s string) int {
	inSingle, inDouble := false, false
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch c {
		case '\'':
			if !inDouble {
				inSingle = !inSingle
			}
		case '"':
			if !inSingle {
				inDouble = !inDouble
			}
		case '#':
			if !inSingle && !inDouble && (i == 0 || s[i-1] == ' ' || s[i-1] == '\t') {
				return i
			}
		}
	}
	return -1
}

func unquoteYAML(s string) string {
	if len(s) >= 2 {
		if (s[0] == '"' && s[len(s)-1] == '"') || (s[0] == '\'' && s[len(s)-1] == '\'') {
			return s[1 : len(s)-1]
		}
	}
	return s
}

// inferYAMLScalar types a YAML scalar: quoted => string; true/false => bool;
// integer => int; float => float; else string.
func inferYAMLScalar(s string, pos tree.Position) *tree.Node {
	if len(s) >= 2 && ((s[0] == '"' && s[len(s)-1] == '"') || (s[0] == '\'' && s[len(s)-1] == '\'')) {
		return tree.NewString(s[1:len(s)-1], pos)
	}
	switch s {
	case "true", "True", "yes", "on":
		return tree.NewBool(true, pos)
	case "false", "False", "no", "off":
		return tree.NewBool(false, pos)
	}
	if i, err := strconv.ParseInt(s, 10, 64); err == nil {
		return tree.NewInt(i, pos)
	}
	if f, err := strconv.ParseFloat(s, 64); err == nil {
		return tree.NewFloat(f, pos)
	}
	return tree.NewString(s, pos)
}
