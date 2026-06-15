// Package objectstorage is the port for blob storage in an S3-compatible object store: Put,
// Get, Delete, Presign, and List an object by reference. The consumer depends only on the
// five-method ObjectStore port (the load-bearing surface, at the 5-method ceiling — 10 §9);
// the vendor SDK lives in EXACTLY ONE place, the minioadapter sub-package (05 §1), so the root
// package is SDK-free.
//
// Credentials are secrets.Reference values that live in configuration and are resolved through
// an already-wired secrets.Provider at the composition root (10 §2). A raw secret value never
// enters the root port, never enters a Config, and never reaches a loggable surface: every
// surfaced artifact — error, ObjectInfo, presigned-URL host, log — is credential-free by
// construction (the redaction half of the errors contract).
//
// Module: github.com/gophersys/libs/go/objectstorage
//
// Concurrency: ObjectRef / ObjectInfo / PutOptions / PresignOptions are immutable values, safe
// to share. A *Store is safe for concurrent use by multiple goroutines iff its injected Backend
// is (the real minioadapter Backend is). Zero value: a Store is not usable; construct via New.
package objectstorage

import (
	"context"
	"io"
	"net/url"
	"strings"
	"time"

	"github.com/gophersys/libs/go/errors"
)

// keySeparator is the canonical object-key path separator, mirroring S3 key semantics.
const keySeparator = "/"

// ObjectRef names exactly one object: a bucket plus a key. It is loggable (it carries no
// credential and no payload) and comparable (usable as a map key for routing and dependency
// records). The zero value is invalid, which NewRef / ParseRef and every ObjectStore method
// reject. The unexported fields make every ObjectRef pass through a validating constructor, so
// the struct stays comparable and shape-checked without an addressable field.
type ObjectRef struct {
	bucket string
	key    string
}

// NewRef validates and constructs an ObjectRef. PURE: no I/O. A blank bucket or key, a key with
// a leading slash, or a key containing a "."/".." path element (a traversal attempt) is rejected
// with a wrapped error inspectable via errors.AsType[InvalidError]. The bucket must be a
// non-empty token with no slash; the key is a non-empty, non-traversing S3 key.
func NewRef(bucket, key string) (ObjectRef, error) {
	if !validBucket(bucket) {
		return ObjectRef{}, InvalidError{Ref: ObjectRef{bucket: bucket, key: key}, Reason: "bucket"}
	}
	if !validKey(key) {
		return ObjectRef{}, InvalidError{Ref: ObjectRef{bucket: bucket, key: key}, Reason: "key"}
	}
	return ObjectRef{bucket: bucket, key: key}, nil
}

// ParseRef constructs an ObjectRef from its canonical "<bucket>/<key>" string form (the form
// String returns). PURE; no I/O. The first path segment is the bucket; the remainder is the key.
// Returns a wrapped InvalidError for a malformed input.
func ParseRef(s string) (ObjectRef, error) {
	i := strings.Index(s, keySeparator)
	if i <= 0 || i == len(s)-1 {
		return ObjectRef{}, InvalidError{Ref: ObjectRef{}, Reason: "shape"}
	}
	return NewRef(s[:i], s[i+1:])
}

// Bucket returns the object's bucket.
func (r ObjectRef) Bucket() string { return r.bucket }

// Key returns the object's key (the path within the bucket).
func (r ObjectRef) Key() string { return r.key }

// String returns the canonical "<bucket>/<key>" form. An ObjectRef is loggable by design.
func (r ObjectRef) String() string {
	if r.IsZero() {
		return ""
	}
	return r.bucket + keySeparator + r.key
}

// IsZero reports whether r is the invalid zero ObjectRef.
func (r ObjectRef) IsZero() bool { return r.bucket == "" && r.key == "" }

// validBucket reports whether bucket is a usable S3 bucket token: non-empty, no slash, no
// whitespace. The strict S3 bucket-naming rules (length, dots, case) are the operator's concern
// at provisioning; this is the shape gate the port enforces so a malformed ref fails fast.
func validBucket(bucket string) bool {
	if bucket == "" || strings.ContainsAny(bucket, "/ \t\n\r") {
		return false
	}
	return true
}

// validKey reports whether key is a usable, non-traversing object key: non-empty, no leading
// slash, no whitespace, and no "."/".." path element (a path-traversal attempt that must never
// reach the backend).
func validKey(key string) bool {
	if key == "" || strings.HasPrefix(key, keySeparator) {
		return false
	}
	if strings.ContainsAny(key, " \t\n\r") {
		return false
	}
	for _, element := range strings.Split(key, keySeparator) {
		if element == "" || element == "." || element == ".." {
			return false
		}
	}
	return true
}

// ObjectInfo is the loggable metadata of a stored object: its reference, byte size, content type,
// strong entity tag, and last-modified time. It carries NO payload and NO credential, so it is
// safe to log, telemeter, and persist.
type ObjectInfo struct {
	// Ref is the object this metadata describes.
	Ref ObjectRef
	// Size is the object's length in bytes.
	Size int64
	// ContentType is the stored MIME type ("" when the backend reports none).
	ContentType string
	// ETag is the backend's strong entity tag for the stored bytes (quotes stripped).
	ETag string
	// LastModified is the object's server-side modification time (zero when the backend reports
	// none — e.g. immediately after a Put on some backends).
	LastModified time.Time
}

// PutOptions is the immutable per-Put configuration: the content type to store and the exact byte
// length of the body. Size is REQUIRED (>= 0) so the backend streams a bounded upload rather than
// buffering the whole body to discover its length. The zero value (ContentType "", Size 0) is a
// valid zero-byte object.
type PutOptions struct {
	// ContentType is the MIME type to store with the object ("" lets the backend default it).
	ContentType string
	// Size is the exact number of bytes the body yields; it MUST equal the bytes read from body.
	// A negative Size is rejected with an InvalidError.
	Size int64
}

// PresignOptions is the immutable configuration of a presigned URL: the HTTP method it authorizes
// and how long it stays valid. The zero value is invalid (Expiry must be > 0); the port rejects
// it so an accidental never-expiring or instantly-expired URL is impossible.
type PresignOptions struct {
	// Method is the HTTP method the URL authorizes: MethodGet (download) or MethodPut (upload).
	Method PresignMethod
	// Expiry is how long the URL stays valid from issuance. Must be > 0 and <= the backend
	// maximum (S3 caps at 7 days); the adapter clamps/validates against its limit.
	Expiry time.Duration
}

// PresignMethod is the HTTP method a presigned URL authorizes. It is a closed enum so the port
// never presigns an unexpected verb.
type PresignMethod uint8

const (
	// MethodGet presigns a download URL.
	MethodGet PresignMethod = iota
	// MethodPut presigns an upload URL.
	MethodPut
)

// String returns the HTTP method token ("GET"/"PUT"), the form the SDK expects.
func (m PresignMethod) String() string {
	switch m {
	case MethodGet:
		return "GET"
	case MethodPut:
		return "PUT"
	default:
		return "GET"
	}
}

// ObjectStore is the five-method consumer port — the library's load-bearing surface, at the
// 5-method ceiling (10 §9). It is consumer-defined: it expresses exactly the blob operations a
// caller needs, not a mirror of the S3 SDK. Accept this interface; return the concrete *Store.
// Implementations MUST be safe for concurrent use by multiple goroutines.
type ObjectStore interface {
	// Put streams body (exactly options.Size bytes) into the object at ref and returns the stored
	// object's ObjectInfo. It overwrites an existing object. On failure it returns a wrapped error
	// inspectable via errors.AsType for InvalidError / DeniedError / UnavailableError; the message
	// carries the ObjectRef, never the payload or a credential.
	Put(ctx context.Context, ref ObjectRef, body io.Reader, options PutOptions) (ObjectInfo, error)
	// Get opens the object at ref for reading. The caller OWNS the returned io.ReadCloser and MUST
	// Close it. An absent object yields a wrapped NotFoundError; a nil ReadCloser is never returned
	// with a nil error. The ObjectInfo describes the bytes the reader will yield.
	Get(ctx context.Context, ref ObjectRef) (io.ReadCloser, ObjectInfo, error)
	// Delete removes the object at ref. Deleting an absent object is NOT an error (idempotent
	// delete — the S3 semantics), so a retried teardown is safe.
	Delete(ctx context.Context, ref ObjectRef) error
	// Presign returns a time-limited, credential-free URL that authorizes options.Method on ref
	// for options.Expiry. The URL embeds a signature, never the raw secret key, so it is safe to
	// hand to an untrusted client and safe to log.
	Presign(ctx context.Context, ref ObjectRef, options PresignOptions) (*url.URL, error)
	// List returns the metadata of every object in bucket whose key starts with prefix (prefix ""
	// lists the bucket). The result is credential-free and payload-free. A non-existent bucket
	// yields a wrapped NotFoundError.
	List(ctx context.Context, bucket, prefix string) ([]ObjectInfo, error)
}

// Backend is the narrow adapter seam (≤5 methods, 10 §9) the root *Store delegates to and an
// adapter (minioadapter) implements over the real SDK. It is consumer-defined here — the shape of
// THIS store's need — not a mirror of minio-go. A test substitutes an in-memory fake Backend to
// exercise the store's validation/mapping logic without a daemon; the REAL-MinIO proof is the
// //go:build integration lane (ADR-0016 §2), never this fake.
//
// A Backend returns the SAME typed taxonomy the port surfaces (InvalidError / NotFoundError /
// DeniedError / UnavailableError), so *Store passes a Backend error through unchanged — the
// mapping from an S3 status to the taxonomy is the adapter's job, in one place.
type Backend interface {
	// PutObject streams exactly size bytes of body into ref, returning the stored ObjectInfo.
	PutObject(ctx context.Context, ref ObjectRef, body io.Reader, size int64, contentType string) (ObjectInfo, error)
	// GetObject opens ref for reading; the caller owns the returned ReadCloser.
	GetObject(ctx context.Context, ref ObjectRef) (io.ReadCloser, ObjectInfo, error)
	// DeleteObject removes ref (idempotent — an absent object is not an error).
	DeleteObject(ctx context.Context, ref ObjectRef) error
	// PresignObject returns a signed, credential-free URL authorizing method on ref for expiry.
	PresignObject(ctx context.Context, ref ObjectRef, method PresignMethod, expiry time.Duration) (*url.URL, error)
	// ListObjects returns the metadata of every object in bucket whose key starts with prefix.
	ListObjects(ctx context.Context, bucket, prefix string) ([]ObjectInfo, error)
}

// Config is the immutable, fully-resolved construction input (the configuration pattern). It is
// SDK-free and credential-free: the root Store needs no endpoint or credential of its own — those
// live in the adapter's Config. This Config carries only the port-level policy knobs.
type Config struct {
	// MaxPresignExpiry caps the Expiry a caller may request on Presign (0 selects the default of
	// 7 days, the S3 maximum). A request above the cap is rejected with an InvalidError, so a
	// never-effectively-expiring URL cannot be minted by accident.
	MaxPresignExpiry time.Duration
}

// Deps is the injected hexagon: the Backend the Store delegates to. Accepting the interface here
// is the accept-interfaces rule; New returns the concrete *Store. The Backend is REQUIRED.
type Deps struct {
	// Backend is the object-store adapter (minioadapter in production, a fake in tests). Required.
	Backend Backend
}

// defaultMaxPresignExpiry is the S3 presigned-URL maximum (7 days), the cap applied when
// Config.MaxPresignExpiry is unset.
const defaultMaxPresignExpiry = 7 * 24 * time.Hour

// errInvalidConfig reports a construction-time wiring mistake (a nil Backend). It is a sentinel so
// the composition root can branch via errors.Is; it carries KindInvalid because Deps is malformed.
var errInvalidConfig = errors.New(errors.KindInvalid, "objectstorage.New: invalid dependencies")

// Store is the concrete ObjectStore returned by New. It holds the immutable Config and the
// injected Backend, validating each ref + options at the port boundary before delegating. Safe
// for concurrent use iff the Backend is. Zero value is not usable; construct via New.
type Store struct {
	maxPresignExpiry time.Duration
	backend          Backend
}

// New is the constructor spine (10 §9). PURE: no I/O, no env reads, no clock, no daemon dial. It
// validates Deps, defaults the Config knobs, and returns the concrete *Store. The first network
// call is the first ObjectStore method on the returned Store.
func New(configuration Config, dependencies Deps) (*Store, error) {
	if dependencies.Backend == nil {
		return nil, errors.Wrap(errors.KindInvalid, "objectstorage.New: Deps.Backend is required", errInvalidConfig)
	}
	maxExpiry := configuration.MaxPresignExpiry
	if maxExpiry <= 0 {
		maxExpiry = defaultMaxPresignExpiry
	}
	return &Store{maxPresignExpiry: maxExpiry, backend: dependencies.Backend}, nil
}

// Put validates ref + options and streams the body through the Backend, returning the stored
// ObjectInfo. A zero ref or a negative Size is rejected with an InvalidError before any I/O.
func (s *Store) Put(ctx context.Context, ref ObjectRef, body io.Reader, options PutOptions) (ObjectInfo, error) {
	if err := validateRef(ref); err != nil {
		return ObjectInfo{}, err
	}
	if options.Size < 0 {
		return ObjectInfo{}, InvalidError{Ref: ref, Reason: "size"}
	}
	if body == nil {
		return ObjectInfo{}, InvalidError{Ref: ref, Reason: "body"}
	}
	info, err := s.backend.PutObject(ctx, ref, body, options.Size, options.ContentType)
	if err != nil {
		return ObjectInfo{}, errors.Wrap(kindOfTaxonomy(err), "objectstorage: Put "+ref.String(), err)
	}
	return info, nil
}

// Get validates ref and opens the object through the Backend. The caller owns and must Close the
// returned ReadCloser. It never returns a non-nil ReadCloser together with a non-nil error.
func (s *Store) Get(ctx context.Context, ref ObjectRef) (io.ReadCloser, ObjectInfo, error) {
	if err := validateRef(ref); err != nil {
		return nil, ObjectInfo{}, err
	}
	reader, info, err := s.backend.GetObject(ctx, ref)
	if err != nil {
		return nil, ObjectInfo{}, errors.Wrap(kindOfTaxonomy(err), "objectstorage: Get "+ref.String(), err)
	}
	return reader, info, nil
}

// Delete validates ref and removes the object through the Backend. Deleting an absent object is
// not an error (idempotent), so a retried teardown is safe.
func (s *Store) Delete(ctx context.Context, ref ObjectRef) error {
	if err := validateRef(ref); err != nil {
		return err
	}
	if err := s.backend.DeleteObject(ctx, ref); err != nil {
		return errors.Wrap(kindOfTaxonomy(err), "objectstorage: Delete "+ref.String(), err)
	}
	return nil
}

// Presign validates ref + options (Expiry must be in (0, MaxPresignExpiry]) and returns a signed,
// credential-free URL through the Backend.
func (s *Store) Presign(ctx context.Context, ref ObjectRef, options PresignOptions) (*url.URL, error) {
	if err := validateRef(ref); err != nil {
		return nil, err
	}
	if options.Expiry <= 0 || options.Expiry > s.maxPresignExpiry {
		return nil, InvalidError{Ref: ref, Reason: "expiry"}
	}
	signed, err := s.backend.PresignObject(ctx, ref, options.Method, options.Expiry)
	if err != nil {
		return nil, errors.Wrap(kindOfTaxonomy(err), "objectstorage: Presign "+ref.String(), err)
	}
	return signed, nil
}

// List validates the bucket and returns the metadata of every object whose key starts with
// prefix. A blank bucket is an InvalidError; a non-existent bucket surfaces the Backend's
// NotFoundError.
func (s *Store) List(ctx context.Context, bucket, prefix string) ([]ObjectInfo, error) {
	if !validBucket(bucket) {
		return nil, InvalidError{Ref: ObjectRef{bucket: bucket}, Reason: "bucket"}
	}
	infos, err := s.backend.ListObjects(ctx, bucket, prefix)
	if err != nil {
		return nil, errors.Wrap(kindOfTaxonomy(err), "objectstorage: List "+bucket, err)
	}
	return infos, nil
}

// validateRef rejects the zero ObjectRef (and, defensively, a ref whose fields fail the shape
// gate) with a typed InvalidError before any I/O. A ref built through NewRef/ParseRef is already
// valid, but a caller can construct a zero ObjectRef{}, so the port re-checks at the boundary.
func validateRef(ref ObjectRef) error {
	if ref.IsZero() || !validBucket(ref.bucket) || !validKey(ref.key) {
		return InvalidError{Ref: ref, Reason: "reference"}
	}
	return nil
}

// compile-time: *Store is an ObjectStore (accept interfaces, return concrete — 10 §9).
var _ ObjectStore = (*Store)(nil)
