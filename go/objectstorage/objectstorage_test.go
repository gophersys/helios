package objectstorage_test

import (
	"bytes"
	"context"
	"io"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/objectstorage"
	"github.com/gophersys/libs/go/objectstorage/objectstoragetest"
)

// newFakeStore builds a concrete *Store over a fresh in-memory fake Backend (return concrete —
// 10 §9; the *Store is an ObjectStore by its method set).
func newFakeStore(t *testing.T) *objectstorage.Store {
	t.Helper()
	store, err := objectstorage.New(objectstorage.Config{}, objectstorage.Deps{Backend: objectstoragetest.NewBackend()})
	if err != nil {
		t.Fatalf("objectstorage.New error = %v", err)
	}
	return store
}

// ── ObjectRef construction + validation ─────────────────────────────────────────────────────────.

func TestNewRef_AcceptsWellFormed(t *testing.T) {
	t.Parallel()
	r, err := objectstorage.NewRef("eden-bucket", "a/b/c.bin")
	if err != nil {
		t.Fatalf("NewRef error = %v", err)
	}
	if r.Bucket() != "eden-bucket" || r.Key() != "a/b/c.bin" {
		t.Errorf("NewRef round-trip = (%q,%q), want (eden-bucket, a/b/c.bin)", r.Bucket(), r.Key())
	}
	if r.String() != "eden-bucket/a/b/c.bin" {
		t.Errorf("String() = %q, want eden-bucket/a/b/c.bin", r.String())
	}
	if r.IsZero() {
		t.Error("a constructed ref reports IsZero")
	}
}

func TestNewRef_RejectsMalformed(t *testing.T) {
	t.Parallel()
	cases := map[string][2]string{
		"blank bucket":      {"", "k"},
		"blank key":         {"b", ""},
		"slash in bucket":   {"a/b", "k"},
		"leading slash key": {"b", "/k"},
		"dotdot traversal":  {"b", "a/../etc/passwd"},
		"dot element":       {"b", "a/./k"},
		"space in key":      {"b", "a b"},
		"empty key element": {"b", "a//b"},
	}
	for name, bk := range cases {
		_, err := objectstorage.NewRef(bk[0], bk[1])
		if !errors.IsType[objectstorage.InvalidError](err) {
			t.Errorf("%s: NewRef(%q,%q) error = %v, want InvalidError", name, bk[0], bk[1], err)
		}
	}
}

func TestParseRef_RoundTripsAndRejects(t *testing.T) {
	t.Parallel()
	r, err := objectstorage.ParseRef("eden-bucket/dir/file.txt")
	if err != nil {
		t.Fatalf("ParseRef error = %v", err)
	}
	if r.String() != "eden-bucket/dir/file.txt" {
		t.Errorf("ParseRef round-trip = %q", r.String())
	}
	for _, bad := range []string{"", "nobucketslash", "/leadingslash", "trailingslash/"} {
		if _, perr := objectstorage.ParseRef(bad); !errors.IsType[objectstorage.InvalidError](perr) {
			t.Errorf("ParseRef(%q) error = %v, want InvalidError", bad, perr)
		}
	}
}

func TestZeroRef_IsZeroAndStringEmpty(t *testing.T) {
	t.Parallel()
	var zero objectstorage.ObjectRef
	if !zero.IsZero() {
		t.Error("zero ObjectRef IsZero() = false")
	}
	if zero.String() != "" {
		t.Errorf("zero ref String() = %q, want empty", zero.String())
	}
}

// ── New construction + validation ───────────────────────────────────────────────────────────────.

func TestNew_RejectsNilBackend(t *testing.T) {
	t.Parallel()
	_, err := objectstorage.New(objectstorage.Config{}, objectstorage.Deps{})
	if err == nil {
		t.Fatal("New with a nil Backend should error")
	}
	if errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("New(nil backend) Kind = %v, want KindInvalid", errors.KindOf(err))
	}
}

// ── Store delegation + boundary validation ──────────────────────────────────────────────────────.

func TestStore_PutGetDeleteHappyPath(t *testing.T) {
	t.Parallel()
	store := newFakeStore(t)
	ctx := context.Background()
	r := mustRef(t, "b", "k/obj.bin")
	payload := []byte("hello-objectstorage")

	info, err := store.Put(ctx, r, bytes.NewReader(payload), objectstorage.PutOptions{ContentType: "text/plain", Size: int64(len(payload))})
	if err != nil {
		t.Fatalf("Put error = %v", err)
	}
	if info.Size != int64(len(payload)) || info.Ref != r || info.ContentType != "text/plain" {
		t.Errorf("Put info = %+v, unexpected", info)
	}

	reader, getInfo, err := store.Get(ctx, r)
	if err != nil {
		t.Fatalf("Get error = %v", err)
	}
	got, rerr := io.ReadAll(reader)
	if rerr != nil {
		t.Fatalf("ReadAll error = %v", rerr)
	}
	if cerr := reader.Close(); cerr != nil {
		t.Errorf("Close error = %v", cerr)
	}
	if !bytes.Equal(got, payload) {
		t.Errorf("Get returned %q, want %q", got, payload)
	}
	if getInfo.ETag != info.ETag {
		t.Errorf("ETag drift %q vs %q", getInfo.ETag, info.ETag)
	}
	if err := store.Delete(ctx, r); err != nil {
		t.Errorf("Delete error = %v", err)
	}
	if _, _, gerr := store.Get(ctx, r); !errors.IsType[objectstorage.NotFoundError](gerr) {
		t.Errorf("Get after Delete = %v, want NotFoundError", gerr)
	}
}

func TestStore_RejectsInvalidAtBoundary(t *testing.T) {
	t.Parallel()
	store := newFakeStore(t)
	ctx := context.Background()
	r := mustRef(t, "b", "k")

	if _, err := store.Put(ctx, objectstorage.ObjectRef{}, bytes.NewReader(nil), objectstorage.PutOptions{}); !errors.IsType[objectstorage.InvalidError](err) {
		t.Errorf("Put(zero ref) = %v, want InvalidError", err)
	}
	if _, err := store.Put(ctx, r, bytes.NewReader(nil), objectstorage.PutOptions{Size: -1}); !errors.IsType[objectstorage.InvalidError](err) {
		t.Errorf("Put(negative size) = %v, want InvalidError", err)
	}
	if _, err := store.Put(ctx, r, nil, objectstorage.PutOptions{}); !errors.IsType[objectstorage.InvalidError](err) {
		t.Errorf("Put(nil body) = %v, want InvalidError", err)
	}
	if _, _, err := store.Get(ctx, objectstorage.ObjectRef{}); !errors.IsType[objectstorage.InvalidError](err) {
		t.Errorf("Get(zero ref) = %v, want InvalidError", err)
	}
	if err := store.Delete(ctx, objectstorage.ObjectRef{}); !errors.IsType[objectstorage.InvalidError](err) {
		t.Errorf("Delete(zero ref) = %v, want InvalidError", err)
	}
	if _, err := store.List(ctx, "", ""); !errors.IsType[objectstorage.InvalidError](err) {
		t.Errorf("List(blank bucket) = %v, want InvalidError", err)
	}
}

func TestStore_PresignValidatesExpiry(t *testing.T) {
	t.Parallel()
	store := newFakeStore(t)
	ctx := context.Background()
	r := mustRef(t, "b", "k")

	if _, err := store.Presign(ctx, r, objectstorage.PresignOptions{Method: objectstorage.MethodGet, Expiry: 0}); !errors.IsType[objectstorage.InvalidError](err) {
		t.Errorf("Presign(zero expiry) = %v, want InvalidError", err)
	}
	if _, err := store.Presign(ctx, r, objectstorage.PresignOptions{Method: objectstorage.MethodGet, Expiry: 100 * 24 * time.Hour}); !errors.IsType[objectstorage.InvalidError](err) {
		t.Errorf("Presign(over-cap expiry) = %v, want InvalidError", err)
	}
	signed, err := store.Presign(ctx, r, objectstorage.PresignOptions{Method: objectstorage.MethodPut, Expiry: 10 * time.Minute})
	if err != nil {
		t.Fatalf("Presign(valid) error = %v", err)
	}
	if signed.Scheme != "https" || !strings.Contains(signed.String(), r.Key()) {
		t.Errorf("presigned URL %q unexpected", signed.String())
	}
	if !strings.Contains(signed.RawQuery, url.QueryEscape("PUT")) {
		t.Errorf("presigned URL query %q does not encode the PUT method", signed.RawQuery)
	}
}

// TestStore_WrapsBackendErrorWithKind proves the store wraps a Backend taxonomy error with the
// matching errors.Kind so a consumer's errors.KindOf branches correctly through the wrap.
func TestStore_WrapsBackendErrorWithKind(t *testing.T) {
	t.Parallel()
	store, err := objectstorage.New(objectstorage.Config{}, objectstorage.Deps{Backend: &failingBackend{}})
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	r := mustRef(t, "b", "k")
	_, _, gerr := store.Get(context.Background(), r)
	if errors.KindOf(gerr) != errors.KindUnavailable {
		t.Errorf("Get error Kind = %v, want KindUnavailable (wrapped from the Backend)", errors.KindOf(gerr))
	}
	if !errors.IsType[objectstorage.UnavailableError](gerr) {
		t.Errorf("wrapped error not AsType[UnavailableError]: %v", gerr)
	}
	if !strings.Contains(gerr.Error(), r.String()) {
		t.Errorf("wrapped error %q does not carry the ref", gerr.Error())
	}
}

func TestPresignMethod_String(t *testing.T) {
	t.Parallel()
	if objectstorage.MethodGet.String() != "GET" || objectstorage.MethodPut.String() != "PUT" {
		t.Errorf("PresignMethod.String drift: %q %q", objectstorage.MethodGet, objectstorage.MethodPut)
	}
}

// ── helpers + a forced-error backend ────────────────────────────────────────────────────────────.

func mustRef(t *testing.T, bucket, key string) objectstorage.ObjectRef {
	t.Helper()
	r, err := objectstorage.NewRef(bucket, key)
	if err != nil {
		t.Fatalf("NewRef(%q,%q) error = %v", bucket, key, err)
	}
	return r
}

// failingBackend returns an UnavailableError from every operation, to drive the store's wrap path.
type failingBackend struct{}

func (*failingBackend) PutObject(_ context.Context, ref objectstorage.ObjectRef, _ io.Reader, _ int64, _ string) (objectstorage.ObjectInfo, error) {
	return objectstorage.ObjectInfo{}, objectstorage.UnavailableError{Ref: ref}
}

func (*failingBackend) GetObject(_ context.Context, ref objectstorage.ObjectRef) (io.ReadCloser, objectstorage.ObjectInfo, error) {
	return nil, objectstorage.ObjectInfo{}, objectstorage.UnavailableError{Ref: ref}
}

func (*failingBackend) DeleteObject(_ context.Context, ref objectstorage.ObjectRef) error {
	return objectstorage.UnavailableError{Ref: ref}
}

func (*failingBackend) PresignObject(_ context.Context, ref objectstorage.ObjectRef, _ objectstorage.PresignMethod, _ time.Duration) (*url.URL, error) {
	return nil, objectstorage.UnavailableError{Ref: ref}
}

func (*failingBackend) ListObjects(_ context.Context, bucket, _ string) ([]objectstorage.ObjectInfo, error) {
	return nil, objectstorage.UnavailableError{Ref: objectstorage.ObjectRef{}}
}

var _ objectstorage.Backend = (*failingBackend)(nil)
