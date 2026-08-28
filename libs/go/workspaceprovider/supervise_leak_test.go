package workspaceprovider_test

import (
	"context"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/dependencies/dependenciestest"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets/secretstest"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// TestSupervise_PartialWatchFailureReapsStartedWatchers proves the partial-failure REAP (finding
// #6): when a Provider fans Supervise over TWO adapters and ONE adapter's Watch errors, the
// library must (a) return the error AND (b) leave NO leaked watcher goroutine from the adapter
// whose Watch already started. Before the fix, the started watcher ran on the caller's ctx (not
// canceled on the error return), leaking its goroutine; now Supervise derives a cancelable ctx and
// cancels it on any Watch error, reaping the started watchers.
//
// The Provider iterates its adapter map in random order, so this loops several times: whenever the
// HEALTHY adapter is started before the FAILING one, the reap path runs. goleak.VerifyNone at the
// end asserts zero residual goroutines across ALL iterations — a single un-reaped watcher fails it.
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the whole-process goroutine set; a parallel sibling would perturb the orphan-goroutine assertion.
func TestSupervise_PartialWatchFailureReapsStartedWatchers(t *testing.T) {
	defer goleak.VerifyNone(t)

	set, _, _, _ := dependenciestest.Fakes()
	for i := 0; i < 8; i++ {
		healthy := workspaceprovidertest.NewAdapter(workspaceprovider.CapSupervise)
		failing := workspaceprovidertest.NewAdapter(workspaceprovider.CapSupervise).
			FailWatchWith(errors.New(errors.KindUnavailable, "fake: watch substrate unavailable"))

		// Seed the healthy adapter with a workspace so its Watch goroutine has a reconcile seed to
		// (try to) emit — making a leak observable if the reap does not fire.
		prov, perr := workspaceprovider.New(
			workspaceprovider.Config{Default: workspaceprovider.SubstrateDocker},
			workspaceprovider.Deps{
				Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{
					workspaceprovider.SubstrateDocker:     healthy,
					workspaceprovider.SubstrateKubernetes: failing,
				},
				Secrets: secretstest.New(nil),
				Clock:   set.Clock,
			},
		)
		if perr != nil {
			t.Fatalf("New: %v", perr)
		}
		if _, err := prov.Provision(context.Background(), workspaceprovider.WorkspaceSpec{
			Name:      "ws-supervise-leak",
			Substrate: workspaceprovider.SubstrateDocker,
			Image:     "busybox:1.36",
			Labels:    map[string]string{workspaceprovider.LabelOrganization: "org-sl", workspaceprovider.LabelProject: "proj-sl"},
		}); err != nil {
			t.Fatalf("Provision: %v", err)
		}

		// Supervise must FAIL (one adapter's Watch errors) and reap any started watcher.
		ctx := context.Background()
		ch, err := prov.Supervise(ctx, workspaceprovider.Selector{Labels: map[string]string{
			workspaceprovider.LabelOrganization: "org-sl",
			workspaceprovider.LabelProject:      "proj-sl",
		}})
		if err == nil {
			t.Fatalf("Supervise over a failing adapter must return an error, got nil (channel %v)", ch)
		}
		if ch != nil {
			t.Errorf("Supervise must return a nil channel alongside its error, got %v", ch)
		}
	}
	// goleak.VerifyNone (deferred) now asserts no watcher goroutine survived the partial failures.
}
