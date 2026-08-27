package gitrepository

import "strings"

// shellQuote single-quotes s for safe inclusion in the /bin/sh credential helper script. It
// is the ONE place library-generated text reaches a shell, and it is over a path the library
// itself created (a temp file), never user input — but it is quoted defensively all the same.
func shellQuote(s string) string {
	return "'" + strings.ReplaceAll(s, "'", `'\''`) + "'"
}

// cutPrefix splits prefix off s, reporting whether it was present (a local stand-in kept
// trivial so the porcelain parsers read cleanly).
func cutPrefix(s, prefix string) (string, bool) {
	return strings.CutPrefix(s, prefix)
}

// hasPrefix reports whether s starts with prefix.
func hasPrefix(s, prefix string) bool { return strings.HasPrefix(s, prefix) }

// shortBranch strips "refs/heads/" (and "refs/remotes/") from a porcelain ref to the short
// branch name git's --short would print.
func shortBranch(ref string) string {
	ref = strings.TrimSpace(ref)
	ref = strings.TrimPrefix(ref, "refs/heads/")
	ref = strings.TrimPrefix(ref, "refs/remotes/")
	return ref
}
