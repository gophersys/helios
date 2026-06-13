package configuration

import (
	"github.com/gophersys/libs/go/configuration/internal/tree"
)

// decode dispatches to the format-specific decoder. Each decoder is total: it
// NEVER panics. Bytes that don't match the declared Format become a Diagnostic
// (the decoder returns an empty/partial tree and appends a SeverityError),
// honoring "Format is closed: a mismatch is a Diagnostic, never a panic."
//
// allowUnknown downgrades the strict unknown/duplicate-key findings from Error
// to Warning. Strict (Error) is the zero-Config default.
func decode(format Format, source string, raw []byte, allowUnknown bool, diags *Diagnostics) *tree.Node {
	sev := SeverityError
	if allowUnknown {
		sev = SeverityWarning
	}
	switch format {
	case FormatJSON:
		return decodeJSON(source, raw, sev, diags)
	case FormatEnv:
		return decodeEnv(source, raw, sev, diags)
	case FormatYAML:
		return decodeYAML(source, raw, sev, diags)
	case FormatTOML:
		return decodeTOML(source, raw, sev, diags)
	default:
		// Unreachable: New rejects unknown formats. Defensive only.
		diags.Append(Diagnostic{
			Severity: SeverityError,
			At:       Position{Source: source},
			Summary:  "unsupported format",
		})
		return tree.Absent()
	}
}
