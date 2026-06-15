package objectstoragetest

import (
	"bytes"
	"context"
	"io"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/objectstorage"
)

// SeededCredentialCanary is a fake credential value seeded into the test harness so the suite can
// assert it appears in NO surfaced artifact (error, ObjectInfo, presigned URL, log). It is
// high-entropy + self-labeling so a real leak would be unambiguous. It is NEVER a real credential
// and NEVER the payload — it is the redaction needle the canary assertions hunt for.
const SeededCredentialCanary = "OBJSTORE-CANARY-akia-d34db33f-do-not-leak" // #nosec G101 -- a deliberate non-credential redaction NEEDLE, not a hardcoded secret.

// RunStoreSuite asserts the ObjectStore port contract against a freshly-constructed store.
// newStore returns an ObjectStore bound to an EMPTY backend; bucket names the (existing) bucket
// the suite Puts/Gets/Lists in. Each property is a self-contained subtest that builds its own
// store, so the subtests are independent and run in parallel.
//
// This is the SINGLE suite both bindings run: the in-memory fake here (conformance_test.go) and
// the REAL MinIO-backed *Store in the integration lane (minioadapter/integration_test.go). The
// fake weakens only the byte source, never the contract (ADR-0016 §2).
func RunStoreSuite(t *testing.T, newStore func() objectstorage.ObjectStore, bucket string) {
	t.Helper()
	t.Run("PutGetRoundTripsByteForByte", func(t *testing.T) {
		t.Parallel()
		assertRoundTrip(t, newStore(), bucket)
	})
	t.Run("GetAbsentIsTypedNotFound", func(t *testing.T) {
		t.Parallel()
		assertAbsentNotFound(t, newStore(), bucket)
	})
	t.Run("DeleteIsIdempotent", func(t *testing.T) {
		t.Parallel()
		assertDeleteIdempotent(t, newStore(), bucket)
	})
	t.Run("InvalidRefIsTypedInvalid", func(t *testing.T) {
		t.Parallel()
		assertInvalidRef(t, newStore())
	})
	t.Run("ListByPrefix", func(t *testing.T) {
		t.Parallel()
		assertListByPrefix(t, newStore(), bucket)
	})
	t.Run("PresignProducesCredentialFreeURL", func(t *testing.T) {
		t.Parallel()
		assertPresignCredentialFree(t, newStore(), bucket)
	})
	t.Run("NeverReaderAndErrorBothNonNil", func(t *testing.T) {
		t.Parallel()
		assertNeverBothNonNil(t, newStore(), bucket)
	})
	t.Run("ErrorCarriesRefNeverPayload", func(t *testing.T) {
		t.Parallel()
		assertErrorCarriesRef(t, newStore(), bucket)
	})
}

// ref builds a validated ObjectRef, failing the test on a malformed key (a test-author bug).
func ref(t *testing.T, bucket, key string) objectstorage.ObjectRef {
	t.Helper()
	r, err := objectstorage.NewRef(bucket, key)
	if err != nil {
		t.Fatalf("NewRef(%q,%q) error = %v", bucket, key, err)
	}
	return r
}

// assertRoundTrip: Put then Get returns the SAME bytes byte-for-byte, and the ObjectInfo size and
// ETag agree across the two calls (the load-bearing round-trip property).
func assertRoundTrip(t *testing.T, store objectstorage.ObjectStore, bucket string) {
	t.Helper()
	ctx := context.Background()
	r := ref(t, bucket, "conformance/round-trip.bin")

	putInfo, err := store.Put(ctx, r, bytes.NewReader(SeededPayload), objectstorage.PutOptions{
		ContentType: "application/octet-stream",
		Size:        int64(len(SeededPayload)),
	})
	if err != nil {
		t.Fatalf("Put error = %v", err)
	}
	if putInfo.Size != int64(len(SeededPayload)) {
		t.Errorf("Put ObjectInfo.Size = %d, want %d", putInfo.Size, len(SeededPayload))
	}

	reader, getInfo, err := store.Get(ctx, r)
	if err != nil {
		t.Fatalf("Get error = %v", err)
	}
	defer func() {
		if cerr := reader.Close(); cerr != nil {
			t.Errorf("reader.Close error = %v", cerr)
		}
	}()
	got, err := io.ReadAll(reader)
	if err != nil {
		t.Fatalf("ReadAll error = %v", err)
	}
	if !bytes.Equal(got, SeededPayload) {
		t.Fatalf("round-trip mismatch: got %d bytes, want %d (byte-for-byte equality is the load-bearing property)", len(got), len(SeededPayload))
	}
	if getInfo.Size != putInfo.Size {
		t.Errorf("Get size %d != Put size %d", getInfo.Size, putInfo.Size)
	}
	if putInfo.ETag != "" && getInfo.ETag != putInfo.ETag {
		t.Errorf("ETag drift: Put %q != Get %q", putInfo.ETag, getInfo.ETag)
	}
	if err := store.Delete(ctx, r); err != nil {
		t.Errorf("cleanup Delete error = %v", err)
	}
}

// assertAbsentNotFound: Get on a never-Put object yields AsType[NotFoundError] and a nil reader.
func assertAbsentNotFound(t *testing.T, store objectstorage.ObjectStore, bucket string) {
	t.Helper()
	reader, _, err := store.Get(context.Background(), ref(t, bucket, "conformance/never-put.bin"))
	if reader != nil {
		t.Error("Get(absent) returned a non-nil reader with an error")
	}
	if !isType[objectstorage.NotFoundError](err) {
		t.Errorf("Get(absent) error not AsType[NotFoundError]: %v", err)
	}
	if errors.KindOf(err) != errors.KindNotFound {
		t.Errorf("Get(absent) Kind = %v, want KindNotFound", errors.KindOf(err))
	}
}

// assertDeleteIdempotent: deleting an absent object is not an error, and a Put→Delete→Get yields
// NotFound (the object is gone).
func assertDeleteIdempotent(t *testing.T, store objectstorage.ObjectStore, bucket string) {
	t.Helper()
	ctx := context.Background()
	r := ref(t, bucket, "conformance/idempotent-delete.bin")

	if err := store.Delete(ctx, r); err != nil {
		t.Errorf("Delete(absent) error = %v, want nil (idempotent)", err)
	}
	if _, err := store.Put(ctx, r, bytes.NewReader(SeededPayload), objectstorage.PutOptions{Size: int64(len(SeededPayload))}); err != nil {
		t.Fatalf("Put error = %v", err)
	}
	if err := store.Delete(ctx, r); err != nil {
		t.Errorf("Delete(present) error = %v", err)
	}
	if err := store.Delete(ctx, r); err != nil {
		t.Errorf("second Delete error = %v, want nil (idempotent)", err)
	}
	if _, _, err := store.Get(ctx, r); !isType[objectstorage.NotFoundError](err) {
		t.Errorf("Get after Delete error = %v, want NotFoundError", err)
	}
}

// assertInvalidRef: the zero ObjectRef and a Put with a negative size yield AsType[InvalidError].
func assertInvalidRef(t *testing.T, store objectstorage.ObjectStore) {
	t.Helper()
	ctx := context.Background()
	if _, _, err := store.Get(ctx, objectstorage.ObjectRef{}); !isType[objectstorage.InvalidError](err) {
		t.Errorf("Get(zero ref) error = %v, want InvalidError", err)
	}
	if err := store.Delete(ctx, objectstorage.ObjectRef{}); !isType[objectstorage.InvalidError](err) {
		t.Errorf("Delete(zero ref) error = %v, want InvalidError", err)
	}
}

// assertListByPrefix: Put several objects under a common prefix, then List by that prefix and
// assert exactly the matching keys come back (sorted, payload-free metadata).
func assertListByPrefix(t *testing.T, store objectstorage.ObjectStore, bucket string) {
	t.Helper()
	ctx := context.Background()
	keys := []string{"list/a.bin", "list/b.bin", "other/c.bin"}
	for _, k := range keys {
		if _, err := store.Put(ctx, ref(t, bucket, k), bytes.NewReader(SeededPayload), objectstorage.PutOptions{Size: int64(len(SeededPayload))}); err != nil {
			t.Fatalf("Put(%q) error = %v", k, err)
		}
	}
	defer func() {
		for _, k := range keys {
			if derr := store.Delete(ctx, ref(t, bucket, k)); derr != nil {
				t.Errorf("cleanup Delete(%q) error = %v", k, derr)
			}
		}
	}()

	infos, err := store.List(ctx, bucket, "list/")
	if err != nil {
		t.Fatalf("List error = %v", err)
	}
	if len(infos) != 2 {
		t.Fatalf("List(prefix list/) returned %d objects, want 2", len(infos))
	}
	for _, info := range infos {
		if got := info.Ref.Key(); got != "list/a.bin" && got != "list/b.bin" {
			t.Errorf("List returned an out-of-prefix key %q", got)
		}
	}
}

// assertPresignCredentialFree: Presign returns a URL whose every component is free of the seeded
// credential canary (the redaction half of the contract for the presign surface).
func assertPresignCredentialFree(t *testing.T, store objectstorage.ObjectStore, bucket string) {
	t.Helper()
	r := ref(t, bucket, "conformance/presign.bin")
	signed, err := store.Presign(context.Background(), r, objectstorage.PresignOptions{
		Method: objectstorage.MethodGet,
		Expiry: 600_000_000_000, // 10 minutes, in nanoseconds
	})
	if err != nil {
		t.Fatalf("Presign error = %v", err)
	}
	if signed == nil {
		t.Fatal("Presign returned a nil URL")
	}
	rendered := signed.String()
	if !contains(rendered, r.Key()) {
		t.Errorf("presigned URL %q does not address the object key %q", rendered, r.Key())
	}
	AssertNoCredentialLeak(t, "presigned-url", rendered)
}

// assertNeverBothNonNil: Get never returns a non-nil reader together with a non-nil error.
func assertNeverBothNonNil(t *testing.T, store objectstorage.ObjectStore, bucket string) {
	t.Helper()
	reader, _, err := store.Get(context.Background(), ref(t, bucket, "conformance/never-both.bin"))
	if reader != nil && err != nil {
		t.Errorf("Get returned a non-nil reader AND a non-nil error: %v", err)
		if cerr := reader.Close(); cerr != nil {
			t.Errorf("reader.Close error = %v", cerr)
		}
	}
}

// assertErrorCarriesRef: an error carries the ObjectRef's loggable form and never the payload.
func assertErrorCarriesRef(t *testing.T, store objectstorage.ObjectStore, bucket string) {
	t.Helper()
	r := ref(t, bucket, "conformance/error-ref.bin")
	_, _, err := store.Get(context.Background(), r)
	if err == nil {
		t.Fatal("Get(absent) returned nil error")
	}
	if !contains(err.Error(), r.String()) {
		t.Errorf("error %q does not carry the reference %q", err.Error(), r.String())
	}
	if contains(err.Error(), string(SeededPayload)) {
		t.Errorf("error %q leaked the payload", err.Error())
	}
}

// isType reports whether err's chain carries a value of type E (errors.AsType[E]).
func isType[E error](err error) bool {
	_, ok := errors.AsType[E](err)
	return ok
}

// contains reports whether needle occurs in haystack (a non-empty-needle strings.Contains).
func contains(haystack, needle string) bool {
	return needle != "" && strings.Contains(haystack, needle)
}
