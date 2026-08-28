package watchloop_test

import (
	"context"
	"testing"
	"time"

	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/internal/watchloop"
)

func TestSleepHonorsCtx(t *testing.T) {
	t.Parallel()
	if !watchloop.Sleep(context.Background(), time.Millisecond) {
		t.Errorf("Sleep must return true after the delay elapses")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if watchloop.Sleep(ctx, time.Hour) {
		t.Errorf("Sleep must return false immediately on a canceled ctx")
	}
}

func TestSendHonorsCtx(t *testing.T) {
	t.Parallel()
	// A buffered channel accepts the send.
	out := make(chan workspaceprovider.WatchEvent, 1)
	if !watchloop.Send(context.Background(), out, workspaceprovider.WatchEvent{Action: "start"}) {
		t.Errorf("Send to a buffered channel must return true")
	}
	// A full channel + a canceled ctx returns false (no block, leak-free).
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if watchloop.Send(ctx, out, workspaceprovider.WatchEvent{Action: "die"}) {
		t.Errorf("Send on a full channel with a canceled ctx must return false (leak-free)")
	}
}
