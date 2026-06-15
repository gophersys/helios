// Package minioadapter is the objectstorage.Backend that stores blobs in a REAL S3-compatible
// object store (MinIO or AWS S3) over the MinIO Go SDK. It is the ONLY place the SDK
// (github.com/minio/minio-go/v7) is imported (05 §1): it translates the objectstorage.Backend
// seam (Put/Get/Delete/Presign/List of an ObjectRef) into SDK calls and maps the SDK's S3 error
// responses onto the objectstorage typed taxonomy.
//
// Credentials are NEVER inline. The access-key and secret-key are secrets.Reference values in
// Config, resolved through an injected secrets.Provider at construction (the composition root,
// 10 §2): New resolves each Reference, reads the bytes inside a single secrets.Use frame, hands
// them to the SDK's static-credential constructor, and zeroizes the resolved *secrets.Secret. The
// raw key never enters a struct field, an error, or a log — every surfaced artifact is
// credential-free by construction (the redaction half of the errors contract).
//
// New is the constructor spine: it performs the credential resolution (which the injected
// Provider may make I/O-free for a fake) and builds the *minio.Client, but dials NOTHING — the
// first network call is the first Backend method.
package minioadapter

import (
	"context"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	minio "github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/objectstorage"
	"github.com/gophersys/libs/go/secrets"
)

// errInvalidConfig reports a construction-time wiring mistake (a missing endpoint, an unset
// credential reference, a nil Provider). It is a sentinel so the composition root can branch via
// errors.Is; it carries KindInvalid because the configuration/dependencies are malformed.
var errInvalidConfig = errors.New(errors.KindInvalid, "minioadapter.New: invalid configuration")

// Config is the immutable, fully-resolved construction input (the configuration pattern). It
// carries the endpoint and the CREDENTIAL REFERENCES (not the values), so a Config is safe to log.
type Config struct {
	// Endpoint is the S3/MinIO host[:port] (no scheme), e.g. "127.0.0.1:9000" or
	// "s3.amazonaws.com". Required.
	Endpoint string
	// Region is the bucket region ("" lets the SDK default, e.g. "us-east-1" for MinIO).
	Region string
	// UseSSL selects https for the SDK transport and presigned URLs.
	UseSSL bool
	// AccessKeyRef / SecretKeyRef name the S3 credential in the secrets store; New resolves them
	// through Deps.Secrets and never retains the values. Both required.
	AccessKeyRef secrets.Reference
	SecretKeyRef secrets.Reference
}

// Deps is the injected hexagon: the secrets.Provider that resolves the credential references and
// the seams a test substitutes (the SDK client builder and the http transport). Accepting
// interfaces here is the accept-interfaces rule; New returns the concrete *Adapter.
type Deps struct {
	// Secrets resolves the AccessKeyRef / SecretKeyRef to their values at construction. Required.
	Secrets secrets.Provider

	// NewClient builds the S3 seam from the resolved (endpoint, credentials, options). It defaults
	// to the real *minio.Client when nil; a unit test injects a fake S3 to exercise the mapping
	// logic without a daemon. The real-MinIO proof is the integration lane, never a fake
	// (ADR-0016 §2).
	NewClient func(endpoint string, options *minio.Options) (S3, error)

	// Transport is the http.RoundTripper the real client dials over (nil → the SDK default). A
	// test can inject one to assert no credential ever crosses the wire in a header it controls;
	// production leaves it nil.
	Transport http.RoundTripper
}

// S3 is the narrow SDK seam (≤5 methods, 10 §9) the adapter drives — consumer-defined here as the
// shape of THIS adapter's need, not a mirror of *minio.Client's wide surface. The real
// implementation wraps *minio.Client; a unit test fakes it.
type S3 interface {
	// PutObject streams size bytes of reader into bucket/object and returns the upload result.
	PutObject(ctx context.Context, bucket, object string, reader io.Reader, size int64, options minio.PutObjectOptions) (minio.UploadInfo, error)
	// GetObject opens bucket/object for reading; StatObject-style errors surface on first read.
	GetObject(ctx context.Context, bucket, object string, options minio.GetObjectOptions) (*minio.Object, error)
	// StatObject returns the object's metadata (used to classify a Get before handing back a reader).
	StatObject(ctx context.Context, bucket, object string, options minio.StatObjectOptions) (minio.ObjectInfo, error)
	// RemoveObject deletes bucket/object (S3 delete is idempotent).
	RemoveObject(ctx context.Context, bucket, object string, options minio.RemoveObjectOptions) error
	// PresignHeader returns a signed, credential-free URL for method on bucket/object for expiry.
	PresignHeader(ctx context.Context, method, bucket, object string, expiry time.Duration, query url.Values, header http.Header) (*url.URL, error)
}

// lister is the OPTIONAL extension a real S3 client also satisfies: a streaming List. It is a
// SEPARATE interface (kept off the 5-method S3 seam) because List has a channel shape the other
// five do not; the adapter type-asserts the injected S3 to it. Both the real wrapper and the unit
// fake implement it.
type lister interface {
	ListObjects(ctx context.Context, bucket string, options minio.ListObjectsOptions) <-chan minio.ObjectInfo
}

// Adapter is the concrete objectstorage.Backend returned by New. It holds the resolved S3 client
// and the endpoint metadata; the credential is NOT a field (it was consumed at construction).
// Safe for concurrent use (the SDK client is). Zero value is not usable; construct via New.
type Adapter struct {
	client S3
}

// New is the constructor spine (10 §9). It validates Config + Deps, RESOLVES the credential
// references through Deps.Secrets (reading each value inside one secrets.Use frame and zeroizing
// the resolved Secret), builds the S3 client from the resolved static credentials, and returns the
// concrete *Adapter. It dials no network: the first call is the first Backend method.
func New(configuration Config, dependencies Deps) (*Adapter, error) {
	if strings.TrimSpace(configuration.Endpoint) == "" {
		return nil, errors.Wrap(errors.KindInvalid, "minioadapter.New: Config.Endpoint is required", errInvalidConfig)
	}
	if configuration.AccessKeyRef.IsZero() || configuration.SecretKeyRef.IsZero() {
		return nil, errors.Wrap(errors.KindInvalid,
			"minioadapter.New: Config.AccessKeyRef and Config.SecretKeyRef are required", errInvalidConfig)
	}
	if dependencies.Secrets == nil {
		return nil, errors.Wrap(errors.KindInvalid, "minioadapter.New: Deps.Secrets is required", errInvalidConfig)
	}

	creds, err := resolveCredentials(context.Background(), dependencies.Secrets, configuration)
	if err != nil {
		return nil, err
	}

	newClient := dependencies.NewClient
	if newClient == nil {
		newClient = realNewClient
	}
	options := &minio.Options{
		Creds:     creds,
		Secure:    configuration.UseSSL,
		Region:    configuration.Region,
		Transport: dependencies.Transport,
	}
	client, err := newClient(configuration.Endpoint, options)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "minioadapter.New: constructing the S3 client", err)
	}
	return &Adapter{client: client}, nil
}

// resolveCredentials resolves the access/secret-key references and builds a static-V4 credential
// provider, reading each value inside a single secrets.Use frame so the plaintext lives only on
// the stack for the duration of the credential construction and never enters a field, error, or
// log. The resolved Secrets are zeroized before return.
func resolveCredentials(ctx context.Context, provider secrets.Provider, configuration Config) (*credentials.Credentials, error) {
	accessSecret, err := provider.Resolve(ctx, configuration.AccessKeyRef)
	if err != nil {
		return nil, errors.Wrap(kindOfSecretsError(err), "minioadapter.New: resolving the access-key reference", err)
	}
	defer accessSecret.Zeroize()
	secretSecret, err := provider.Resolve(ctx, configuration.SecretKeyRef)
	if err != nil {
		return nil, errors.Wrap(kindOfSecretsError(err), "minioadapter.New: resolving the secret-key reference", err)
	}
	defer secretSecret.Zeroize()

	creds, err := secrets.Use1(accessSecret, func(accessKey []byte) (*credentials.Credentials, error) {
		return secrets.Use1(secretSecret, func(secretKey []byte) (*credentials.Credentials, error) {
			return credentials.NewStaticV4(string(accessKey), string(secretKey), ""), nil
		})
	})
	if err != nil {
		return nil, errors.Wrap(kindOfSecretsError(err), "minioadapter.New: reading the resolved credential", err)
	}
	return creds, nil
}

// kindOfSecretsError classifies a secrets-taxonomy error onto an errors.Kind so the wrapping
// preserves the cause's meaning end-to-end (the secrets taxonomy types are plain structs, not
// *errors.Error, so errors.KindOf alone reports Unknown — the same mapping the root store does for
// its own taxonomy). A non-secrets cause falls through to the errors-library classification.
func kindOfSecretsError(err error) errors.Kind {
	switch {
	case errors.IsType[secrets.InvalidReferenceError](err):
		return errors.KindInvalid
	case errors.IsType[secrets.NotFoundError](err):
		return errors.KindNotFound
	case errors.IsType[secrets.DeniedError](err):
		return errors.KindPermission
	case errors.IsType[secrets.UnavailableError](err):
		return errors.KindUnavailable
	default:
		return errors.KindOf(err)
	}
}

// PutObject streams size bytes of body into ref and returns the stored ObjectInfo.
func (a *Adapter) PutObject(ctx context.Context, ref objectstorage.ObjectRef, body io.Reader, size int64, contentType string) (objectstorage.ObjectInfo, error) {
	uploaded, err := a.client.PutObject(ctx, ref.Bucket(), ref.Key(), body, size, minio.PutObjectOptions{ContentType: contentType})
	if err != nil {
		return objectstorage.ObjectInfo{}, mapS3Error(ref, err)
	}
	return objectstorage.ObjectInfo{
		Ref:          ref,
		Size:         uploaded.Size,
		ContentType:  contentType,
		ETag:         strings.Trim(uploaded.ETag, `"`),
		LastModified: uploaded.LastModified,
	}, nil
}

// GetObject stats the object first (so an absent object is a clean typed NotFoundError before any
// reader is handed back), then opens it for reading. The caller owns the returned ReadCloser.
func (a *Adapter) GetObject(ctx context.Context, ref objectstorage.ObjectRef) (io.ReadCloser, objectstorage.ObjectInfo, error) {
	stat, err := a.client.StatObject(ctx, ref.Bucket(), ref.Key(), minio.StatObjectOptions{})
	if err != nil {
		return nil, objectstorage.ObjectInfo{}, mapS3Error(ref, err)
	}
	object, err := a.client.GetObject(ctx, ref.Bucket(), ref.Key(), minio.GetObjectOptions{})
	if err != nil {
		return nil, objectstorage.ObjectInfo{}, mapS3Error(ref, err)
	}
	return object, infoFromStat(ref, &stat), nil
}

// DeleteObject removes ref. S3 delete is idempotent, so an absent object is not an error.
func (a *Adapter) DeleteObject(ctx context.Context, ref objectstorage.ObjectRef) error {
	if err := a.client.RemoveObject(ctx, ref.Bucket(), ref.Key(), minio.RemoveObjectOptions{}); err != nil {
		return mapS3Error(ref, err)
	}
	return nil
}

// PresignObject returns a signed, credential-free URL authorizing method on ref for expiry.
func (a *Adapter) PresignObject(ctx context.Context, ref objectstorage.ObjectRef, method objectstorage.PresignMethod, expiry time.Duration) (*url.URL, error) {
	signed, err := a.client.PresignHeader(ctx, method.String(), ref.Bucket(), ref.Key(), expiry, url.Values{}, http.Header{})
	if err != nil {
		return nil, mapS3Error(ref, err)
	}
	return signed, nil
}

// ListObjects returns the metadata of every object in bucket whose key starts with prefix. It
// drains the SDK's streaming channel, surfacing a per-item error (a missing bucket → NotFound).
func (a *Adapter) ListObjects(ctx context.Context, bucket, prefix string) ([]objectstorage.ObjectInfo, error) {
	channelLister, ok := a.client.(lister)
	if !ok {
		return nil, errors.New(errors.KindInternal, "minioadapter: injected S3 client does not support List")
	}
	var infos []objectstorage.ObjectInfo
	for item := range channelLister.ListObjects(ctx, bucket, minio.ListObjectsOptions{Prefix: prefix, Recursive: true}) {
		if item.Err != nil {
			return nil, mapS3Error(objectstorage.ObjectRef{}, item.Err)
		}
		ref, err := objectstorage.NewRef(bucket, item.Key)
		if err != nil {
			// A key the port would reject (e.g. a directory marker) is skipped, not surfaced as a
			// store failure — the listing is of valid object keys.
			continue
		}
		infos = append(infos, infoFromStat(ref, &item))
	}
	return infos, nil
}

// infoFromStat projects a minio.ObjectInfo onto the credential-free objectstorage.ObjectInfo. stat
// is taken by pointer because minio.ObjectInfo is a heavy struct (gocritic hugeParam).
func infoFromStat(ref objectstorage.ObjectRef, stat *minio.ObjectInfo) objectstorage.ObjectInfo {
	return objectstorage.ObjectInfo{
		Ref:          ref,
		Size:         stat.Size,
		ContentType:  stat.ContentType,
		ETag:         strings.Trim(stat.ETag, `"`),
		LastModified: stat.LastModified,
	}
}

// mapS3Error maps an SDK error onto the objectstorage taxonomy so callers branch on AsType[…]
// across rewordings. It inspects the SDK's ErrorResponse HTTP status: 403 → DeniedError,
// 404 → NotFoundError, 400 → InvalidError, everything else (connection refused, 5xx, timeouts) →
// UnavailableError (the one retryable signal). The ObjectRef is carried; no payload/credential is.
func mapS3Error(ref objectstorage.ObjectRef, err error) error {
	if err == nil {
		return nil
	}
	response := minio.ToErrorResponse(err)
	switch response.StatusCode {
	case http.StatusForbidden:
		return objectstorage.DeniedError{Ref: ref}
	case http.StatusNotFound:
		return objectstorage.NotFoundError{Ref: ref}
	case http.StatusBadRequest:
		return objectstorage.InvalidError{Ref: ref, Reason: "request"}
	default:
		// A zero StatusCode is a non-HTTP transport error (dial failure, deadline, TLS) — an
		// availability problem. Also covers explicit NoSuchKey/NoSuchBucket whose code string the
		// SDK sets without always a status: classify those as NotFound.
		if response.Code == "NoSuchKey" || response.Code == "NoSuchBucket" {
			return objectstorage.NotFoundError{Ref: ref}
		}
		return objectstorage.UnavailableError{Ref: ref}
	}
}

// compile-time: *Adapter is an objectstorage.Backend.
var _ objectstorage.Backend = (*Adapter)(nil)
