package objectstorage_test

import (
	"bytes"
	"context"
	"io"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/objectstorage"
	"github.com/gophersys/libs/go/objectstorage/objectstoragetest"
)

// The `property` ctl.sh verb runs go test with RAPID_CHECKS set (default 1000 iterations/property,
// ADR-0020 dimension (a)); rapid reads it directly.

// drawBucket / drawKey draw the components of a well-formed ObjectRef so every shape NewRef accepts
// is exercised. They avoid '/' in the bucket and whitespace/traversal in the key so the drawn ref
// is valid by construction.
func drawBucket(rt *rapid.T) string {
	return rapid.StringMatching(`[a-z][a-z0-9-]{2,20}`).Draw(rt, "bucket")
}

func drawKey(rt *rapid.T) string {
	return rapid.StringMatching(`[a-z0-9][a-z0-9._-]{0,12}(/[a-z0-9][a-z0-9._-]{0,12}){0,3}`).Draw(rt, "key")
}

func drawPayload(rt *rapid.T) []byte {
	return rapid.SliceOfN(rapid.Byte(), 0, 4096).Draw(rt, "payload")
}

// TestProperty_RefRoundTrips asserts the load-bearing ObjectRef fingerprint invariant over the
// whole shape space: for any (bucket, key) NewRef accepts, ParseRef(ref.String()) reproduces the
// SAME ObjectRef, and Bucket()/Key() return exactly the inputs. This is the parse↔render identity
// of dimension (a).
func TestProperty_RefRoundTrips(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		bucket := drawBucket(rt)
		key := drawKey(rt)
		ref, err := objectstorage.NewRef(bucket, key)
		if err != nil {
			rt.Fatalf("NewRef(%q,%q) rejected a well-formed ref: %v", bucket, key, err)
		}
		if ref.Bucket() != bucket || ref.Key() != key {
			rt.Fatalf("accessor drift: (%q,%q) != (%q,%q)", ref.Bucket(), ref.Key(), bucket, key)
		}
		parsed, perr := objectstorage.ParseRef(ref.String())
		if perr != nil {
			rt.Fatalf("ParseRef(%q) error = %v", ref.String(), perr)
		}
		if parsed != ref {
			rt.Fatalf("round-trip mismatch: %v != %v", parsed, ref)
		}
	})
}

// TestProperty_AnyPayloadRoundTripsByteForByte asserts that for ANY byte payload of any length in
// range, Put then Get through a fake-backed *Store returns EXACTLY those bytes — the byte-for-byte
// round-trip property over the whole payload space (the load-bearing object-store invariant). The
// value flows through the real *Store validation/delegation code, not a mock of the contract.
func TestProperty_AnyPayloadRoundTripsByteForByte(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		store, err := objectstorage.New(objectstorage.Config{}, objectstorage.Deps{Backend: objectstoragetest.NewBackend()})
		if err != nil {
			rt.Fatalf("New error = %v", err)
		}
		bucket := drawBucket(rt)
		key := drawKey(rt)
		payload := drawPayload(rt)
		ref, err := objectstorage.NewRef(bucket, key)
		if err != nil {
			rt.Fatalf("NewRef error = %v", err)
		}
		ctx := context.Background()
		if _, perr := store.Put(ctx, ref, bytes.NewReader(payload), objectstorage.PutOptions{Size: int64(len(payload))}); perr != nil {
			rt.Fatalf("Put error = %v", perr)
		}
		reader, _, gerr := store.Get(ctx, ref)
		if gerr != nil {
			rt.Fatalf("Get error = %v", gerr)
		}
		got, rerr := io.ReadAll(reader)
		if cerr := reader.Close(); cerr != nil {
			rt.Fatalf("reader.Close error = %v", cerr)
		}
		if rerr != nil {
			rt.Fatalf("ReadAll error = %v", rerr)
		}
		if !bytes.Equal(got, payload) {
			rt.Fatalf("round-trip drifted for %d-byte payload", len(payload))
		}
	})
}

// TestProperty_TraversingKeyIsAlwaysInvalid asserts the negative security invariant: any key
// containing a ".." path element is ALWAYS rejected by NewRef with an InvalidError — never accepted,
// never silently normalized. A path-traversal attempt must not reach a backend.
func TestProperty_TraversingKeyIsAlwaysInvalid(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		bucket := drawBucket(rt)
		prefix := drawKey(rt)
		suffix := drawKey(rt)
		traversing := prefix + "/../" + suffix
		_, err := objectstorage.NewRef(bucket, traversing)
		if !errors.IsType[objectstorage.InvalidError](err) {
			rt.Fatalf("NewRef(%q,%q) accepted a traversing key (or wrong error): %v", bucket, traversing, err)
		}
	})
}
