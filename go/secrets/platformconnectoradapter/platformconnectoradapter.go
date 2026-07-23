// Package platformconnectoradapter is the secrets.Provider that resolves a user/org connector
// credential from the platformgateway `connectors` domain. It is the adapter that lets an agent
// session CONSUME a user-uploaded credential (a Claude API token, a GitHub token, an OpenRouter key)
// through the FROZEN secrets.Provider port — the ADR-0029 §4 / doc 19 §4 follow-on (Brief A3). It
// translates a secrets.Reference of the canonical form
//
//	eden://connector/<id>
//
// into (1) a load of the envelope-sealed row the platformgateway `connectors` domain wrote (through a
// narrow, consumer-defined SealedRowLoader port — the real binding hits the SAME Postgres the connectors
// domain persists to, per ADR-0029 §4), then (2) an envelope.Unseal of that row under the KEK resolved
// through the EXISTING vault:// path, minting the plaintext into a genuine, un-printable
// *secrets.Secret inside the Unseal Use window.
//
// It slots behind the EXISTING secrets.Provider port — NO contract change (ADR-0029 §4) — and is wired
// into a secrets.Mediator under the "eden" scheme, alongside "vault" (adding a Deps.Resolvers key is
// the sanctioned extension). Neither the secrets port nor vaultadapter's .apibaseline changes: this is
// an ADDITIVE package. vault:// is NOT overloaded — a user connector is an envelope-sealed Postgres row
// with an org-authorization check, a distinct concept from a KV-v2 read, so it gets a distinct scheme.
//
// Resolution is a hexagon (the constructor spine): the KEK is resolved and the two AES-256-GCM opens
// run inside libs/go/envelope (the single audited crypto home — this adapter never re-implements the
// cipher, one concept one home); the sealed-row load is the injected SealedRowLoader port. The secrets.Use +
// zeroize + redaction no-leak contract is unchanged: the adapter mints the plaintext through the
// module-internal minting seam (internal/mint, secrets.md §3) INSIDE envelope's Unseal callback, so a
// resolved value never reaches a String()/error/log — only the loggable Reference does.
//
// It is resident IN the secrets module (a sibling of vaultadapter) precisely so it can mint through the
// module-internal seam. It imports envelope (whose module requires secrets), which is a module-require
// cycle but NOT a package cycle — the root secrets package never imports this subpackage — so it builds
// (the envelope contract §1 sanctions "a caller resident in the secrets module can mint through Use").
package platformconnectoradapter

import (
	"context"
	"strings"

	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/internal/mint"
)

// scheme is the Reference scheme this adapter owns at the composition root.
const scheme = "eden"

// resourcePrefix is the connector-resource segment the scheme addresses: the canonical reference is
// "eden://connector/<id>". Only the connector resource is served here; any other "eden://" resource is
// an InvalidReferenceError (this adapter resolves connectors, not an open-ended eden:// namespace).
const resourcePrefix = "connector/"

// errInvalidConfig reports a construction-time wiring mistake (a nil Sealer, a nil Loader). It is a
// sentinel so the composition root can branch via errors.Is; it carries KindInvalid because the
// dependencies are malformed.
var errInvalidConfig = errors.New(errors.KindInvalid, "platformconnectoradapter.New: invalid configuration")

// SealedRecord is the at-rest envelope material the SealedRowLoader loads for a connector id: the SAME
// byte blobs the platformgateway connectors domain wrote (its persistence.SealedMaterial / the
// connector_secrets row) and the KEK generation that wrapped the DEK. It is the loader's return
// shape — a plain value carrying NO plaintext, NO DEK, NO KEK — which the adapter maps 1:1 onto an
// envelope.Sealed for the Unseal. Comparable-free (holds slices); the zero value (empty blobs) is the
// "no such connector" signal the adapter maps to NotFound.
type SealedRecord struct {
	// Ciphertext is AES-256-GCM(DEK, credential) — the sealed credential value.
	Ciphertext []byte
	// WrappedDEK is AES-256-GCM(KEK, DEK) — the data key sealed under the platform-Vault KEK.
	WrappedDEK []byte
	// NonceCiphertext is the 12-byte GCM nonce for Ciphertext.
	NonceCiphertext []byte
	// NonceDEK is the 12-byte GCM nonce for WrappedDEK.
	NonceDEK []byte
	// KEKVersion is the KEK generation that wrapped the DEK (rotation coexistence).
	KEKVersion int
}

// isAbsent reports whether the record is the "no such connector" zero value — an empty ciphertext or
// wrapped DEK means the transport found no sealed row for the id, which the adapter maps to NotFound
// (never a panic into the cipher). A malformed-but-present record (wrong nonce length) is left to
// envelope.Unseal to reject as KindInvalid, so the crypto owns the authenticity verdict (one home).
func (r *SealedRecord) isAbsent() bool {
	return len(r.Ciphertext) == 0 || len(r.WrappedDEK) == 0
}

// SealedRowLoader is the narrow sealed-row load seam the adapter depends on (≤5 methods, 10 §9). It is
// consumer-defined here (the shape of THIS adapter's need — load the sealed material for a connector
// id), NOT a mirror of any persistence SDK, and named for the concept (HNS-1) rather than a transport
// mechanism. The real binding (the composition root's) hits the SAME Postgres the platformgateway
// connectors domain persists to (ADR-0029 §4); a unit test fakes it. The real-substrate proof is the
// //go:build integration lane over a REAL Postgres, never a mock (ADR-0016 §2). It is defined OUTSIDE
// the secrets module's pgx-free foundation on purpose: the real pgx-backed binding lives in the
// consumer, so the secrets module stays free of a database dependency.
type SealedRowLoader interface {
	// LoadSealed loads the envelope-sealed material for the connector named by id. The id is the
	// opaque connector-id string parsed from "eden://connector/<id>". A connector the caller's tenant
	// does not own (or that does not exist) is the zero SealedRecord (the adapter maps it to NotFound)
	// — the org-authorization + tenancy filter is the loader's responsibility (it carries the
	// WHERE organization_id = $caller predicate, ADR-0029 §2.3), so a cross-tenant id never leaks a
	// row. A backing-store fault is returned as an error the adapter maps onto the secrets taxonomy.
	LoadSealed(ctx context.Context, id string) (SealedRecord, error)
}

// Config is the immutable, fully-resolved construction input (the configuration pattern). It carries
// NO key value and NO plaintext — only the loggable KEK reference + version stamp the envelope Sealer
// is built over. New reads it and dials NOTHING; all I/O (KEK resolve, sealed-row load) is lazy, on
// Resolve.
type Config struct {
	// KEK is the loggable secrets.Reference the envelope key-encryption key resolves from (e.g.
	// vault://eden/production#connectors-kek — the SAME reference the platformgateway connectors domain
	// seals under, so a row sealed there unseals here). REQUIRED when Deps.Sealer is nil (New builds the
	// Sealer from it); ignored when Deps.Sealer is supplied. The value never lives here.
	KEK secrets.Reference
	// KEKVersion is the generation stamp the built Sealer records on new Seals. It is unused on the
	// Resolve (Unseal) path — Unseal reads the version FROM the loaded record — but envelope.New
	// requires it (>= 1); it defaults to 1 when unset and Deps.Sealer is nil.
	KEKVersion int
}

// Deps is the injected hexagon: the sealed-row Loader (required) and, optionally, a pre-built
// envelope.Sealer. Accepting interfaces here is the accept-interfaces rule; New returns the concrete
// *Adapter.
type Deps struct {
	// Loader loads the envelope-sealed connector row by id. REQUIRED — there is no default (the real
	// pgx binding lives in the consumer's composition root, so the secrets module stays pgx-free).
	Loader SealedRowLoader

	// Sealer is the envelope port the loaded record is unsealed through. When nil, New builds one from
	// Config.KEK + Config.KEKVersion over Secrets (so a composition root that only has the KEK reference
	// need not construct envelope itself). When non-nil, Config.KEK/KEKVersion are ignored and Secrets
	// is optional — the caller has already wired the KEK seam into the Sealer. Supplying it is the
	// idiom when the same envelope.Sealer is shared with the platformgateway connectors domain.
	Sealer envelope.Sealer

	// Secrets is the redaction port envelope resolves the KEK through, used ONLY when Sealer is nil
	// (New builds the Sealer over it). REQUIRED in that case; ignored when Sealer is supplied.
	Secrets secrets.Provider
}

// Adapter is the concrete secrets.Provider returned by New. It holds the injected sealed-row loader +
// the envelope.Sealer the loaded record is unsealed through. It is stateless per-Resolve (each Resolve
// loads a fresh row and unseals it), so it is safe for concurrent use. Zero value is not usable;
// construct via New.
type Adapter struct {
	loader SealedRowLoader
	sealer envelope.Sealer
}

// New is the constructor spine (10 §9). PURE: no I/O, no env reads, no clock, no database dial, no KEK
// resolve. It validates the dependencies, builds the envelope.Sealer from Config when one was not
// injected (envelope.New is itself pure — the KEK is resolved lazily on Unseal), and returns the
// concrete *Adapter. The KEK resolve + the sealed-row load both happen lazily on Resolve.
func New(configuration Config, dependencies Deps) (*Adapter, error) {
	if dependencies.Loader == nil {
		return nil, errors.Wrap(errors.KindInvalid,
			"platformconnectoradapter.New: Deps.Loader is required (the sealed-row load seam)", errInvalidConfig)
	}

	sealer := dependencies.Sealer
	if sealer == nil {
		if dependencies.Secrets == nil {
			return nil, errors.Wrap(errors.KindInvalid,
				"platformconnectoradapter.New: Deps.Secrets is required when Deps.Sealer is nil (the KEK resolution port)", errInvalidConfig)
		}
		if configuration.KEK.IsZero() {
			return nil, errors.Wrap(errors.KindInvalid,
				"platformconnectoradapter.New: Config.KEK is required when Deps.Sealer is nil (the envelope KEK reference)", errInvalidConfig)
		}
		version := configuration.KEKVersion
		if version < 1 {
			version = 1
		}
		built, err := envelope.New(
			envelope.Config{KEK: configuration.KEK, KEKVersion: version},
			envelope.Deps{Secrets: dependencies.Secrets},
		)
		if err != nil {
			return nil, errors.Wrap(errors.KindInvalid, "platformconnectoradapter.New: build envelope sealer", err)
		}
		sealer = built
	}

	return &Adapter{loader: dependencies.Loader, sealer: sealer}, nil
}

// Resolve implements secrets.Provider: it parses ref into a connector id, loads the envelope-sealed row
// through the SealedRowLoader, and unseals it via envelope — minting an independent, un-printable
// *secrets.Secret from the revealed plaintext INSIDE the Unseal Use window. It returns the secrets
// taxonomy errors (InvalidReferenceError / NotFoundError / DeniedError / UnavailableError) — the
// message carries the Reference, never the value — and never a non-nil Secret with a non-nil error.
func (a *Adapter) Resolve(ctx context.Context, ref secrets.Reference) (*secrets.Secret, error) {
	if ref.IsZero() {
		return nil, secrets.InvalidReferenceError{Ref: ref}
	}
	id, err := parseConnectorID(ref)
	if err != nil {
		return nil, err
	}

	record, err := a.loader.LoadSealed(ctx, id)
	if err != nil {
		return nil, mapLoadError(ref, err)
	}
	if record.isAbsent() {
		return nil, secrets.NotFoundError{Ref: ref}
	}

	// Unseal reveals the plaintext ONLY inside fn; the adapter mints the *secrets.Secret there (the one
	// legitimate window). envelope zeroizes the DEK + the revealed plaintext buffer after fn returns, so
	// nothing survives — and minting COPIES the bytes into a private, un-printable Secret, so the mint
	// does not retain envelope's transient buffer. A tampered/wrong-KEK record fails GCM authentication
	// inside envelope → KindInvalid, which maps to InvalidReferenceError (the row is not one this KEK
	// opens); a KEK-resolution fault carries its own Kind, mapped to the secrets taxonomy.
	var minted *secrets.Secret
	unsealErr := a.sealer.Unseal(ctx, toSealed(&record), func(plaintext []byte) error {
		minted = mintSecret(plaintext)
		return nil
	})
	if unsealErr != nil {
		return nil, mapUnsealError(ref, unsealErr)
	}
	return minted, nil
}

// toSealed maps the transport's SealedRecord onto the envelope.Sealed the Unseal takes. It is the ONE
// seam between the adapter's transport shape and the crypto lib's value type (one concept, one home).
// The record is taken by pointer (a heavy multi-slice value never copied at the call site).
func toSealed(record *SealedRecord) envelope.Sealed {
	return envelope.Sealed{
		Ciphertext:      record.Ciphertext,
		WrappedDEK:      record.WrappedDEK,
		NonceCiphertext: record.NonceCiphertext,
		NonceDEK:        record.NonceDEK,
		KEKVersion:      record.KEKVersion,
	}
}

// parseConnectorID splits an "eden://connector/<id>" Reference into its connector id. A malformed
// reference (wrong scheme, missing "connector/" resource, empty id) yields a typed
// secrets.InvalidReferenceError carrying the Reference, never a fabricated value.
func parseConnectorID(ref secrets.Reference) (string, error) {
	raw := ref.String()
	const schemePrefix = scheme + "://"
	if !strings.HasPrefix(raw, schemePrefix) {
		return "", secrets.InvalidReferenceError{Ref: ref}
	}
	rest := strings.TrimPrefix(raw, schemePrefix)
	if !strings.HasPrefix(rest, resourcePrefix) {
		return "", secrets.InvalidReferenceError{Ref: ref}
	}
	id := strings.TrimPrefix(rest, resourcePrefix)
	// The id must be a single non-empty segment (no further "/" path, no "#" fragment — a connector is
	// addressed by id alone, unlike a vault:// path#key).
	if id == "" || strings.ContainsAny(id, "/#") {
		return "", secrets.InvalidReferenceError{Ref: ref}
	}
	return id, nil
}

// mintSecret builds a genuine, un-printable *secrets.Secret from value through the module-internal
// minting seam (secrets.md §3 — the adapter is a sanctioned producer). The comma-ok guard turns an
// impossible registration mismatch into a clear panic, not a silent miscast.
func mintSecret(value []byte) *secrets.Secret {
	sec, ok := mint.Hook()(value).(*secrets.Secret)
	if !ok {
		panic("platformconnectoradapter: minting hook returned a non-*secrets.Secret value")
	}
	return sec
}

// compile-time: *Adapter is a secrets.Provider.
var _ secrets.Provider = (*Adapter)(nil)
