# Contract — objectstorage

> Status: Frozen (ADR-0016) · 2026-06-14 · Reconciled from independent producer/consumer drafts
> (09 §4) and frozen with the library built: the exported surface is mechanically recorded at
> `libs/go/objectstorage/.apibaseline` (the freeze made mechanical, ADR-0020) and the ADR-0020
> 8-dimension test taxonomy is green. This is a **10 §4 library pattern** (the object-store port;
> a substrate adapter over MinIO/S3). A breaking change to the surface requires a contract
> revision (ADR-0016 §1) + re-recording the `.apibaseline` — the cardinal sin otherwise (10 §9).

## 1. Scope

`objectstorage` is the port that puts, gets, deletes, presigns, and lists blobs in an
S3-compatible object store **by reference**. The consumer depends on ONE narrow port —
`ObjectStore`, exactly five methods (`Put`, `Get`, `Delete`, `Presign`, `List`) at the 5-method
ceiling (10 §9) — and never on a vendor SDK. The SDK (`github.com/minio/minio-go/v7`) is imported
in EXACTLY ONE place, the `minioadapter` sub-package (05 §1); the root package is SDK-free.

The credential discipline is the secrets contract reused, not re-invented: the access-key and
secret-key are `secrets.Reference` values that live in `configuration` and are resolved through an
already-wired `secrets.Provider` at the composition root (10 §2). A raw secret value never enters
the root port, never enters a `Config`, and never reaches a loggable surface — the adapter resolves
the credential through `secrets.Use`, hands the bytes to the SDK inside one call frame, and the
resolved `*secrets.Secret` is zeroized. Every surfaced artifact — error, `ObjectInfo`, presigned
URL host, log — is credential-free by construction (the redaction half of the errors contract).

It does **not** provide: bucket lifecycle (create/delete bucket), policy/ACL management,
multipart-upload orchestration, server-side-encryption key management, or versioning — those are
operator/adapter concerns off the consumer port. It does **not** read the environment, the clock,
or a global; everything arrives through `Config` or `Deps` (the pure `New(configuration,
dependencies)` spine, 10 §4).

## 2. Contract

```go
// Package objectstorage is the port for blob storage in an S3-compatible object store: Put,
// Get, Delete, Presign, and List an object by reference. The consumer depends only on the
// five-method ObjectStore port; the vendor SDK is isolated in minioadapter. Credentials are
// secrets.Reference values resolved at the composition root, never inline — so no surfaced
// artifact carries a credential.
package objectstorage

// ObjectRef names one object: a bucket plus a key. It is loggable (it carries no credential and
// no payload) and comparable (usable as a map key). The zero value is invalid; NewRef / ParseRef
// validate the shape.
type ObjectRef struct{ /* unexported: bucket, key */ }

// NewRef constructs a validated ObjectRef. Pure; no I/O. A blank bucket/key or a key with a
// leading slash or a ".."/"." path element is rejected with an InvalidError.
func NewRef(bucket, key string) (ObjectRef, error)

// The five-method ObjectStore port (the load-bearing surface; consumer-defined, ≤5 methods).
type ObjectStore interface {
	Put(ctx context.Context, ref ObjectRef, body io.Reader, options PutOptions) (ObjectInfo, error)
	Get(ctx context.Context, ref ObjectRef) (io.ReadCloser, ObjectInfo, error)
	Delete(ctx context.Context, ref ObjectRef) error
	Presign(ctx context.Context, ref ObjectRef, options PresignOptions) (*url.URL, error)
	List(ctx context.Context, bucket, prefix string) ([]ObjectInfo, error)
}

// New is the constructor spine. PURE: no I/O, no env/clock reads, no daemon dial. It validates
// the configuration + dependencies and returns the concrete *Store, which delegates to the
// injected Backend. The first network call is the first ObjectStore method.
func New(configuration Config, dependencies Deps) (*Store, error)
```

The typed error taxonomy is a set of distinct types — `InvalidError`, `NotFoundError`,
`DeniedError`, `UnavailableError` — each carrying the offending `ObjectRef` (never a payload, never
a credential), inspectable via `errors.AsType[…]` and classified by a stable `errors.Kind`
(`KindInvalid` / `KindNotFound` / `KindPermission` / `KindUnavailable`). The adapter maps an S3
status (400/403/404/5xx, connection-refused, deadline) onto the taxonomy; callers branch on type,
never on a message substring (the errors contract).

## 3. The Backend seam (adapter contract)

`Backend` is the narrow port (≤5 methods) the root `*Store` delegates to and `minioadapter`
implements over the real SDK. A test substitutes an in-memory fake `Backend` to exercise the
store's mapping logic without a daemon; the REAL-MinIO proof is the `//go:build integration` lane
(ADR-0016 §2 — never a mock). `minioadapter.New(Config, Deps)` resolves the access-key/secret-key
`secrets.Reference` pair through the injected `secrets.Provider`, builds the `*minio.Client` once,
and is the ONLY compilation unit that imports the SDK.

## 4. Conformance

`objectstoragetest.RunStoreSuite` is the exported two-binding conformance suite (08 §2): it runs
the SAME property set over the in-memory fake AND, in the integration lane, the real MinIO-backed
`*Store` — round-trip byte-for-byte, typed NotFound on an absent object, Invalid on a malformed
ref, list-by-prefix, presign produces a credential-free URL, and no surfaced artifact carries the
seeded credential canary. The fake weakens the SOURCE of bytes, never the contract.
