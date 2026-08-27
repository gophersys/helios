// Package ghadapter is the secrets.Provider that resolves the GitHub Personal Access Token
// (PAT) to a secrets.Secret from the two places a developer / agent pod actually holds it:
// the `gh` CLI's confined keyring (`gh auth token`) and the process environment. It is the
// ONE home for "where does the GitHub PAT come from", so its two consumers — the
// gitrepository git transport (push/fetch credential) and the forge REST API client — depend
// on the SAME secrets.Provider port and never re-derive token discovery.
//
// It translates a secrets.Reference of either canonical form
//
//	gh://token        — shell `gh auth token` and take its stdout as the PAT (the keyring path)
//	env://GITHUB_TOKEN — read the named environment variable as the PAT (the fallback path)
//
// into a resolved *secrets.Secret. It slots behind the EXISTING secrets.Provider port
// (composition root, secrets.md §5) — no contract change — and is wired into a
// secrets.Mediator under the "gh" and "env" schemes. A composition root that wants
// "keyring, else environment" wires both schemes and routes the bare token request through
// whichever Reference it prefers; the adapter itself owns exactly one scheme's resolution per
// Resolve, so the fallback is a routing choice, not a hidden fork in this code.
//
// The secrets no-leak contract is unchanged and load-bearing here because the token transits a
// child process: the adapter mints a genuine, un-printable *secrets.Secret through the
// module-internal minting seam (internal/mint, secrets.md §3), so the resolved value never
// reaches a String()/error/log — only the loggable Reference does. The `gh` child runs under a
// MINIMAL, isolated environment (the gitrepository systemGit precedent, 07 §2): the token
// arrives only on the child's stdout, never on an argv, never in a logged command line, and is
// scrubbed from every error the adapter returns (a `gh` failure surfaces the Reference and the
// bounded, credential-free stderr, never stdout).
package ghadapter
