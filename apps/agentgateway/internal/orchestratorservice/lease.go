package orchestratorservice

import (
	"context"
	"sync"
	"sync/atomic"
	"time"

	"github.com/gophersys/libs/go/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	coordinationv1client "k8s.io/client-go/kubernetes/typed/coordination/v1"
	corev1client "k8s.io/client-go/kubernetes/typed/core/v1"
	"k8s.io/client-go/tools/leaderelection"
	"k8s.io/client-go/tools/leaderelection/resourcelock"
)

// Lease is the single-leader seam guarding the reconcile loop: in a multi-instance
// deployment exactly ONE instance may drive reconcile (so two controllers never both
// provision the same Pending agent), and that instance is the lease holder. The service
// consults IsLeader before each pass; a non-leader instance ticks but skips the pass (it
// observes desired-state writes through its Manager verbs, but only the leader reconciles).
//
// It is exactly the shape a kubernetes coordination.k8s.io/v1 Lease binds (a real leader
// election), but the surface is deployment-neutral so the SAME service runs locally and in
// k8s with no change — only the injected Lease differs. One method, well under the ≤5 ceiling.
type Lease interface {
	// IsLeader reports whether THIS instance currently holds the reconcile lease. It honors
	// ctx so a real k8s-Lease implementation can refresh/renew under the deadline; the docker
	// no-op returns immediately. A non-leader return is NOT an error — it is the steady state
	// of every follower instance.
	IsLeader(ctx context.Context) (bool, error)
}

// dockerLease is the docker single-instance Lease: ALWAYS the leader. On docker the service is
// one process, so there is no election to lose — the lone instance reconciles every pass. The
// seam exists (rather than hard-coding leadership in the loop) precisely so the kubernetes
// deployment swaps in a real k8s Lease without touching the loop. Its zero value is usable.
type dockerLease struct{}

// IsLeader always reports true (the single docker instance is the sole, permanent leader). It
// never fails and never blocks.
func (dockerLease) IsLeader(context.Context) (bool, error) { return true, nil }

// static assertion: the docker no-op binds the Lease seam.
var _ Lease = dockerLease{}

// LeaseConfig is the immutable construction input for the kubernetes leader-election Lease (the
// configuration pattern: resolved once at the composition root, frozen here). Every field is
// resolved from the deployment environment by the command BEFORE NewKubernetesLease, so this
// package reads no env and the constructor stays pure (no apiserver dial).
type LeaseConfig struct {
	// LeaseName is the coordination.k8s.io/v1 Lease object NAME the replicas contend for (the
	// one election). All replicas of one orchestrator Deployment MUST name the identical Lease;
	// it is the election's identity. Required.
	LeaseName string
	// Namespace is the kubernetes namespace the Lease object lives in (the orchestrator's OWN
	// control-plane namespace, e.g. eden-system — NOT a per-project workspace namespace). The
	// orchestrator's Role/RoleBinding grant get/create/update on leases in THIS namespace.
	// Required.
	Namespace string
	// Identity is THIS replica's unique holder identity recorded in the Lease's holderIdentity
	// field (the pod name, from the downward API). Two replicas MUST present distinct identities
	// or the election cannot distinguish them. Required.
	Identity string

	// LeaseDuration is how long a non-leader waits without observing a renewal before it may
	// acquire the lease. Zero == defaultLeaseDuration. It MUST exceed RenewDeadline.
	LeaseDuration time.Duration
	// RenewDeadline is how long the acting leader retries renewal before giving up leadership.
	// Zero == defaultRenewDeadline. It MUST exceed RetryPeriod*1.2 (the election's jitter floor).
	RenewDeadline time.Duration
	// RetryPeriod is the interval clients wait between election actions. Zero == defaultRetryPeriod.
	RetryPeriod time.Duration
}

// the standard controller-manager election cadence (kube-controller-manager defaults): a 15s
// lease renewed within 10s, retried every 2s. They satisfy the library's invariant
// LeaseDuration > RenewDeadline > RetryPeriod*1.2, so a zero LeaseConfig field folds to a valid
// election rather than a NewLeaderElector validation error.
const (
	defaultLeaseDuration = 15 * time.Second
	defaultRenewDeadline = 10 * time.Second
	defaultRetryPeriod   = 2 * time.Second
)

// LeaseDependencies is the injected hexagon for the kubernetes Lease (accept interfaces): the
// two typed clients leaderelection's LeaseLock issues its get/create/update against. The
// composition root builds them from the SAME kubeconfig/in-cluster REST config the
// workspaceprovider kubernetes adapter uses (one cluster, one client family).
type LeaseDependencies struct {
	// Coordination issues the Lease object get/create/update (coordination.k8s.io/v1) — the
	// resource the election contends for. Required.
	Coordination coordinationv1client.CoordinationV1Interface
	// Events records the optional leadership-transition Event the LeaseLock emits; the election
	// runs without it (the LeaseLock tolerates a nil event recorder). Required for the client
	// family but never the value path.
	Events corev1client.CoreV1Interface
}

// KubernetesLease is the REAL coordination.k8s.io/v1 Lease binding of the Lease seam: it runs a
// client-go leaderelection election in the background and reports live leadership through
// IsLeader. Only the replica that currently holds the Lease object returns true, so only ONE
// replica's reconcile loop drives actual toward desired — the multi-node single-leader guarantee
// the service's Start consults before each pass. A non-leader replica still serves the read/
// admission Manager verbs; it just never reconciles.
//
// Lifecycle: Start launches the election (a background goroutine renewing the Lease); the
// returned cancel stops it and (when ReleaseOnCancel) releases the Lease so a peer acquires it
// promptly on a graceful shutdown. The zero value is unusable; construct via NewKubernetesLease.
type KubernetesLease struct {
	elector *leaderelection.LeaderElector

	// leading is the atomic leadership flag IsLeader reads, flipped true by OnStartedLeading and
	// false by OnStoppedLeading. The election goroutine writes it; IsLeader reads it — atomic so
	// the per-pass read needs no lock on the reconcile hot path.
	leading atomic.Bool

	mu      sync.Mutex
	started bool
	cancel  context.CancelFunc
}

// static assertion: the kubernetes Lease binds the Lease seam exactly like the docker no-op.
var _ Lease = (*KubernetesLease)(nil)

// NewKubernetesLease builds the kubernetes leader-election Lease over the coordination client.
// It is the pure constructor spine New(configuration, dependencies) -> (*KubernetesLease, error):
// it validates the wiring and constructs the LeaseLock + LeaderElector but performs NO apiserver
// I/O (the first Lease get/create happens when Start runs the election). A misconfigured wiring
// is a wrapped KindInvalid error naming the missing field; an election-config violation (the
// library's LeaseDuration > RenewDeadline > RetryPeriod invariant) is a wrapped KindInternal.
//
//nolint:gocritic // LeaseConfig is the frozen, copyable composition input (the configuration pattern); the constructor takes it by value.
func NewKubernetesLease(configuration LeaseConfig, dependencies LeaseDependencies) (*KubernetesLease, error) {
	if err := validateLeaseWiring(&configuration, &dependencies); err != nil {
		return nil, err
	}

	lock := &resourcelock.LeaseLock{
		LeaseMeta:  leaseMeta(configuration.Namespace, configuration.LeaseName),
		Client:     dependencies.Coordination,
		LockConfig: resourcelock.ResourceLockConfig{Identity: configuration.Identity},
	}

	lease := &KubernetesLease{}
	elector, err := leaderelection.NewLeaderElector(leaderelection.LeaderElectionConfig{
		Lock:            lock,
		LeaseDuration:   orDuration(configuration.LeaseDuration, defaultLeaseDuration),
		RenewDeadline:   orDuration(configuration.RenewDeadline, defaultRenewDeadline),
		RetryPeriod:     orDuration(configuration.RetryPeriod, defaultRetryPeriod),
		ReleaseOnCancel: true, // a graceful shutdown releases the Lease so a peer leads immediately
		Name:            configuration.LeaseName,
		Callbacks: leaderelection.LeaderCallbacks{
			// OnStartedLeading runs in the election goroutine the instant THIS replica acquires the
			// Lease; flipping the flag is all the seam needs (the service's Start consults IsLeader).
			OnStartedLeading: func(context.Context) { lease.leading.Store(true) },
			// OnStoppedLeading runs when leadership is lost (renewal failed, or Start's ctx canceled).
			// Clearing the flag makes IsLeader report false on the next pass, so the reconcile loop
			// stops driving actual — the at-most-one-leader guarantee under a network partition.
			OnStoppedLeading: func() { lease.leading.Store(false) },
		},
	})
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "orchestratorservice: build kubernetes leader elector", err)
	}
	lease.elector = elector
	return lease, nil
}

// Start launches the leader election in a background goroutine (the LeaderElector.Run loop that
// acquires + renews the Lease object) and returns a cancel that stops the election and releases
// the Lease (ReleaseOnCancel). It is the composition root's call — the command runs it once at
// startup and defers the cancel for a graceful shutdown. A second Start is a no-op returning the
// existing cancel (the election runs once per Lease). Start does NOT block: the election runs
// until cancel; IsLeader reports the live result throughout.
func (l *KubernetesLease) Start(ctx context.Context) context.CancelFunc {
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.started {
		return l.cancel
	}
	runCtx, cancel := context.WithCancel(ctx)
	l.cancel = cancel
	l.started = true
	go l.elector.Run(runCtx) // the election loop: acquire → renew → (on ctx cancel) release
	return cancel
}

// IsLeader reports whether THIS replica currently holds the Lease (the live election flag). The
// read is lock-free (an atomic flag) so the reconcile loop consults it every pass with no
// contention. ctx is accepted to satisfy the Lease seam (a renewing implementation could honor a
// deadline), but this binding needs no I/O on the consult: the election goroutine keeps the flag
// current (OnStartedLeading/OnStoppedLeading), so a shutting-down replica reads false the instant
// ReleaseOnCancel fires. A non-leader read is the steady state of every follower, never an error.
func (l *KubernetesLease) IsLeader(_ context.Context) (bool, error) {
	return l.leading.Load(), nil
}

// validateLeaseWiring checks the required configuration + dependencies BEFORE the LeaseLock is
// built, returning a wrapped KindInvalid error naming the missing seam (never echoing a value),
// so a misconfigured lease fails at composition rather than at the first election action.
func validateLeaseWiring(configuration *LeaseConfig, dependencies *LeaseDependencies) error {
	switch {
	case configuration.LeaseName == "":
		return errors.New(errors.KindInvalid, "orchestratorservice: LeaseConfig.LeaseName is required (the contended Lease object name)")
	case configuration.Namespace == "":
		return errors.New(errors.KindInvalid, "orchestratorservice: LeaseConfig.Namespace is required (the orchestrator control-plane namespace holding the Lease)")
	case configuration.Identity == "":
		return errors.New(errors.KindInvalid, "orchestratorservice: LeaseConfig.Identity is required (this replica's unique holder identity, e.g. the pod name)")
	case dependencies.Coordination == nil:
		return errors.New(errors.KindInvalid, "orchestratorservice: LeaseDependencies.Coordination is required (the coordination.k8s.io/v1 client the LeaseLock contends through)")
	case dependencies.Events == nil:
		return errors.New(errors.KindInvalid, "orchestratorservice: LeaseDependencies.Events is required (the core client the LeaseLock's event recorder family needs)")
	}
	return nil
}

// leaseMeta names the Lease object the election contends for (namespace + name), the single
// coordination.k8s.io/v1 object all replicas of one orchestrator Deployment share.
func leaseMeta(namespace, name string) metav1.ObjectMeta {
	return metav1.ObjectMeta{Name: name, Namespace: namespace}
}

// orDuration returns d when positive, else the fallback — the zero-folds-to-default rule for the
// optional election cadence fields (so a zero LeaseConfig still yields a valid election).
func orDuration(d, fallback time.Duration) time.Duration {
	if d > 0 {
		return d
	}
	return fallback
}
