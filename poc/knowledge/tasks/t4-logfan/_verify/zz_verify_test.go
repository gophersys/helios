package logfan_test

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"strings"
	"testing"

	logfan "example.helios/logfan"
)

func mustRing(t *testing.T, capacity int) *logfan.Ring {
	t.Helper()
	r, err := logfan.NewRing(capacity)
	if err != nil {
		t.Fatalf("NewRing(%d): %v", capacity, err)
	}
	return r
}

func messages(records []slog.Record) []string {
	var out []string
	for _, r := range records {
		out = append(out, r.Message)
	}
	return out
}

func TestVerifyFanOutDeliversToAllHandlers(t *testing.T) {
	ringA := mustRing(t, 10)
	var buf bytes.Buffer
	jsonHandler := slog.NewJSONHandler(&buf, &slog.HandlerOptions{Level: slog.LevelInfo})

	logger, err := logfan.New(ringA, jsonHandler)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	logger.Info("first", "k", 1)
	logger.Warn("second")

	got := messages(ringA.Records())
	if len(got) != 2 || got[0] != "first" || got[1] != "second" {
		t.Fatalf("ring messages = %v; want [first second]", got)
	}

	lines := strings.Split(strings.TrimSpace(buf.String()), "\n")
	if len(lines) != 2 {
		t.Fatalf("json handler got %d lines; want 2", len(lines))
	}
	var entry map[string]any
	if err := json.Unmarshal([]byte(lines[0]), &entry); err != nil {
		t.Fatalf("json line: %v", err)
	}
	if entry["msg"] != "first" {
		t.Fatalf("json msg = %v; want first", entry["msg"])
	}
}

func TestVerifyRingEvictsOldestFirst(t *testing.T) {
	ring := mustRing(t, 2)
	logger, err := logfan.New(ring)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	logger.Info("a")
	logger.Info("b")
	logger.Info("c")

	got := messages(ring.Records())
	if len(got) != 2 || got[0] != "b" || got[1] != "c" {
		t.Fatalf("ring messages = %v; want [b c] (oldest first)", got)
	}
}

func TestVerifyRecordsReturnsACopy(t *testing.T) {
	ring := mustRing(t, 4)
	logger, _ := logfan.New(ring)
	logger.Info("a")
	logger.Info("b")

	first := ring.Records()
	first[0] = slog.Record{} // mutate the copy
	second := ring.Records()
	if second[0].Message != "a" {
		t.Fatal("mutating the slice returned by Records() affected the ring")
	}
}

func TestVerifyValidation(t *testing.T) {
	if _, err := logfan.NewRing(0); err == nil {
		t.Fatal("NewRing(0): want error")
	}
	if _, err := logfan.New(); err == nil {
		t.Fatal("New with no handlers: want error")
	}
}

func TestVerifyRingConcurrentUse(t *testing.T) {
	ring := mustRing(t, 64)
	logger, _ := logfan.New(ring)
	done := make(chan struct{})
	for i := 0; i < 8; i++ {
		go func() {
			defer func() { done <- struct{}{} }()
			for j := 0; j < 50; j++ {
				logger.Info("concurrent")
			}
		}()
	}
	for i := 0; i < 8; i++ {
		<-done
	}
	if got := len(ring.Records()); got != 64 {
		t.Fatalf("ring holds %d records; want 64 (capacity)", got)
	}
}
