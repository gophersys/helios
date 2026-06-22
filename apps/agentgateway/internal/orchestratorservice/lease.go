package orchestratorservice

import "context"

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
