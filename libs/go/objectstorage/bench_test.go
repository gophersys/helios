package objectstorage_test

import (
	"bytes"
	"context"
	"io"
	"testing"

	"github.com/gophersys/libs/go/objectstorage"
	"github.com/gophersys/libs/go/objectstorage/objectstoragetest"
)

// The sinks below prevent the compiler from proving the benchmarked work dead and eliding it. `any`
// keeps them off any typed sentinel path (ADR-0020 §g); package-level so the optimizer cannot see
// across the benchmark boundary.
//
//nolint:gochecknoglobals // benchmark sinks must be package-level so the compiler cannot elide the measured work.
var (
	sink    any
	sinkRef objectstorage.ObjectRef
)

// BenchmarkNewRef measures the ref-construction/validation spine the port runs on every operation.
func BenchmarkNewRef(b *testing.B) {
	b.ReportAllocs()
	var (
		r   objectstorage.ObjectRef
		err error
	)
	for b.Loop() {
		r, err = objectstorage.NewRef("eden-bucket", "objects/nested/path/file.bin")
	}
	if err != nil {
		b.Fatalf("NewRef error = %v", err)
	}
	sinkRef = r
}

// BenchmarkPutGetRoundTrip measures the *Client hot path over the fake backend: validate → Put →
// validate → Get → drain. It isolates the store's CPU/alloc cost (the fake is in-memory) from real
// network latency, so the bench-guard tracks the ADAPTER-LAYER cost a consumer pays.
func BenchmarkPutGetRoundTrip(b *testing.B) {
	objectStore, err := objectstorage.New(objectstorage.Config{}, objectstorage.Deps{Backend: objectstoragetest.NewBackend()})
	if err != nil {
		b.Fatalf("New error = %v", err)
	}
	ref, err := objectstorage.NewRef("eden", "bench/object.bin")
	if err != nil {
		b.Fatalf("NewRef error = %v", err)
	}
	payload := objectstoragetest.SeededPayload
	ctx := context.Background()
	b.ReportAllocs()
	for b.Loop() {
		if _, perr := objectStore.Put(ctx, ref, bytes.NewReader(payload), objectstorage.PutOptions{Size: int64(len(payload))}); perr != nil {
			b.Fatalf("Put error = %v", perr)
		}
		reader, _, gerr := objectStore.Get(ctx, ref)
		if gerr != nil {
			b.Fatalf("Get error = %v", gerr)
		}
		if _, cerr := io.Copy(io.Discard, reader); cerr != nil {
			b.Fatalf("Copy error = %v", cerr)
		}
		if cerr := reader.Close(); cerr != nil {
			b.Fatalf("Close error = %v", cerr)
		}
	}
	sink = objectStore
}
