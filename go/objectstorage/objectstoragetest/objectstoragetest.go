// Package objectstoragetest provides the canonical in-memory fake Backend and the exported
// two-binding conformance suite, so consumers never hand-roll a fake that drifts from the
// ObjectStore contract. The fake weakens the SOURCE of bytes (an in-memory map instead of a real
// S3 daemon), never the contract: the SAME RunStoreSuite runs over the fake here and over the
// REAL MinIO-backed *Client in the integration lane (ADR-0016 §2).
package objectstoragetest

import (
	"bytes"
	"context"
	"io"
	"net/url"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/gophersys/libs/go/objectstorage"
)

// SeededPayload is the byte-for-byte round-trip needle the suite Puts and Gets back. It is fixed
// so the round-trip and leak assertions have a concrete value; it is NOT a credential.
var SeededPayload = []byte("the-seeded-object-payload-bytes-0123456789")

// Backend is a deterministic, in-memory objectstorage.Backend for tests. Zero value is usable and
// empty (every Get → NotFoundError). Deterministic; no clock-dependent behavior beyond the
// recorded modification time. Safe for concurrent use.
type Backend struct {
	mu      sync.Mutex
	objects map[string]storedObject // keyed by ref.String()
	now     time.Time
	host    string // presign host (default "fake-objectstore.invalid")
}

// storedObject is one object the fake holds: its bytes plus the metadata a real backend records.
type storedObject struct {
	body         []byte
	contentType  string
	etag         string
	lastModified time.Time
}

// NewBackend returns an empty in-memory Backend with a deterministic clock and presign host, so
// the suite's assertions (ETag, LastModified, presigned host) are stable.
func NewBackend() *Backend {
	return &Backend{
		objects: make(map[string]storedObject),
		now:     time.Date(2026, time.June, 14, 0, 0, 0, 0, time.UTC),
		host:    "fake-objectstore.invalid",
	}
}

// PutObject stores exactly size bytes of body under ref and returns the recorded ObjectInfo. It
// reads at most size bytes so a caller that lies about size cannot overrun; the ETag is a stable
// content hash so equal bytes round-trip to an equal tag.
func (b *Backend) PutObject(_ context.Context, ref objectstorage.ObjectRef, body io.Reader, size int64, contentType string) (objectstorage.ObjectInfo, error) {
	limited := io.LimitReader(body, size)
	buffer, err := io.ReadAll(limited)
	if err != nil {
		return objectstorage.ObjectInfo{}, objectstorage.UnavailableError{Ref: ref}
	}
	stored := storedObject{
		body:         buffer,
		contentType:  contentType,
		etag:         contentETag(buffer),
		lastModified: b.now,
	}
	b.mu.Lock()
	b.objects[ref.String()] = stored
	b.mu.Unlock()
	return objectstorage.ObjectInfo{
		Ref:          ref,
		Size:         int64(len(buffer)),
		ContentType:  contentType,
		ETag:         stored.etag,
		LastModified: stored.lastModified,
	}, nil
}

// GetObject opens ref for reading; an absent object is a NotFoundError. The caller owns the
// returned ReadCloser.
func (b *Backend) GetObject(_ context.Context, ref objectstorage.ObjectRef) (io.ReadCloser, objectstorage.ObjectInfo, error) {
	b.mu.Lock()
	stored, ok := b.objects[ref.String()]
	b.mu.Unlock()
	if !ok {
		return nil, objectstorage.ObjectInfo{}, objectstorage.NotFoundError{Ref: ref}
	}
	info := objectstorage.ObjectInfo{
		Ref:          ref,
		Size:         int64(len(stored.body)),
		ContentType:  stored.contentType,
		ETag:         stored.etag,
		LastModified: stored.lastModified,
	}
	return io.NopCloser(bytes.NewReader(stored.body)), info, nil
}

// DeleteObject removes ref. Deleting an absent object is a no-op (idempotent), matching S3.
func (b *Backend) DeleteObject(_ context.Context, ref objectstorage.ObjectRef) error {
	b.mu.Lock()
	delete(b.objects, ref.String())
	b.mu.Unlock()
	return nil
}

// PresignObject returns a deterministic, credential-free URL: scheme+host+path with the method
// and expiry encoded in the query, and a fixed opaque signature token. It embeds NO credential,
// proving the presign surface is safe to log/hand out.
func (b *Backend) PresignObject(_ context.Context, ref objectstorage.ObjectRef, method objectstorage.PresignMethod, expiry time.Duration) (*url.URL, error) {
	query := url.Values{}
	query.Set("X-Amz-Method", method.String())
	query.Set("X-Amz-Expires", strconvSeconds(expiry))
	query.Set("X-Amz-Signature", "fake-opaque-signature-no-credential")
	return &url.URL{
		Scheme:   "https",
		Host:     b.host,
		Path:     "/" + ref.Bucket() + "/" + ref.Key(),
		RawQuery: query.Encode(),
	}, nil
}

// ListObjects returns the metadata of every object in bucket whose key starts with prefix, sorted
// by key for determinism. The fake has no notion of a non-existent bucket, so it lists whatever
// matches (an empty slice when nothing does).
func (b *Backend) ListObjects(_ context.Context, bucket, prefix string) ([]objectstorage.ObjectInfo, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	var infos []objectstorage.ObjectInfo
	for key, stored := range b.objects {
		slash := strings.Index(key, "/")
		if slash < 0 || key[:slash] != bucket {
			continue
		}
		objectKey := key[slash+1:]
		if !strings.HasPrefix(objectKey, prefix) {
			continue
		}
		ref, err := objectstorage.NewRef(bucket, objectKey)
		if err != nil {
			continue
		}
		infos = append(infos, objectstorage.ObjectInfo{
			Ref:          ref,
			Size:         int64(len(stored.body)),
			ContentType:  stored.contentType,
			ETag:         stored.etag,
			LastModified: stored.lastModified,
		})
	}
	sort.Slice(infos, func(i, j int) bool { return infos[i].Ref.Key() < infos[j].Ref.Key() })
	return infos, nil
}

// contentETag is a stable hex content tag over the bytes, so equal payloads round-trip to an equal
// ETag (the fake's stand-in for the real backend's MD5/strong tag). FNV-1a is sufficient for a
// test fixture — it is not a security primitive here.
func contentETag(buffer []byte) string {
	const (
		offset uint64 = 1469598103934665603
		prime  uint64 = 1099511628211
	)
	hash := offset
	for _, b := range buffer {
		hash ^= uint64(b)
		hash *= prime
	}
	const hexDigits = "0123456789abcdef"
	var out [16]byte
	for i := 15; i >= 0; i-- {
		out[i] = hexDigits[hash&0xf]
		hash >>= 4
	}
	return string(out[:])
}

// strconvSeconds renders a duration's whole seconds without importing strconv at every call site
// (keeps the fake's imports tight). It is small and total for the non-negative expiries the port
// admits.
func strconvSeconds(d time.Duration) string {
	seconds := int64(d / time.Second)
	if seconds == 0 {
		return "0"
	}
	var digits []byte
	for seconds > 0 {
		digits = append([]byte{byte('0' + seconds%10)}, digits...)
		seconds /= 10
	}
	return string(digits)
}

// compile-time: *Backend is an objectstorage.Backend.
var _ objectstorage.Backend = (*Backend)(nil)
