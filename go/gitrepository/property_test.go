package gitrepository_test

import (
	"strings"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS in the process environment
// (default 1000 iterations/property, ADR-0020 dimension (a)); rapid reads it directly. These
// properties drive the REAL pure value layer of the library — ParseBranchName, CommitIDFromHex,
// the typed-error Kind table, the ChangeKind tokens — the argv-injection guard and the
// transport-classification contract that every git op rides on.

// TestProperty_ParseBranchNameRoundTrips asserts the load-bearing round-trip: ANY name built
// from legal slug components parses, and its String() is byte-identical to the input. A drift
// here would mean a name the orchestrator handed in is silently rewritten before it reaches a
// git argv — a correctness AND a safety break (02 §2 worktree branch names).
func TestProperty_ParseBranchNameRoundTrips(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		name := drawValidBranchName(rt)
		parsed, err := gitrepository.ParseBranchName(name)
		if err != nil {
			rt.Fatalf("ParseBranchName(%q) errored on a legal name: %v", name, err)
		}
		if parsed.String() != name {
			rt.Fatalf("ParseBranchName(%q).String() = %q, want byte-identical round-trip", name, parsed.String())
		}
		if parsed.IsZero() {
			rt.Fatalf("ParseBranchName(%q).IsZero() = true on a non-empty legal name", name)
		}
	})
}

// TestProperty_ParseBranchNameRejectsInjection asserts the injection-guard half is TOTAL: a
// name carrying ANY forbidden marker (a leading dash, a "..", whitespace, a control byte, a
// git-forbidden punctuation byte, an empty component) is rejected with a KindInvalid
// *InvalidRefError — never silently accepted onto an argv. The needle is spliced into an
// otherwise-legal base so the property explores the boundary, not just obviously-garbage input.
func TestProperty_ParseBranchNameRejectsInjection(t *testing.T) {
	t.Parallel()
	forbidden := []string{"-", "..", " ", "\t", "\x00", "~", "^", ":", "?", "*", "[", "\\", "//", "@{"}
	rapid.Check(t, func(rt *rapid.T) {
		base := drawValidBranchName(rt)
		needle := forbidden[rapid.IntRange(0, len(forbidden)-1).Draw(rt, "needle")]
		// Prefix with the needle for the leading-dash case; otherwise splice it in the middle so
		// the resulting name is still non-empty and exercises the byte/affix/component rules.
		var bad string
		if needle == "-" {
			bad = needle + base
		} else {
			bad = base + needle + base
		}
		_, err := gitrepository.ParseBranchName(bad)
		if err == nil {
			rt.Fatalf("ParseBranchName(%q) must reject an injection-shaped name", bad)
		}
		if errors.KindOf(err) != errors.KindInvalid {
			rt.Fatalf("ParseBranchName(%q) error must be KindInvalid, got %v", bad, errors.KindOf(err))
		}
		if !is[*gitrepository.InvalidRefError](err) {
			rt.Fatalf("ParseBranchName(%q) error must be *InvalidRefError, got %T", bad, err)
		}
	})
}

// TestProperty_CommitIDFromHexNormalizesIdempotently asserts the CommitID constructor is a
// total, idempotent normalizer: a legal 40/64-hex id (in any case, with surrounding
// whitespace) round-trips to its lowercase form, and re-parsing that form is a fixed point. A
// non-hex / wrong-length value is the zero CommitID. This pins the only path an object id
// enters the surface (a Backend resolving git output).
func TestProperty_CommitIDFromHexNormalizesIdempotently(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		canonical := drawHexID(rt)
		// Re-case some nibbles to upper and pad with whitespace: the constructor must fold both.
		noisy := pad(rt, recase(rt, canonical))
		got := gitrepository.CommitIDFromHex(noisy)
		if got.IsZero() {
			rt.Fatalf("CommitIDFromHex(%q) returned zero for a legal hex id", noisy)
		}
		if got.String() != canonical {
			rt.Fatalf("CommitIDFromHex(%q) = %q, want normalized %q", noisy, got.String(), canonical)
		}
		// Idempotent: re-parsing the normalized form is a fixed point.
		again := gitrepository.CommitIDFromHex(got.String())
		if again.String() != got.String() {
			rt.Fatalf("CommitIDFromHex is not idempotent: %q then %q", got.String(), again.String())
		}
	})
}

// TestProperty_CommitIDFromHexRejectsMalformed asserts a wrong-length hex string (any length
// that is neither 40 nor 64) yields the zero CommitID — the constructor never admits a partial
// or over-long id onto the surface.
func TestProperty_CommitIDFromHexRejectsMalformed(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		n := rapid.IntRange(0, 80).Filter(func(k int) bool { return k != 40 && k != 64 }).Draw(rt, "len")
		s := strings.Repeat("a", n)
		if got := gitrepository.CommitIDFromHex(s); !got.IsZero() {
			rt.Fatalf("CommitIDFromHex(len=%d) = %q, want zero (only 40/64 hex are legal)", n, got.String())
		}
	})
}

// TestProperty_ErrorKindRoundTripStable asserts the transport-classification contract: for
// EVERY typed gitrepository error, WrapError(e) classifies via errors.KindOf to the SAME stable
// Kind the error's own Kind() reports — across repeated wraps. This is the table the transport
// boundary reads instead of a per-port switch (10 §9); a drift between Kind() and the wrapped
// KindOf would split the wire contract from the in-process one.
func TestProperty_ErrorKindRoundTripStable(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		want, err := drawTypedError(rt)
		wrapped := gitrepository.WrapError(err)
		if errors.KindOf(wrapped) != want {
			rt.Fatalf("KindOf(WrapError(%T)) = %v, want %v", err, errors.KindOf(wrapped), want)
		}
		// Wrapping again must not drift the Kind (idempotent classification through the chain).
		if errors.KindOf(gitrepository.WrapError(wrapped)) != want {
			rt.Fatalf("re-wrapping %T drifted its Kind", err)
		}
	})
}

// TestProperty_ChangeKindTokenTotalAndStable asserts ChangeKind.String() is TOTAL (non-empty
// for every enumerated value) and STABLE (a value rebuilt from its raw byte renders the
// identical token) — the token the frontend's file-modification panel and any telemetry branch
// on. An empty or drifting token is a surface break.
func TestProperty_ChangeKindTokenTotalAndStable(t *testing.T) {
	t.Parallel()
	all := []gitrepository.ChangeKind{
		gitrepository.ChangeAdded, gitrepository.ChangeModified, gitrepository.ChangeDeleted,
		gitrepository.ChangeRenamed, gitrepository.ChangeUntracked, gitrepository.ChangeConflicted,
	}
	rapid.Check(t, func(rt *rapid.T) {
		ck := all[rapid.IntRange(0, len(all)-1).Draw(rt, "changeKind")]
		rebuilt := gitrepository.ChangeKind(uint8(ck))
		if rebuilt.String() == "" {
			rt.Fatalf("ChangeKind(%d).String() is empty (tokens must be total)", ck)
		}
		if rebuilt.String() != ck.String() {
			rt.Fatalf("ChangeKind(%d).String() unstable: %q vs %q", ck, rebuilt.String(), ck.String())
		}
	})
}

// ── draw helpers ──────────────────────────────────────────────────────────────.

// drawValidBranchName builds a legal git short branch name from slug components: each component
// starts with a letter and is followed by [a-z0-9-], joined by "/", with no forbidden affix.
func drawValidBranchName(rt *rapid.T) string {
	n := rapid.IntRange(1, 3).Draw(rt, "components")
	parts := make([]string, n)
	for i := range parts {
		head := rapid.RuneFrom([]rune("abcdefghijklmnopqrstuvwxyz")).Draw(rt, "head")
		tail := rapid.StringOfN(rapid.RuneFrom([]rune("abcdefghijklmnopqrstuvwxyz0123456789-")), 0, 8, -1).Draw(rt, "tail")
		// A trailing dash is legal; a trailing dot is not, so the alphabet excludes ".".
		parts[i] = string(head) + tail
	}
	return strings.Join(parts, "/")
}

// drawHexID builds a canonical (lowercase) 40- or 64-hex object id.
func drawHexID(rt *rapid.T) string {
	width := 40
	if rapid.Bool().Draw(rt, "sha256") {
		width = 64
	}
	return rapid.StringOfN(rapid.RuneFrom([]rune("0123456789abcdef")), width, width, -1).Draw(rt, "hex")
}

// recase flips a random subset of a hex string's letters to upper case (the constructor must
// fold case).
func recase(rt *rapid.T, s string) string {
	out := []rune(s)
	for i, r := range out {
		if r >= 'a' && r <= 'f' && rapid.Bool().Draw(rt, "upper") {
			out[i] = r - ('a' - 'A')
		}
	}
	return string(out)
}

// pad surrounds a string with a random amount of whitespace (the constructor trims it).
func pad(rt *rapid.T, s string) string {
	left := strings.Repeat(" ", rapid.IntRange(0, 3).Draw(rt, "left"))
	right := strings.Repeat(" ", rapid.IntRange(0, 3).Draw(rt, "right"))
	return left + s + right
}

// drawTypedError draws one of the typed gitrepository errors together with its expected stable
// Kind, so the round-trip property covers the whole error taxonomy. The Kind is returned first
// (error-last convention) so the caller reads `want, err := drawTypedError(rt)`.
func drawTypedError(rt *rapid.T) (errors.Kind, error) {
	type entry struct {
		kind errors.Kind
		err  error
	}
	table := []entry{
		{errors.KindInvalid, &gitrepository.InvalidRefError{Ref: "x"}},
		{errors.KindNotFound, &gitrepository.NotFoundError{What: "x"}},
		{errors.KindConflict, &gitrepository.AlreadyExistsError{What: "x"}},
		{errors.KindConflict, &gitrepository.NothingToCommitError{}},
		{errors.KindConflict, &gitrepository.NonFastForwardError{}},
		{errors.KindConflict, &gitrepository.ConflictError{}},
		{errors.KindConflict, &gitrepository.DirtyWorktreeError{Worktree: "wt"}},
		{errors.KindUnauthenticated, &gitrepository.AuthError{Remote: "origin"}},
		{errors.KindPermission, &gitrepository.DeniedError{}},
		{errors.KindUnavailable, &gitrepository.UnavailableError{Remote: "origin"}},
	}
	e := table[rapid.IntRange(0, len(table)-1).Draw(rt, "typedError")]
	return e.kind, e.err
}
