package dockeradapter

import (
	"context"
	"strconv"

	"github.com/docker/docker/api/types/events"
	"github.com/docker/docker/api/types/filters"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/internal/watchloop"
)

// Static assertion: *Adapter implements the OPTIONAL workspaceprovider.Watcher seam (it declares
// CapSupervise). The library type-asserts for this to drive Supervise's docker half.
var _ workspaceprovider.Watcher = (*Adapter)(nil)

// Watch is the docker half of the supervising provider's global label-filtered watch (ADR-0022
// §4). It FIRST reconciles-from-reality — listing the ownership domain by label and emitting a
// synthetic WatchEvent per existing container (so a control-plane restart rebuilds the supervised
// set from the LIVE daemon) — then streams the daemon's filtered container event log, normalizing
// each docker action (start/die/stop/kill/destroy/oom) into a raw WatchEvent the LIBRARY maps onto
// the platform-neutral Event. A transient stream fault reconnects with backoff (the channel stays
// open). The stream closes when ctx is canceled.
func (a *Adapter) Watch(ctx context.Context, selector workspaceprovider.Selector) (<-chan workspaceprovider.WatchEvent, error) {
	out := make(chan workspaceprovider.WatchEvent, watchloop.Buffer)
	// Reconcile-from-reality up front: a List by the same ownership labels seeds the supervised
	// set from the live daemon BEFORE any live event, so a restart re-adopts what Eden authored.
	seed, err := a.List(ctx, selector)
	if err != nil {
		close(out)
		return nil, err
	}
	go a.runWatch(ctx, selector, seed, out)
	return out, nil
}

// runWatch emits the reconcile-from-reality seed, then loops the daemon event stream (reconnecting
// on a transient fault) until ctx is canceled, forwarding a raw WatchEvent per container action.
func (a *Adapter) runWatch(ctx context.Context, selector workspaceprovider.Selector, seed []workspaceprovider.Descriptor, out chan<- workspaceprovider.WatchEvent) {
	defer close(out)

	// 1) Reconcile-from-reality: one synthetic "running" WatchEvent per already-existing workspace.
	for i := range seed {
		ev := workspaceprovider.WatchEvent{
			Handle: seed[i].Handle,
			Action: "start",
			State:  seed[i].State,
			Detail: "reconcile-from-reality (existing container)",
		}
		if !watchloop.Send(ctx, out, ev) {
			return
		}
	}

	// 2) Live stream: the daemon's filtered container events, reconnecting on a transient fault.
	for {
		ch, errCh := a.client.Events(ctx, events.ListOptions{Filters: a.watchFilters(selector)})
		if !a.drainEvents(ctx, ch, errCh, out) {
			return
		}
		// A non-nil error closed the stream: back off and reconnect (unless ctx is done).
		if !watchloop.Sleep(ctx, watchloop.ReconnectDelay) {
			return
		}
	}
}

// drainEvents forwards normalized container events until the stream errors (returns true to
// reconnect) or ctx is canceled (returns false to stop).
func (a *Adapter) drainEvents(ctx context.Context, ch <-chan events.Message, errCh <-chan error, out chan<- workspaceprovider.WatchEvent) bool {
	for {
		select {
		case <-ctx.Done():
			return false
		case err := <-errCh:
			// io.EOF or a transient fault: signal the caller to reconnect after a backoff.
			_ = err
			return true
		case msg := <-ch:
			ev, ok := a.watchEventFrom(ctx, msg)
			if !ok {
				continue
			}
			if !watchloop.Send(ctx, out, ev) {
				return false
			}
		}
	}
}

// watchFilters builds the docker event filter: container events carrying the ownership label,
// scoped to this adapter's namespace + the selector's tenancy labels, for the lifecycle actions
// the supervision normalizes (start/die/stop/kill/destroy/oom).
func (a *Adapter) watchFilters(selector workspaceprovider.Selector) filters.Args {
	args := filters.NewArgs(
		filters.Arg("type", "container"),
		filters.Arg("label", ownerLabel+"=true"),
		filters.Arg("event", string(events.ActionStart)),
		filters.Arg("event", string(events.ActionDie)),
		filters.Arg("event", string(events.ActionStop)),
		filters.Arg("event", string(events.ActionKill)),
		filters.Arg("event", string(events.ActionDestroy)),
		filters.Arg("event", string(events.ActionOOM)),
	)
	if a.namespace != "" {
		args.Add("label", namespaceLabel+"="+a.namespace)
	}
	for k, v := range selector.Labels {
		args.Add("label", k+"="+v)
	}
	return args
}

// watchEventFrom normalizes ONE docker event message into a raw WatchEvent: it derives the
// workspace Handle from the container's labels, maps the action to a State, and (for a die/oom)
// inspects the container's cgroup State.OOMKilled + exit code to attach the ConditionOOMKilled
// discriminator and the native reason. ok=false when the message carries no ownership labels (a
// foreign container the filter let through, or a destroy with no labels).
//
//nolint:gocritic // hugeParam: msg is delivered by value off the docker SDK's events channel; the normalizer reads it once.
func (a *Adapter) watchEventFrom(ctx context.Context, msg events.Message) (workspaceprovider.WatchEvent, bool) {
	labels := msg.Actor.Attributes
	descSpec := descriptorSpec(labels)
	if descSpec.Name == "" {
		// A foreign container the filter let through, or an event whose actor carries no
		// ownership name (some destroy events strip labels) — not a supervised workspace.
		return workspaceprovider.WatchEvent{}, false
	}
	handle := a.handleFor(&descSpec, labels[workdirLabel])

	ev := workspaceprovider.WatchEvent{
		Handle: handle,
		Action: string(msg.Action),
		State:  watchActionState(msg.Action),
		Detail: string(msg.Action),
	}
	// On a die / oom, read the container's terminal cgroup state for the OOM discriminator + exit
	// code (docker sets State.OOMKilled on the container when any process in its cgroup — the PID-1
	// workload OR an exec child — is OOM-killed). This is the workload-pod OOM signal on the
	// supervision path (the same reading runDriver uses for a Run).
	if msg.Action == events.ActionDie || msg.Action == events.ActionOOM {
		a.foldTerminalDetail(ctx, msg.Actor.ID, &ev)
	}
	return ev, true
}

// foldTerminalDetail inspects a just-terminated container for its OOM-kill flag + exit code,
// attaching ConditionOOMKilled (+ the native reason) when the cgroup OOM-killed the workload, else
// recording the exit code in Detail. A best-effort inspect failure leaves the coarse action State.
func (a *Adapter) foldTerminalDetail(ctx context.Context, containerID string, ev *workspaceprovider.WatchEvent) {
	if containerID == "" {
		return
	}
	inspect, err := a.client.ContainerInspect(ctx, containerID)
	if err != nil || inspect.State == nil {
		return
	}
	if inspect.State.OOMKilled {
		ev.State = workspaceprovider.StateDegraded
		ev.Conditions = append(ev.Conditions, workspaceprovider.ConditionOOMKilled)
		ev.Detail = "OOMKilled"
		return
	}
	ev.Detail = "die exit " + strconv.Itoa(inspect.State.ExitCode)
}

// watchActionState maps a docker action to the lifecycle State it implies (the action string still
// rides Detail verbatim; the library re-derives EventKind from both).
func watchActionState(action events.Action) workspaceprovider.State {
	switch action {
	case events.ActionStart:
		return workspaceprovider.StateRunning
	case events.ActionStop, events.ActionKill:
		return workspaceprovider.StateReady
	case events.ActionDie:
		return workspaceprovider.StateGone
	case events.ActionDestroy:
		return workspaceprovider.StateGone
	case events.ActionOOM:
		return workspaceprovider.StateDegraded
	default:
		return workspaceprovider.StateReady
	}
}
