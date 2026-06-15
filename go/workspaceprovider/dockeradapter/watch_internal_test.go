// White-box unit tests for the docker supervision watcher's PURE normalization — the
// Action→State/Condition mapping, the terminal cgroup OOM/exit fold, and the event drain loop —
// driven against a tiny fake dockerClient so the branches are exercised DETERMINISTICALLY (a real
// OOM-kill's timing is asserted by the integration lane; here we prove the normalization table for
// every action without a daemon). This complements, never replaces, the real-substrate proof.
//
//nolint:testpackage // the dockerClient seam + the watch normalizers are unexported by design (05 §1); white-box is the only way to unit-test the per-action mapping without a daemon.
package dockeradapter

import (
	"context"
	stderrors "errors"
	"io"
	"testing"
	"time"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/events"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/api/types/network"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/internal/watchloop"
	ocispec "github.com/opencontainers/image-spec/specs-go/v1"
)

// watchFakeClient is a minimal dockerClient for the watcher white-box tests: it serves a scripted
// event stream from Events and a scripted ContainerInspect (for the terminal OOM/exit fold). Every
// other seam method is an unused stub (the watcher never calls them).
type watchFakeClient struct {
	eventCh   chan events.Message
	errCh     chan error
	inspectFn func(id string) (container.InspectResponse, error)
}

func newWatchFakeClient() *watchFakeClient {
	return &watchFakeClient{
		eventCh: make(chan events.Message, 8),
		errCh:   make(chan error, 1),
	}
}

func (f *watchFakeClient) Events(_ context.Context, _ events.ListOptions) (messages <-chan events.Message, errs <-chan error) {
	return f.eventCh, f.errCh
}

func (f *watchFakeClient) ContainerInspect(_ context.Context, id string) (container.InspectResponse, error) {
	if f.inspectFn != nil {
		return f.inspectFn(id)
	}
	return container.InspectResponse{}, nil
}

// errUnusedWatchSeam is returned by the watcher fake's unused stream stubs so they never return a
// (nil, nil) the nilnil linter rejects — the watcher never calls them, so the value is inert.
var errUnusedWatchSeam = stderrors.New("dockeradapter watch fake: seam method not used by the watcher")

// Unused dockerClient seam methods follow — the watcher never calls them.

func (f *watchFakeClient) ImagePull(context.Context, string, image.PullOptions) (io.ReadCloser, error) {
	return nil, errUnusedWatchSeam
}

func (f *watchFakeClient) ImageList(context.Context, image.ListOptions) ([]image.Summary, error) {
	return nil, nil
}

func (f *watchFakeClient) ImageRemove(context.Context, string, image.RemoveOptions) ([]image.DeleteResponse, error) {
	return nil, nil
}

func (f *watchFakeClient) NetworkCreate(context.Context, string, network.CreateOptions) (network.CreateResponse, error) {
	return network.CreateResponse{}, nil
}

func (f *watchFakeClient) NetworkList(context.Context, network.ListOptions) ([]network.Summary, error) {
	return nil, nil
}
func (f *watchFakeClient) NetworkRemove(context.Context, string) error { return nil }
func (f *watchFakeClient) ContainerCreate(context.Context, *container.Config, *container.HostConfig, *network.NetworkingConfig, *ocispec.Platform, string) (container.CreateResponse, error) {
	return container.CreateResponse{}, nil
}

func (f *watchFakeClient) ContainerStart(context.Context, string, container.StartOptions) error {
	return nil
}

func (f *watchFakeClient) ContainerList(context.Context, container.ListOptions) ([]container.Summary, error) {
	return nil, nil
}

func (f *watchFakeClient) ContainerRemove(context.Context, string, container.RemoveOptions) error {
	return nil
}

func (f *watchFakeClient) ContainerStats(context.Context, string, bool) (container.StatsResponseReader, error) {
	return container.StatsResponseReader{}, nil
}

func (f *watchFakeClient) ContainerLogs(context.Context, string, container.LogsOptions) (io.ReadCloser, error) {
	return nil, errUnusedWatchSeam
}

func (f *watchFakeClient) ContainerExecCreate(context.Context, string, container.ExecOptions) (container.ExecCreateResponse, error) {
	return container.ExecCreateResponse{}, nil
}

func (f *watchFakeClient) ContainerExecAttach(context.Context, string, container.ExecAttachOptions) (types.HijackedResponse, error) {
	return types.HijackedResponse{}, nil
}

func (f *watchFakeClient) ContainerExecInspect(context.Context, string) (container.ExecInspect, error) {
	return container.ExecInspect{}, nil
}

func (f *watchFakeClient) CopyToContainer(context.Context, string, string, io.Reader, container.CopyToContainerOptions) error {
	return nil
}

func (f *watchFakeClient) CopyFromContainer(context.Context, string, string) (io.ReadCloser, container.PathStat, error) {
	return nil, container.PathStat{}, nil
}
func (f *watchFakeClient) Ping(context.Context) (types.Ping, error) { return types.Ping{}, nil }
func (f *watchFakeClient) Close() error                             { return nil }

// ownerActor builds an events.Actor whose attributes carry the ownership labels watchEventFrom
// reads to re-derive the workspace Handle.
func ownerActor(id, name string) events.Actor {
	return events.Actor{
		ID: id,
		Attributes: map[string]string{
			ownerLabel:   "true",
			nameLabel:    name,
			workdirLabel: "/workspace",
			orgLabel:     "org-w",
			projectLabel: "proj-w",
		},
	}
}

// TestWatchActionStateMapsEveryAction asserts the Action→State table is total over the supervised
// docker actions (the normalization the library re-derives EventKind from).
func TestWatchActionStateMapsEveryAction(t *testing.T) {
	t.Parallel()
	cases := map[events.Action]workspaceprovider.State{
		events.ActionStart:   workspaceprovider.StateRunning,
		events.ActionStop:    workspaceprovider.StateReady,
		events.ActionKill:    workspaceprovider.StateReady,
		events.ActionDie:     workspaceprovider.StateGone,
		events.ActionDestroy: workspaceprovider.StateGone,
		events.ActionOOM:     workspaceprovider.StateDegraded,
	}
	for action, want := range cases {
		if got := watchActionState(action); got != want {
			t.Errorf("watchActionState(%q) = %v, want %v", action, got, want)
		}
	}
	// An unknown action falls back to Ready (the coarse default; the State stays authoritative).
	if got := watchActionState(events.Action("paused")); got != workspaceprovider.StateReady {
		t.Errorf("watchActionState(paused) = %v, want Ready (default)", got)
	}
}

// TestWatchEventFromDerivesHandleAndState proves watchEventFrom re-derives the workspace Handle from
// the container's ownership labels and maps a start action to a Running raw WatchEvent.
func TestWatchEventFromDerivesHandleAndState(t *testing.T) {
	t.Parallel()
	a := &Adapter{namespace: "", prePulled: map[string]bool{}}
	msg := events.Message{Action: events.ActionStart, Actor: ownerActor("c1", "ws-w")}
	ev, ok := a.watchEventFrom(context.Background(), msg)
	if !ok {
		t.Fatalf("watchEventFrom returned ok=false for an owned container event")
	}
	if ev.Handle.Name() != "ws-w" {
		t.Errorf("watchEventFrom Handle.Name() = %q, want ws-w", ev.Handle.Name())
	}
	if ev.State != workspaceprovider.StateRunning {
		t.Errorf("watchEventFrom(start) State = %v, want Running", ev.State)
	}

	// An event with NO ownership name is skipped (a foreign container the filter let through).
	if _, ok := a.watchEventFrom(context.Background(), events.Message{Action: events.ActionStart, Actor: events.Actor{ID: "x"}}); ok {
		t.Errorf("watchEventFrom must skip an event with no ownership name")
	}
}

// TestWatchEventFromFoldsOOMOnDie proves the terminal fold: a die/oom event reads the container's
// cgroup State.OOMKilled and attaches ConditionOOMKilled + the native reason — the workload-pod OOM
// signal on the supervision path (the OD-15-a discriminator on the readable container).
func TestWatchEventFromFoldsOOMOnDie(t *testing.T) {
	t.Parallel()
	fake := newWatchFakeClient()
	fake.inspectFn = func(string) (container.InspectResponse, error) {
		return container.InspectResponse{ContainerJSONBase: &container.ContainerJSONBase{State: &container.State{OOMKilled: true, ExitCode: 137}}}, nil
	}
	a := &Adapter{client: fake, prePulled: map[string]bool{}}
	ev, ok := a.watchEventFrom(context.Background(), events.Message{Action: events.ActionDie, Actor: ownerActor("c1", "ws-oom")})
	if !ok {
		t.Fatalf("watchEventFrom returned ok=false for an owned die event")
	}
	if !hasCond(ev.Conditions, workspaceprovider.ConditionOOMKilled) {
		t.Errorf("a die with cgroup OOMKilled must attach ConditionOOMKilled, conditions = %v", ev.Conditions)
	}
	if ev.State != workspaceprovider.StateDegraded {
		t.Errorf("an OOM-killed container State = %v, want Degraded", ev.State)
	}
	if ev.Detail != "OOMKilled" {
		t.Errorf("the native OOM reason must ride Detail, got %q", ev.Detail)
	}

	// A NON-OOM die records the exit code in Detail without an OOM condition.
	fake.inspectFn = func(string) (container.InspectResponse, error) {
		return container.InspectResponse{ContainerJSONBase: &container.ContainerJSONBase{State: &container.State{ExitCode: 2}}}, nil
	}
	ev2, _ := a.watchEventFrom(context.Background(), events.Message{Action: events.ActionDie, Actor: ownerActor("c1", "ws-exit")})
	if hasCond(ev2.Conditions, workspaceprovider.ConditionOOMKilled) {
		t.Errorf("a non-OOM die must NOT attach ConditionOOMKilled")
	}
	if ev2.Detail != "die exit 2" {
		t.Errorf("a non-OOM die Detail = %q, want 'die exit 2'", ev2.Detail)
	}
}

// TestDrainEventsForwardsThenReconnectsOnError proves the drain loop forwards a normalized event
// onto the out channel, returns true (reconnect) on a stream error, and returns false (stop) on ctx
// cancellation — the supervision watch's resilience loop, deterministically.
func TestDrainEventsForwardsThenReconnectsOnError(t *testing.T) {
	t.Parallel()
	fake := newWatchFakeClient()
	a := &Adapter{client: fake, prePulled: map[string]bool{}}
	out := make(chan workspaceprovider.WatchEvent, 4)

	// Run drainEvents in a goroutine and SEQUENCE the inputs: send the event, observe it forwarded,
	// THEN send the error — so the assertion does not depend on select-ordering when both an event
	// and an error are simultaneously buffered (drainEvents' select is intentionally unordered).
	done := make(chan bool, 1)
	go func() { done <- a.drainEvents(context.Background(), fake.eventCh, fake.errCh, out) }()

	fake.eventCh <- events.Message{Action: events.ActionStart, Actor: ownerActor("c1", "ws-d")}
	ev := <-out // blocks until drainEvents forwards the start event
	if ev.Handle.Name() != "ws-d" {
		t.Errorf("forwarded event Handle.Name() = %q, want ws-d", ev.Handle.Name())
	}
	fake.errCh <- io.EOF // now signal the stream error
	if reconnect := <-done; !reconnect {
		t.Errorf("drainEvents must return true (reconnect) after a stream error")
	}

	// A canceled ctx → drainEvents returns false (stop), never blocking.
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if reconnect := a.drainEvents(ctx, fake.eventCh, fake.errCh, out); reconnect {
		t.Errorf("drainEvents must return false (stop) on a canceled ctx")
	}
}

// TestSleepWatchHonorsCtx proves the SHARED reconnect backoff (internal/watchloop.Sleep, now cited
// by both adapters) returns true after the delay elapses and false immediately when ctx is already
// canceled (so a canceled watch never sleeps out the backoff).
func TestSleepWatchHonorsCtx(t *testing.T) {
	t.Parallel()
	if !watchloop.Sleep(context.Background(), time.Millisecond) {
		t.Errorf("watchloop.Sleep must return true after the delay elapses")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if watchloop.Sleep(ctx, time.Hour) {
		t.Errorf("watchloop.Sleep must return false immediately on a canceled ctx")
	}
}

// hasCond reports whether conds carry want.
func hasCond(conds []workspaceprovider.Condition, want workspaceprovider.Condition) bool {
	for i := range conds {
		if conds[i] == want {
			return true
		}
	}
	return false
}
