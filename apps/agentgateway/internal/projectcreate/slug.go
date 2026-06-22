package projectcreate

import "strings"

// deriveRepositorySlug renders a project name + its unique project id into a single, valid, unique
// HNS-1 repository slug (lowercase, hyphen-separated, [a-z0-9] words) so forge.CreateRepo always
// receives a legal, collision-free repository name. PURE: no I/O.
//
// The name is slugified to the HNS-1 grammar (the human-readable prefix) and the project id's unique
// suffix is appended so two projects named "pay backend" never collide on the GitHub account — the
// project id is already collision-resistant ("project-" + 18 hex), so the slug inherits its uniqueness.
// A name that slugifies to empty (all punctuation) falls back to "eden-project" + the id suffix, so the
// slug is never just a bare id and never empty.
func deriveRepositorySlug(name, projectID string) string {
	base := slugifyHNS1(name)
	if base == "" {
		base = "eden-project"
	}
	suffix := uniqueSuffix(projectID)
	if suffix == "" {
		return base
	}
	return base + "-" + suffix
}

// slugifyHNS1 renders free text into the HNS-1 slug grammar (lowercase, [a-z0-9] words joined by single
// hyphens, no leading/trailing hyphen). It mirrors the gateway's own slugify so a project name and its
// repository slug share one normalization; it is reproduced here (not imported) only because the
// gateway's helper is unexported — the rule is identical, not a second definition of the concept.
func slugifyHNS1(name string) string {
	var builder strings.Builder
	previousHyphen := true // suppress a leading hyphen
	for _, r := range strings.ToLower(strings.TrimSpace(name)) {
		switch {
		case (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9'):
			builder.WriteRune(r)
			previousHyphen = false
		case !previousHyphen:
			builder.WriteByte('-')
			previousHyphen = true
		}
	}
	return strings.Trim(builder.String(), "-")
}

// uniqueSuffix extracts the collision-resistant unique tail of a project id for the slug. A project id
// is "project-<hex>"; the hex tail is the unique part, so the suffix is everything after the last "-"
// (or the whole id slugified when it carries no "-"). The result is HNS-1-legal by construction (the id
// hex is [a-z0-9]).
func uniqueSuffix(projectID string) string {
	trimmed := slugifyHNS1(projectID)
	if index := strings.LastIndexByte(trimmed, '-'); index >= 0 && index+1 < len(trimmed) {
		return trimmed[index+1:]
	}
	return trimmed
}
