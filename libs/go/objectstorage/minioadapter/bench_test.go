package minioadapter_test

import (
	"context"
	"net/http"
	"strings"
	"testing"

	minio "github.com/minio/minio-go/v7"

	"github.com/gophersys/libs/go/objectstorage"
)

// sink keeps the benchmarked work from being elided. `any` keeps it off any typed sentinel path
// (ADR-0020 §g); package-level so the optimizer cannot see across the benchmark boundary.
//
//nolint:gochecknoglobals // benchmark sinks must be package-level so the compiler cannot elide the measured work.
var sink any

// BenchmarkAdapterPut measures the adapter's Put hot path over the fake S3: map ref → SDK PutObject
// → project the UploadInfo onto a credential-free ObjectInfo. Isolated from real network latency
// (the fake returns in-memory) so it measures the ADAPTER's CPU/alloc cost, not MinIO's. The
// performance lane (`ctl.sh bench`/`bench-guard`, dimension (g)) guards it against the baseline.
func BenchmarkAdapterPut(b *testing.B) {
	adapter, err := newAdapter(newFakeS3(), seededSecrets())
	if err != nil {
		b.Fatalf("New error = %v", err)
	}
	ref, err := objectstorage.NewRef("eden", "bench/object.bin")
	if err != nil {
		b.Fatalf("NewRef error = %v", err)
	}
	const payload = "benchmark-object-payload-not-a-credential"
	ctx := context.Background()
	var (
		info objectstorage.ObjectInfo
		perr error
	)
	b.ReportAllocs()
	for b.Loop() {
		info, perr = adapter.PutObject(ctx, ref, strings.NewReader(payload), int64(len(payload)), "")
	}
	if perr != nil {
		b.Fatalf("PutObject error = %v", perr)
	}
	sink = info
}

// BenchmarkMapError measures the error-mapping spine the adapter runs on every failed SDK call
// (ToErrorResponse → status switch → typed taxonomy), the per-failure cost.
func BenchmarkMapError(b *testing.B) {
	client := newFakeS3()
	client.statErr = minio.ErrorResponse{StatusCode: http.StatusForbidden}
	adapter, err := newAdapter(client, seededSecrets())
	if err != nil {
		b.Fatalf("New error = %v", err)
	}
	ref, err := objectstorage.NewRef("eden", "k.bin")
	if err != nil {
		b.Fatalf("NewRef error = %v", err)
	}
	ctx := context.Background()
	var mapped error
	b.ReportAllocs()
	for b.Loop() {
		_, _, mapped = adapter.GetObject(ctx, ref)
	}
	sink = mapped
}
