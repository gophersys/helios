# Contract draft — configuration

> Status: Draft for negotiation (WS1, not frozen) · 2026-06-12 · Reconciled from independent producer/consumer drafts (09 §4). Freezes at the contract-PR gate after review.

## 1. Scope

This pattern is the universal **input-IR machinery**: raw bytes are parsed ONCE at the edge into an immutable, fully-resolved `Document`, then frozen and read concurrently forever. It owns the parse → diagnose → validate → freeze spine, the closed `Format` set it can decode, and the typed, positioned `Diagnostic` discipline. It does NOT own any library's domain `Config` type — every library declares its own concrete `Config` and *builds it FROM* a `Document` it reads by `Path`. It does not resolve secrets (a `SecretReference` is just a leaf `Value`; resolution is the `secrets` port's job, 10 §4), open files (the injected `Source` port reads bytes), consult a clock, or read env. It refuses an open decoder registry: new formats are added here, additively, in a minor version.

## 2. Contract

```go
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

// Path is a resolved-tree location: dotted keys with [i] indices
// (e.g. "engine.models[0].auth"). It is the join key between a typed library
// view and a source Position. Empty Path is the root.
type Path string

// Child appends ".key" to the path.
func (p Path) Child(key string) Path { /* ... */ return "" }

// Index appends "[i]" to the path.
func (p Path) Index(i int) Path { /* ... */ return "" }

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

// Diagnostics is the accumulating sink a Validator writes into and the edge
// reports. It has value semantics on copy; Append is the only mutator. The
// zero Diagnostics is an empty, usable sink: HasError() is false, All() is nil.
type Diagnostics struct {
	// unexported slice; never an exported mutable field (immutability of a
	// reported set is structural).
	findings []Diagnostic
}

// Append adds findings to the sink.
func (d *Diagnostics) Append(findings ...Diagnostic) { /* ... */ }

// HasError reports whether any appended finding is SeverityError.
func (d *Diagnostics) HasError() bool { /* ... */ return false }

// All returns a copy of every finding, ordered by At.Source then At.Position.
// Callers may freely retain or mutate the returned slice.
func (d *Diagnostics) All() []Diagnostic { /* ... */ return nil }

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

// New is the pure constructor spine. It validates Config, wires the Format
// table and the Validator list into a ready Parser, and captures Deps. It
// performs NO I/O, reads NO env, consults NO clock: the first byte is read
// only when Parse is later called with a context. A malformed Config (e.g.
// negative MaxSourceBytes, an unknown Format) is the only error path.
func New(configuration Config, dependencies Deps) (Parser, error) { /* ... */ return nil, nil }

// ParseError wraps an I/O failure surfaced by Parse/Merge (the err channel),
// so callers branch on structure, not strings. It is inspectable via
// errors.AsType[*ParseError] and wraps the underlying Source error with %w.
// (Config-is-wrong is NOT a ParseError — it is Diagnostics; see rationale 4.)
type ParseError struct {
	Source string // the input name that failed to read
	Err    error  // the wrapped Source.Read error
}

func (e *ParseError) Error() string { /* "<source>: ..." */ return "" }
func (e *ParseError) Unwrap() error { return e.Err }
```

## 3. Fake

```go
// Package configurationtest provides the canonical public fakes for the
// configuration pattern (the testing discipline, 10 §4). It is the
// substitutability oracle: the conformance suite asserts the real Parser and
// these fakes agree on the same fixtures.
package configurationtest

import (
	"context"

	"github.com/gophersys/libs/go/configuration"
)

// Doc builds an in-memory Document from a Go map — no parser, no source. The
// composition-root-side workhorse: a library Config test constructs the exact
// resolved tree it needs and asserts its Validator/ConfigFrom against it.
func Doc(tree map[string]any, opts ...DocOption) configuration.Document { /* ... */ return nil }

type DocOption func(*docState)

// WithFormat stamps the Document's reported Format.
func WithFormat(f configuration.Format) DocOption { /* ... */ return nil }

// WithOrigin sets the Document's root Position source name.
func WithOrigin(src string) DocOption { /* ... */ return nil }

// WithPosition stamps a synthetic Position on a Path so diagnostic line/column
// assertions are exercisable without real source text.
func WithPosition(p configuration.Path, pos configuration.Position) DocOption { /* ... */ return nil }

// Parser is a scripted, deterministic fake configuration.Parser. Parse/Merge
// return whatever was staged per name; an unstaged name returns a *ParseError
// so missing-input paths are testable. Calls are recorded for assertion. The
// zero value is usable: every name is unstaged.
type Parser struct {
	Documents   map[string]configuration.Document   // name -> staged doc
	Diagnostics map[string]configuration.Diagnostics // name -> staged findings
	ReadErr     map[string]error                     // name -> staged I/O error
	ParseCalls  []string                             // recorded, in order
}

func (p *Parser) Parse(ctx context.Context, name string) (configuration.Document, configuration.Diagnostics, error) {
	return nil, configuration.Diagnostics{}, nil
}
func (p *Parser) Merge(ctx context.Context, base, overlay configuration.Document) (configuration.Document, configuration.Diagnostics, error) {
	return nil, configuration.Diagnostics{}, nil
}

// Source is a map-backed configuration.Source for driving the REAL Parser in
// tests without touching the filesystem.
type Source struct {
	Files map[string][]byte
	Err   map[string]error
}

func (s Source) Read(ctx context.Context, name string) ([]byte, error) { /* ... */ return nil, nil }

// Diags returns the diagnostics at or under a Path, so a test can assert
// "exactly one SeverityError at engine.models[0].auth."
func Diags(d configuration.Diagnostics, under configuration.Path) []configuration.Diagnostic {
	return nil
}
```

## 4. Conformance suite

```go
// Run drives any configuration.Parser produced by newParser through the
// substitutability properties. The real adapter and configurationtest.Parser
// must both pass identically (08 §2).
func Run(t *testing.T, newParser func(configuration.Config, configuration.Deps) (configuration.Parser, error))
```

Properties asserted:

- **Purity of New.** `New` performs no I/O and reads nothing from `Source`; constructing with a panicking `Source` does not panic. A malformed `Config` (negative `MaxSourceBytes`, unknown `Format`) is the only `New` error.
- **Strict-by-default.** Zero `Config` flags unknown and duplicate keys as `SeverityError`; `AllowUnknownKeys` downgrades them to `SeverityWarning`.
- **Diagnostics accumulate.** A source with N independent problems yields N findings in one `Parse` — never short-circuits on the first.
- **Error-channel discipline.** A `Source.Read` failure returns a `*ParseError` (inspectable via `errors.AsType`, `Unwrap` reaching the cause); a syntactically/semantically wrong-but-readable source returns `(doc, diags, nil)` with `diags.HasError()`.
- **Position truthfulness.** Every parse-derived finding carries a non-zero `Position`; synthetic/default findings carry `Line == 0`. No fabricated coordinates.
- **Immutability after resolve.** A returned `Document` exposes no mutator; concurrent `Lookup` from many goroutines is race-free; `Merge` does not mutate its inputs.
- **Zero-value safety.** The zero `Document` Lookups miss cleanly; the zero `Value` conversions return zero+`*Diagnostic` and `Field`/`Len` report `ok == false`; no accessor panics.
- **Total conversions.** `Value.Int()`/`Bool()`/`String()` on a mismatched node return a `*Diagnostic` stamped with the leaf's `At()` Position, not a Go error.
- **Merge semantics.** `overlay` wins per `Path`; each surviving leaf keeps its origin `Position`; `Format()`/`Origin()` reflect the fold.
- **Validators run as a phase.** All `Config.Validators` run after parse, in order; their findings join the parse findings; a Validator that writes a `SeverityError` makes `HasError()` true without changing the `err` channel.
- **Format is closed.** An unknown `Format` is rejected by `New`; a source whose bytes don't match `Config.Format` is a `Diagnostic`, never a panic.

## 5. Usage

```go
// apps/backend composition root — the ONLY place bytes become a frozen IR
// (cmd/eden/main.go, called once before any backend.New; 10 §7.1).
func loadConfig(ctx context.Context, stage environment.Stage) (engine.Config, error) {
	parser, err := configuration.New(
		configuration.Config{
			Format: configuration.FormatYAML, // strict by default
			Validators: []configuration.Validator{
				engine.ConfigValidator(),             // each kernel lib ships its own
				agentconfiguration.ConfigValidator(), // shape rules stay with the domain
				evidence.ConfigValidator(),
			},
		},
		configuration.Deps{Source: osfile.Source{Root: "/etc/eden"}}, // injected; New reads nothing
	)
	if err != nil {
		return engine.Config{}, err
	}

	base, d1, err := parser.Parse(ctx, "backend.yaml")
	if err != nil {
		// I/O failure ONLY (couldn't read) — distinct operator action: retry/abort.
		var pe *configuration.ParseError
		if errors.AsType(err, &pe) {
			log.Printf("config read failed: %s: %v", pe.Source, pe.Err)
		}
		return engine.Config{}, err
	}
	overlay, d2, _ := parser.Parse(ctx, "backend."+stage.String()+".yaml")
	doc, d3, _ := parser.Merge(ctx, base, overlay) // stage overlay folds in (10 §2)

	var diags configuration.Diagnostics
	diags.Append(d1.All()...)
	diags.Append(d2.All()...)
	diags.Append(d3.All()...)
	if diags.HasError() {
		// Config-is-wrong: report EVERY problem once, then exit — not 5 restarts.
		for _, dg := range diags.All() {
			log.Printf("%s:%d:%d %s", dg.At.Source, dg.At.Line, dg.At.Column, dg.Summary)
		}
		return engine.Config{}, fmt.Errorf("configuration: %d error(s)", len(diags.All()))
	}

	// The frozen Document is handed to each library's typed view builder.
	// Libraries NEVER see bytes — they read the resolved tree by Path.
	return engine.ConfigFrom(doc) // pure: Document -> typed engine.Config
}

// Inside a kernel library (libs/go/engine) — built FROM the Document, not bytes.
// The library physically cannot re-parse: it holds no Source.
func ConfigFrom(doc configuration.Document) (Config, error) {
	v, ok := doc.Lookup("engine.maxConcurrency")
	if !ok {
		return Config{}, nil // zero-value safe: absent optional key -> default
	}
	n, diag := v.Int()
	if diag != nil {
		// Position preserved: the operator sees backend.yaml:14:7, not "bad int".
		return Config{}, fmt.Errorf("engine: %s:%d:%d %s",
			diag.At.Source, diag.At.Line, diag.At.Column, diag.Summary)
	}
	return Config{MaxConcurrency: int(n)}, nil // passed to engine.New(cfg, deps) — pure from here
}
```

## 6. Design rationale

1. **The pattern is the edge machinery, not each library's `Config`.** The brief says "every library Config type is built FROM this pattern" (10 §4). So the deliverable is `Document` (frozen IR) + `Diagnostics` + the parse/validate/merge spine; `engine.Config` etc. are *consumers* that read a `Document` by `Path`. `ConfigFrom(doc)` lives in the library, not here — zero speculative generality about domain shape.
2. **Parse-once-at-the-edge is enforced by the type system.** Libraries receive a `Document`, never bytes or a `Source`, so a library physically cannot re-open input (10 §7.1 spine). This is why `configuration` is one shared library rather than copied per-lib.
3. **Immutability is structural, not promised.** `Document` and `Value` are read-only interfaces with no setter and no exported mutable field; the only way to obtain one is through `Parse`/`Merge`/the fake's `Doc`. "Frozen after resolve" cannot be violated by a future field, and concurrency safety comes for free (10 §4 discipline).
4. **Diagnostics are data; the `error` channel is I/O-only.** `Parse` returns `(Document, Diagnostics, error)` where `error` is reserved for `Source` read failures (wrapped as `*ParseError`); a configuration with `SeverityError` is a valid return. "Couldn't read the file" (retry/abort) and "the file is wrong" (report-and-exit) are different operator actions, so they are different return channels — branchable without string-matching. This also lets the edge collect EVERY problem and report once (04 §8 retry-with-diagnostics), instead of failing one-at-a-time.
5. **Diagnostics are self-contained value types — no upward dependency.** `Diagnostic`/`Position`/`Severity`/`Path` are comparable, copyable, loggable, and carry line/column. They do NOT import the `errors` library: `configuration` is the lowest layer, parsed before anything is wired (10 §4). The one cross-pattern coupling is `*ParseError` wrapping its `Source` cause via `%w` for `errors.AsType` — that satisfies structured inspection on the I/O path without configuration depending *on* the `errors` library.
6. **Zero values are the strict, safe default.** Zero `Config` = strict parse (unknown/duplicate keys error). Zero `Document` = empty valid tree whose `Lookup` misses cleanly. Zero `Value` = absent. Zero `Diagnostics` = empty sink. No accessor panics — total zero-value safety (the catalogue's stated property), which kernel `ConfigFrom` builders depend on directly because they run before `errors`/`observability` are wired (cold-start safety).
7. **Validation is a separate phase, owned by the domain.** `Validator` is its own one-method port supplied in `Config.Validators` and run after parse. Parse never validates shape; validate never re-parses. Each kernel library owns its own rules — the pattern centralizes no schema, keeping "accept interfaces, return concrete" intact (10 §9).
8. **`New` is pure and uniform.** It validates `Config` and wires the format table + validators; the first byte is read only inside `Parse(ctx, …)` via the injected `Source` port. No I/O, clock, or env read in the constructor (10 §4). `SecretReference` (10 §4) is just another leaf `Value` here — configuration holds the loggable handle; resolution is the `secrets` port's job.
9. **`Format` is a closed, decode-only set.** An unknown format is a `New` error (config) or a `Diagnostic` (bytes), never a panic and never a plugin hook. Refusing an open decoder registry in v1 keeps "parsed once" honest; new formats are added here, additively, in a minor version (10 §4).
10. **Interfaces stay ≤5 methods.** `Parser` has 2 (`Parse`, `Merge`), `Document` 3, `Value` 5, `Validator`/`Source` 1 each. `Diagnostics` is a concrete value type, not a port. Returning concrete `Document`/`Value`/`Diagnostics` behind the abstract `Parser`/`Source`/`Validator` seams honors "accept interfaces, return concrete" (10 §9).

## 7. Open questions

| # | Question / conflict | Producer position | Consumer position | Reconciler resolution 🧩 |
|---|---|---|---|---|
| 1 | Decode target: typed `v any` pointer vs opaque `Document` read by `Path`? | `Parse(ctx, v any, sources...)` decodes into a library's `Config` pointer; package never sees domain shape. | `Parse` returns an opaque `Document`; libraries read by `Path` via `ConfigFrom(doc)`. | 🧩 **Consumer.** The `Document`/`Value` read surface honors immutability structurally, enables accumulate-all-diagnostics on conversion, and matches the real kernel call sites (`engine.ConfigFrom`). Producer's "package owns IR not schema" goal is fully preserved — `Document` is the IR, the library still owns its `Config`. Decoding into a typed pointer would either re-introduce reflection-driven errors or duplicate validation; rejected. |
| 2 | Error channel: `error` non-nil iff `SeverityError` (with `ParseError` carrying findings) vs `error` for I/O-only? | `Parse` err is non-nil iff a `SeverityError` finding exists; `*ParseError` carries all error findings. | `error` is I/O-only; config-is-wrong is `(doc, diags, nil)`. | 🧩 **Consumer**, with producer's `ParseError` repurposed. "Couldn't read" vs "is wrong" are different operator actions and must be different channels. `*ParseError` survives — but it now wraps the `Source` I/O cause (via `%w`/`Unwrap`), not the diagnostic set. Structured findings live in `Diagnostics`, which is the accumulate-all sink both sides ultimately need. |
| 3 | Byte input: `Source` structs passed to `Parse` vs a `Source` port in `Deps` + `Parse(ctx, name)`? | `Source` is a value struct (`Name/Format/Bytes`) passed per `Parse` call; parser is a pure function of bytes. | `Source` is an injected one-method port read inside `Parse`. | 🧩 **Consumer.** The injected port keeps the composition root the sole reader AND keeps `New` pure (the port is read only inside `Parse`, never in `New`). Producer's "pure function of (Config, Deps, Sources)" purity is preserved: the bytes still come from outside; only the delivery mechanism (port vs struct) changed, and the port is testable via `configurationtest.Source`. |
| 4 | `Merge` / overlay folding — present at all? | Absent: multiple `Source`s applied later-over-earlier inside one `Parse`. | Explicit `Merge(base, overlay)` for stage overlays + env overrides, position-preserving. | 🧩 **Consumer.** Stage-overlay folding is a real composition-root need (10 §2: stage selects values). An explicit, position-preserving `Merge` blames the right file in diagnostics; folding it invisibly inside `Parse` (producer) loses per-leaf origin. `Parser` stays at 2 methods, well under the ceiling. |
| 5 | `Diagnostics` accumulator type vs bare `[]Diagnostic`? | `Resolved.Diagnostics()` returns a copy of `[]Diagnostic`. | A `Diagnostics` value type with `Append`/`HasError`/`All` that Validators write into. | 🧩 **Consumer.** Validators need a sink to write into during the separate validation phase; a bare slice can't be the injected write target without exposing a mutable field. `Diagnostics` keeps `Append` as the only mutator and value semantics on copy. Producer's "copy of findings" guarantee is kept by `All()` returning a copy. |
| 6 | `Severity` levels: Info/Warning/Error vs Warning/Error? | Three: `SeverityInfo`, `SeverityWarning`, `SeverityError`. | Two: `SeverityWarning`, `SeverityError`. | 🧩 **Consumer (simpler).** Per the "keep the simpler formulation where sides agree on intent" rule. Info-level findings are not a failure mode this pattern must model, and a Document is usable iff no `SeverityError` regardless. Producer's `SeverityInfo` is **rejected for v1**; if telemetry needs informational findings later it is an additive const, non-breaking. |
| 7 | Producer's `Value.Slice()` and concrete `Resolved`/`Value` structs vs consumer's `Value.Field`/`Len` interface? | Concrete `Value` struct with `String/Int/Bool/Slice/Position`. | `Value` interface with `String/Int/Bool/Field/Len/At` (total, *Diagnostic-returning). | 🧩 **Consumer**, capped at 5. `Value` as an interface lets the fake supply views without exposing internal state, and `*Diagnostic`-returning conversions feed the accumulate-all discipline. `Slice()` is folded into `Len()` + indexed `Field`/`Lookup(path.Index(i))` to hold the 5-method ceiling. Element access via `path.Index(i)` keeps the join key (`Path`) authoritative. |
| 8 | `MaxSourceBytes` / `AllowUnknownKeys` knobs on `Config`? | Both present (cap + strictness toggle). | `Strict bool` only (no byte cap). | 🧩 **Producer retained.** `MaxSourceBytes` is a cheap DoS/footgun guard at the parse edge and harmless when 0. `AllowUnknownKeys` (producer) is kept over consumer's inverted `Strict bool` because strict-by-default must be the ZERO value — a `Strict bool` defaults to `false` = lax, which inverts the discipline. The flag is named for the opt-OUT so the zero `Config` stays strict. |
| 9 | Does configuration resolve `SecretReference`? | Not addressed directly (a leaf value). | Explicitly no — `SecretReference` is a leaf `Value`; resolution is the `secrets` port. | 🧩 **Agreed (consumer's explicit statement adopted).** `SecretReference` lives in configuration as an opaque loggable leaf (10 §4); the `secrets` pattern resolves it at point-of-use. No conflict — recorded for the cross-contract seam with `secrets.md`. |
