// Package limitedbuffer is the bounded output sink both adapters use to capture an Exec/Run
// workload's stdout/stderr. The contract documents ExecResult.Stdout/Stderr as BOUNDED
// (types.go:131-134: "bounded ... large output streams via a Run instead"), but a plain
// bytes.Buffer fed by an external process's output is UNBOUNDED — a chatty workload can grow it
// without limit and OOM the control plane. A Buffer caps the captured bytes at Cap and sets a
// Truncated flag once the cap is hit, so the documented bound is a real, enforced invariant rather
// than a comment. For genuinely large output the contract directs callers to Run.Logs streaming
// (the docker Run path drains asynchronously); this sink protects the buffered Exec/Run-drain path.
package limitedbuffer

import "sync"

// DefaultCap is the documented ceiling on captured Exec/Run output: 4 MiB. It is generous for the
// readiness-probe / git-invocation / one-shot-command workloads Exec serves while bounding a
// runaway emitter. A workload that needs more uses Run.Logs streaming (the contract's escape hatch
// for large output). It is exported as a named constant so the bound is documented, not implicit.
const DefaultCap = 4 << 20

// Buffer is a goroutine-safe bounded byte sink. Writes accumulate until Cap is reached; further
// bytes are DROPPED (not stored) and Truncated is recorded. It is safe for the docker Run drain
// (a goroutine writes while Logs/Status read) — the mutex guards every field. The zero value is
// NOT usable; construct with New so Cap is set.
type Buffer struct {
	mu        sync.Mutex
	cap       int
	buf       []byte
	truncated bool
}

// New returns a Buffer capped at limit bytes. A non-positive limit is replaced with DefaultCap so a
// caller can pass 0 to mean "the documented default".
func New(limit int) *Buffer {
	if limit <= 0 {
		limit = DefaultCap
	}
	return &Buffer{cap: limit}
}

// Write appends p up to the remaining capacity, dropping any overflow and recording truncation.
// It always reports len(p) written with a nil error so it is a drop-in io.Writer for io.Copy /
// StdCopy: signaling a short write would abort the drain and lose the workload's exit code, but
// the WHOLE point is to keep draining (so the process is not blocked on a full pipe) while bounding
// what we RETAIN. The bytes past the cap are read off the stream and discarded.
func (b *Buffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	remaining := b.cap - len(b.buf)
	if remaining <= 0 {
		if len(p) > 0 {
			b.truncated = true
		}
		return len(p), nil
	}
	if len(p) > remaining {
		b.buf = append(b.buf, p[:remaining]...)
		b.truncated = true
		return len(p), nil
	}
	b.buf = append(b.buf, p...)
	return len(p), nil
}

// Bytes returns a COPY of the captured (bounded) bytes — a copy because the docker Run drain
// writes from its own goroutine while Status/Logs may read, so handing out the backing slice would
// race.
func (b *Buffer) Bytes() []byte {
	b.mu.Lock()
	defer b.mu.Unlock()
	return append([]byte(nil), b.buf...)
}

// Len reports the number of RETAINED bytes (≤ Cap).
func (b *Buffer) Len() int {
	b.mu.Lock()
	defer b.mu.Unlock()
	return len(b.buf)
}

// Truncated reports whether any byte was dropped because the cap was reached — the signal a caller
// surfaces (e.g. into ExecResult.Detail) so the consumer knows the output is bounded, not whole.
func (b *Buffer) Truncated() bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.truncated
}
