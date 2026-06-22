package forge

import (
	"regexp"
	"strings"
)

// ProtectedRepoNames are repository names DeleteRepo refuses OUTRIGHT — case-insensitively,
// regardless of owner or credential. The load-bearing Eden/Gophersys repositories (and a few
// look-alikes) can NEVER be deleted through the forge port. This is the second wall behind the
// EphemeralRepoName allowlist: a deletion must clear BOTH the denylist and the allowlist.
var ProtectedRepoNames = map[string]struct{}{
	"eden": {}, "helios": {}, "libs": {}, "template": {}, "templates": {},
	"infrastructure": {}, ".devcontainer": {}, "devcontainer": {},
	"application-templates": {}, "iotea-archive": {}, "iotea": {},
	"gophersys": {}, ".github": {}, "config": {},
}

// ephemeralRepo matches ONLY the reserved throwaway integration-test repository shape
// `eden-it-<suffix>`. No real project repository, platform repository, or library carries this
// prefix, so a repository whose name matches is provably a disposable test artifact — the single
// shape DeleteRepo is permitted to reap.
var ephemeralRepo = regexp.MustCompile(`^eden-it-[a-z0-9][a-z0-9-]{2,38}$`)

// EphemeralRepoName reports whether name is a deletable ephemeral integration-test repository
// (the reserved `eden-it-*` prefix) — the allowlist half of the delete guard.
func EphemeralRepoName(name string) bool { return ephemeralRepo.MatchString(strings.TrimSpace(name)) }

// GuardDelete is the HARD FENCE every DeleteRepo MUST apply BEFORE any network call. It returns a
// ForbiddenDeletionError (errors.KindInvalid) — and the adapter makes NO HTTP request — unless
// name is an ephemeral `eden-it-*` test repository (EphemeralRepoName) that is NOT protected
// (ProtectedRepoNames). One home for the delete-safety contract (10 §9); because every DeleteRepo
// path funnels through this and there is no unguarded delete, a real repository (eden / libs /
// template / infrastructure / any non-`eden-it-*` name) cannot be deleted through the forge port by
// any caller — a test, the saga, or production — no matter the credential's scopes.
func GuardDelete(owner, name string) error {
	trimmed := strings.ToLower(strings.TrimSpace(name))
	if _, protected := ProtectedRepoNames[trimmed]; protected {
		return ForbiddenDeletionError{Owner: owner, Name: name, Reason: "protected repository — never deletable through forge"}
	}
	if !EphemeralRepoName(name) {
		return ForbiddenDeletionError{Owner: owner, Name: name, Reason: "not an ephemeral eden-it-* test repository — refused"}
	}
	return nil
}

// ForbiddenDeletionError reports that DeleteRepo REFUSED a deletion at the guard, before any
// network call — the name is protected (ProtectedRepoNames) or is not an ephemeral test repository
// (EphemeralRepoName). It carries the offending identity (never a token) and maps to
// errors.KindInvalid: the request is structurally not a permitted deletion target.
type ForbiddenDeletionError struct {
	// Owner is the repository owner the refused deletion targeted.
	Owner string
	// Name is the repository name the guard refused.
	Name string
	// Reason names why the guard fired (operator-safe; never a token).
	Reason string
}

func (e ForbiddenDeletionError) Error() string {
	return "forge: REFUSED to delete " + slug(e.Owner, e.Name) + ": " + e.Reason
}
