package objectstorage_test

import (
	"testing"

	"github.com/gophersys/libs/go/objectstorage"
	"github.com/gophersys/libs/go/objectstorage/objectstoragetest"
)

// conformanceBucket is the bucket the conformance suite Puts/Gets/Lists in. The fake Backend has
// no notion of bucket existence, so any non-empty token works; the integration lane creates a real
// bucket of the same shape.
const conformanceBucket = "eden-objectstorage-conformance"

// TestConformanceFakeBacked runs THE exported ObjectStore conformance suite (objectstorage.md §4)
// against a production *objectstorage.Client wired to the canonical in-memory fake Backend — the
// FAKE binding of the two-binding suite (08 §2). It proves the *Client mapping/validation logic
// holds the contract (round-trip, typed NotFound/Invalid, idempotent delete, list-by-prefix,
// credential-free presign) WITHOUT a daemon. The REAL-MinIO binding runs THIS SAME suite shape
// against an actual minio/minio container in minioadapter/integration_test.go — the fake weakens
// only the byte SOURCE, never the contract (ADR-0016 §2).
func TestConformanceFakeBacked(t *testing.T) {
	t.Parallel()
	objectstoragetest.RunStoreSuite(t, func() objectstorage.ObjectStore {
		// The fake is constructed WITH the canary credential (the in-memory analog of the secret key
		// the real adapter resolves), and the SAME value is threaded as the suite's redaction needle —
		// so the presign-redaction assertion is LIVE on the fake binding: it hunts for the exact value
		// the fake holds, not a stale constant.
		objectStore, err := objectstorage.New(
			objectstorage.Config{},
			objectstorage.Deps{Backend: objectstoragetest.NewBackendWithCredential(objectstoragetest.SeededCredentialCanary)},
		)
		if err != nil {
			t.Fatalf("objectstorage.New error = %v", err)
		}
		return objectStore
	}, conformanceBucket, objectstoragetest.SeededCredentialCanary)
}
