package minioadapter_test

import (
	"bytes"
	"context"
	"io"
	"net/http"
	"net/url"
	"testing"
	"time"

	minio "github.com/minio/minio-go/v7"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/objectstorage"
	"github.com/gophersys/libs/go/objectstorage/minioadapter"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// nonListerS3 implements the 5-method minioadapter.S3 seam but NOT the required streaming-List
// extension (lister) — so New must reject it at construction with a KindInvalid. It exists ONLY to
// make the lister type-assertion in New reachable and correct: a wiring fault is a construction-time
// KindInvalid, never an off-taxonomy per-call error. It is never a production shape (the real
// *minio.Client and the unit fakeS3 both implement ListObjects).
type nonListerS3 struct{}

//nolint:gocritic // hugeParam: the options param type is fixed by the minioadapter.S3 interface seam; a fake must match it by value.
func (nonListerS3) PutObject(context.Context, string, string, io.Reader, int64, minio.PutObjectOptions) (minio.UploadInfo, error) {
	return minio.UploadInfo{}, nil
}

//nolint:gocritic // hugeParam: fixed by the S3 seam.
func (nonListerS3) GetObject(context.Context, string, string, minio.GetObjectOptions) (*minio.Object, error) {
	return nil, nil //nolint:nilnil // unreachable stub: New rejects this client before any method runs.
}

//nolint:gocritic // hugeParam: fixed by the S3 seam.
func (nonListerS3) StatObject(context.Context, string, string, minio.StatObjectOptions) (minio.ObjectInfo, error) {
	return minio.ObjectInfo{}, nil
}

//nolint:gocritic // hugeParam: fixed by the S3 seam.
func (nonListerS3) RemoveObject(context.Context, string, string, minio.RemoveObjectOptions) error {
	return nil
}

func (nonListerS3) PresignHeader(context.Context, string, string, string, time.Duration, url.Values, http.Header) (*url.URL, error) {
	return nil, nil //nolint:nilnil // unreachable stub: New rejects this client before any method runs.
}

var _ minioadapter.S3 = nonListerS3{}

func mustRef(t *testing.T, bucket, key string) objectstorage.ObjectRef {
	t.Helper()
	r, err := objectstorage.NewRef(bucket, key)
	if err != nil {
		t.Fatalf("NewRef(%q,%q) error = %v", bucket, key, err)
	}
	return r
}

// ── construction + credential resolution ────────────────────────────────────────────────────────.

func TestNew_RejectsMissingEndpoint(t *testing.T) {
	t.Parallel()
	_, err := minioadapter.New(
		minioadapter.Config{AccessKeyRef: accessRef, SecretKeyRef: secretRef},
		minioadapter.Deps{Secrets: seededSecrets()},
	)
	if !errors.IsType[error](err) || errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("New(no endpoint) = %v, want KindInvalid", err)
	}
}

func TestNew_RejectsMissingCredentialRefs(t *testing.T) {
	t.Parallel()
	_, err := minioadapter.New(
		minioadapter.Config{Endpoint: "127.0.0.1:9000"},
		minioadapter.Deps{Secrets: seededSecrets()},
	)
	if errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("New(no cred refs) Kind = %v, want KindInvalid", errors.KindOf(err))
	}
}

func TestNew_RejectsNilSecretsProvider(t *testing.T) {
	t.Parallel()
	_, err := minioadapter.New(
		minioadapter.Config{Endpoint: "127.0.0.1:9000", AccessKeyRef: accessRef, SecretKeyRef: secretRef},
		minioadapter.Deps{NewClient: func(string, *minio.Options) (minioadapter.S3, error) { return newFakeS3(), nil }},
	)
	if errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("New(nil Secrets) Kind = %v, want KindInvalid", errors.KindOf(err))
	}
}

// TestNew_PropagatesCredentialResolutionFailure proves a secrets resolution error surfaces with its
// Kind preserved (the access-key ref is not seeded → NotFound), so the composition root learns the
// credential is missing rather than getting a confusing dial failure later.
func TestNew_PropagatesCredentialResolutionFailure(t *testing.T) {
	t.Parallel()
	emptyProvider := secretstest.New(map[string]string{}) // resolves nothing → NotFound
	_, err := newAdapter(newFakeS3(), emptyProvider)
	if err == nil {
		t.Fatal("New should fail when the credential reference cannot be resolved")
	}
	if errors.KindOf(err) != errors.KindNotFound {
		t.Errorf("credential-resolution failure Kind = %v, want KindNotFound (preserved from secrets)", errors.KindOf(err))
	}
}

// TestNew_RejectsS3WithoutListerSeam proves the lister requirement is enforced at CONSTRUCTION: an
// S3 client that implements the 5-method seam but not the streaming-List extension is a wiring fault,
// surfaced by New as a KindInvalid — never as an off-taxonomy KindInternal on a later ListObjects
// call. This is the test that makes the New-time assertion branch reachable and correct (the dead
// per-call defensive branch it replaced could never be hit, since the real client and the unit fake
// both implement ListObjects).
func TestNew_RejectsS3WithoutListerSeam(t *testing.T) {
	t.Parallel()
	_, err := minioadapter.New(
		minioadapter.Config{Endpoint: "127.0.0.1:9000", AccessKeyRef: accessRef, SecretKeyRef: secretRef},
		minioadapter.Deps{
			Secrets:   seededSecrets(),
			NewClient: func(string, *minio.Options) (minioadapter.S3, error) { return nonListerS3{}, nil },
		},
	)
	if err == nil {
		t.Fatal("New should reject an S3 client that does not implement the streaming-List seam")
	}
	if errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("New(non-lister S3) Kind = %v, want KindInvalid (a construction-time wiring fault)", errors.KindOf(err))
	}
}

func TestNew_SucceedsAndResolvesCredential(t *testing.T) {
	t.Parallel()
	adapter, err := newAdapter(newFakeS3(), seededSecrets())
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	if adapter == nil {
		t.Fatal("New returned a nil adapter with no error")
	}
}

// ── Backend operations over the fake S3 ──────────────────────────────────────────────────────────.

func TestAdapter_PutThenStatRoundTripsInfo(t *testing.T) {
	t.Parallel()
	client := newFakeS3()
	adapter, err := newAdapter(client, seededSecrets())
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	ctx := context.Background()
	r := mustRef(t, "eden", "objects/a.bin")
	payload := []byte("adapter-payload")

	info, err := adapter.PutObject(ctx, r, bytes.NewReader(payload), int64(len(payload)), "application/octet-stream")
	if err != nil {
		t.Fatalf("PutObject error = %v", err)
	}
	if info.Size != int64(len(payload)) || info.Ref != r || info.ETag != "fake-etag" {
		t.Errorf("PutObject info = %+v, unexpected", info)
	}
}

func TestAdapter_GetAbsentIsNotFound(t *testing.T) {
	t.Parallel()
	adapter, err := newAdapter(newFakeS3(), seededSecrets())
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	_, _, gerr := adapter.GetObject(context.Background(), mustRef(t, "eden", "absent.bin"))
	if !errors.IsType[objectstorage.NotFoundError](gerr) {
		t.Errorf("GetObject(absent) = %v, want NotFoundError", gerr)
	}
}

func TestAdapter_DeleteIsIdempotent(t *testing.T) {
	t.Parallel()
	adapter, err := newAdapter(newFakeS3(), seededSecrets())
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	r := mustRef(t, "eden", "gone.bin")
	if derr := adapter.DeleteObject(context.Background(), r); derr != nil {
		t.Errorf("DeleteObject(absent) = %v, want nil (idempotent)", derr)
	}
}

func TestAdapter_PresignProducesURL(t *testing.T) {
	t.Parallel()
	adapter, err := newAdapter(newFakeS3(), seededSecrets())
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	signed, perr := adapter.PresignObject(context.Background(), mustRef(t, "eden", "p.bin"), objectstorage.MethodGet, 10*time.Minute)
	if perr != nil {
		t.Fatalf("PresignObject error = %v", perr)
	}
	if signed.Host != "fake-minio.invalid" || signed.Path != "/eden/p.bin" {
		t.Errorf("presigned URL = %q, unexpected", signed.String())
	}
}

func TestAdapter_ListByPrefix(t *testing.T) {
	t.Parallel()
	client := newFakeS3()
	adapter, err := newAdapter(client, seededSecrets())
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	ctx := context.Background()
	for _, k := range []string{"list/a.bin", "list/b.bin", "other/c.bin"} {
		if _, perr := adapter.PutObject(ctx, mustRef(t, "eden", k), bytes.NewReader([]byte("x")), 1, ""); perr != nil {
			t.Fatalf("seed Put(%q) error = %v", k, perr)
		}
	}
	infos, lerr := adapter.ListObjects(ctx, "eden", "list/")
	if lerr != nil {
		t.Fatalf("ListObjects error = %v", lerr)
	}
	if len(infos) != 2 {
		t.Errorf("ListObjects(list/) = %d objects, want 2", len(infos))
	}
}

// ── error mapping ────────────────────────────────────────────────────────────────────────────────.

func TestAdapter_MapsStatusToTaxonomy(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	r := mustRef(t, "eden", "k.bin")
	cases := map[int]func(error) bool{
		http.StatusForbidden:           errors.IsType[objectstorage.DeniedError],
		http.StatusNotFound:            errors.IsType[objectstorage.NotFoundError],
		http.StatusBadRequest:          errors.IsType[objectstorage.InvalidError],
		http.StatusInternalServerError: errors.IsType[objectstorage.UnavailableError],
	}
	for status, want := range cases {
		client := newFakeS3()
		client.statErr = minio.ErrorResponse{StatusCode: status}
		adapter, err := newAdapter(client, seededSecrets())
		if err != nil {
			t.Fatalf("New error = %v", err)
		}
		_, _, gerr := adapter.GetObject(ctx, r)
		if !want(gerr) {
			t.Errorf("status %d mapped to %v, not the expected taxonomy type", status, gerr)
		}
	}
}

func TestAdapter_DialErrorIsUnavailable(t *testing.T) {
	t.Parallel()
	client := newFakeS3()
	client.statErr = errors.New(errors.KindUnavailable, "connection refused")
	adapter, err := newAdapter(client, seededSecrets())
	if err != nil {
		t.Fatalf("New error = %v", err)
	}
	_, _, gerr := adapter.GetObject(context.Background(), mustRef(t, "eden", "k.bin"))
	if !errors.IsType[objectstorage.UnavailableError](gerr) {
		t.Errorf("dial error mapped to %v, want UnavailableError", gerr)
	}
}
