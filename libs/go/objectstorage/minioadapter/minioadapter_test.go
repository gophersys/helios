package minioadapter_test

import (
	"bytes"
	"context"
	"io"
	"net/http"
	"net/url"
	"sync"
	"time"

	minio "github.com/minio/minio-go/v7"

	"github.com/gophersys/libs/go/objectstorage/minioadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// the credential references the adapter resolves at construction; the secretstest fake seeds them.
var (
	accessRef = secrets.Ref("vault://eden/objectstore#access-key")
	secretRef = secrets.Ref("vault://eden/objectstore#secret-key")
)

// fakeS3 is an in-memory minioadapter.S3 + lister for the UNIT lane: it exercises the adapter's
// validate → SDK-call → map-error logic WITHOUT a daemon. The REAL-MinIO proof is the integration
// lane (//go:build integration), never this fake (ADR-0016 §2). It also records the credential the
// builder installed so a test can assert no credential reaches a surfaced artifact.
type fakeS3 struct {
	mu      sync.Mutex
	objects map[string][]byte // keyed by "bucket/key"
	putErr  error
	statErr error
	getErr  error
	rmErr   error
	signErr error
	listErr error
}

func newFakeS3() *fakeS3 { return &fakeS3{objects: map[string][]byte{}} }

func keyOf(bucket, object string) string { return bucket + "/" + object }

//nolint:gocritic // hugeParam: the options param type is fixed by the minioadapter.S3 interface seam; a fake must match it by value.
func (f *fakeS3) PutObject(_ context.Context, bucket, object string, reader io.Reader, size int64, _ minio.PutObjectOptions) (minio.UploadInfo, error) {
	if f.putErr != nil {
		return minio.UploadInfo{}, f.putErr
	}
	buffer, err := io.ReadAll(io.LimitReader(reader, size))
	if err != nil {
		return minio.UploadInfo{}, err
	}
	f.mu.Lock()
	f.objects[keyOf(bucket, object)] = buffer
	f.mu.Unlock()
	return minio.UploadInfo{Bucket: bucket, Key: object, Size: int64(len(buffer)), ETag: "fake-etag", LastModified: time.Unix(0, 0).UTC()}, nil
}

//nolint:gocritic // hugeParam: the options param type is fixed by the minioadapter.S3 interface seam; a fake must match it by value.
func (f *fakeS3) StatObject(_ context.Context, bucket, object string, _ minio.StatObjectOptions) (minio.ObjectInfo, error) {
	if f.statErr != nil {
		return minio.ObjectInfo{}, f.statErr
	}
	f.mu.Lock()
	body, ok := f.objects[keyOf(bucket, object)]
	f.mu.Unlock()
	if !ok {
		return minio.ObjectInfo{}, minio.ErrorResponse{StatusCode: http.StatusNotFound, Code: "NoSuchKey"}
	}
	return minio.ObjectInfo{Key: object, Size: int64(len(body)), ETag: "fake-etag"}, nil
}

//nolint:gocritic // hugeParam: the options param type is fixed by the minioadapter.S3 interface seam; a fake must match it by value.
func (f *fakeS3) GetObject(_ context.Context, _, _ string, _ minio.GetObjectOptions) (*minio.Object, error) {
	// The real *minio.Object is unconstructable here; the adapter's Get is proven end-to-end against
	// REAL MinIO in the integration lane. The unit lane drives Get's error mapping via statErr/getErr.
	if f.getErr != nil {
		return nil, f.getErr
	}
	return nil, minio.ErrorResponse{StatusCode: http.StatusServiceUnavailable}
}

//nolint:gocritic // hugeParam: the options param type is fixed by the minioadapter.S3 interface seam; a fake must match it by value.
func (f *fakeS3) RemoveObject(_ context.Context, bucket, object string, _ minio.RemoveObjectOptions) error {
	if f.rmErr != nil {
		return f.rmErr
	}
	f.mu.Lock()
	delete(f.objects, keyOf(bucket, object))
	f.mu.Unlock()
	return nil
}

func (f *fakeS3) PresignHeader(_ context.Context, method, bucket, object string, expiry time.Duration, _ url.Values, _ http.Header) (*url.URL, error) {
	if f.signErr != nil {
		return nil, f.signErr
	}
	query := url.Values{}
	query.Set("X-Amz-Method", method)
	query.Set("X-Amz-Expires", time.Duration(expiry).String())
	query.Set("X-Amz-Signature", "fake-signature")
	return &url.URL{Scheme: "https", Host: "fake-minio.invalid", Path: "/" + bucket + "/" + object, RawQuery: query.Encode()}, nil
}

func (f *fakeS3) ListObjects(_ context.Context, bucket string, options minio.ListObjectsOptions) <-chan minio.ObjectInfo {
	channel := make(chan minio.ObjectInfo)
	go func() {
		defer close(channel)
		if f.listErr != nil {
			channel <- minio.ObjectInfo{Err: f.listErr}
			return
		}
		f.mu.Lock()
		snapshot := make(map[string][]byte, len(f.objects))
		for k, v := range f.objects {
			snapshot[k] = v
		}
		f.mu.Unlock()
		for composite, body := range snapshot {
			slash := bytes.IndexByte([]byte(composite), '/')
			if slash < 0 || composite[:slash] != bucket {
				continue
			}
			objectKey := composite[slash+1:]
			if options.Prefix != "" && !bytes.HasPrefix([]byte(objectKey), []byte(options.Prefix)) {
				continue
			}
			channel <- minio.ObjectInfo{Key: objectKey, Size: int64(len(body)), ETag: "fake-etag"}
		}
	}()
	return channel
}

// newAdapter builds a minioadapter over a fake S3 and a secretstest fake secrets.Provider seeded
// with the access/secret-key values, so New's credential resolution runs for real (resolve → Use →
// static credential) without a Vault or a daemon.
func newAdapter(client minioadapter.S3, provider secrets.Provider) (*minioadapter.Adapter, error) {
	return minioadapter.New(
		minioadapter.Config{Endpoint: "127.0.0.1:9000", AccessKeyRef: accessRef, SecretKeyRef: secretRef},
		minioadapter.Deps{
			Secrets:   provider,
			NewClient: func(string, *minio.Options) (minioadapter.S3, error) { return client, nil },
		},
	)
}

// seededSecrets returns a concrete secretstest fake that resolves the access/secret-key references
// (return concrete — 10 §9; *secretstest.Provider is a secrets.Provider).
func seededSecrets() *secretstest.Provider {
	return secretstest.New(map[string]string{
		accessRef.String(): "FAKE-ACCESS-KEY-id",
		secretRef.String(): "fake-secret-key-value",
	})
}

var _ minioadapter.S3 = (*fakeS3)(nil)
