package slogadapter_test

import (
	"context"
	"io"
	"testing"
	"time"

	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/slogadapter"
)

// sink keeps the benchmarked work from being elided by the compiler (ADR-0020 dimension
// (g)); `any` keeps it off any sentinel path.
//
//nolint:gochecknoglobals // benchmark sink must be package-level so the compiler cannot elide the measured work.
var sink any

// BenchmarkExport measures the slog adapter's hot path: rendering a resource-stamped,
// correlation-stamped Record to one JSON line (the Exporter seam the library drives off
// the hot path on Flush). Writing to io.Discard isolates the adapter's projection cost
// from real I/O. benchstat guards this HEAD vs .benchbaseline (> +10% fails).
func BenchmarkExport(b *testing.B) {
	exp := slogadapter.New(io.Discard)
	rec := observability.Record{
		Event: observability.Event{
			Time:     time.Unix(1700000000, 0).UTC(),
			Plane:    observability.PlaneAgent,
			Severity: observability.SeverityInfo,
			Name:     "cost.ledger",
			Fields: []observability.Field{
				observability.String("run.id", "run-1"),
				observability.Int64("tokens.in", 1200),
				observability.Bool("gate.passed", true),
				observability.Dur("wall.time", 5*time.Second),
			},
		},
		Resource: map[string]string{
			"service.name":                "eden-backend",
			"deployment.environment.name": "test",
		},
		TraceID: "trace-7",
		SpanID:  "span-7",
	}
	batch := []observability.Record{rec}
	ctx := context.Background()
	var err error
	b.ReportAllocs()
	for b.Loop() {
		err = exp.Export(ctx, batch)
	}
	sink = err
}
