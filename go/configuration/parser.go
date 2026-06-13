package configuration

import (
	"context"
	"errors"
	"fmt"

	"github.com/gophersys/libs/go/configuration/internal/tree"
)

// defaultMaxSourceBytes is the internal sane cap applied when
// Config.MaxSourceBytes is 0 (a DoS/footgun guard at the parse edge).
const defaultMaxSourceBytes = 16 << 20 // 16 MiB

// ErrUnknownFormat is the sentinel for a Config naming a Format outside the
// closed set. New returns it wrapped with the offending value via %w so a
// caller can branch with errors.Is without string-matching.
var ErrUnknownFormat = errors.New("configuration: unknown Format")

// ErrInvalidMaxSourceBytes is the sentinel for a negative Config.MaxSourceBytes.
// New returns it wrapped with the offending value via %w.
var ErrInvalidMaxSourceBytes = errors.New("configuration: MaxSourceBytes must be >= 0")

// New is the pure constructor spine. It validates Config, wires the Format
// table and the Validator list into a ready Parser, and captures Deps. It
// performs NO I/O, reads NO env, consults NO clock: the first byte is read
// only when Parse is later called with a context. A malformed Config (e.g.
// negative MaxSourceBytes, an unknown Format) is the only error path.
//
// The Parser return is an INTERFACE by the frozen contract
// (contracts/configuration.md §2, signature verbatim): the fake Parser
// (configurationtest.Parser) must be substitutable for the real one — the
// conformance suite asserts it — so returning the unexported concrete *parser
// is impossible without breaking the published surface (the cardinal sin, 10 §9).
//
//nolint:ireturn // Parser is an interface fixed by contracts/configuration.md §2; see doc above.
func New(configuration Config, dependencies Deps) (Parser, error) {
	if !isKnownFormat(configuration.Format) {
		// stdlib fmt.Errorf+%w wraps this package's OWN sentinel: configuration
		// is the lowest layer and must NOT depend on the errors library
		// (rationale 5; it is parsed before anything is wired). errors.Is reaches
		// ErrUnknownFormat; that is the structured-inspection contract here.
		return nil, fmt.Errorf("%w: %q", ErrUnknownFormat, configuration.Format) //nolint:wrapcheck // own sentinel via stdlib %w; no errors-library dep (rationale 5).
	}
	if configuration.MaxSourceBytes < 0 {
		return nil, fmt.Errorf("%w, got %d", ErrInvalidMaxSourceBytes, configuration.MaxSourceBytes) //nolint:wrapcheck // own sentinel via stdlib %w; no errors-library dep (rationale 5).
	}
	maxBytes := configuration.MaxSourceBytes
	if maxBytes == 0 {
		maxBytes = defaultMaxSourceBytes
	}
	return &parser{
		format:         configuration.Format,
		allowUnknown:   configuration.AllowUnknownKeys,
		maxSourceBytes: maxBytes,
		validators:     configuration.Validators,
		source:         dependencies.Source,
	}, nil
}

func isKnownFormat(f Format) bool {
	switch f {
	case FormatJSON, FormatYAML, FormatTOML, FormatEnv:
		return true
	default:
		return false
	}
}

// parser is the single concrete Parser. It is immutable after New and safe for
// concurrent use: Parse/Merge build fresh trees and never write shared state.
type parser struct {
	format         Format
	allowUnknown   bool
	maxSourceBytes int
	validators     []Validator
	source         Source
}

// Parse returns the Document INTERFACE by the frozen contract
// (contracts/configuration.md §2): immutability is structural and the fake
// shares this read surface; the signature is fixed by the Parser contract.
//
//nolint:ireturn // Document is an interface fixed by contracts/configuration.md §2; see doc above.
func (p *parser) Parse(ctx context.Context, name string) (Document, Diagnostics, error) {
	var diags Diagnostics

	raw, err := p.source.Read(ctx, name)
	if err != nil {
		// I/O failure ONLY — the document is unusable; surface a *ParseError.
		return nil, diags, &ParseError{Source: name, Err: err}
	}

	if len(raw) > p.maxSourceBytes {
		// Over-cap is a data problem, not couldn't-read: it is a Diagnostic.
		diags.Append(Diagnostic{
			Severity: SeverityError,
			At:       Position{Source: name},
			Summary:  fmt.Sprintf("source exceeds MaxSourceBytes (%d > %d)", len(raw), p.maxSourceBytes),
		})
		return newDocument(tree.Absent(), p.format, Position{Source: name}), diags, nil
	}

	root := decode(p.format, name, raw, p.allowUnknown, &diags)
	doc := newDocument(root, p.format, Position{Source: name})

	// Validation is a separate phase: all validators run, in order, after parse.
	for _, v := range p.validators {
		if v == nil {
			continue
		}
		v.Validate(doc, &diags)
	}

	return doc, diags, nil
}

// Merge returns the Document INTERFACE by the frozen contract
// (contracts/configuration.md §2), the same read surface Parse yields; the
// signature is fixed by the Parser contract.
//
//nolint:ireturn // Document is an interface fixed by contracts/configuration.md §2; see doc above.
func (p *parser) Merge(ctx context.Context, base, overlay Document) (Document, Diagnostics, error) {
	var diags Diagnostics

	baseRoot := rootOf(base)
	overlayRoot := rootOf(overlay)

	merged := mergeNodes(baseRoot, overlayRoot, "", &diags)

	// Format/Origin reflect the fold: the overlay is the winning layer.
	format := p.format
	origin := Position{}
	switch {
	case overlay != nil:
		format = overlay.Format()
		origin = overlay.Origin()
	case base != nil:
		format = base.Format()
		origin = base.Origin()
	}

	return newDocument(merged, format, origin), diags, nil
}

// rootOf extracts the internal tree root from a Document built by this package
// (the real parser or the configurationtest fakes both yield *document). An
// unknown Document implementation degrades to an empty tree rather than panic.
func rootOf(d Document) *tree.Node {
	if d == nil {
		return tree.Absent()
	}
	if doc, ok := d.(*document); ok && doc.root != nil {
		return doc.root
	}
	return tree.Absent()
}

// mergeNodes folds overlay over base. Objects merge key-by-key; any other
// overlay node replaces the base wholesale (overlay wins per Path). Each
// surviving leaf keeps its own origin Position because nodes are reused, never
// rebuilt. Inputs are never mutated: object merges allocate a fresh node.
func mergeNodes(base, overlay *tree.Node, path Path, diags *Diagnostics) *tree.Node {
	switch {
	case overlay == nil || overlay.Kind == tree.KindAbsent:
		return base
	case base == nil || base.Kind == tree.KindAbsent:
		return overlay
	}

	// Both present and both objects: deep-merge into a fresh object node.
	if base.Kind == tree.KindObject && overlay.Kind == tree.KindObject {
		out := tree.NewObject(overlay.Pos)
		// base keys first (preserving order), overridden where overlay has them.
		for _, k := range base.Keys() {
			bChild, _ := base.Child(k)
			if oChild, ok := overlay.Child(k); ok {
				out.Set(k, mergeNodes(bChild, oChild, path.Child(k), diags))
			} else {
				out.Set(k, bChild)
			}
		}
		// overlay-only keys appended.
		for _, k := range overlay.Keys() {
			if !base.Has(k) {
				oChild, _ := overlay.Child(k)
				out.Set(k, oChild)
			}
		}
		return out
	}

	// Type conflict (e.g. object base, scalar overlay) is surfaced, not fatal.
	if base.Kind != overlay.Kind {
		diags.Append(Diagnostic{
			Severity: SeverityWarning,
			Path:     path,
			At:       fromTreePos(overlay.Pos),
			Summary: fmt.Sprintf("merge type conflict: base is %s, overlay is %s; overlay wins",
				kindName(base.Kind), kindName(overlay.Kind)),
		})
	}

	// Overlay wins per Path: the overlay leaf (with its own origin) replaces base.
	return overlay
}
