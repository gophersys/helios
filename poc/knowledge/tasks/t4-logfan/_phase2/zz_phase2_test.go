package logfan_test

import (
	"bytes"
	"context"
	"log/slog"
	"strings"
	"testing"

	logfan "example.helios/logfan"
)

func TestVerifyP2LeveledFiltersBelowMinimum(t *testing.T) {
	ring := mustRing(t, 10)
	var buf bytes.Buffer
	jsonHandler := slog.NewJSONHandler(&buf, &slog.HandlerOptions{Level: slog.LevelDebug})

	logger, err := logfan.NewLeveled(slog.LevelWarn, ring, jsonHandler)
	if err != nil {
		t.Fatalf("NewLeveled: %v", err)
	}
	logger.Info("dropped")
	logger.Warn("kept-warn")
	logger.Error("kept-error")

	got := messages(ring.Records())
	if len(got) != 2 || got[0] != "kept-warn" || got[1] != "kept-error" {
		t.Fatalf("ring messages = %v; want [kept-warn kept-error]", got)
	}
	if strings.Contains(buf.String(), "dropped") {
		t.Fatal("json handler received a record below the minimum level")
	}
	if !strings.Contains(buf.String(), "kept-warn") || !strings.Contains(buf.String(), "kept-error") {
		t.Fatalf("json handler missing kept records: %s", buf.String())
	}
}

func TestVerifyP2LeveledEnabled(t *testing.T) {
	ring := mustRing(t, 4)
	logger, err := logfan.NewLeveled(slog.LevelWarn, ring)
	if err != nil {
		t.Fatalf("NewLeveled: %v", err)
	}
	ctx := context.Background()
	if logger.Enabled(ctx, slog.LevelInfo) {
		t.Fatal("Enabled(Info) = true with minimum Warn; want false")
	}
	if !logger.Enabled(ctx, slog.LevelError) {
		t.Fatal("Enabled(Error) = false with minimum Warn; want true")
	}
}

func TestVerifyP2LeveledValidation(t *testing.T) {
	if _, err := logfan.NewLeveled(slog.LevelInfo); err == nil {
		t.Fatal("NewLeveled with no handlers: want error")
	}
}

func TestVerifyP2NewStillUnfiltered(t *testing.T) {
	ring := mustRing(t, 4)
	logger, err := logfan.New(ring)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	logger.Debug("debug-kept")
	got := messages(ring.Records())
	if len(got) != 1 || got[0] != "debug-kept" {
		t.Fatalf("plain New must stay unfiltered; ring = %v", got)
	}
}
