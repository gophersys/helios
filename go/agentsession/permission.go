package agentsession

import (
	"context"
	"strings"
)

// This file holds the RATIFIED Eden permission model (founder-designed, 2026-06-15) on
// top of the frozen permission round-trip: the per-session resolution chain mode, the
// PermissionAdvisor port (an injected dependency — agentsession CALLS it, never spawns an
// agent itself), the AdviceContext the session hands it, and the pure risk-class table
// that bounds the advisor's authority. The CLAMP that enforces the risk-class wall lives
// next to the resolution chain in session.go, so it holds regardless of the advisor impl.
//
// The chain (out-of-grant requests; grants are auto-allowed before this):
//
//	CHAT (a human is present):  grants → EventPermissionRequest (human Resolve)
//	                                   → on TIMEOUT → the ADVISOR → default-deny
//	AUTONOMOUS (no human):      grants → the ADVISOR → default-deny
//
// The terminal fallback is ALWAYS default-deny. If no advisor is injected, the chain
// degrades to the existing Spec.OnPermission / default-deny with NO regression.

// PermissionResolution selects the per-session out-of-grant resolution chain (a Spec
// setting). Append-only (10 §9): never reordered or renamed. The zero value is the SAFE
// default (ResolveChatHumanThenAdvisor) — a session that does not name a mode gets the
// human-first chain, never the autonomous one.
type PermissionResolution uint8

// The per-session resolution chains.
const (
	// ResolveChatHumanThenAdvisor is the interactive chain (the zero value, safe default):
	// an out-of-grant request emits EventPermissionRequest and awaits a human Resolve; on
	// Spec.PermissionTimeout it falls back to the injected advisor; the terminal fallback is
	// default-deny. With no advisor injected it degrades to OnPermission/default-deny.
	ResolveChatHumanThenAdvisor PermissionResolution = iota

	// ResolveAutonomousAdvisor is the unattended chain (no human present): an out-of-grant
	// request goes straight to the injected advisor (no EventPermissionRequest wait); the
	// terminal fallback is default-deny. With no advisor injected it degrades to
	// OnPermission/default-deny — an unattended session with neither is always default-deny.
	ResolveAutonomousAdvisor
)

// resolutionTokens holds the stable lower-kebab token for each PermissionResolution.
var resolutionTokens = [...]string{
	ResolveChatHumanThenAdvisor: "chat-human-then-advisor",
	ResolveAutonomousAdvisor:    "autonomous-advisor",
}

// String returns the stable lower-kebab token (e.g. "autonomous-advisor"). Total:
// returns "chat-human-then-advisor" for any out-of-range value.
func (r PermissionResolution) String() string {
	if int(r) < len(resolutionTokens) {
		return resolutionTokens[r]
	}
	return resolutionTokens[ResolveChatHumanThenAdvisor]
}

// RiskLevel is the prompt-injection wall: the advisor's authority is bounded by a risk
// class derived from the TOOL+SCOPE (DATA), NEVER the agent's prose. Append-only (10 §9).
// The clamp (session.go) lets the advisor auto-allow only RiskLow/RiskMedium; on RiskHigh
// the advisor may ONLY deny or escalate-to-human — injection can argue but can never cross
// the high-risk wall. The zero value (RiskHigh) is the SAFE default: an unclassified tool
// is treated as high-risk, so a new/unknown tool is never auto-allowed by the advisor.
type RiskLevel uint8

// The risk levels. RiskHigh is iota 0 so the zero value (an unclassified/unknown tool) is
// the safe, un-auto-allowable class.
const (
	RiskHigh   RiskLevel = iota // destructive/irreversible/egress/credential/write-outside-workspace — advisor may ONLY deny or escalate, NEVER auto-allow
	RiskMedium                  // mutating but reversible (in-workspace write/edit) — advisor MAY auto-allow
	RiskLow                     // read-scoped, reversible (Read, Bash(ls/grep)) — advisor MAY auto-allow
)

// riskTokens holds the stable lower-kebab token for each RiskLevel.
var riskTokens = [...]string{
	RiskHigh:   "high",
	RiskMedium: "medium",
	RiskLow:    "low",
}

// String returns the stable lower-kebab token (e.g. "high"). Total: returns "high" for
// any out-of-range value (the safe default).
func (r RiskLevel) String() string {
	if int(r) < len(riskTokens) {
		return riskTokens[r]
	}
	return riskTokens[RiskHigh]
}

// AdviceContext is the bundle the session hands the PermissionAdvisor alongside the
// PermissionRequest: everything the session can share WITHOUT a secret value, so the
// advisor's reasoning subagent has the session goal/role/phase, the higher-level intent,
// the standing grants, a recent transcript snippet, and the security posture. It is a
// plain copyable value; it carries NO live handles and NO credential material (the
// SecurityPosture is a coarse loggable label, never a token).
type AdviceContext struct {
	// SessionGoal is the role/phase intent for THIS session (RouteKey, plus the optional
	// product/task intent the engine threads through SystemHints). It is the "what is this
	// agent here to do" the advisor weighs the request against.
	SessionGoal string
	Role        string // RouteKey.Role ("assistant" | "implementer" | "reviewer" | ...)
	Phase       string // RouteKey.Phase ("implement" | "review" | ... | "" interactive)

	// Grants is a COPY of the session's current standing grant set (the allowlist AS DATA,
	// including any ScopeSession widenings already granted this session). The advisor reads
	// it to reason about precedent ("Write is already granted; this Bash(go test) is in
	// the same spirit") — it never mutates it.
	Grants []ToolGrant

	// RecentTranscript is a bounded, redacted snippet of the recent stream (the last few
	// text/tool deltas) so the advisor sees what led to the request. It is REDACTED text,
	// never raw secret-bearing data, and never the credential value.
	RecentTranscript string

	// SecurityPosture is a coarse, loggable label of the session's sandbox/egress stance
	// (e.g. "strict-sandbox-no-egress"). It is a CLASSIFICATION the advisor weighs, never a
	// secret value or a token.
	SecurityPosture string

	// Risk is the risk class the session derived from the request's tool+scope DATA, handed
	// to the advisor for transparency. The advisor's verdict is CLAMPED by this regardless
	// of what the advisor returns (the wall is enforced in agentsession, not trusted to the
	// advisor) — but the advisor sees it so it can self-escalate a high-risk request.
	Risk RiskLevel
}

// PermissionAdvisor is the injected reasoning port for out-of-grant requests (the ratified
// model's ADVISOR). It is a DEPENDENCY agentsession CALLS — agentsession stays pure and
// does NOT implement it (the impl lives in the runtime, which can spawn a max-thinking
// reasoning subagent). agentsession injects the request + an AdviceContext and audit-logs
// the returned Decision's Rationale. The advisor's authority is BOUNDED by the risk-class
// clamp applied in agentsession: it can NEVER auto-allow a RiskHigh tool no matter what it
// returns. A single method (well under the 5-method ceiling, 10 §9).
type PermissionAdvisor interface {
	// Advise reasons about an out-of-grant request and returns a Decision (Verdict + Scope
	// + By + Rationale) or an error. ctx bounds the reasoning (a slow advisor is treated as
	// a deny by the chain, never an indefinite block). The returned Decision is subject to
	// the risk-class clamp before it takes effect — an allow of a RiskHigh tool is overridden
	// to deny (or escalate-to-human where a human path exists). By SHOULD be "advisor:<name>";
	// Rationale SHOULD be populated (it is audit-logged on EventPermissionResolved).
	Advise(ctx context.Context, request PermissionRequest, advice AdviceContext) (Decision, error)
}

// riskClass derives the RiskLevel of a request from the tool name + its requested scopes —
// DATA, never the agent's prose. This is the documented table the injection wall stands on:
//
//	HIGH  — destructive / irreversible / egress / credential / write-outside-workspace:
//	        rm, network/fetch/curl/web, secret/credential/token/vault access, sudo, kill,
//	        chmod/chown, push/force, and any UNKNOWN tool (the safe default is high).
//	MEDIUM— mutating but reversible, in-workspace: Write, Edit, MultiEdit, NotebookEdit,
//	        and an in-workspace mutating Bash (mkdir/touch/mv/cp/go build/go test/git add/commit).
//	LOW   — read-scoped, reversible: Read, Glob, Grep, LS, and a read-only Bash (ls/cat/grep/find/pwd/git status/git diff).
//
// A SHELL tool (Bash/shell/exec/run) is classified BY ITS SCOPES: a bare shell tool with NO
// scope is unbounded → HIGH; with scopes it is the MOST DANGEROUS scope's class (so
// "Bash(ls)" is LOW but "Bash(rm)" is HIGH, and a mixed ["ls *","rm *"] is HIGH). A
// non-shell tool is classified by its name, and a scope can only ESCALATE it (never lower a
// known non-shell tool below its name's class).
func riskClass(tool string, scopes []string) RiskLevel {
	// Fold a scope embedded in the tool string ("Bash(rm -rf)") into the scope set so the
	// table behaves identically whether the caller passed scopes explicitly or wrapped.
	if len(scopes) == 0 {
		scopes = scopesFromTool(tool)
	}
	if isShellTool(tool) {
		if len(scopes) == 0 {
			return RiskHigh // a bare shell with no scope is unbounded
		}
		worst := RiskLow
		for _, scope := range scopes {
			worst = moreDangerous(worst, classifyScope(scope))
		}
		return worst
	}
	level := classifyToolName(tool)
	for _, scope := range scopes {
		level = moreDangerous(level, classifyScope(scope))
	}
	return level
}

// moreDangerous returns the more dangerous of two levels (RiskHigh==0 is the most
// dangerous, so the smaller numeric value wins).
func moreDangerous(a, b RiskLevel) RiskLevel {
	if a < b {
		return a
	}
	return b
}

// isShellTool reports whether a tool is a shell-shaped tool whose risk is governed by its
// command scopes rather than its bare name.
func isShellTool(tool string) bool {
	switch normalizeToken(tool) {
	case "bash", "shell", "exec", "run", "sh":
		return true
	default:
		return false
	}
}

// classifyToolName classifies a NON-shell tool by its name alone (the shell tools are
// scope-governed and handled in riskClass).
func classifyToolName(tool string) RiskLevel {
	name := normalizeToken(tool)
	if isHighRiskToolName(name) {
		return RiskHigh
	}
	switch name {
	case "read", "glob", "grep", "ls", "notebookread", "todoread":
		return RiskLow
	case "write", "edit", "multiedit", "notebookedit", "applypatch", "update":
		return RiskMedium
	default:
		// An UNKNOWN tool is HIGH by default — the advisor may never auto-allow a tool the
		// table has not vetted (the safe wall).
		return RiskHigh
	}
}

// classifyScope classifies one Bash-shaped scope pattern (e.g. "ls *", "go test ./...",
// "rm -rf"). The verb (the first token of the scope) drives the class; an egress/credential/
// destructive verb is HIGH, an in-workspace mutating verb is MEDIUM, a read-only verb is LOW.
// An empty scope is HIGH (an unbounded shell command is not narrowed — the safe default).
func classifyScope(scope string) RiskLevel {
	verb := firstToken(scope)
	if verb == "" {
		return RiskHigh
	}
	if isHighRiskVerb(verb) || isHighRiskToolName(normalizeToken(scope)) {
		return RiskHigh
	}
	switch verb {
	case "ls", "cat", "grep", "find", "pwd", "echo", "head", "tail", "wc", "stat", "which", "test", "true", "diff":
		return RiskLow
	case "git", "go":
		// A read-only git/go subcommand (status/diff/log/show/version/env/list) is LOW; an
		// egress sub-form (push/clone/fetch/pull/get -u/install) is HIGH; everything else
		// in-workspace (add/commit/build/test) is MEDIUM.
		if isReadOnlyVcsForm(scope) {
			return RiskLow
		}
		if isEgressGitForm(scope) {
			return RiskHigh
		}
		return RiskMedium
	case "mkdir", "touch", "mv", "cp", "make", "npm", "yarn", "bun", "node", "python", "gofmt", "gofumpt", "sed", "awk":
		// In-workspace mutating/build verbs are reversible-in-workspace → MEDIUM.
		return RiskMedium
	default:
		// An unrecognized verb is HIGH (the safe default).
		return RiskHigh
	}
}

// isReadOnlyVcsForm reports whether a git/go scope is a read-only inspection subcommand
// (status/diff/log/show/branch/version/env/list) — LOW even though git/go are otherwise
// in-workspace MEDIUM verbs.
func isReadOnlyVcsForm(scope string) bool {
	lowered := strings.ToLower(scope)
	for _, marker := range []string{"git status", "git diff", "git log", "git show", "git branch", "go version", "go env", "go list", "go doc"} {
		if strings.HasPrefix(lowered, marker) {
			return true
		}
	}
	return false
}

// isHighRiskToolName reports whether a tool name is itself a high-risk capability
// (egress/credential/destructive), independent of scopes.
func isHighRiskToolName(name string) bool {
	switch name {
	case "webfetch", "websearch", "fetch", "curl", "wget", "httprequest", "http",
		"networkaccess", "network", "browser",
		"secret", "secrets", "credential", "credentials", "vault", "token",
		"killbash", "kill", "delete", "remove", "destroy":
		return true
	default:
		return false
	}
}

// isHighRiskVerb reports whether a shell verb is destructive/egress/credential/privilege —
// the high-risk wall in scope form.
func isHighRiskVerb(verb string) bool {
	switch verb {
	case "rm", "rmdir", "unlink", "shred", "dd", "mkfs", "format",
		"curl", "wget", "nc", "ncat", "ssh", "scp", "rsync", "ftp", "telnet",
		"sudo", "su", "doas", "chmod", "chown", "chgrp", "kill", "pkill", "killall",
		"vault", "gpg", "openssl", "keychain", "security",
		"eval", "source", "reboot", "shutdown", "halt", "mount", "umount":
		return true
	default:
		return false
	}
}

// isEgressGitForm reports whether a git/go scope is an egress/destructive sub-form
// (push / clone / fetch / pull / reset --hard) that must be HIGH even though the base verb
// (git/go) is otherwise an in-workspace MEDIUM verb.
func isEgressGitForm(scope string) bool {
	lowered := strings.ToLower(scope)
	for _, marker := range []string{"push", "clone", "fetch", "pull", "remote add", "reset --hard", "clean -", "get -u", "install"} {
		if strings.Contains(lowered, marker) {
			return true
		}
	}
	return false
}

// normalizeToken lowercases a token and strips a parenthesized scope suffix and surrounding
// whitespace, so "Bash(go test)" and " bash " both normalize to "bash". It is the pure
// canonicalizer the risk table keys on.
func normalizeToken(token string) string {
	t := strings.ToLower(strings.TrimSpace(token))
	if idx := strings.IndexByte(t, '('); idx >= 0 {
		t = t[:idx]
	}
	return strings.TrimSpace(t)
}

// firstToken returns the first whitespace-delimited token of a scope pattern, lowercased
// (the shell verb). It strips a leading "Bash(" wrapper if a scope was passed wrapped.
func firstToken(scope string) string {
	s := strings.TrimSpace(scope)
	s = strings.TrimPrefix(s, "Bash(")
	s = strings.TrimPrefix(s, "bash(")
	s = strings.TrimSuffix(s, ")")
	fields := strings.Fields(s)
	if len(fields) == 0 {
		return ""
	}
	return strings.ToLower(fields[0])
}

// cloneGrants deep-copies a grant slice so the session's mutable grant set and the
// advisor's AdviceContext copy never share backing arrays with the frozen Spec.Grants.
func cloneGrants(in []ToolGrant) []ToolGrant {
	if len(in) == 0 {
		return nil
	}
	out := make([]ToolGrant, len(in))
	for i := range in {
		out[i] = in[i]
		if in[i].Scopes != nil {
			out[i].Scopes = append([]string(nil), in[i].Scopes...)
		}
	}
	return out
}

// grantCovers reports whether the grant set authorizes tool with the requested scopes. A
// grant with NO scopes covers the whole tool (any scope); a scoped grant covers a request
// only when EVERY requested scope is in the grant's scope set (a partial match still
// escalates). An empty requested-scope set is covered by any grant for the tool.
func grantCovers(grants []ToolGrant, tool string, scopes []string) bool {
	for i := range grants {
		grant := &grants[i]
		if grant.Tool != tool {
			continue
		}
		if len(grant.Scopes) == 0 {
			return true // a whole-tool grant covers any scope
		}
		if len(scopes) == 0 {
			continue // a scoped grant does not cover a bare (no-scope) request
		}
		if scopeSubset(scopes, grant.Scopes) {
			return true
		}
	}
	return false
}

// scopeSubset reports whether every scope in want is present in have.
func scopeSubset(want, have []string) bool {
	for _, w := range want {
		found := false
		for _, h := range have {
			if h == w {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}
	return true
}

// scopesFor extracts the requested sub-scopes from a permission payload. The frozen
// PermissionPayload carries no explicit scope list, so the scope is derived from the tool
// string itself ("Bash(go test)" -> ["go test"]); a bare tool name yields no scopes. This
// keeps the risk class data-derived without widening the frozen event surface.
func scopesFor(payload *PermissionPayload) []string {
	if payload == nil {
		return nil
	}
	return scopesFromTool(payload.Tool)
}

// scopesFromTool pulls a parenthesized scope out of a tool string ("Bash(rm -rf /)" ->
// ["rm -rf /"]); a plain tool name yields nil.
func scopesFromTool(tool string) []string {
	open := strings.IndexByte(tool, '(')
	if open < 0 || !strings.HasSuffix(strings.TrimSpace(tool), ")") {
		return nil
	}
	inner := strings.TrimSpace(tool[open+1 : strings.LastIndexByte(tool, ')')])
	if inner == "" {
		return nil
	}
	return []string{inner}
}

// joinRecent renders the recent-delta ring as a single bounded snippet for the advisor.
func joinRecent(deltas []string) string {
	return strings.Join(deltas, "\n")
}

// securityPosture renders a coarse, loggable label of the session's sandbox/egress stance
// for the advisor's AdviceContext. It is a CLASSIFICATION, never a secret: it reflects only
// whether the session launched with any standing grants and a credential reference.
//
//nolint:gocritic // Spec is the contract's frozen copyable input (§2); this pure label reader takes it by value.
func securityPosture(spec Spec) string {
	if len(spec.Grants) == 0 {
		return "strict-sandbox-no-standing-grants"
	}
	return "sandboxed-with-standing-grants"
}
