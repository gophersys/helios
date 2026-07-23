# Contract — envelope

> Status: Frozen (ADR-0016) · 2026-07-20 · Frozen with the library built: the exported surface is
> mechanically recorded at `libs/go/envelope/.apibaseline` (the freeze made mechanical, ADR-0020) and
> the ADR-0020 8-dimension test taxonomy is green. This is a **10 §4 leaf library pattern** — the
> AES-256-GCM **envelope-encryption** primitive (per-secret DEK, external KEK): the crypto model that
> lets Eden store a retrievable user credential encrypted at rest without ever holding the plaintext
> in a database or in git. The RULING (why envelope-in-Postgres over Vaultwarden-per-tenant, why this
> is a distinct leaf and not a `secrets` change) is [ADR-0029](../adr/0029-user-connectors-and-secret-material.md)
> and the canonical spec [19](../19-connectors-and-user-secrets.md) — this contract cites them, never
> re-decides them. A breaking change to the surface requires a contract revision (ADR-0016 §1) +
> re-recording the `.apibaseline` — the cardinal sin otherwise (10 §9).

## 1. Scope

`envelope` is the **envelope-encryption** primitive: it seals a plaintext secret under a fresh
per-secret data-encryption key (DEK), then wraps that DEK under an external key-encryption key (KEK),
and reverses the two steps to reveal the plaintext ONLY inside a caller-supplied `Use` window. Both
layers are AES-256-GCM (a NIST-standard AEAD) with a fresh random nonce per operation. The KEK is
never held by this library — it is resolved on demand through the injected `secrets.Provider` +
`secrets.Reference` (the frozen redaction seam), so the KEK's plaintext lives only inside a
`secrets.Secret.Use` window and is zeroized after each Seal/Unseal.

It is a **leaf** library — it imports only the standard library, `crypto/*`, and the two foundation
libs `errors` (typed errors) and `secrets` (the KEK arrives as a `secrets.Reference`, resolved
through `secrets.Provider`). It never imports `observability`, a persistence layer, or any transport
package.

It explicitly does **not**: store anything (the sealed material is a value the caller persists — the
`connectors` domain in `platformgateway` owns the row); mint a `*secrets.Secret` (that is the
`secrets` module's exclusive right through its internal minting seam — `Unseal` reveals the plaintext
inside a `Use` callback so a caller resident in the `secrets` module can mint through `Use`, but
`envelope` never produces a `Secret` itself); rotate the KEK autonomously (`kek_version` on the
`Sealed` record makes two KEK generations coexist during a re-wrap pass the caller drives); or choose
the cipher by configuration (AES-256-GCM is the single hard-wired AEAD — one algorithm, one home).

## 2. Contract

```go
// Package envelope is the Eden envelope-encryption primitive: seal a plaintext under a
// fresh per-secret data key (DEK), wrap the DEK under an external key-encryption key
// (KEK) resolved through the frozen secrets.Provider seam, and reverse both steps to
// reveal the plaintext only inside a Use window. Both layers are AES-256-GCM. It is a
// leaf library: crypto/* + the standard library + errors + secrets, nothing else. It
// stores nothing and mints no secrets.Secret (that is the secrets module's right).
package envelope

// Sealer is the port a caller depends on to seal and unseal secret material. It is the
// ONLY port a consumer holds; the composition root binds the concrete *Envelope.
// At most 3 methods (interface-design rule, <=5). Safe for concurrent use.
type Sealer interface {
    // Seal encrypts plaintext under a fresh per-call DEK, wraps the DEK under the KEK
    // resolved from the configured Reference, and returns the Sealed record the caller
    // persists. It never returns the DEK, the KEK, or the plaintext. plaintext is
    // read-only and not retained.
    Seal(ctx context.Context, plaintext []byte) (Sealed, error)
    // Unseal decrypts a Sealed record and hands the plaintext to fn for the DURATION of
    // the call only. The slice passed to fn is valid only inside fn and MUST NOT be
    // retained — this mirrors secrets.Secret.Use so the plaintext never escapes as a
    // return value. Unseal returns fn's error, or a typed decrypt/kek error.
    Unseal(ctx context.Context, sealed Sealed, fn func(plaintext []byte) error) error
}

// Sealed is the at-rest record: the ciphertext, the wrapped DEK, the two nonces, and the
// KEK generation that wrapped the DEK. It carries NO plaintext, NO DEK, NO KEK — it is
// safe to persist and (except the byte blobs, which are opaque) to log. Comparable-free
// (holds slices); the zero value is the invalid record Unseal rejects.
type Sealed struct {
    Ciphertext      []byte // AES-256-GCM(DEK, plaintext)
    WrappedDEK      []byte // AES-256-GCM(KEK, DEK)
    NonceCiphertext []byte // 12-byte GCM nonce for Ciphertext
    NonceDEK        []byte // 12-byte GCM nonce for WrappedDEK
    KEKVersion      int    // the KEK generation that wrapped the DEK (rotation coexistence)
}

// Fingerprint is a one-way, truncated SHA-256 digest of a plaintext, safe to store and
// display (the write-only UI's change-detection hint). It is NOT reversible and reveals
// nothing about the value beyond equality — the same class as a password hash. Pure.
func Fingerprint(plaintext []byte) string

// New is the constructor spine. PURE: no I/O, no clock, no env. It validates configuration
// and wires the injected secrets.Provider + KEK Reference. Returns the concrete *Envelope.
func New(configuration Config, dependencies Deps) (*Envelope, error)

// Config is the immutable, fully-resolved input: the KEK reference and the version stamp
// new Seals record.
type Config struct {
    // KEK is the loggable secrets.Reference the key-encryption key resolves from (e.g.
    // vault://eden/production#connectors-kek). REQUIRED; the value never lives here.
    KEK secrets.Reference
    // KEKVersion is the generation stamp Seal records on every new Sealed. REQUIRED (>=1).
    KEKVersion int
}

// Deps is the injected hexagon: the secrets port the KEK is resolved through.
type Deps struct {
    // Secrets is the redaction port the KEK is resolved through at Seal/Unseal time. The
    // KEK value is read inside a Use window and zeroized after each operation. REQUIRED.
    Secrets secrets.Provider
}
```

## 3. Errors

Every fault is a typed `*errors.Error` (the errors contract), inspectable by `Kind`, carrying the
KEK `Reference` (loggable) but NEVER a plaintext, DEK, or KEK value:

| Condition | Kind |
|---|---|
| `New` with a zero KEK reference / `KEKVersion < 1` / nil `Secrets` | `KindInvalid` |
| KEK resolution fails (secrets port error) | wrapped, Kind preserved from the port |
| `Unseal` on a zero/short/malformed `Sealed` (bad nonce/DEK length, wrong version with no key) | `KindInvalid` |
| GCM open fails (tampered ciphertext, wrong KEK) | `KindInvalid` (authentication failure) |
| `fn` returns an error inside `Unseal` | that error, unwrapped-Kind-preserving |

## 4. The no-leak invariant

The **SeededCanary** property (rule 21 §f) is the mechanical proof: a seeded needle plaintext, once
sealed, must appear in NO surfaced artifact — not in the `Sealed` byte blobs as plaintext, not in any
error string, not in a `Fingerprint`, not in a log line. `Seal`→`Unseal` is the identity for arbitrary
plaintext (the round-trip property, rule 21 §a); tampering with any `Sealed` field fails `Unseal` with
`KindInvalid` (GCM authenticity). The KEK never rides an error (only its loggable `Reference` does).

## 5. Rotation (caller-driven, not autonomous)

`KEKVersion` on every `Sealed` records which KEK generation wrapped the DEK. A KEK rotation is a
caller-driven re-wrap pass: for each stored `Sealed`, `Unseal` the DEK under the old KEK and `Seal`
a fresh record under the new KEK — the ciphertext/DEK never change wholesale, only the small wrapped
DEK, so no plaintext is ever re-handled at scale. `envelope` provides the primitives; the schedule
and the two-generation coexistence window are the caller's (ADR-0029 §rotation).
