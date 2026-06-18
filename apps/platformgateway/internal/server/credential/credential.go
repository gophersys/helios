// Package credential is the ONE home for the gateway's password hashing: the bcrypt digest the password
// authentication provider writes at seed time and checks at login. It is a thin, typed wrapper over
// golang.org/x/crypto/bcrypt so the rest of the gateway never imports bcrypt directly and a hashing
// fault is a typed Eden error, not a bare bcrypt sentinel.
//
// The package name is `credential` (the full HNS-1 word) — not `auth` (banned, rule 11), not `pwd`/
// `hash` (abbreviation/non-concept). It owns exactly the credential digest concept: Hash (digest a
// plaintext) and Verify (constant-time compare a digest against a plaintext). A plaintext password and
// the digest are credential values — neither is ever logged, and a mismatch is a typed
// KindUnauthenticated (→ 401) that never reveals whether it was the digest or the plaintext that did
// not match.
package credential

import (
	"golang.org/x/crypto/bcrypt"

	"github.com/gophersys/libs/go/errors"
)

// Hash digests a plaintext password into a bcrypt hash (the DEFAULT cost — bcrypt.DefaultCost, the
// vetted work factor; not pinned to a weaker value). The composition root calls it once at seed time to
// plant the default user's password account. A bcrypt failure (e.g. a plaintext over bcrypt's 72-byte
// limit) is a typed KindInvalid wrapping the cause; the plaintext is NEVER attached to the error.
func Hash(plaintext string) (string, error) {
	digest, err := bcrypt.GenerateFromPassword([]byte(plaintext), bcrypt.DefaultCost)
	if err != nil {
		return "", errors.Wrap(errors.KindInvalid, "credential: hash password", err)
	}
	return string(digest), nil
}

// Verify reports nil iff plaintext matches the bcrypt hash, using bcrypt's constant-time compare. A
// mismatch (or a malformed hash) is a typed KindUnauthenticated error (→ 401 at the HTTP boundary) — an
// authentication failure, surfaced WITHOUT revealing whether the hash or the plaintext was at fault
// (the login flow must never tell an attacker which of email/password was wrong). Neither the hash nor
// the plaintext is ever attached to the error or logged.
func Verify(hash, plaintext string) error {
	if err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(plaintext)); err != nil {
		return errors.Wrap(errors.KindUnauthenticated, "credential: verify password", err)
	}
	return nil
}
