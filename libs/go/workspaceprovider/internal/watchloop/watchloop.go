// Package watchloop holds the substrate-neutral supervision-watch primitives both adapters' Watch
// loops share: the raw-channel buffer size, the reconnect backoff, the ctx-honoring channel send,
// and the ctx-honoring sleep. These were verbatim-duplicated as send/sendWatch, sleepWatch/
// sleepWatchK8s, and the watchBuffer/watchReconnectDelay constants in dockeradapter and
// kubernetesadapter; they live ONCE here (one concept, one home — 10 §9) so the leak-free
// fan-out send and the reconnect backoff cannot drift between the two adapters.
package watchloop

import (
	"context"
	"time"

	"github.com/gophersys/libs/go/workspaceprovider"
)

// Buffer bounds the raw watch channel so a momentary burst of substrate events does not block the
// watch goroutine; the library's normalize fan-in applies the real backpressure.
const Buffer = 64

// ReconnectDelay bounds the backoff before re-establishing a faulted/closed watch stream, so the
// supervision channel stays open across a substrate blip (the orchestrator never sees a silent gap
// — IOTEA's reconnect, adapted).
const ReconnectDelay = time.Second

// Send forwards ev onto out, honoring ctx so a canceled watch never blocks on a full buffer with no
// reader (leak-free). It returns false when ctx is canceled (the caller stops the loop).
//
//nolint:gocritic // hugeParam: ev is the value forwarded onto the channel (a channel send copies regardless); passing it by value is the natural seam.
func Send(ctx context.Context, out chan<- workspaceprovider.WatchEvent, ev workspaceprovider.WatchEvent) bool {
	select {
	case out <- ev:
		return true
	case <-ctx.Done():
		return false
	}
}

// Sleep sleeps for d or returns false when ctx is canceled (the reconnect backoff).
func Sleep(ctx context.Context, d time.Duration) bool {
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-timer.C:
		return true
	case <-ctx.Done():
		return false
	}
}
