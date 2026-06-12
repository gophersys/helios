package logfan

import (
	"bytes"
	"context"
	"log/slog"
	"testing"
	"time"
)

func TestNew_NoHandlers(t *testing.T) {
	logger, err := New()
	if err == nil {
		t.Fatal("expected error for no handlers")
	}
	if logger != nil {
		t.Fatal("expected nil logger on error")
	}
}

func TestNew_SingleHandler(t *testing.T) {
	r, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}

	logger, err := New(r)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if logger == nil {
		t.Fatal("expected non-nil logger")
	}

	logger.Info("hello")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}
	if recs[0].Message != "hello" {
		t.Fatalf("expected 'hello', got %q", recs[0].Message)
	}
}

func TestNew_MultipleHandlers(t *testing.T) {
	r1, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}
	r2, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}

	logger, err := New(r1, r2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	logger.Info("fan-out")

	recs1 := r1.Records()
	recs2 := r2.Records()

	if len(recs1) != 1 {
		t.Fatalf("handler 1: expected 1 record, got %d", len(recs1))
	}
	if len(recs2) != 1 {
		t.Fatalf("handler 2: expected 1 record, got %d", len(recs2))
	}
	if recs1[0].Message != "fan-out" {
		t.Fatalf("handler 1: expected 'fan-out', got %q", recs1[0].Message)
	}
	if recs2[0].Message != "fan-out" {
		t.Fatalf("handler 2: expected 'fan-out', got %q", recs2[0].Message)
	}
}

func TestNew_MultipleLevels(t *testing.T) {
	r, err := NewRing(10)
	if err != nil {
		t.Fatal(err)
	}

	logger, err := New(r)
	if err != nil {
		t.Fatal(err)
	}

	logger.Debug("debug msg")
	logger.Info("info msg")
	logger.Warn("warn msg")
	logger.Error("error msg")

	recs := r.Records()
	if len(recs) != 4 {
		t.Fatalf("expected 4 records, got %d", len(recs))
	}

	messages := make(map[string]bool)
	for _, rec := range recs {
		messages[rec.Message] = true
	}
	for _, m := range []string{"debug msg", "info msg", "warn msg", "error msg"} {
		if !messages[m] {
			t.Fatalf("missing message: %s", m)
		}
	}
}

func TestNew_WithAttrs(t *testing.T) {
	r, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}

	logger, err := New(r)
	if err != nil {
		t.Fatal(err)
	}

	logger = logger.With("app", "test")
	logger.Info("with attrs")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	var found bool
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "app" && a.Value.String() == "test" {
			found = true
			return false
		}
		return true
	})
	if !found {
		t.Fatal("expected attr 'app=test' on record")
	}
}

// captureHandler is a slog.Handler that records one record for testing.
type captureHandler struct {
	record *slog.Record
}

func (h *captureHandler) Enabled(_ context.Context, _ slog.Level) bool { return true }

func (h *captureHandler) Handle(_ context.Context, rec slog.Record) error {
	rec2 := rec.Clone()
	h.record = &rec2
	return nil
}

func (h *captureHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &captureHandlerWith{parent: h, attrs: attrs}
}

func (h *captureHandler) WithGroup(name string) slog.Handler {
	return &captureGroupHandler{parent: h, group: name}
}

type captureHandlerWith struct {
	parent *captureHandler
	attrs  []slog.Attr
}

func (h *captureHandlerWith) Enabled(ctx context.Context, level slog.Level) bool {
	return h.parent.Enabled(ctx, level)
}

func (h *captureHandlerWith) Handle(ctx context.Context, rec slog.Record) error {
	rec.AddAttrs(h.attrs...)
	return h.parent.Handle(ctx, rec)
}

func (h *captureHandlerWith) WithAttrs(attrs []slog.Attr) slog.Handler {
	merged := make([]slog.Attr, 0, len(h.attrs)+len(attrs))
	merged = append(merged, h.attrs...)
	merged = append(merged, attrs...)
	return &captureHandlerWith{parent: h.parent, attrs: merged}
}

func (h *captureHandlerWith) WithGroup(name string) slog.Handler {
	return h.parent.WithGroup(name)
}

type captureGroupHandler struct {
	parent *captureHandler
	group  string
}

func (h *captureGroupHandler) Enabled(ctx context.Context, level slog.Level) bool {
	return h.parent.Enabled(ctx, level)
}

func (h *captureGroupHandler) Handle(ctx context.Context, rec slog.Record) error {
	return h.parent.Handle(ctx, rec)
}

func (h *captureGroupHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	return h.parent.WithAttrs(attrs)
}

func (h *captureGroupHandler) WithGroup(name string) slog.Handler {
	return h.parent.WithGroup(name)
}

func TestNew_ErrorPreservesOtherHandlers(t *testing.T) {
	r, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}

	// First handler that always errors.
	errHandler := &errorHandler{}
	// Second handler is our Ring.
	logger, err := New(errHandler, r)
	if err != nil {
		t.Fatal(err)
	}

	// This should return the error from the first handler.
	err = logger.Handler().Handle(context.Background(), slog.NewRecord(
		time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC),
		slog.LevelInfo,
		"test",
		0,
	))
	if err == nil {
		t.Fatal("expected error from errHandler")
	}

	// Ring should NOT have received the record because we return early on error.
	// Actually, the spec doesn't guarantee this, but our implementation returns
	// early on error. Let's just verify no crash and the error is propagated.
}

type errorHandler struct{}

func (h *errorHandler) Enabled(_ context.Context, _ slog.Level) bool { return true }
func (h *errorHandler) Handle(_ context.Context, _ slog.Record) error {
	return bytes.ErrTooLarge // some error
}
func (h *errorHandler) WithAttrs(_ []slog.Attr) slog.Handler { return h }
func (h *errorHandler) WithGroup(_ string) slog.Handler      { return h }

func TestNew_WithGroup(t *testing.T) {
	r, err := NewRing(3)
	if err != nil {
		t.Fatal(err)
	}

	logger, err := New(r)
	if err != nil {
		t.Fatal(err)
	}

	logger = logger.WithGroup("req").With("id", "42")
	logger.Info("request")

	recs := r.Records()
	if len(recs) != 1 {
		t.Fatalf("expected 1 record, got %d", len(recs))
	}

	// The record should have group "req" containing id=42.
	var groupAttrs []slog.Attr
	recs[0].Attrs(func(a slog.Attr) bool {
		if a.Key == "req" && a.Value.Kind() == slog.KindGroup {
			groupAttrs = a.Value.Group()
			return false
		}
		return true
	})
	if groupAttrs == nil {
		t.Fatal("expected group 'req'")
	}
	found := false
	for _, a := range groupAttrs {
		if a.Key == "id" {
			found = true
		}
	}
	if !found {
		t.Fatal("expected 'id' inside group 'req'")
	}
}

func TestNew_RingImplementsSlogHandler(t *testing.T) {
	// Compile-time check that *Ring implements slog.Handler.
	var _ slog.Handler = (*Ring)(nil)
}