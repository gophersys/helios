package agentsession_test

import (
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
)

// This file REPLACES A GATE THAT CANNOT FIRE. `_enum_liveness_scan` only inspects a closed
// taxonomy whose doc matches /[Cc]losed taxonomy/ plus an emission word; EventKind's doc says
// "stable, closed, additive-only" and Capability's says "Append-only." — neither matches, so
// the scan is INERT on both. Meanwhile eventKindTokens (types.go) and capabilityTokens
// (agentsession.go) are `[...]string` tables indexed BY VALUE with a String() that falls back
// to the FIRST member's token for anything out of range. So a member appended without its
// token row does not fail to compile and does not fail any gate — it silently renders as
// "extension" / "steer", colliding with a real member. That is the defect class this file
// exists to make loud.
//
// It is built so it CANNOT be vacuous and CANNOT go stale:
//
//   - the member list is read from the CONST DECLARATION in the package source (go/ast), never
//     from len(<the token table>). Deriving the bound from the table under test is exactly the
//     blind gate: a missing row shrinks the bound and the check passes.
//   - the token is then read at RUNTIME through the real String() method, so what is asserted
//     is the behavior a consumer sees, not a source literal.
//   - appending a member therefore EXTENDS the assertion with no edit to this file. Contract
//     revision R1 appends EventTurnEnd; if its token row is forgotten, EventTurnEnd.String()
//     returns "extension" and the distinctness check below fails naming both members.

// TestTaxonomyTokens_EveryMemberHasADistinctToken walks EVERY member of the two additive-only
// taxonomies, from the first const through the LAST one declared in the source, and asserts each
// renders a distinct, non-empty, lower-kebab token through its real String() method.
func TestTaxonomyTokens_EveryMemberHasADistinctToken(t *testing.T) {
	t.Parallel()
	for _, taxonomy := range taxonomies() {
		t.Run(taxonomy.typeName, func(t *testing.T) {
			t.Parallel()
			members := declaredMembers(t, taxonomy.sourceFile, taxonomy.typeName)
			if len(members) < 2 {
				t.Fatalf("%s: found %d declared members in %s; the source scan is broken, so this test would be vacuous",
					taxonomy.typeName, len(members), taxonomy.sourceFile)
			}
			seen := make(map[string]string, len(members))
			for ordinal, name := range members {
				// Named wireToken, not token: `go/token` is imported here for the source scan,
				// and a local `token` shadows it (gocritic importShadow).
				wireToken := taxonomy.render(ordinal)
				assertTokenShape(t, taxonomy.typeName, name, ordinal, wireToken)
				if previous, clash := seen[wireToken]; clash {
					t.Errorf("%s: %s (ordinal %d) and %s render the SAME token %q — %s has no row in the token table, so String() fell back to the first member's token",
						taxonomy.typeName, name, ordinal, previous, wireToken, name)
					continue
				}
				seen[wireToken] = name
			}
		})
	}
}

// TestTaxonomyTokens_SourceScanSeesTheKnownMembers is the NON-VACUITY anchor for the scan
// itself: it pins members the taxonomies are known to declare today, at their known ordinals.
// If the go/ast walk above silently found nothing (a refactor moved the const block, a parse
// error was swallowed), the distinctness loop would pass over an empty set — this catches that.
func TestTaxonomyTokens_SourceScanSeesTheKnownMembers(t *testing.T) {
	t.Parallel()
	eventKinds := declaredMembers(t, "types.go", "EventKind")
	assertMemberAt(t, eventKinds, 0, "EventSessionState")
	assertMemberAt(t, eventKinds, int(agentsession.EventResult), "EventResult")
	assertMemberAt(t, eventKinds, int(agentsession.EventExtension), "EventExtension")
	assertMemberAt(t, eventKinds, int(agentsession.EventThinkingProgress), "EventThinkingProgress")
	// PR-1c-i appends the peer + subagent kinds. Pinning them here makes the source scan a
	// non-vacuous oracle for the new members: a kind added without its eventKindTokens row
	// renders as "extension" (the [...]string fallback) and the distinctness loop above then
	// fails naming both members — the defect class this file exists to make loud.
	assertMemberAt(t, eventKinds, int(agentsession.EventPeerMessage), "EventPeerMessage")
	assertMemberAt(t, eventKinds, int(agentsession.EventPeerSent), "EventPeerSent")
	assertMemberAt(t, eventKinds, int(agentsession.EventSubagentMessage), "EventSubagentMessage")

	capabilities := declaredMembers(t, "agentsession.go", "Capability")
	assertMemberAt(t, capabilities, 0, "CapSteer")
	assertMemberAt(t, capabilities, int(agentsession.CapPermissionPrompt), "CapPermissionPrompt")
	assertMemberAt(t, capabilities, int(agentsession.CapPartialToolResults), "CapPartialToolResults")
	// PR-1c-i appends the two peer/subagent capability bits; a bit added without its
	// capabilityTokens row renders as "steer" and collides.
	assertMemberAt(t, capabilities, int(agentsession.CapPeerMessaging), "CapPeerMessaging")
	assertMemberAt(t, capabilities, int(agentsession.CapSubagentMessaging), "CapSubagentMessaging")
}

// ── the taxonomies under guard ───────────────────────────────────────────────────────────.

// taxonomy binds an additive-only enum's SOURCE declaration to its RUNTIME rendering, so the
// member set comes from the declaration and the token comes from the shipped String().
type taxonomy struct {
	typeName   string
	sourceFile string
	render     func(ordinal int) string
}

// taxonomies is the guarded set: the two [...]string-indexed-by-value tables whose missing row
// is silent. Adding an enum here is the ONLY edit a future taxonomy needs.
func taxonomies() []taxonomy {
	return []taxonomy{
		{
			typeName:   "EventKind",
			sourceFile: "types.go",
			render:     func(ordinal int) string { return agentsession.EventKind(ordinal).String() }, //nolint:gosec // ordinal is a bounded source-derived index
		},
		{
			typeName:   "Capability",
			sourceFile: "agentsession.go",
			render:     func(ordinal int) string { return agentsession.Capability(ordinal).String() }, //nolint:gosec // ordinal is a bounded source-derived index
		},
	}
}

// assertTokenShape asserts one member's token is non-empty and is the stable lower-kebab wire
// form the gateway projects and the UI keys off. The parameter is named wireToken, not token:
// `go/token` is imported here for the source scan, and a parameter named `token` shadows it
// (gocritic importShadow).
func assertTokenShape(t *testing.T, typeName, name string, ordinal int, wireToken string) {
	t.Helper()
	if wireToken == "" {
		t.Errorf("%s: %s (ordinal %d) renders an EMPTY token", typeName, name, ordinal)
		return
	}
	if strings.TrimSpace(wireToken) != wireToken {
		t.Errorf("%s: %s renders %q with surrounding whitespace", typeName, name, wireToken)
	}
	if wireToken != strings.ToLower(wireToken) {
		t.Errorf("%s: %s renders %q, which is not the stable lower-kebab wire form", typeName, name, wireToken)
	}
	if strings.ContainsAny(wireToken, " _") {
		t.Errorf("%s: %s renders %q; the wire form separates words with '-'", typeName, name, wireToken)
	}
}

// assertMemberAt asserts the source scan placed name at ordinal.
func assertMemberAt(t *testing.T, members []string, ordinal int, name string) {
	t.Helper()
	if ordinal >= len(members) {
		t.Fatalf("source scan found %d members, expected %s at ordinal %d", len(members), name, ordinal)
	}
	if members[ordinal] != name {
		t.Errorf("source scan: ordinal %d = %s, want %s (the const block was reordered — the taxonomy is additive-only)",
			ordinal, members[ordinal], name)
	}
}

// ── the source scan ──────────────────────────────────────────────────────────────────────.

// declaredMembers returns the member names of the iota const block that declares typeName, in
// declaration order (index == the member's value). It reads the SOURCE, so a member appended
// without a token row is still counted — which is the whole point: the token table cannot be
// its own completeness oracle.
func declaredMembers(t *testing.T, sourceFile, typeName string) []string {
	t.Helper()
	path := filepath.Join(".", sourceFile)
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("taxonomy source %s is missing: %v", sourceFile, err)
	}
	fileSet := token.NewFileSet()
	parsed, err := parser.ParseFile(fileSet, path, nil, parser.SkipObjectResolution)
	if err != nil {
		t.Fatalf("parse %s: %v", sourceFile, err)
	}
	for _, declaration := range parsed.Decls {
		general, isGeneral := declaration.(*ast.GenDecl)
		if !isGeneral || general.Tok != token.CONST {
			continue
		}
		if names, ok := iotaBlockMembers(general, typeName); ok {
			return names
		}
	}
	t.Fatalf("no `const ( X %s = iota ... )` block found in %s", typeName, sourceFile)
	return nil
}

// iotaBlockMembers extracts the member names of a const block whose FIRST spec is typed
// typeName (the `X Type = iota` head). ok=false for any other const block.
func iotaBlockMembers(general *ast.GenDecl, typeName string) (names []string, ok bool) {
	if len(general.Specs) == 0 {
		return nil, false
	}
	head, isValue := general.Specs[0].(*ast.ValueSpec)
	if !isValue {
		return nil, false
	}
	typeIdent, isIdent := head.Type.(*ast.Ident)
	if !isIdent || typeIdent.Name != typeName {
		return nil, false
	}
	for _, spec := range general.Specs {
		value, isValueSpec := spec.(*ast.ValueSpec)
		if !isValueSpec {
			continue
		}
		for _, ident := range value.Names {
			if ident.Name == "_" {
				// A skipped ordinal still consumes a value; record it so indexes stay honest.
				names = append(names, "_reserved_"+strconv.Itoa(len(names)))
				continue
			}
			names = append(names, ident.Name)
		}
	}
	return names, true
}
