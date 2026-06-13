package checker

import "strings"

// bannedTokens is the HNS-1 forbidden-identifier set (10 §5, ADR-0018 Layer 1).
// These are the abbreviation/grab-bag tokens that golangci/forbidigo rejects as
// *identifiers*; hnslint additionally rejects them as *directory and package
// names*, which forbidigo cannot see. The required full spelling is given in the
// comment so the diagnostic can point at it, but the structural rule only needs
// membership.
//
// The set is the union of the §5 "Forbidden → required" table and the ADR-0018
// forbidigo enumeration:
//
//	cfg/config        → configuration
//	deps              → dependencies
//	obsv/o11y         → observability
//	mgmt              → management
//	auth              → identity
//	db/repo/store     → persistence
//	k8s               → kubernetes
//	ts                → typescript
//	golang            → go
//	util/utils/common/core/misc → banned outright (name the actual pattern)
var bannedTokens = map[string]string{
	"cfg":    "configuration",
	"config": "configuration",
	"deps":   "dependencies",
	"obsv":   "observability",
	"o11y":   "observability",
	"mgmt":   "management",
	"auth":   "identity",
	"db":     "persistence",
	"repo":   "persistence",
	"store":  "persistence",
	"k8s":    "kubernetes",
	"ts":     "typescript",
	"golang": "go",
	"util":   "(name the actual pattern)",
	"utils":  "(name the actual pattern)",
	"common": "(name the actual pattern)",
	"core":   "(name the actual pattern)",
	"misc":   "(name the actual pattern)",
}

// IsBanned reports whether token is an HNS-1 forbidden directory/package name.
func IsBanned(token string) bool {
	_, ok := bannedTokens[token]
	return ok
}

// requiredFor returns the full spelling an HNS-1 banned token must be replaced
// with. It assumes IsBanned(token) is true.
func requiredFor(token string) string {
	return bannedTokens[token]
}

// bannedFakesStem reports whether name is a fakes-style package (it ends in the
// conventional "test" suffix) built on a banned abbreviation — e.g. "cfgtest",
// "depstest", "obsvtest", "authtest". This is the exact class of break ADR-0018
// names as its motivating case: the Wave-3A "cfgtest" fakes package that passed
// prompt guidance because forbidigo only sees the *cfg* identifier, not the
// composed package name. It returns the banned stem and true when matched.
//
// The check is deliberately narrow — it splits only on the trailing "test"
// suffix and tests the stem for *exact* membership in the banned set, so the
// conformant "configurationtest"/"errorstest"/"secretstest" families (whose
// stems are full words) never match, and no substring heuristic can misfire on
// an unrelated name.
func bannedFakesStem(name string) (string, bool) {
	const suffix = "test"
	if name == suffix || !strings.HasSuffix(name, suffix) {
		return "", false
	}
	stem := strings.TrimSuffix(name, suffix)
	if IsBanned(stem) {
		return stem, true
	}
	return "", false
}
