package configuration

import (
	"fmt"
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/configuration/internal/tree"
)

// decodeEnv decodes KEY=VALUE lines into a nested tree. Dotted keys nest
// ("ENGINE.NAME=x" -> {ENGINE:{NAME:x}}). Blank lines and lines whose first
// non-space rune is '#' are comments. Each leaf carries its 1-based source line.
// It is total: a malformed line is a Diagnostic, never a panic.
//
// dupSev is the severity for duplicate keys (Error strict, Warning when
// AllowUnknownKeys downgrades it). Env values are typed by inference: an integer
// literal becomes an int, true/false a bool, everything else a string — so a
// library's typed read does not have to re-parse "8" out of a string.
func decodeEnv(source string, raw []byte, dupSev Severity, diags *Diagnostics) *tree.Node {
	root := tree.NewObject(tree.Position{Source: source})
	for lineNo, line := range strings.Split(string(raw), "\n") {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		eq := strings.IndexByte(line, '=')
		if eq < 0 {
			diags.Append(Diagnostic{
				Severity: SeverityError,
				At:       Position{Source: source, Line: lineNo + 1, Column: 1},
				Summary:  fmt.Sprintf("malformed env line: missing '=' in %q", trimmed),
			})
			continue
		}
		key := strings.TrimSpace(line[:eq])
		val := strings.TrimSpace(line[eq+1:])
		if key == "" {
			diags.Append(Diagnostic{
				Severity: SeverityError,
				At:       Position{Source: source, Line: lineNo + 1, Column: 1},
				Summary:  "malformed env line: empty key",
			})
			continue
		}
		col := eq + 2 // 1-based column where the value begins
		pos := tree.Position{Source: source, Line: lineNo + 1, Column: col}
		setEnvPath(root, strings.Split(key, "."), inferLeaf(val, pos), pos, dupSev, diags)
	}
	return root
}

// setEnvPath walks/creates the object chain for a dotted key and sets the leaf.
func setEnvPath(root *tree.Node, segs []string, leaf *tree.Node, pos tree.Position, dupSev Severity, diags *Diagnostics) {
	cur := root
	for i, seg := range segs {
		last := i == len(segs)-1
		if last {
			if cur.Has(seg) {
				diags.Append(Diagnostic{
					Severity: dupSev,
					Path:     envPath(segs),
					At:       fromTreePos(pos),
					Summary:  fmt.Sprintf("duplicate key %q", strings.Join(segs, ".")),
				})
			}
			cur.Set(seg, leaf)
			return
		}
		child, ok := cur.Child(seg)
		if ok && child.Kind != tree.KindObject {
			// Strict-by-default: a non-object already occupies an intermediate
			// segment that a dotted key needs as a container. Overwriting it
			// silently is exactly the typo footgun this pattern exists to catch
			// (e.g. LOG=info then LOG.LEVEL=debug loses LOG). Diagnose, then
			// proceed — accumulate-all means later leaves still get placed.
			diags.Append(Diagnostic{
				Severity: dupSev,
				Path:     envPath(segs[:i+1]),
				At:       fromTreePos(pos),
				Summary: fmt.Sprintf("key %q is set as a scalar but %q needs it as an object",
					strings.Join(segs[:i+1], "."), strings.Join(segs, ".")),
			})
		}
		if !ok || child.Kind != tree.KindObject {
			child = tree.NewObject(pos)
			cur.Set(seg, child)
		}
		cur = child
	}
}

func envPath(segs []string) Path {
	var p Path
	for _, s := range segs {
		p = p.Child(s)
	}
	return p
}

// inferLeaf types an env value: a matched surrounding quote pair forces a string
// (quotes are stripped and no further inference runs, exactly as YAML/TOML treat
// a quoted scalar — `KEY="8"` is the string "8", never the int 8); an unquoted
// value infers int, bool, else string. The shared stripSurroundingQuotes helper
// keeps env's quote rule identical to the other decoders (one concept, one home).
func inferLeaf(val string, pos tree.Position) *tree.Node {
	if stripped := stripSurroundingQuotes(val); stripped != val {
		return tree.NewString(stripped, pos)
	}
	if val == "true" || val == "false" {
		return tree.NewBool(val == "true", pos)
	}
	if i, err := strconv.ParseInt(val, 10, 64); err == nil {
		return tree.NewInt(i, pos)
	}
	return tree.NewString(val, pos)
}
