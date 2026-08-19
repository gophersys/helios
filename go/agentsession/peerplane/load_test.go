//go:build load

package peerplane

import (
	"context"
	"fmt"
	"os"
	"strconv"
	"sync/atomic"
	"testing"
	"time"

	"go.uber.org/goleak"
	"golang.org/x/sync/errgroup"

	"github.com/gophersys/libs/go/agentsession"
)

// meshN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, ADR-0020
// dimension (e)). The mesh is all-pairs, so send volume is N*(N-1); the default is kept
// modest for the in-process root and overridden by the verb.
func meshN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 1 {
			return n
		}
	}
	return 8
}

// loadClock is a real clock for the load orchestrator.
type loadClock struct{}

func (loadClock) Now() time.Time { return time.Now() }

// TestLoad_MeshDeliversOrBouncesUnderRaceNoDeadlock is THE deadlock proof (design §6 C2/C3,
// testMap #36, break #8). N peers join and each sends to every other peer — N*(N-1)
// concurrent sends under -race. Every message is either delivered (its recipient's drainer
// corroborates it with Received) or loudly bounced; the total that resolves must reach
// N*(N-1) inside a NAMED deadline, and the goroutine high-water must return to baseline.
//
// The deadline NAMES the deliver-on-pump hazard: the concurrency ruling is that the pump
// goroutine NEVER writes to the harness for peer delivery (a pump blocked in a stdin write
// stops draining stdout, the child's stdout pipe fills, and the write never returns — a
// permanent pipe deadlock that presents as a peer that is "thinking"). If a change moves
// delivery onto the pump goroutine, this mesh HANGS and the named deadline below is what
// catches it — never a silent timeout.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set.
func TestLoad_MeshDeliversOrBouncesUnderRaceNoDeadlock(t *testing.T) {
	defer goleak.VerifyNone(t)
	ctx := context.Background()
	n := meshN()

	orchestrator, err := New(Config{DeliveryDeadline: 2 * time.Second}, Deps{Clock: loadClock{}})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	t.Cleanup(func() { _ = orchestrator.Close(ctx) }) //nolint:errcheck // best-effort reap.

	names := make([]string, n)
	links := make([]agentsession.PeerLink, n)
	for i := range n {
		names[i] = fmt.Sprintf("peer-%03d", i)
		link, joinErr := orchestrator.Join(ctx, names[i], "")
		if joinErr != nil {
			t.Fatalf("Join %s: %v", names[i], joinErr)
		}
		links[i] = link
	}

	target := int64(n * (n - 1))
	var resolved atomic.Int64
	done := make(chan struct{})

	// One drainer per peer: it takes delivery, corroborates it to the root (Received), and
	// counts every message that resolves (a real delivery or an in-band bounce).
	drainCtx, stopDrainers := context.WithCancel(ctx)
	defer stopDrainers()
	for i := range n {
		link := links[i]
		go func() {
			for {
				select {
				case <-drainCtx.Done():
					return
				case message := <-link.Inbound():
					link.Received(message.MsgID)
					if resolved.Add(1) >= target {
						select {
						case <-done:
						default:
							close(done)
						}
					}
				}
			}
		}()
	}

	// N*(N-1) concurrent sends under -race.
	group, sendCtx := errgroup.WithContext(ctx)
	for from := range n {
		for to := range n {
			if from == to {
				continue
			}
			from, to := from, to
			group.Go(func() error {
				_, sendErr := links[from].Send(sendCtx, agentsession.PeerMessage{
					From: names[from], To: names[to],
					Body: fmt.Sprintf("%s->%s", names[from], names[to]),
				})
				return sendErr
			})
		}
	}
	if err := group.Wait(); err != nil {
		t.Fatalf("a concurrent Send failed: %v", err)
	}

	const deliverDeadline = 20 * time.Second
	select {
	case <-done:
		// every message resolved
	case <-time.After(deliverDeadline):
		t.Fatalf("deliver-on-pump deadlock: only %d of %d mesh messages delivered-or-bounced within %s — "+
			"the deliver goroutine blocked (delivery was moved onto the pump goroutine, whose harness write never returned)",
			resolved.Load(), target, deliverDeadline)
	}
}
