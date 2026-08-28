// Package envelope is the Eden envelope-encryption primitive: it seals a plaintext secret under a
// fresh per-secret data-encryption key (DEK), wraps that DEK under an external key-encryption key
// (KEK), and reverses the two steps to reveal the plaintext ONLY inside a caller-supplied Use
// window. Both layers are AES-256-GCM (a NIST-standard AEAD) with a fresh random nonce per
// operation. The KEK is never held by this library — it is resolved on demand through the injected
// secrets.Provider + secrets.Reference (the frozen redaction seam), so the KEK plaintext lives only
// inside a secrets.Secret.Use window and is zeroized after each Seal/Unseal.
//
// It is a LEAF library (contract: docs/architecture/contracts/envelope.md, ADR-0029): it imports
// only crypto/*, the standard library, and the two foundation libs errors + secrets. It stores
// nothing (the Sealed record is a value the caller persists — the platformgateway `connectors`
// domain owns the row) and it mints no *secrets.Secret (that is the secrets module's exclusive
// right through its internal minting seam — Unseal reveals the plaintext inside a Use callback,
// mirroring secrets.Secret.Use, so a caller resident in the secrets module can mint through Use,
// but envelope never produces a Secret itself).
package envelope

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// keyLength is the AES-256 key size in bytes: both the DEK and the KEK are 32-byte keys. A KEK of a
// different length is a wiring fault the caller's Vault seed must not produce; Seal/Unseal reject it
// as KindInvalid rather than silently truncating.
const keyLength = 32

// nonceLength is the AES-GCM standard nonce size in bytes (96 bits). A fresh random nonce is drawn
// per Seal for both the ciphertext AEAD and the wrapped-DEK AEAD; a nonce reuse under one key is the
// one catastrophic GCM misuse, which per-call random nonces preclude.
const nonceLength = 12

// fingerprintHexLength is the number of hex characters a Fingerprint renders: 16 hex chars = 8 bytes
// = 64 bits of a SHA-256 digest — enough to distinguish credentials for change-detection without
// storing the full digest (the display is a short, one-way hint, never the value).
const fingerprintHexLength = 16

// Sealer is the port a caller depends on to seal and unseal secret material. It is the ONLY port a
// consumer holds; the composition root binds the concrete *Envelope. At most three methods (the
// interface-design 5-method ceiling); safe for concurrent use.
type Sealer interface {
	// Seal encrypts plaintext under a fresh per-call DEK, wraps the DEK under the KEK resolved from
	// the configured Reference, and returns the Sealed record the caller persists. It never returns
	// the DEK, the KEK, or the plaintext; plaintext is read-only and not retained.
	Seal(ctx context.Context, plaintext []byte) (Sealed, error)
	// Unseal decrypts a Sealed record and hands the plaintext to fn for the DURATION of the call
	// only. The slice passed to fn is valid only inside fn and MUST NOT be retained — this mirrors
	// secrets.Secret.Use so the plaintext never escapes as a return value. Unseal returns fn's
	// error, or a typed decrypt/KEK error.
	Unseal(ctx context.Context, sealed Sealed, fn func(plaintext []byte) error) error
}

// Sealed is the at-rest record: the ciphertext, the wrapped DEK, the two nonces, and the KEK
// generation that wrapped the DEK. It carries NO plaintext, NO DEK, NO KEK — it is safe to persist.
// The byte blobs are opaque AEAD output (no plaintext in the clear). The zero value is the invalid
// record Unseal rejects (empty blobs fail the length checks).
type Sealed struct {
	// Ciphertext is AES-256-GCM(DEK, plaintext) — the sealed credential.
	Ciphertext []byte
	// WrappedDEK is AES-256-GCM(KEK, DEK) — the DEK sealed under the KEK.
	WrappedDEK []byte
	// NonceCiphertext is the 12-byte GCM nonce used for Ciphertext.
	NonceCiphertext []byte
	// NonceDEK is the 12-byte GCM nonce used for WrappedDEK.
	NonceDEK []byte
	// KEKVersion is the KEK generation that wrapped the DEK (rotation coexistence — the caller's
	// re-wrap pass reads this to know which KEK opens the record).
	KEKVersion int
}

// isZero reports whether s is the unusable zero/short record — any missing blob or a wrong-length
// nonce means there is nothing this KEK could open, so Unseal fails fast with KindInvalid rather
// than handing malformed input to the cipher. Pointer receiver: Sealed is a heavy record (four
// slices), so it is inspected by reference, never copied.
func (s *Sealed) isZero() bool {
	return len(s.Ciphertext) == 0 || len(s.WrappedDEK) == 0 ||
		len(s.NonceCiphertext) != nonceLength || len(s.NonceDEK) != nonceLength
}

// Config is the immutable, fully-resolved input: the KEK reference and the version stamp new Seals
// record. It holds NO key value — only the loggable secrets.Reference.
type Config struct {
	// KEK is the loggable secrets.Reference the key-encryption key resolves from (e.g.
	// vault://eden/production#connectors-kek). REQUIRED; the value never lives here.
	KEK secrets.Reference
	// KEKVersion is the generation stamp Seal records on every new Sealed. REQUIRED (>= 1).
	KEKVersion int
}

// Deps is the injected hexagon: the secrets port the KEK is resolved through. New consumes ports; it
// constructs none.
type Deps struct {
	// Secrets is the redaction port the KEK is resolved through at Seal/Unseal time. The KEK value is
	// read inside a Use window and zeroized after each operation. REQUIRED.
	Secrets secrets.Provider
}

// Envelope is the concrete Sealer New returns (return-concrete). It holds only immutable
// configuration + the injected secrets port, so it is safe for concurrent use — each Seal/Unseal
// resolves the KEK freshly and holds no per-operation state on the struct. The zero value is
// unusable; construct via New.
type Envelope struct {
	kekReference secrets.Reference
	kekVersion   int
	secrets      secrets.Provider
}

// New is the constructor spine (10 §9). PURE: no I/O, no clock, no env — it validates configuration
// and wires the injected secrets.Provider + KEK Reference, and returns the concrete *Envelope. The
// KEK is NOT resolved here (that is per-operation, so a rotated KEK is picked up without a
// reconstruct); New only checks the wiring is well-formed.
func New(configuration Config, dependencies Deps) (*Envelope, error) {
	if dependencies.Secrets == nil {
		return nil, invalidConfig("New requires Deps.Secrets (a secrets.Provider)")
	}
	if configuration.KEK.IsZero() {
		return nil, invalidConfig("New requires Config.KEK (a secrets.Reference)")
	}
	if configuration.KEKVersion < 1 {
		return nil, invalidConfig("New requires Config.KEKVersion >= 1")
	}
	return &Envelope{
		kekReference: configuration.KEK,
		kekVersion:   configuration.KEKVersion,
		secrets:      dependencies.Secrets,
	}, nil
}

// Seal implements Sealer. It mints a fresh 32-byte DEK, encrypts plaintext under it (AES-256-GCM,
// random nonce), resolves the KEK, wraps the DEK under it (AES-256-GCM, a second random nonce), and
// returns the Sealed record stamped with the configured KEKVersion. The DEK is zeroized before
// return; the KEK Secret is zeroized by the defer. plaintext is read-only and never retained.
func (e *Envelope) Seal(ctx context.Context, plaintext []byte) (Sealed, error) {
	dek := make([]byte, keyLength)
	if _, err := rand.Read(dek); err != nil {
		return Sealed{}, invalidConfig("Seal: generate DEK: " + err.Error())
	}
	defer zeroize(dek)

	ciphertext, nonceCiphertext, err := aeadSeal(dek, plaintext)
	if err != nil {
		return Sealed{}, err
	}

	wrappedDEK, nonceDEK, err := e.sealDEKUnderKEK(ctx, dek)
	if err != nil {
		return Sealed{}, err
	}

	return Sealed{
		Ciphertext:      ciphertext,
		WrappedDEK:      wrappedDEK,
		NonceCiphertext: nonceCiphertext,
		NonceDEK:        nonceDEK,
		KEKVersion:      e.kekVersion,
	}, nil
}

// Unseal implements Sealer. It resolves the KEK, opens the wrapped DEK under it, opens the ciphertext
// under the recovered DEK, and hands the plaintext to fn for the duration of the call only. The DEK
// and the recovered plaintext are zeroized after fn returns, so nothing survives the window. A
// tampered blob or a wrong KEK fails GCM authentication → KindInvalid (never a plaintext in the
// error). fn's error is returned unchanged so the caller can branch on its Kind.
//
// caller hands over the record it loaded from the row); the frozen Sealer contract passes it by value.
//
//nolint:gocritic // hugeParam: sealed is the by-value at-rest record the port takes by design (the
func (e *Envelope) Unseal(ctx context.Context, sealed Sealed, fn func(plaintext []byte) error) error {
	if sealed.isZero() {
		return invalidSealed("Unseal: malformed Sealed record (empty blob or wrong-length nonce)")
	}

	dek, err := e.openDEKUnderKEK(ctx, &sealed)
	if err != nil {
		return err
	}
	defer zeroize(dek)

	plaintext, err := aeadOpen(dek, sealed.NonceCiphertext, sealed.Ciphertext)
	if err != nil {
		return err
	}
	defer zeroize(plaintext)

	//nolint:wrapcheck // fn's error is the CALLER's own; Unseal is a pass-through (contract §3) so
	// the caller can branch on its Kind — wrapping would bury the caller's classification.
	return fn(plaintext)
}

// sealDEKUnderKEK resolves the KEK and wraps dek under it. The KEK value lives only inside the Use
// window (secrets.Use1) and is zeroized by the Secret's defer, so the KEK never reaches a variable
// that outlives the call. The loggable KEK Reference rides any error; the KEK value never does.
func (e *Envelope) sealDEKUnderKEK(ctx context.Context, dek []byte) (wrapped, nonce []byte, err error) {
	secret, err := e.secrets.Resolve(ctx, e.kekReference)
	if err != nil {
		return nil, nil, wrapKEK(e.kekReference, err)
	}
	defer secret.Zeroize()

	type wrappedResult struct {
		wrapped []byte
		nonce   []byte
	}
	result, err := secrets.Use1(secret, func(kek []byte) (wrappedResult, error) {
		if len(kek) != keyLength {
			return wrappedResult{}, invalidConfig("Seal: KEK is not a 32-byte AES-256 key")
		}
		w, n, aerr := aeadSeal(kek, dek)
		if aerr != nil {
			return wrappedResult{}, aerr
		}
		return wrappedResult{wrapped: w, nonce: n}, nil
	})
	if err != nil {
		// Preserve the Kind across the secrets.Use1 boundary (the wrap adds stage context).
		return nil, nil, errors.Wrap(errors.KindOf(err), "envelope: wrap DEK under KEK", err)
	}
	return result.wrapped, result.nonce, nil
}

// openDEKUnderKEK resolves the KEK and opens the wrapped DEK under it, returning a fresh DEK the
// caller owns and must zeroize. The KEK value lives only inside the Use window. A GCM authentication
// failure (wrong KEK / tampered wrapped DEK) is KindInvalid — the record is not one this KEK opens.
// sealed is taken by pointer (the heavy at-rest record is never copied at a call site).
func (e *Envelope) openDEKUnderKEK(ctx context.Context, sealed *Sealed) ([]byte, error) {
	secret, err := e.secrets.Resolve(ctx, e.kekReference)
	if err != nil {
		return nil, wrapKEK(e.kekReference, err)
	}
	defer secret.Zeroize()

	dek, err := secrets.Use1(secret, func(kek []byte) ([]byte, error) {
		if len(kek) != keyLength {
			return nil, invalidConfig("Unseal: KEK is not a 32-byte AES-256 key")
		}
		return aeadOpen(kek, sealed.NonceDEK, sealed.WrappedDEK)
	})
	if err != nil {
		// Preserve the Kind (KindInvalid from aeadOpen / invalidConfig) across the secrets.Use1
		// boundary so the caller still branches on it; the wrap adds the stage context.
		return nil, errors.Wrap(errors.KindOf(err), "envelope: open wrapped DEK", err)
	}
	return dek, nil
}

// aeadSeal encrypts plaintext under key with AES-256-GCM and a fresh random nonce, returning the
// ciphertext and the nonce. key MUST be 32 bytes (the callers guard it). A crypto/rand failure or a
// cipher-construction failure is KindInvalid — an environment fault the caller surfaces, never masks.
func aeadSeal(key, plaintext []byte) (ciphertext, nonce []byte, err error) {
	gcm, err := newGCM(key)
	if err != nil {
		return nil, nil, err
	}
	nonce = make([]byte, nonceLength)
	if _, rerr := rand.Read(nonce); rerr != nil {
		return nil, nil, invalidConfig("seal: generate nonce: " + rerr.Error())
	}
	// #nosec G407 -- the nonce is CRYPTOGRAPHICALLY RANDOM (crypto/rand.Read above), not hardcoded;
	// gosec's flow analysis cannot track the rand.Read mutation into the same slice, a known G407
	// false positive. A fresh random nonce per Seal is exactly the GCM misuse-resistance requirement.
	ciphertext = gcm.Seal(nil, nonce, plaintext, nil)
	return ciphertext, nonce, nil
}

// aeadOpen decrypts ciphertext under key with AES-256-GCM and nonce, returning the plaintext. A GCM
// open failure (tampered ciphertext, wrong key, wrong nonce) is the authenticated-decryption
// rejection — KindInvalid, carrying no byte content (the failed plaintext does not exist).
func aeadOpen(key, nonce, ciphertext []byte) ([]byte, error) {
	gcm, err := newGCM(key)
	if err != nil {
		return nil, err
	}
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return nil, invalidSealed("open: authenticated decryption failed (tampered ciphertext or wrong key)")
	}
	return plaintext, nil
}

// newGCM builds the AES-256-GCM AEAD for key. key MUST be 32 bytes; a wrong length is a caller-guarded
// invariant, but aes.NewCipher enforces it too, so a slipped-through bad length is KindInvalid, not a
// panic. This is the ONE place the AEAD is constructed (one concept, one home).
func newGCM(key []byte) (cipher.AEAD, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, invalidConfig("cipher: construct AES block: " + err.Error())
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, invalidConfig("cipher: construct GCM: " + err.Error())
	}
	return gcm, nil
}

// Fingerprint is a one-way, truncated SHA-256 digest of plaintext, safe to store and display (the
// write-only UI's change-detection hint). It is NOT reversible and reveals nothing about the value
// beyond equality — the same class as a password hash. PURE: no I/O, no state. An empty plaintext
// fingerprints to the empty string (there is nothing to hint at), so a caller never displays a
// digest of "nothing".
func Fingerprint(plaintext []byte) string {
	if len(plaintext) == 0 {
		return ""
	}
	digest := sha256.Sum256(plaintext)
	return hex.EncodeToString(digest[:])[:fingerprintHexLength]
}

// zeroize best-effort wipes a byte slice. The DEK and the recovered plaintext pass through it before
// they leave scope, so a secret byte does not linger in a freed buffer (10 §4 discipline, applied to
// the transient key material envelope handles directly).
func zeroize(buffer []byte) {
	for i := range buffer {
		buffer[i] = 0
	}
}

// compile-time assertion: *Envelope is a Sealer (the port consumers hold).
var _ Sealer = (*Envelope)(nil)
