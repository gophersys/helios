// Package agentprofile is the single source of truth for agent instrumentation: it parses and
// validates one profile document into a role x harness matrix, renders each cell to that harness's
// own native instrumentation files, and reports the divergence between a fresh render and what is
// committed.
//
// Module: github.com/gophersys/libs/go/agentprofile  (go 1.26)
//
// It is NOT agentconfiguration. agentconfiguration is the reserved-but-unbuilt library that
// resolves a RouteKey to a (harness, model) binding — WHICH harness runs a phase and under which
// model (the agentsession.Route projection). agentprofile never chooses a harness, never names a
// model and never reads a route; it answers the other question — WHAT instrumentation the chosen
// harness reads once it starts. The split is deliberate: one concept, one home. A caller that needs
// both wires both — agentconfiguration routes the session, agentprofile renders the files that
// session's harness loads.
//
// DETERMINISM: the same document and the same Target render byte-identical output, on any host, in
// any order, forever. Nothing here reads a clock, an environment variable or a random source, and
// no emission order is ever a Go map's iteration order: every composed set is sorted by name and
// every FileSet is sorted by Path before it leaves Render. That is what makes the rendered files
// committable and the drift check meaningful — a check whose expectation moved would be no check.
// FileSet.Digest addresses a whole emission as "sha256:<hex>", which is what a pod's profileRef
// points at.
//
// PRECEDENCE: a cell is composed from three layers, lowest to highest:
//
//	defaults  <  role  <  repository overlay
//
// A rule or skill declared at a higher layer REPLACES the same-named fragment from a lower one — it
// is never appended to and never merged — and the instruction body is the one from the highest
// layer that declares a non-empty one. The composed sets are then sorted by fragment name, so
// precedence decides WHICH fragment wins and never WHERE it lands.
//
// ERRORS: every failure is an *errors.Error carrying a stable errors.Kind the caller branches on
// (never a string match): KindInvalid for a malformed document or malformed wiring, KindNotFound
// for a Target that names no cell of the matrix or a harness no injected Renderer claims, and
// KindInternal for a renderer that broke this library's emission invariants — including the
// declared-but-unbuilt harnesses, whose renderers fail loudly with a NotImplementedError naming the
// harness rather than emitting nothing. Inspect with errors.KindOf, or with errors.IsType for the
// typed cause; never by matching message text.
//
// HEXAGON: the ports (Renderer, Tree) and the value types live here. Renderer is the harness
// emission seam — the shape agentprofile needs, not a mirror of any harness's CLI. Tree is the
// read-only view of the committed working tree the drift check compares against. New is the pure
// constructor spine (New(configuration, dependencies)): it parses, validates and binds, and
// performs no I/O.
//
// Concurrency: a *Compiler is immutable after New and is safe for concurrent use by multiple
// goroutines iff the injected Renderers and Tree are.
package agentprofile

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"io/fs"
	"strconv"
)

// digestPrefix labels every digest this library prints with the algorithm that produced it, so a
// profileRef stays readable and a future algorithm change is a visible prefix change, not a silent
// reinterpretation of the same-looking hex.
const digestPrefix = "sha256:"

// digestSeparator delimits the components of the canonical serialization Digest hashes. NUL cannot
// occur in a path or in a decimal length, so no content can forge a component boundary.
const digestSeparator = 0x00

// Harness is the agent harness a profile is rendered for: the adapter key that selects which native
// instrumentation layout is emitted.
type Harness string

// The harnesses Eden runs. The tokens are the SAME adapter keys agentsession.Route.Harness carries
// (agentsession/agentsession.go and the claudeadapter harnessName const), so one string both routes
// a session and selects its profile. agentsession exports no constant for them, so the tokens —
// never a new spelling — are what binds the two libraries; cite these when it does.
const (
	// HarnessClaudeCode is Anthropic's claude CLI, the only harness with a built renderer.
	HarnessClaudeCode Harness = "claude-code"
	// HarnessOMP is the omp CLI. Its renderer is declared and fails loudly by name.
	HarnessOMP Harness = "omp"
	// HarnessCodex is OpenAI's codex CLI. Its renderer is declared and fails loudly by name.
	HarnessCodex Harness = "codex"
)

// known reports whether h is a harness this library recognizes. A document naming any other token
// is rejected at New rather than rendered into a directory nothing will ever read.
func (h Harness) known() bool {
	switch h {
	case HarnessClaudeCode, HarnessOMP, HarnessCodex:
		return true
	default:
		return false
	}
}

// Role is the agent role a profile is rendered for — the row of the matrix. It is an HNS-1 slug
// (rule 11), because it becomes a path component of the emission.
type Role string

// Target is one cell of the role x harness matrix: the unit Render and Drift address.
type Target struct {
	// Role is the row: the agent role the profile is rendered for.
	Role Role
	// Harness is the column: the harness whose native layout is emitted.
	Harness Harness
}

// String renders the target as "<role>/<harness>", the same order the emission path uses, so an
// error message and a directory listing read alike.
func (t Target) String() string { return string(t.Role) + "/" + string(t.Harness) }

// File is one emitted file. Content is the exact bytes to write — the renderer has already applied
// every composition rule, so a consumer writes it verbatim or compares it verbatim, never both
// interprets and rewrites it.
type File struct {
	// Path is the destination, repository-relative and slash-separated on every host (it is a
	// contract string, not a filesystem path, so it never carries a platform separator).
	Path string
	// Content is the exact bytes of the emitted file.
	Content []byte
	// Mode is the permission bits the file is written with.
	Mode fs.FileMode
}

// FileSet is the complete emission for one Target, in a deterministic order: Render sorts it by
// Path before returning, so two runs over the same input produce the same sequence and therefore
// the same Digest.
type FileSet []File

// Digest returns the content address of the whole emission as "sha256:<hex>". The hash covers a
// canonical serialization of every file — path, mode, content length and content, each NUL-
// separated — so a renamed file, a mode change and an edited byte are all distinguishable, and no
// content can forge a component boundary. This is the value a pod's profileRef points at.
func (s FileSet) Digest() string {
	canonical := make([]byte, 0, s.canonicalSize())
	for i := range s {
		file := &s[i]
		canonical = append(canonical, file.Path...)
		canonical = append(canonical, digestSeparator)
		canonical = strconv.AppendUint(canonical, uint64(file.Mode), 8)
		canonical = append(canonical, digestSeparator)
		canonical = strconv.AppendInt(canonical, int64(len(file.Content)), 10)
		canonical = append(canonical, digestSeparator)
		canonical = append(canonical, file.Content...)
	}
	return digestOf(canonical)
}

// canonicalSize is the exact byte budget the canonical serialization needs, so Digest allocates
// once. The 32-byte slack per file covers the octal mode and the decimal length.
func (s FileSet) canonicalSize() int {
	size := 0
	for i := range s {
		size += len(s[i].Path) + len(s[i].Content) + 32
	}
	return size
}

// digestOf is the ONE spelling of a content address in this library: lowercase hex of the SHA-256
// of the bytes, behind the algorithm prefix. Both FileSet.Digest and the drift summaries use it, so
// two digests printed side by side are always comparable.
func digestOf(content []byte) string {
	sum := sha256.Sum256(content)
	return digestPrefix + hex.EncodeToString(sum[:])
}

// DivergenceReason classifies why a rendered file and the committed working tree disagree. The two
// members mirror the shape gophersys/cictl's drift verb reports (its precedent, cited not imported:
// a missing artifact and an edited artifact need different remedies from a human, so a check that
// collapsed them into one "differs" would bury the more urgent of the two).
type DivergenceReason string

const (
	// DivergenceMissing is a rendered file that the committed tree does not contain at all.
	DivergenceMissing DivergenceReason = "missing"
	// DivergenceContentDiffers is a committed file whose bytes are not the rendered bytes.
	DivergenceContentDiffers DivergenceReason = "content-differs"
)

// Divergence is one disagreement between a fresh render and the committed tree. A non-empty slice
// of these is what fails a CI drift gate.
type Divergence struct {
	// Path is the repository-relative path that diverged.
	Path string
	// Reason classifies the divergence.
	Reason DivergenceReason
	// Diff is a short, deterministic, redaction-safe summary of the difference, ending in the
	// instruction that resolves it. It reports WHAT differs (digests and lengths) rather than HOW,
	// because the remedy for every divergence is the same — re-render — so a line-level diff of a
	// generated file would be noise a reader has to skip.
	Diff string
}

// Renderer is the harness-emission port: given one fully-resolved cell of the matrix, it produces
// that harness's native instrumentation files. It is consumer-defined — the shape agentprofile
// needs, not a mirror of any harness's CLI or configuration format — and an implementation is
// bound at the composition root through Deps.Renderers. Two methods; implementations MUST be pure
// and safe for concurrent use.
type Renderer interface {
	// Harness reports the adapter key this renderer emits for. It is how a Compiler binds a Target
	// to a renderer, so it MUST be constant for the lifetime of the value.
	Harness() Harness
	// Render emits the complete file set for one resolved cell. It MUST be deterministic (the same
	// Resolved yields byte-identical files), and it MUST NOT return an empty FileSet: a harness it
	// cannot emit for is an error naming that harness, never a silent nothing.
	Render(ctx context.Context, resolved Resolved) (FileSet, error)
}

// Tree is the read-only view of the committed working tree the drift check compares a fresh render
// against. It is read-only ON PURPOSE: a check that can repair its own expectation cannot fail, so
// this port offers no way to write, create or delete. Emission and drift stay two verbs, and the
// only remedy for a divergence is to re-render deliberately.
type Tree interface {
	// ReadFile returns the committed bytes at path, which is repository-relative and slash-
	// separated exactly as File.Path is. An ABSENT path MUST be reported as an error satisfying
	// errors.Is(err, fs.ErrNotExist) — os.ReadFile already does — because that is how Drift tells a
	// file that was never written from a tree it could not read.
	ReadFile(ctx context.Context, path string) ([]byte, error)
}

// Fragment is one named unit of instrumentation text — a rule or a skill — as it appears both in
// the profile document and in the resolved projection. One concept, one home: the document's wire
// shape and the renderer's input are the same type, so a fragment cannot mean two things.
type Fragment struct {
	// Name is the fragment's HNS-1 slug (rule 11). It becomes a file or directory name in the
	// emission, and it is the identity precedence replaces on.
	Name string `json:"name"`
	// Body is the fragment's text, emitted verbatim under whatever layout the harness wants.
	Body string `json:"body"`
}

// Resolved is the immutable, fully-resolved projection of one Target: the intermediate
// representation a Renderer consumes. A renderer sees ONLY this — never the raw document, never
// the other cells — so a harness cannot reach across the matrix, and a cell can be rendered from a
// Resolved a test wrote by hand.
type Resolved struct {
	// SchemaVersion is the document schema version this projection was built from. Renderers stamp
	// it into the emission so a committed file names the schema that produced it.
	SchemaVersion int
	// Target is the cell this projection resolves.
	Target Target
	// Repository is the per-repository overlay that was applied, empty when none was selected.
	Repository string
	// Instruction is the composed top-level instruction body for the role.
	Instruction string
	// Rules is the composed rule set, precedence applied, sorted by Name.
	Rules []Fragment
	// Skills is the composed skill set, precedence applied, sorted by Name.
	Skills []Fragment
}
