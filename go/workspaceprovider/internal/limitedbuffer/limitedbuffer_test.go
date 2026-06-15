package limitedbuffer_test

import (
	"bytes"
	"io"
	"testing"

	"github.com/gophersys/libs/go/workspaceprovider/internal/limitedbuffer"
)

// TestBoundedCapTruncates is the executable form of the "ExecResult is bounded" invariant (finding
// #2): a writer that emits MORE than the cap retains at most Cap bytes and reports Truncated — it
// does NOT grow unbounded. WEAKEN-TO-CONFIRM: replace the Write body with an unbounded append (a
// plain bytes.Buffer) and len(b.Bytes()) becomes the full input, failing the len(<=cap) assertion.
func TestBoundedCapTruncates(t *testing.T) {
	t.Parallel()
	const limit = 1 << 10 // 1 KiB
	b := limitedbuffer.New(limit)

	// Emit 64 KiB through the buffer (the io.Copy drain path).
	emitted := bytes.Repeat([]byte("X"), 64<<10)
	n, err := io.Copy(b, bytes.NewReader(emitted))
	if err != nil {
		t.Fatalf("io.Copy into limitedbuffer: %v", err)
	}
	// Write reports the full length consumed (so the drain keeps going), but RETAINS only the cap.
	if n != int64(len(emitted)) {
		t.Errorf("io.Copy reported %d bytes consumed, want %d (the drain must not stall)", n, len(emitted))
	}
	if got := b.Len(); got != limit {
		t.Errorf("retained %d bytes, want exactly the cap %d (bounded, not unbounded)", got, limit)
	}
	if got := len(b.Bytes()); got > limit {
		t.Errorf("Bytes() returned %d bytes, exceeding the cap %d (UNBOUNDED — the OOM bug)", got, limit)
	}
	if !b.Truncated() {
		t.Errorf("Truncated() = false after exceeding the cap, want true (the bound must be signaled)")
	}
}

// TestUnderCapKeepsAll proves a workload UNDER the cap is captured whole and not flagged truncated
// (the common Exec case — a small command's output rides ExecResult intact).
func TestUnderCapKeepsAll(t *testing.T) {
	t.Parallel()
	b := limitedbuffer.New(1 << 20)
	want := []byte("exec-ok\n")
	if _, err := b.Write(want); err != nil {
		t.Fatalf("Write: %v", err)
	}
	if !bytes.Equal(b.Bytes(), want) {
		t.Errorf("Bytes() = %q, want %q (under-cap output must be whole)", b.Bytes(), want)
	}
	if b.Truncated() {
		t.Errorf("Truncated() = true for under-cap output, want false")
	}
}

// TestZeroCapUsesDefault proves New(0) falls back to the documented DefaultCap (so a caller can pass
// 0 to mean "the default bound").
func TestZeroCapUsesDefault(t *testing.T) {
	t.Parallel()
	b := limitedbuffer.New(0)
	over := bytes.Repeat([]byte("Y"), limitedbuffer.DefaultCap+4096)
	if _, err := b.Write(over); err != nil {
		t.Fatalf("Write: %v", err)
	}
	if b.Len() != limitedbuffer.DefaultCap {
		t.Errorf("New(0) retained %d bytes, want DefaultCap %d", b.Len(), limitedbuffer.DefaultCap)
	}
}
