package gitrepository

import "strings"

// ParseBranchName validates and constructs a BranchName. PURE; no I/O. Returns a
// wrapped InvalidRefError (errors.AsType) for a name git refuses. The rules mirror
// git-check-ref-format's short-name constraints, plus the argv-injection guard (no
// leading "-"): a name that survives this can never be mistaken for a flag or break
// out of a pathspec when it reaches a git argv.
func ParseBranchName(s string) (BranchName, error) {
	if !validBranchName(s) {
		return BranchName{}, wrapKind(&InvalidRefError{Ref: s})
	}
	return BranchName{name: s}, nil
}

// validBranchName reports whether s is a legal git short branch name AND is safe to
// place on an argv. It rejects exactly what `git check-ref-format --branch` rejects
// for the cases that matter here, and additionally a leading "-" (the flag-injection
// surface). The rules:
//
//   - non-empty, no leading/trailing "/" and no "//" (empty path component);
//   - no leading "-" (would parse as a flag on an argv);
//   - no "..", no "@{", no trailing ".lock", and a bare "@" is rejected;
//   - no ASCII control char, space, or any of the bytes git forbids in a ref
//     component: ~ ^ : ? * [ \ and DEL;
//   - no component ending in "." and no trailing ".".
func validBranchName(s string) bool {
	if s == "" || s == "@" {
		return false
	}
	if branchHasForbiddenAffix(s) {
		return false
	}
	if strings.Contains(s, "..") || strings.Contains(s, "@{") || strings.Contains(s, "//") {
		return false
	}
	if !branchBytesLegal(s) {
		return false
	}
	return branchComponentsLegal(s)
}

// branchHasForbiddenAffix rejects a leading dash (flag injection), a leading/trailing slash,
// and the .lock / trailing-dot suffixes git forbids.
func branchHasForbiddenAffix(s string) bool {
	return strings.HasPrefix(s, "-") ||
		strings.HasPrefix(s, "/") || strings.HasSuffix(s, "/") ||
		strings.HasSuffix(s, ".lock") || strings.HasSuffix(s, ".")
}

// branchBytesLegal rejects any ASCII control char, space, DEL, or a byte git forbids in a ref.
func branchBytesLegal(s string) bool {
	for _, r := range s {
		if r <= 0x20 || r == 0x7f || strings.ContainsRune("~^:?*[\\", r) {
			return false
		}
	}
	return true
}

// branchComponentsLegal enforces git's per-component rule: no empty component, and no
// component beginning or ending with ".".
func branchComponentsLegal(s string) bool {
	for _, component := range strings.Split(s, "/") {
		if component == "" || strings.HasPrefix(component, ".") || strings.HasSuffix(component, ".") {
			return false
		}
	}
	return true
}

// validRevision reports whether s is safe to hand git as a revision/start point. It is
// looser than a branch name (a revision may be a sha, "HEAD", "main~2", "a/b") but it
// keeps the argv-injection guard: a revision must be non-empty and may not start with
// "-" (a flag), contain whitespace, a NUL, or a ".." double-dot range token (which a
// caller must express through DiffOptions.From/To, never smuggle into a single rev).
func validRevision(s string) bool {
	if s == "" {
		return false
	}
	if strings.HasPrefix(s, "-") {
		return false
	}
	if strings.Contains(s, "..") {
		return false
	}
	for _, r := range s {
		if r <= 0x20 || r == 0x7f {
			return false
		}
	}
	return true
}

// validRemoteName reports whether name is a legal logical remote name: non-empty, no
// leading "-" (flag-injection), no "/" or whitespace. It keeps a remote key that
// reaches an argv from being mistaken for a flag or a path.
func validRemoteName(name string) bool {
	if name == "" || strings.HasPrefix(name, "-") {
		return false
	}
	for _, r := range name {
		if r <= 0x20 || r == 0x7f || r == '/' {
			return false
		}
	}
	return true
}
