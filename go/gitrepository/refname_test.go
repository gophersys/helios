package gitrepository_test

import (
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/gitrepository"
)

// TestParseBranchName_RoundTrips proves a valid name round-trips through Parse → String (the
// contract's value-round-trip property).
func TestParseBranchName_RoundTrips(t *testing.T) {
	t.Parallel()
	for _, name := range []string{"main", "feature/x", "release/2026.06", "a/b/c", "fix-123"} {
		parsed, err := gitrepository.ParseBranchName(name)
		if err != nil {
			t.Errorf("ParseBranchName(%q) errored: %v", name, err)
			continue
		}
		if parsed.String() != name {
			t.Errorf("ParseBranchName(%q).String() = %q, want round-trip", name, parsed.String())
		}
		if parsed.IsZero() {
			t.Errorf("ParseBranchName(%q).IsZero() = true, want false", name)
		}
	}
}

// TestParseBranchName_RejectsInjection proves an injection-shaped or git-illegal name is
// rejected with an InvalidRefError (KindInvalid) before it can reach an argv.
func TestParseBranchName_RejectsInjection(t *testing.T) {
	t.Parallel()
	bad := []string{
		"",   // empty
		"-x", // leading dash → flag injection
		"--upload-pack=evil",
		"a..b",                                           // double-dot range token
		"a b",                                            // space
		"feature/",                                       // trailing slash
		"/feature",                                       // leading slash
		"a//b",                                           // empty component
		"a\x00b",                                         // NUL
		"a\tb",                                           // control char
		"@",                                              // bare @
		"a@{0}",                                          // reflog syntax
		"branch.lock",                                    // .lock suffix
		".hidden",                                        // component starts with dot
		"name.",                                          // trailing dot
		"a~b", "a^b", "a:b", "a?b", "a*b", "a[b", "a\\b", // git-forbidden bytes
	}
	for _, name := range bad {
		parsed, err := gitrepository.ParseBranchName(name)
		if err == nil {
			t.Errorf("ParseBranchName(%q) must reject, got %q", name, parsed.String())
			continue
		}
		if errors.KindOf(err) != errors.KindInvalid {
			t.Errorf("ParseBranchName(%q) error must be KindInvalid, got %v", name, errors.KindOf(err))
		}
		if !is[*gitrepository.InvalidRefError](err) {
			t.Errorf("ParseBranchName(%q) error must be *InvalidRefError, got %T", name, err)
		}
	}
}

// is reports whether err's chain carries a *E (the Go 1.26 single-arg AsType form), keeping
// the typed-error checks free of an unchecked discard.
func is[E error](err error) bool {
	_, ok := errors.AsType[E](err)
	return ok
}

// TestCommitID_Zero proves the zero CommitID is the invalid/unborn commit.
func TestCommitID_Zero(t *testing.T) {
	t.Parallel()
	var zero gitrepository.CommitID
	if !zero.IsZero() {
		t.Errorf("zero CommitID must report IsZero")
	}
	if zero.String() != "" {
		t.Errorf("zero CommitID String() = %q, want empty", zero.String())
	}
}

// TestCommitIDFromHex proves the backend constructor accepts full sha-1/sha-256 ids and
// rejects malformed input to the zero value.
func TestCommitIDFromHex(t *testing.T) {
	t.Parallel()
	sha1 := "0123456789abcdef0123456789abcdef01234567"                            // 40 hex
	sha256 := sha1 + "0123456789abcdef0123456789abcdef01234567"                   // 80 — too long
	full256 := "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" // 64 hex

	if got := gitrepository.CommitIDFromHex(sha1); got.String() != sha1 || got.IsZero() {
		t.Errorf("CommitIDFromHex(sha1) = %q, want round-trip non-zero", got.String())
	}
	if got := gitrepository.CommitIDFromHex(full256); got.IsZero() {
		t.Errorf("CommitIDFromHex(sha256) must accept a 64-hex id")
	}
	for _, bad := range []string{"", "xyz", "012345", sha256, "  spaces  "} {
		if got := gitrepository.CommitIDFromHex(bad); !got.IsZero() {
			t.Errorf("CommitIDFromHex(%q) = %q, want zero", bad, got.String())
		}
	}
	// Whitespace around a valid id is trimmed; case is normalized to lower.
	if got := gitrepository.CommitIDFromHex("  " + sha1 + "  "); got.String() != sha1 {
		t.Errorf("CommitIDFromHex trims whitespace; got %q", got.String())
	}
	upper := "ABCDEF0123456789ABCDEF0123456789ABCDEF01"
	if got := gitrepository.CommitIDFromHex(upper); got.String() != "abcdef0123456789abcdef0123456789abcdef01" {
		t.Errorf("CommitIDFromHex must lowercase; got %q", got.String())
	}
}
