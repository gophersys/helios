package agentprofile_test

import (
	"context"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentprofile"
	"github.com/gophersys/libs/go/agentprofile/agentprofiletest"
	"github.com/gophersys/libs/go/errors"
)

// minimalDocument is the smallest document that validates: one role, one harness, an instruction
// that resolves. Every negative case below is this document with exactly ONE thing wrong, so the
// failure a case reports is attributable to the thing it changed.
const minimalDocument = `{"schemaVersion":1,"roles":{"reviewer":{"instruction":"i","harnesses":["claude-code"]}}}`

// ── New: the constructor spine's wiring arms ────────────────────────────────────────────────────

// TestNew_RejectsMalformedWiring walks every wiring fault New refuses. Each is KindInvalid — the
// caller handed this library something it cannot honor — and each message names WHAT is wrong so the
// composition root can be fixed without reading source. A nil *Compiler must come back with every
// error: a half-built Compiler is a check that cannot fail.
func TestNew_RejectsMalformedWiring(t *testing.T) {
	t.Parallel()
	claude := agentprofile.ClaudeRenderer{}
	cases := []struct {
		name         string
		document     string
		renderers    []agentprofile.Renderer
		tree         agentprofile.Tree
		wantKind     errors.Kind
		wantContains string
	}{
		{
			name:         "EmptyDocument",
			document:     "",
			renderers:    []agentprofile.Renderer{claude},
			tree:         agentprofiletest.NewTree(),
			wantKind:     errors.KindInvalid,
			wantContains: "Config.Document",
		},
		{
			name:         "NilTree",
			document:     minimalDocument,
			renderers:    []agentprofile.Renderer{claude},
			tree:         nil,
			wantKind:     errors.KindInvalid,
			wantContains: "Deps.Tree",
		},
		{
			name:         "NoRenderers",
			document:     minimalDocument,
			renderers:    nil,
			tree:         agentprofiletest.NewTree(),
			wantKind:     errors.KindInvalid,
			wantContains: "at least one Deps.Renderers entry",
		},
		{
			name:         "NilRendererEntry",
			document:     minimalDocument,
			renderers:    []agentprofile.Renderer{nil},
			tree:         agentprofiletest.NewTree(),
			wantKind:     errors.KindInvalid,
			wantContains: "nil entry",
		},
		{
			name:         "RendererClaimingAnUnknownHarness",
			document:     minimalDocument,
			renderers:    []agentprofile.Renderer{agentprofiletest.NewRenderer("cursor")},
			tree:         agentprofiletest.NewTree(),
			wantKind:     errors.KindInvalid,
			wantContains: "unknown harness cursor",
		},
		{
			name:     "TwoRenderersClaimingOneHarness",
			document: minimalDocument,
			renderers: []agentprofile.Renderer{
				claude, agentprofiletest.NewRenderer(agentprofile.HarnessClaudeCode),
			},
			tree:         agentprofiletest.NewTree(),
			wantKind:     errors.KindInvalid,
			wantContains: "two Deps.Renderers entries claiming harness claude-code",
		},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			compiler, err := agentprofile.New(
				agentprofile.Config{Document: []byte(testCase.document)},
				agentprofile.Deps{Renderers: testCase.renderers, Tree: testCase.tree},
			)
			if compiler != nil {
				t.Errorf("New returned a non-nil *Compiler alongside its error")
			}
			assertKindAndMessage(t, err, testCase.wantKind, testCase.wantContains)
		})
	}
}

// TestNew_OverlaySelectorMustNameADeclaredOverlay asserts the selector arm: an unknown repository is
// KindNotFound at New, never an overlay that silently resolves to nothing. A repository that meant to
// override a rule and quietly did not is precisely the drift this library exists to prevent. The
// empty selector is the base matrix and is accepted.
func TestNew_OverlaySelectorMustNameADeclaredOverlay(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)

	_, err := agentprofile.New(
		agentprofile.Config{Document: document, Repository: "no-such-repository"},
		agentprofile.Deps{Renderers: []agentprofile.Renderer{agentprofile.ClaudeRenderer{}}, Tree: agentprofiletest.NewTree()},
	)
	assertKindAndMessage(t, err, errors.KindNotFound, `no overlay for repository "no-such-repository"`)

	if _, err := agentprofile.New(
		agentprofile.Config{Document: document},
		agentprofile.Deps{Renderers: []agentprofile.Renderer{agentprofile.ClaudeRenderer{}}, Tree: agentprofiletest.NewTree()},
	); err != nil {
		t.Errorf("the empty selector is the base matrix and must be accepted: %v", err)
	}
}

// ── The document parser and validator ───────────────────────────────────────────────────────────

// TestNew_RejectsAMalformedDocument walks every document fault. All are KindInvalid, and each
// message names the offending element — a role, an overlay, a fragment — because a 40-role document
// whose validator said only "invalid" would send a human hunting.
func TestNew_RejectsAMalformedDocument(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name         string
		document     string
		wantContains string
	}{
		{"TrailingContent", minimalDocument + `{"schemaVersion":1}`, "trailing content"},
		{"UnknownField", `{"schemaVersion":1,"rols":{}}`, "parse profile document"},
		{"UnsupportedSchemaVersion", `{"schemaVersion":2,"roles":{"reviewer":{"instruction":"i","harnesses":["claude-code"]}}}`, "schemaVersion 2 is not supported"},
		{"NoRoles", `{"schemaVersion":1,"roles":{}}`, "declares no roles"},
		{"RoleNameIsNotASlug", `{"schemaVersion":1,"roles":{"Reviewer":{"instruction":"i","harnesses":["claude-code"]}}}`, `role name "Reviewer" is not an HNS-1 slug`},
		{"RoleDeclaresNoHarnesses", `{"schemaVersion":1,"roles":{"reviewer":{"instruction":"i","harnesses":[]}}}`, "declares no harnesses"},
		{"RoleDeclaresAnUnknownHarness", `{"schemaVersion":1,"roles":{"reviewer":{"instruction":"i","harnesses":["cursor"]}}}`, `unknown harness "cursor"`},
		{"RoleDeclaresAHarnessTwice", `{"schemaVersion":1,"roles":{"reviewer":{"instruction":"i","harnesses":["omp","omp"]}}}`, "declares harness omp twice"},
		{"RoleResolvesToAnEmptyInstruction", `{"schemaVersion":1,"roles":{"reviewer":{"harnesses":["claude-code"]}}}`, "resolves to an empty instruction"},
		{
			"FragmentNameIsNotASlug",
			`{"schemaVersion":1,"roles":{"reviewer":{"instruction":"i","harnesses":["claude-code"],"rules":[{"name":"00-identity","body":"b"}]}}}`,
			`fragment name "00-identity" is not an HNS-1 slug`,
		},
		{
			"FragmentBodyIsEmpty",
			`{"schemaVersion":1,"roles":{"reviewer":{"instruction":"i","harnesses":["claude-code"],"rules":[{"name":"naming","body":""}]}}}`,
			"fragment naming has an empty body",
		},
		{
			"FragmentIsDeclaredTwice",
			`{"schemaVersion":1,"roles":{"reviewer":{"instruction":"i","harnesses":["claude-code"],"skills":[{"name":"a","body":"b"},{"name":"a","body":"c"}]}}}`,
			"skills: fragment a is declared twice",
		},
		{
			"DefaultsFragmentIsValidatedToo",
			`{"schemaVersion":1,"defaults":{"rules":[{"name":"Naming","body":"b"}]},"roles":{"reviewer":{"instruction":"i","harnesses":["claude-code"]}}}`,
			`defaults rules: fragment name "Naming"`,
		},
		{
			"OverlayNameIsNotASlug",
			`{"schemaVersion":1,"roles":{"reviewer":{"instruction":"i","harnesses":["claude-code"]}},"overlays":{"Eden":{}}}`,
			`overlay name "Eden" is not an HNS-1 slug`,
		},
		{
			"OverlayFragmentIsValidatedToo",
			`{"schemaVersion":1,"roles":{"reviewer":{"instruction":"i","harnesses":["claude-code"]}},"overlays":{"eden":{"skills":[{"name":"a","body":""}]}}}`,
			"overlay eden skills: fragment a has an empty body",
		},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			_, err := newOverDocument(testCase.document)
			assertKindAndMessage(t, err, errors.KindInvalid, testCase.wantContains)
		})
	}
}

// TestNew_ParseFaultNamesTheLine asserts the parser converts encoding/json's byte offset into a LINE
// and a COLUMN for BOTH offset-carrying decoder types (a syntax fault and a type fault). A human
// editing a 300-line profile document cannot act on "offset 412"; the position is the difference
// between a fixable error and a re-read of the whole file. The LINE is unambiguous for both types,
// so it is asserted exactly here; the column has its own case below.
func TestNew_ParseFaultNamesTheLine(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name     string
		document string
		want     string
	}{
		// A stray comma where a key belongs: *json.SyntaxError, on line 3.
		{"SyntaxFault", "{\n  \"schemaVersion\": 1,\n  \"roles\": {,}\n}", "at line 3, column "},
		// A string where an int belongs: *json.UnmarshalTypeError, on line 2.
		{"TypeFault", "{\n  \"schemaVersion\": \"one\"\n}", "at line 2, column "},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			_, err := newOverDocument(testCase.document)
			assertKindAndMessage(t, err, errors.KindInvalid, testCase.want)
		})
	}
}

// TestNew_SyntaxFaultColumnNamesTheOffendingCharacter asserts the COLUMN of a syntax fault points AT
// the character the decoder rejected, which is what lineColumn's own doc comment claims it does:
// "encoding/json reports the offset just PAST the byte it rejected, so the position names the
// character the decoder choked on rather than the one before it."
//
// The document below puts a stray ',' at line 3, column 13 — count it: two spaces, then `"roles":`
// (8 characters, columns 3-10), a space (11), '{' (12), ',' (13), '}' (14). A position of 14 names
// the '}' that FOLLOWS the fault, which sends an editor's cursor one character past the thing to
// delete. This case is deliberately asserted at 13 rather than adjusted to whatever the code
// currently prints; see the report.
func TestNew_SyntaxFaultColumnNamesTheOffendingCharacter(t *testing.T) {
	t.Parallel()
	_, err := newOverDocument("{\n  \"schemaVersion\": 1,\n  \"roles\": {,}\n}")
	assertKindAndMessage(t, err, errors.KindInvalid, "at line 3, column 13")
}

// TestNew_SlugGrammarIsTheHNS1Grammar pins rule 11's grammar (word := [a-z][a-z0-9]*, joined by
// single hyphens) through the role-name gate, in both directions. The grammar is what keeps a
// document from steering a write outside the profile root — it admits no dot, no slash and no
// separator — so both halves matter: every accepted name and every rejected one.
func TestNew_SlugGrammarIsTheHNS1Grammar(t *testing.T) {
	t.Parallel()
	accepted := []string{"a", "ab", "a1", "a-b", "reviewer", "deep-research", "a1-b2-c3"}
	rejected := []string{"", "-a", "a-", "A", "aB", "a--b", "a_b", "1a", "a-1b", "a.b", "a/b", "a b", "a..b"}

	for _, name := range accepted {
		t.Run("accept/"+name, func(t *testing.T) {
			t.Parallel()
			if _, err := newOverDocument(documentNamingRole(name)); err != nil {
				t.Errorf("role name %q is a valid HNS-1 slug but was rejected: %v", name, err)
			}
		})
	}
	for _, name := range rejected {
		t.Run("reject/"+name, func(t *testing.T) {
			t.Parallel()
			_, err := newOverDocument(documentNamingRole(name))
			assertKindAndMessage(t, err, errors.KindInvalid, "is not an HNS-1 slug")
		})
	}
}

// ── Render: the emission invariants a third-party renderer cannot widen ─────────────────────────

// TestRender_RefusesAnEmissionThatBreaksTheContract is the ANTI-FALSE-GREEN battery. Every case
// scripts a renderer that returns something the library refuses, and asserts the refusal is a typed
// KindInternal error — the defect is on our side of the port, not in the caller's document — with a
// nil FileSet. The empty-emission case is the load-bearing one: an empty FileSet would let a drift
// check pass over a profile that was never written, which is a green gate proving nothing.
func TestRender_RefusesAnEmissionThatBreaksTheContract(t *testing.T) {
	t.Parallel()
	good := agentprofile.File{Path: "profiles/reviewer/claude-code/CLAUDE.md", Content: []byte("x"), Mode: 0o644}
	cases := []struct {
		name         string
		emission     agentprofile.FileSet
		wantContains string
	}{
		{"EmptyEmission", agentprofile.FileSet{}, "emitted no files"},
		{"DuplicatePath", agentprofile.FileSet{good, good}, "twice; one path, one file"},
		{"EmptyPath", agentprofile.FileSet{{Path: "", Content: []byte("x"), Mode: 0o644}}, "unusable path"},
		{"AbsolutePath", agentprofile.FileSet{{Path: "/etc/passwd", Content: []byte("x"), Mode: 0o644}}, "unusable path"},
		{"BackslashPath", agentprofile.FileSet{{Path: `profiles\reviewer\CLAUDE.md`, Content: []byte("x"), Mode: 0o644}}, "unusable path"},
		{"ParentEscape", agentprofile.FileSet{{Path: "profiles/../../etc/passwd", Content: []byte("x"), Mode: 0o644}}, "unusable path"},
		{"DotElement", agentprofile.FileSet{{Path: "profiles/./CLAUDE.md", Content: []byte("x"), Mode: 0o644}}, "unusable path"},
		{"EmptyElement", agentprofile.FileSet{{Path: "profiles//CLAUDE.md", Content: []byte("x"), Mode: 0o644}}, "unusable path"},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			renderer := agentprofiletest.NewRenderer(agentprofile.HarnessClaudeCode).Emitting(testCase.emission)
			files, err := renderThrough(t, renderer)
			if files != nil {
				t.Errorf("Render returned %d file(s) alongside its error, want nil", len(files))
			}
			assertKindAndMessage(t, err, errors.KindInternal, testCase.wantContains)
		})
	}
}

// TestRender_AcceptsAWellFormedEmissionVerbatim is the counterpart the battery above needs: the
// guards must ADMIT a legal emission unchanged. A guard that refused everything would pass every
// negative case and prove nothing.
func TestRender_AcceptsAWellFormedEmissionVerbatim(t *testing.T) {
	t.Parallel()
	emission := agentprofile.FileSet{
		{Path: "profiles/reviewer/claude-code/b.md", Content: []byte("second"), Mode: 0o644},
		{Path: "profiles/reviewer/claude-code/a.md", Content: []byte("first"), Mode: 0o600},
	}
	files, err := renderThrough(t, agentprofiletest.NewRenderer(agentprofile.HarnessClaudeCode).Emitting(emission))
	if err != nil {
		t.Fatalf("Render of a well-formed emission: %v", err)
	}
	// Render SORTS by path before returning, so the out-of-order script comes back ordered.
	want := []string{"profiles/reviewer/claude-code/a.md", "profiles/reviewer/claude-code/b.md"}
	if len(files) != len(want) {
		t.Fatalf("Render returned %d file(s), want %d", len(files), len(want))
	}
	for i := range want {
		if files[i].Path != want[i] {
			t.Errorf("file %d Path = %q, want %q — Render must sort the emission by Path", i, files[i].Path, want[i])
		}
	}
	if string(files[0].Content) != "first" || files[0].Mode != 0o600 {
		t.Errorf("file 0 = %q mode %v, want %q mode 0600 — content and mode pass through verbatim", files[0].Content, files[0].Mode, "first")
	}
}

// TestRender_WrapsARendererFaultPreservingItsKind asserts a renderer's own failure crosses the port
// wrapped, not flattened: the cause stays reachable, the Kind the renderer chose is preserved (never
// re-classified), and the target is attached as a field so a log line says which cell failed.
func TestRender_WrapsARendererFaultPreservingItsKind(t *testing.T) {
	t.Parallel()
	fault := errors.New(errors.KindExhausted, "the renderer ran out of budget")
	_, err := renderThrough(t, agentprofiletest.NewRenderer(agentprofile.HarnessClaudeCode).FailWith(fault))
	if err == nil {
		t.Fatal("Render returned nil error over a failing renderer")
	}
	if !errors.Is(err, fault) {
		t.Errorf("the renderer's fault is not reachable through the chain: %v", err)
	}
	if kind := errors.KindOf(err); kind != errors.KindExhausted {
		t.Errorf("KindOf = %v, want KindExhausted — the wrap adds context, it does not re-classify", kind)
	}
	if !strings.Contains(err.Error(), "render reviewer/claude-code") {
		t.Errorf("the error %q does not name the cell that failed", err.Error())
	}
	typed, matched := errors.AsType[*errors.Error](err)
	if !matched {
		t.Fatalf("the wrapped fault is not an *errors.Error: %v", err)
	}
	if got := typed.Fields()["target"]; got != "reviewer/claude-code" {
		t.Errorf(`Fields()["target"] = %v, want %q`, got, "reviewer/claude-code")
	}
}

// TestRender_UnknownCellIsNotFound asserts the two address faults a Target can carry — a role the
// document does not declare, and a harness the role does not declare — are both KindNotFound with a
// message that says which. They are the caller's addressing mistake, not a defect in the renderer.
func TestRender_UnknownCellIsNotFound(t *testing.T) {
	t.Parallel()
	document := agentprofiletest.CanonicalDocument(agentprofile.HarnessClaudeCode)
	// BOTH the claude and the omp renderer are wired, while the document declares the row for
	// claude-code ONLY. That separates the two not-found arms: omp is BOUND but off this row (the
	// matrix has no such cell), and codex is on no row AND unbound (no renderer claims it).
	compiler, err := agentprofile.New(
		agentprofile.Config{Document: document},
		agentprofile.Deps{
			Renderers: []agentprofile.Renderer{agentprofile.ClaudeRenderer{}, agentprofile.OMPRenderer{}},
			Tree:      agentprofiletest.NewTree(),
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	cases := []struct {
		name         string
		target       agentprofile.Target
		wantContains string
	}{
		{"UndeclaredRole", agentprofile.Target{Role: "auditor", Harness: agentprofile.HarnessClaudeCode}, `declares no role "auditor"`},
		{"HarnessNotOnThisRow", agentprofile.Target{Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessOMP}, "the matrix has no such cell"},
		{"UnclaimedHarness", agentprofile.Target{Role: agentprofiletest.CanonicalRole, Harness: agentprofile.HarnessCodex}, "no Deps.Renderers entry claims harness codex"},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Parallel()
			files, renderErr := compiler.Render(context.Background(), testCase.target)
			if files != nil {
				t.Errorf("Render returned %d file(s) for an unaddressable cell", len(files))
			}
			assertKindAndMessage(t, renderErr, errors.KindNotFound, testCase.wantContains)
		})
	}
}

// ── Target ──────────────────────────────────────────────────────────────────────────────────────

// TestTarget_StringIsTheEmissionPathOrder asserts Target.String renders "<role>/<harness>" — the
// same order the emission path uses — so an error message and a directory listing read alike.
func TestTarget_StringIsTheEmissionPathOrder(t *testing.T) {
	t.Parallel()
	got := agentprofile.Target{Role: "reviewer", Harness: agentprofile.HarnessClaudeCode}.String()
	if got != "reviewer/claude-code" {
		t.Errorf("Target.String() = %q, want %q", got, "reviewer/claude-code")
	}
}

// ── Helpers ─────────────────────────────────────────────────────────────────────────────────────

// newOverDocument builds a Compiler over the raw document with the real ClaudeRenderer and an empty
// tree, so a case's only variable is the document bytes.
func newOverDocument(document string) (*agentprofile.Compiler, error) {
	//nolint:wrapcheck // the test asserts on New's own typed error verbatim; wrapping would hide it.
	return agentprofile.New(
		agentprofile.Config{Document: []byte(document)},
		agentprofile.Deps{
			Renderers: []agentprofile.Renderer{agentprofile.ClaudeRenderer{}, agentprofile.OMPRenderer{}},
			Tree:      agentprofiletest.NewTree(),
		},
	)
}

// documentNamingRole is minimalDocument with the role named `name`, so the slug grammar is exercised
// through the gate a real document hits.
func documentNamingRole(name string) string {
	quoted := strings.ReplaceAll(name, `\`, `\\`)
	quoted = strings.ReplaceAll(quoted, `"`, `\"`)
	return `{"schemaVersion":1,"roles":{"` + quoted + `":{"instruction":"i","harnesses":["claude-code"]}}}`
}

// renderThrough renders the canonical cell through the scripted fake renderer.
func renderThrough(t *testing.T, renderer *agentprofiletest.Renderer) (agentprofile.FileSet, error) {
	t.Helper()
	compiler, err := agentprofile.New(
		agentprofile.Config{Document: []byte(minimalDocument)},
		agentprofile.Deps{Renderers: []agentprofile.Renderer{renderer}, Tree: agentprofiletest.NewTree()},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	//nolint:wrapcheck // the test asserts on Render's own typed error verbatim.
	return compiler.Render(context.Background(), agentprofile.Target{
		Role: "reviewer", Harness: agentprofile.HarnessClaudeCode,
	})
}

// assertKindAndMessage fails t unless err is non-nil, carries wantKind, and its message contains
// wantContains. Kind is the contract a caller branches on; the substring proves the message names
// the offending element, which is what makes the error actionable without reading source.
func assertKindAndMessage(t *testing.T, err error, wantKind errors.Kind, wantContains string) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected an error of kind %v containing %q, got nil", wantKind, wantContains)
	}
	if kind := errors.KindOf(err); kind != wantKind {
		t.Errorf("KindOf = %v, want %v (error: %v)", kind, wantKind, err)
	}
	if !strings.Contains(err.Error(), wantContains) {
		t.Errorf("error %q does not contain %q", err.Error(), wantContains)
	}
	if !strings.HasPrefix(err.Error(), "agentprofile: ") {
		t.Errorf("error %q does not carry this library's prefix", err.Error())
	}
}
