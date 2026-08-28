// Package logcursor holds the substrate-neutral, bounds-checked log-replay slice both adapters'
// RunDriver.Logs use. The cursor is a uint64 (workspaceprovider.LogCursor); it is bounds-checked
// AS a uint64 against the buffer length BEFORE the int conversion, so a cursor past the buffer (or
// one that would overflow int) clamps to the END rather than wrapping into a negative index. This
// is a real bounds check on the log-replay load path; it lived verbatim in both adapters and now
// lives ONCE (one concept, one home — 10 §9).
package logcursor

import "github.com/gophersys/libs/go/workspaceprovider"

// Replay returns the tail of buffer starting at the cursor, clamped to the end when the cursor is
// at or past the buffer length. The guard (from < len(buffer), compared as uint64) proves the int
// conversion cannot overflow or go negative.
func Replay(buffer []byte, from workspaceprovider.LogCursor) []byte {
	start := len(buffer)
	if uint64(from) < uint64(len(buffer)) {
		start = int(from) // #nosec G115 -- guarded: from < len(buffer) (an int), so the value provably fits in int; gosec cannot follow the uint64 guard.
	}
	return buffer[start:]
}
