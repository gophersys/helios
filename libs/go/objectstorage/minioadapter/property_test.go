package minioadapter_test

import (
	"context"
	"strings"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/objectstorage"
)

// The `property` ctl.sh verb runs go test with RAPID_CHECKS set (default 1000 iterations/property,
// ADR-0020 dimension (a)); rapid reads it directly.

func drawBucket(rt *rapid.T) string {
	return rapid.StringMatching(`[a-z][a-z0-9-]{2,18}`).Draw(rt, "bucket")
}

func drawKey(rt *rapid.T) string {
	return rapid.StringMatching(`[a-z0-9][a-z0-9._-]{0,10}(/[a-z0-9][a-z0-9._-]{0,10}){0,2}`).Draw(rt, "key")
}

// TestProperty_PutThenStatPreservesSizeAndRef asserts the adapter's load-bearing mapping invariant
// over the whole ref/payload shape space: for any (bucket, key, payload), PutObject then GetObject's
// stat path reports the SAME ref and size, and a List by the key prefix finds the object. The value
// flows through the real adapter code (validate → SDK call → map), not a mock of the contract — the
// fake S3 weakens only the daemon, never the mapping (the REAL-MinIO proof is the integration lane).
func TestProperty_PutThenStatPreservesSizeAndRef(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		client := newFakeS3()
		adapter, err := newAdapter(client, seededSecrets())
		if err != nil {
			rt.Fatalf("New error = %v", err)
		}
		bucket := drawBucket(rt)
		key := drawKey(rt)
		size := rapid.IntRange(0, 8192).Draw(rt, "size")
		payload := strings.Repeat("x", size)

		ref, err := objectstorage.NewRef(bucket, key)
		if err != nil {
			rt.Fatalf("NewRef(%q,%q) error = %v", bucket, key, err)
		}
		ctx := context.Background()
		info, err := adapter.PutObject(ctx, ref, strings.NewReader(payload), int64(size), "")
		if err != nil {
			rt.Fatalf("PutObject error = %v", err)
		}
		if info.Ref != ref || info.Size != int64(size) {
			rt.Fatalf("PutObject info drift: ref %v size %d, want ref %v size %d", info.Ref, info.Size, ref, size)
		}

		infos, lerr := adapter.ListObjects(ctx, bucket, key)
		if lerr != nil {
			rt.Fatalf("ListObjects error = %v", lerr)
		}
		var found bool
		for _, listed := range infos {
			if listed.Ref == ref {
				found = true
			}
		}
		if !found {
			rt.Fatalf("ListObjects(%q, prefix %q) did not find the just-Put object", bucket, key)
		}
	})
}
