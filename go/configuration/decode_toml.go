package configuration

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/configuration/internal/tree"
)

// decodeTOML decodes the "key = value" + "[table]" subset of TOML using only
// the standard library (the contract names no TOML dependency, and Go's stdlib
// has no TOML parser). It handles top-level pairs, [table] and [a.b.c] dotted
// table headers, and scalar values with type inference; it does NOT implement
// arrays-of-tables ([[x]]), inline tables, multiline strings, or datetimes.
// Bytes outside this subset produce a SeverityError Diagnostic, never a panic.
//
// As with YAML this is the pragmatic v1 surface that keeps the closed Format set
// honest without a third-party dependency; a richer decoder is an additive,
// non-breaking upgrade later (10 §4).
func decodeTOML(source string, raw []byte, dupSev Severity, diags *Diagnostics) *tree.Node {
	root := tree.NewObject(tree.Position{Source: source})
	cur := root

	for lineNo, line := range strings.Split(string(raw), "\n") {
		content := stripTOMLComment(line)
		trimmed := strings.TrimSpace(content)
		if trimmed == "" {
			continue
		}

		if strings.HasPrefix(trimmed, "[[") {
			diags.Append(Diagnostic{
				Severity: SeverityError,
				At:       Position{Source: source, Line: lineNo + 1, Column: 1},
				Summary:  "unsupported TOML construct: arrays-of-tables are not decoded in v1",
			})
			continue
		}

		if strings.HasPrefix(trimmed, "[") {
			if !strings.HasSuffix(trimmed, "]") {
				diags.Append(Diagnostic{
					Severity: SeverityError,
					At:       Position{Source: source, Line: lineNo + 1, Column: 1},
					Summary:  fmt.Sprintf("malformed TOML table header: %q", trimmed),
				})
				continue
			}
			name := strings.TrimSpace(trimmed[1 : len(trimmed)-1])
			pos := tree.Position{Source: source, Line: lineNo + 1, Column: 1}
			cur = ensureTable(root, strings.Split(name, "."), pos, dupSev, diags)
			continue
		}

		eq := strings.IndexByte(content, '=')
		if eq < 0 {
			diags.Append(Diagnostic{
				Severity: SeverityError,
				At:       Position{Source: source, Line: lineNo + 1, Column: 1},
				Summary:  fmt.Sprintf("malformed TOML line: expected 'key = value', got %q", trimmed),
			})
			continue
		}
		key := strings.TrimSpace(content[:eq])
		key = strings.Trim(key, `"'`)
		valStr := strings.TrimSpace(content[eq+1:])
		col := eq + 2
		pos := tree.Position{Source: source, Line: lineNo + 1, Column: col}
		if cur.Has(key) {
			diags.Append(Diagnostic{
				Severity: dupSev,
				Path:     Path("").Child(key),
				At:       fromTreePos(pos),
				Summary:  fmt.Sprintf("duplicate key %q", key),
			})
		}
		cur.Set(key, inferTOMLScalar(valStr, pos))
	}
	return root
}

// ensureTable walks/creates the dotted table chain and returns the leaf table.
// A scalar already occupying a segment a table header needs as a container is a
// strict-by-default finding (the silent clobber that loses `server = 1` when a
// later `[server]` header appears is exactly the typo footgun this pattern
// exists to catch), then the table replaces it so later keys still land.
func ensureTable(root *tree.Node, segs []string, pos tree.Position, dupSev Severity, diags *Diagnostics) *tree.Node {
	cur := root
	for i, seg := range segs {
		seg = strings.TrimSpace(seg)
		child, ok := cur.Child(seg)
		if ok && child.Kind != tree.KindObject {
			trimmed := make([]string, len(segs))
			for j, s := range segs {
				trimmed[j] = strings.TrimSpace(s)
			}
			diags.Append(Diagnostic{
				Severity: dupSev,
				Path:     Path("").Child(strings.Join(trimmed[:i+1], ".")),
				At:       fromTreePos(pos),
				Summary: fmt.Sprintf("key %q is set as a scalar but table header [%s] needs it as a table",
					strings.Join(trimmed[:i+1], "."), strings.Join(trimmed, ".")),
			})
		}
		if !ok || child.Kind != tree.KindObject {
			child = tree.NewObject(pos)
			cur.Set(seg, child)
		}
		cur = child
	}
	return cur
}

func stripTOMLComment(line string) string {
	inSingle, inDouble := false, false
	for i := 0; i < len(line); i++ {
		c := line[i]
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
			if !inSingle && !inDouble {
				return line[:i]
			}
		}
	}
	return line
}

func inferTOMLScalar(s string, pos tree.Position) *tree.Node {
	if len(s) >= 2 && ((s[0] == '"' && s[len(s)-1] == '"') || (s[0] == '\'' && s[len(s)-1] == '\'')) {
		return tree.NewString(s[1:len(s)-1], pos)
	}
	switch s {
	case "true":
		return tree.NewBool(true, pos)
	case "false":
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
