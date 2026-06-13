package orchestratortest_test

import (
	"testing"

	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/orchestratortest"
)

// TestConformance_V0Pool runs the ONE orchestrator conformance suite against the v0
// in-process Manager (a real orchestrator.New over the in-memory fakes + the scripted
// agentsessiontest session adapter + the workspaceprovidertest frozen-seam fake). It is
// the proof that the v0 *Pool is substitutable against the lifecycle/limit/credential
// properties (contract §4) — and the template a future multi-node build re-runs.
func TestConformance_V0Pool(t *testing.T) {
	t.Parallel()
	orchestratortest.RunManagerSuite(t, func() (orchestrator.Manager, orchestratortest.Harness) {
		manager := orchestratortest.New(
			orchestratortest.WithTemplate(orchestratortest.DefaultTemplate()),
			orchestratortest.WithTemplate(orchestratortest.BudgetTemplate()),
			orchestratortest.WithMaxConcurrent(2),
		)
		return manager, orchestratortest.Harness{
			Reconcile:  manager.Reconcile,
			Workspaces: manager.Workspaces(),
			Probe:      manager.Probe(),
			Telemetry:  manager.Telemetry(),
			Clock:      manager.Clock(),
		}
	})
}
