package kubernetesadapter

import (
	"context"
	"strings"
	"time"

	"github.com/gophersys/libs/go/workspaceprovider"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/watch"
)

// watchReconnectDelay bounds the backoff before re-establishing the pod watch after a transient
// fault / a closed watch channel, so the supervision channel stays open across an apiserver blip
// (the orchestrator never sees a silent gap — IOTEA's listenForK8sEvents reconnect, adapted).
const watchReconnectDelay = time.Second

// watchBuffer bounds the raw watch channel so a burst of pod transitions does not block the watch
// goroutine; the library's normalize fan-in applies the real backpressure.
const watchBuffer = 64

// Static assertion: *Adapter implements the OPTIONAL workspaceprovider.Watcher seam (it declares
// CapSupervise). The library type-asserts for this to drive Supervise's kubernetes half.
var _ workspaceprovider.Watcher = (*Adapter)(nil)

// Watch is the kubernetes half of the supervising provider's global label-filtered watch (ADR-0022
// §4). It FIRST reconciles-from-reality — listing the ownership domain by label and emitting a
// synthetic WatchEvent per existing workspace pod (so a control-plane restart rebuilds the
// supervised set from the LIVE apiserver) — then opens a CROSS-namespace label-filtered pod watch
// (Eden is namespace-per-workspace), normalizing each pod-phase transition + container-status OOM
// reason into a raw WatchEvent the LIBRARY maps onto the platform-neutral Event. A closed/faulted
// watch reconnects with backoff. The stream closes when ctx is canceled.
func (a *Adapter) Watch(ctx context.Context, selector workspaceprovider.Selector) (<-chan workspaceprovider.WatchEvent, error) {
	out := make(chan workspaceprovider.WatchEvent, watchBuffer)
	seed, err := a.List(ctx, selector)
	if err != nil {
		close(out)
		return nil, err
	}
	go a.runWatch(ctx, selector, seed, out)
	return out, nil
}

// runWatch emits the reconcile-from-reality seed, then loops the pod watch (reconnecting on a
// closed/faulted channel) until ctx is canceled, forwarding a raw WatchEvent per pod transition.
func (a *Adapter) runWatch(ctx context.Context, selector workspaceprovider.Selector, seed []workspaceprovider.Descriptor, out chan<- workspaceprovider.WatchEvent) {
	defer close(out)

	// 1) Reconcile-from-reality: one synthetic WatchEvent per already-existing workspace.
	for i := range seed {
		ev := workspaceprovider.WatchEvent{
			Handle: seed[i].Handle,
			Action: "Running",
			State:  seed[i].State,
			Detail: "reconcile-from-reality (existing pod)",
		}
		if !sendWatch(ctx, out, ev) {
			return
		}
	}

	// 2) Live stream: a cross-namespace label-filtered pod watch, reconnecting on close/fault.
	labelSelector := a.supervisionLabelSelector(selector)
	for {
		w, err := a.client.WatchPods(ctx, labelSelector)
		if err != nil {
			if !sleepWatchK8s(ctx, watchReconnectDelay) {
				return
			}
			continue
		}
		if !a.drainPodWatch(ctx, w, out) {
			w.Stop()
			return
		}
		w.Stop()
		// The watch channel closed (apiserver bookmark/timeout): reconnect after a backoff.
		if !sleepWatchK8s(ctx, watchReconnectDelay) {
			return
		}
	}
}

// drainPodWatch forwards normalized pod events until the watch channel closes (returns true to
// reconnect) or ctx is canceled (returns false to stop).
func (a *Adapter) drainPodWatch(ctx context.Context, w watch.Interface, out chan<- workspaceprovider.WatchEvent) bool {
	for {
		select {
		case <-ctx.Done():
			return false
		case event, ok := <-w.ResultChan():
			if !ok {
				return true // channel closed: reconnect
			}
			pod, isPod := event.Object.(*corev1.Pod)
			if !isPod {
				continue
			}
			ev, emit := a.watchEventFrom(event.Type, pod)
			if !emit {
				continue
			}
			if !sendWatch(ctx, out, ev) {
				return false
			}
		}
	}
}

// supervisionLabelSelector builds the cross-namespace pod label selector: the ownership label plus
// this adapter's namespace scope and the selector's tenancy labels (so the watch sees exactly the
// ownership domain, never another tenant's pods).
func (a *Adapter) supervisionLabelSelector(selector workspaceprovider.Selector) string {
	parts := []string{ownerLabel + "=true"}
	if a.namespace != "" {
		parts = append(parts, namespaceLabel+"="+labelValue(a.namespace))
	}
	for k, v := range selector.Labels {
		parts = append(parts, mapSelectorLabel(k)+"="+labelValue(v))
	}
	return strings.Join(parts, ",")
}

// watchEventFrom normalizes ONE pod watch event into a raw WatchEvent: it derives the workspace
// Handle from the pod's namespace + ownership labels, maps the pod phase (and a Deleted watch type)
// to a State + Action, and folds a container-status OOMKilled reason into ConditionOOMKilled — the
// NATIVE OOM discriminator the workload-pod (Entrypoint) model surfaces on the readable container,
// closing the OD-15 / §7 Q14 gap. A Pending pod with no fault emits nothing (emit=false) — the
// supervision stream reports transitions INTO a meaningful State, not every scheduling tick.
func (a *Adapter) watchEventFrom(eventType watch.EventType, pod *corev1.Pod) (workspaceprovider.WatchEvent, bool) {
	descSpec := descriptorSpec(pod.Labels)
	if descSpec.Name == "" {
		return workspaceprovider.WatchEvent{}, false
	}
	workDir := pod.Annotations[workdirAnnotation]
	if workDir == "" {
		workDir = "/workspace"
	}
	handle := a.handleFor(&descSpec, pod.Namespace, workDir)

	if eventType == watch.Deleted {
		return workspaceprovider.WatchEvent{
			Handle: handle,
			Action: "Deleted",
			State:  workspaceprovider.StateGone,
			Detail: "pod deleted",
		}, true
	}

	probe := normalizeProbe(pod)
	// A still-provisioning pod (Pending, no fault) is not a supervision-worthy transition yet.
	if probe.State == workspaceprovider.StateProvisioning {
		return workspaceprovider.WatchEvent{}, false
	}
	return workspaceprovider.WatchEvent{
		Handle:     handle,
		Action:     string(pod.Status.Phase),
		State:      probe.State,
		Conditions: probe.Conditions,
		Detail:     probe.Detail,
	}, true
}

// sendWatch forwards ev onto out, honoring ctx so a canceled watch never blocks on a full buffer
// with no reader (leak-free).
//
//nolint:gocritic // hugeParam: ev is the value forwarded onto the channel (a channel send copies regardless); passing it by value is the natural seam.
func sendWatch(ctx context.Context, out chan<- workspaceprovider.WatchEvent, ev workspaceprovider.WatchEvent) bool {
	select {
	case out <- ev:
		return true
	case <-ctx.Done():
		return false
	}
}

// sleepWatchK8s sleeps for d or returns false when ctx is canceled (the reconnect backoff).
func sleepWatchK8s(ctx context.Context, d time.Duration) bool {
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case <-timer.C:
		return true
	case <-ctx.Done():
		return false
	}
}
