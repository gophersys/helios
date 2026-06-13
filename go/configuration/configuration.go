// Package configuration is the universal input-IR pattern: raw bytes are parsed
// ONCE at the edge into an immutable, fully-resolved Document; library Config
// types are then built FROM that Document by reading it by Path. The composition
// root owns parsing — no library parses bytes itself. Strict parsing and
// validation are separate phases, both emitting typed Diagnostics that carry a
// source Position. The package is the lowest layer (parsed before anything is
// wired) and therefore does NOT depend on the errors library; its diagnostics
// are self-contained value types.
//
// Module: github.com/gophersys/libs/go/configuration
package configuration

import "context"

// Format identifies a source encoding the edge knows how to decode. It is a
// CLOSED set on purpose: unknown formats are a Diagnostic, never a panic and
// never a plugin hook. New formats are added here additively, in a minor
// version (10 §4).
type Format string

const (
	FormatJSON Format = "json"
	FormatYAML Format = "yaml"
	FormatTOML Format = "toml"
	FormatEnv  Format = "env" // KEY=VALUE lines; dotted keys nest. The env edge.
)

// Severity orders Diagnostics. A Document is usable iff it carries no
// SeverityError finding. (Two levels only — info-level findings are not a
// failure mode this pattern needs to model; see Open Questions #6.)
type Severity int

const (
	SeverityWarning Severity = iota
	SeverityError
)

// Position is a 1-based source coordinate. The zero Position (Line == 0) means
// "synthetic / no source" — e.g. a value supplied by a default rather than
// parsed. A 0 line is an HONEST "I don't know," never a fabricated guess: the
// retry-with-diagnostics loop (04 §8) and human operators depend on that.
type Position struct {
	Source string // logical input name: "backend.yaml", "ENV", "--flag"
	Line   int    // 1-based; 0 == synthetic / unknown
	Column int    // 1-based; 0 == unknown within line
}

// Diagnostic is one typed finding produced by parsing or validation. It is a
// value type — comparable, copyable, safe to log — NOT an error chain, so a
// phase can collect ALL findings before failing (every problem reported once,
// never one-at-a-time). It carries no dependency on the errors library.
type Diagnostic struct {
	Severity Severity
	Path     Path     // where in the resolved tree
	At       Position // where in the source text (or synthetic)
	Summary  string   // stable, operator-facing
	Detail   string   // optional remediation hint
}

// Validator is the SEPARATE validation phase, consumer-supplied: a library
// declares its OWN shape rules here. The pattern centralizes no schema. Pure:
// it reads the Document and writes Diagnostics, performing no I/O.
type Validator interface {
	// Validate inspects doc and appends any findings to into.
	Validate(doc Document, into *Diagnostics)
}

// Source yields the raw bytes for a logical input name. Accept-interface: the
// composition root passes a file reader, an embed.FS, an env snapshot, etc.
// It is read only inside Parse (with a context) — NEVER inside New. This is
// the only port the edge needs; the parser opens nothing on its own.
type Source interface {
	// Read returns the bytes for name, or an I/O error.
	Read(ctx context.Context, name string) ([]byte, error)
}

// Config is the parse configuration. Zero value is valid and STRICT: unknown
// and duplicate keys become SeverityError (silent acceptance of typo'd config
// is the failure mode this pattern exists to prevent). Idiomatic Go type name,
// exempt from the HNS-1 slug rule (10 §5).
type Config struct {
	Format Format // the encoding Parse decodes; FormatEnv for the env edge
	// AllowUnknownKeys downgrades unknown/duplicate-field findings from Error
	// to Warning. Off by default — strict parsing is the discipline.
	AllowUnknownKeys bool
	// MaxSourceBytes caps any single source read; 0 means an internal sane cap.
	MaxSourceBytes int
	// Validators run in order AFTER parse; all run, all Diagnostics collected.
	Validators []Validator
}

// Deps is the injected port record. The parser is pure over its inputs; the
// only port it needs is the Source it reads bytes from — supplied here, never
// opened internally. The record stays uniform across every pattern and can
// gain ports additively.
type Deps struct {
	Source Source
}

// Parser is the returned edge component: stateless and safe for concurrent
// use; every method is pure over its arguments (modulo the injected Source's
// I/O inside Parse). Two methods, well under the 5-method ceiling.
type Parser interface {
	// Parse reads the named source (via Deps.Source), decodes it per
	// Config.Format, then runs Config.Validators. It returns a frozen Document
	// plus EVERY Diagnostic from both phases. err is non-nil ONLY for an I/O
	// failure from Source: a Document carrying SeverityError findings is a
	// VALID return (doc, diags, nil) — config-is-wrong is data, not a Go error,
	// because it drives a different operator action than couldn't-read-file.
	Parse(ctx context.Context, name string) (Document, Diagnostics, error)

	// Merge layers documents (base <- overlay) with overlay winning per Path,
	// preserving each leaf's origin Position — the stage-overlay / env-override
	// fold (10 §2: stage selects values, never mechanism). The result is a new
	// frozen Document; inputs are not mutated. err is non-nil only on an
	// internal merge fault; conflicting types surface as Diagnostics.
	Merge(ctx context.Context, base, overlay Document) (Document, Diagnostics, error)
}
