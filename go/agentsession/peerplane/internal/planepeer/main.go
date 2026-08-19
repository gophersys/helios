// Command planepeer is a test-only stub: a real member PROCESS the peerplane socket integration
// test spawns to prove the plane over a real unix socket and real OS processes. It Dials the root,
// Joins under -name/-parent, drains its inbound (corroborating each delivery with Received), and
// exits on a signal. No vendor harness, no credential — so the proof runs in libs CI.
package main

import (
	"context"
	"flag"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gophersys/libs/go/agentsession/peerplane"
)

// realClock is the member's wall clock (the stub reads real time; the root owns the ledger).
type realClock struct{}

func (realClock) Now() time.Time { return time.Now() }

func main() {
	socket := flag.String("socket", "", "path to the root's unix socket")
	name := flag.String("name", "", "this member's tree name")
	parent := flag.String("parent", "", "this member's tree parent (\"\" == root)")
	flag.Parse()

	client, err := peerplane.Dial(
		peerplane.DialConfig{SocketPath: *socket, Name: *name, Parent: *parent, Harness: "planepeer"},
		peerplane.Deps{Clock: realClock{}},
	)
	if err != nil {
		os.Exit(1)
	}
	ctx := context.Background()
	link, err := client.Join(ctx, *name, *parent)
	if err != nil {
		os.Exit(1)
	}

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGTERM, syscall.SIGINT)
	for {
		select {
		case message := <-link.Inbound():
			link.Received(message.MsgID)
		case <-signals:
			_ = link.Close(ctx) //nolint:errcheck // best-effort leave before exit; a kill skips it and the root detects the dropped conn.
			return
		}
	}
}
