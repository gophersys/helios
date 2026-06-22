package projectcreate

import (
	"context"
	"crypto/sha1" //nolint:gosec // RFC-4122 v5 UUID derivation is DEFINED over SHA-1; this is name->UUID mapping, not a security hash.
	"encoding/json"
	"errors"
	"fmt"

	edenerrors "github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// The saga step tokens — the stable, ordered identity of each step, used as the ledger key
// (projectUUID, step) AND recorded on the project (Project.SagaStep) so a Retry knows where to
// re-enter. They are lower-snake to match the project-status tokens; the set is closed and ordered
// (the saga walks them in this sequence).
const (
	StepProvisionRepository = "provision_repo"
	StepSeedTemplate        = "seed_template"
	StepLaunchSupervisor    = "launch_supervisor"
	StepSupervisorReady     = "supervisor_ready"
)

// orderedSteps is the saga's step sequence, in order. The driver walks it from the first not-yet-done
// step (the resume point) to the end; a done step is skipped (idempotent replay). Each entry pairs the
// step token with the in-progress project status it sets and the worker that performs its effect.
//
//nolint:gochecknoglobals // a package-level immutable plan table (the ordered step list), not mutable state.
var orderedSteps = []stepPlan{
	{Step: StepProvisionRepository, Status: gateway.ProjectStatusProvisioningRepo, Run: (*Saga).runProvisionRepository},
	{Step: StepSeedTemplate, Status: gateway.ProjectStatusSeedingTemplate, Run: (*Saga).runSeedTemplate},
	{Step: StepLaunchSupervisor, Status: gateway.ProjectStatusLaunchingSupervisor, Run: (*Saga).runLaunchSupervisor},
	{Step: StepSupervisorReady, Status: gateway.ProjectStatusSupervisorReady, Run: (*Saga).runSupervisorReady},
}

// stepPlan is one entry of the saga plan: the step token, the in-progress project status the driver
// flips to before running it, and the worker that performs the step's effect and returns the patch +
// ledger output to record on success.
type stepPlan struct {
	Step   string
	Status string
	Run    func(*Saga, context.Context, *gateway.Project) (stepOutcome, error)
}

// stepOutcome is what a successful step worker returns: the saga-scratch patch to fold onto the project
// (repo coordinates, refs) and the redaction-safe machine Output to advance the ledger row with. Patch
// is the durable project mutation; Output is the ledger's "what this step produced" record the next
// step (or a human) can read.
type stepOutcome struct {
	Patch  gateway.ProjectStatusPatch
	Output gateway.RawJSON
}

// Run drives the project named by projectUUID through the ordered creation saga, RESUMABLY and
// IDEMPOTENTLY. It is the saga's single entry point — the handler kicks it asynchronously after writing
// the DRAFT row (DB-first), and a Retry calls it again with the same id.
//
// It reads the durable project row, replays the step ledger to find the resume point (the first
// not-yet-done step), then for each remaining step: flips the project status, records a PENDING ledger
// row (idempotent on (projectUUID, step)), runs the step's effect, advances the ledger to DONE with the
// machine output, and folds the step's saga-scratch patch onto the project. A reload after a crash
// resumes at exactly the step that was in flight (its work is idempotent, so re-running it converges).
//
// On any step fault the saga parks the project at status=FAILED with the human reason (LastError) and
// the machine step (SagaStep) and advances the in-flight ledger row to FAILED, then returns the wrapped
// fault. A Retry re-enters at SagaStep. On success the final step flips the project to WIZARD (build-
// ready) and Run returns nil.
func (s *Saga) Run(ctx context.Context, projectUUID string) error {
	project, err := s.dependencies.Projects.Get(ctx, projectUUID)
	if err != nil {
		return edenerrors.Wrap(edenerrors.KindNotFound, "projectcreate: load project to run saga", err)
	}

	resumeIndex, err := s.resumePoint(ctx, projectUUID)
	if err != nil {
		return err
	}
	if resumeIndex >= len(orderedSteps) {
		// Every step is already done — a replay of a completed saga. Ensure the terminal projection and
		// return cleanly (idempotent: a completed saga re-run is a no-op).
		return s.finish(ctx, &project)
	}

	s.logInfo("projectcreate: saga start", "project", projectUUID, "resumeStep", orderedSteps[resumeIndex].Step)

	for index := resumeIndex; index < len(orderedSteps); index++ {
		plan := orderedSteps[index]
		if err := s.runStep(ctx, &project, plan); err != nil {
			return err
		}
	}
	return s.finish(ctx, &project)
}

// runStep performs one saga step end to end: flip the project's in-progress status (clearing any stale
// LastError so a Retry's status reflects forward progress), record the PENDING ledger row, run the
// effect, advance the ledger to DONE, and fold the step's patch onto the project. A fault at any point
// parks the project at FAILED and advances the ledger row to FAILED before returning the wrapped error.
func (s *Saga) runStep(ctx context.Context, project *gateway.Project, plan stepPlan) error {
	if err := s.enterStep(ctx, project, plan); err != nil {
		return err
	}

	outcome, runErr := plan.Run(s, ctx, project)
	if runErr != nil {
		return s.failStep(ctx, project, plan.Step, runErr)
	}

	if _, err := s.dependencies.Steps.Advance(ctx, project.ID, plan.Step, gateway.CreateStepStatusDone, outcome.Output); err != nil {
		return s.failStep(ctx, project, plan.Step, edenerrors.Wrap(edenerrors.KindUnavailable, "projectcreate: advance step ledger to done", err))
	}

	// Fold the step's saga-scratch patch onto the project so the next step reads the produced
	// coordinates/refs and the dashboard projection carries them. SagaStep is stamped to the just-
	// completed step (the resume marker); the status stays the in-progress one until finish/next step.
	patch := outcome.Patch
	patch.SagaStep = stringPointer(plan.Step)
	updated, err := s.dependencies.Projects.UpdateStatus(ctx, project.ID, patch)
	if err != nil {
		return s.failStep(ctx, project, plan.Step, edenerrors.Wrap(edenerrors.KindUnavailable, "projectcreate: persist step result", err))
	}
	*project = updated
	s.logInfo("projectcreate: saga step done", "project", project.ID, "step", plan.Step)
	return nil
}

// enterStep flips the project to the step's in-progress status (clearing LastError) and records the
// PENDING ledger row. Record is idempotent on (projectUUID, step): on a resume the row already exists
// and Record returns it unchanged, so re-entering a step never duplicates the ledger.
func (s *Saga) enterStep(ctx context.Context, project *gateway.Project, plan stepPlan) error {
	updated, err := s.dependencies.Projects.UpdateStatus(ctx, project.ID, gateway.ProjectStatusPatch{
		Status:    stringPointer(plan.Status),
		SagaStep:  stringPointer(plan.Step),
		LastError: stringPointer(""), // clear any stale fault — this step is being (re)attempted.
	})
	if err != nil {
		return edenerrors.Wrap(edenerrors.KindUnavailable, "projectcreate: set in-progress status", err)
	}
	*project = updated

	if _, err := s.dependencies.Steps.Record(ctx, gateway.CreateStep{
		ProjectID:      project.ID,
		Step:           plan.Step,
		IdempotencyKey: idempotencyKey(project.ID, plan.Step),
	}); err != nil {
		return edenerrors.Wrap(edenerrors.KindUnavailable, "projectcreate: record pending step ledger", err)
	}
	return nil
}

// failStep parks the project at FAILED with the human reason + the machine step, and advances the
// in-flight ledger row to FAILED with the machine fault detail. It then returns the original error
// wrapped — the caller surfaces it. A secondary fault while recording the failure is logged and folded
// into the returned error chain, never swallowed. A Retry re-enters at SagaStep (the parked step).
func (s *Saga) failStep(ctx context.Context, project *gateway.Project, step string, cause error) error {
	reason := humanReason(cause)
	s.logError("projectcreate: saga step failed", "project", project.ID, "step", step, "reason", reason, "kind", edenerrors.KindOf(cause).String())

	failOutput := mustJSON(map[string]string{"error": reason, "kind": edenerrors.KindOf(cause).String()})
	if _, advanceErr := s.dependencies.Steps.Advance(ctx, project.ID, step, gateway.CreateStepStatusFailed, failOutput); advanceErr != nil {
		s.logError("projectcreate: advance step ledger to failed", "project", project.ID, "step", step, "error", advanceErr.Error())
	}

	if _, updateErr := s.dependencies.Projects.UpdateStatus(ctx, project.ID, gateway.ProjectStatusPatch{
		Status:    stringPointer(gateway.ProjectStatusFailed),
		SagaStep:  stringPointer(step),
		LastError: stringPointer(reason),
	}); updateErr != nil {
		// The project could not even be marked failed — surface BOTH faults (never swallow the second).
		return edenerrors.Wrap(edenerrors.KindUnavailable,
			fmt.Sprintf("projectcreate: step %q failed (%s) and the failure could not be persisted", step, reason), updateErr)
	}
	return edenerrors.Wrap(edenerrors.KindOf(cause), "projectcreate: step "+step, cause)
}

// finish flips the project from the supervisor-ready in-progress status to the user-visible WIZARD
// status (the saga's terminal success state — the project is now build-ready and the supervisor session
// is live). Idempotent: a project already at WIZARD/BUILDING is left as-is so a completed-saga replay is
// a no-op.
func (s *Saga) finish(ctx context.Context, project *gateway.Project) error {
	if project.Status == gateway.ProjectStatusWizard || project.Status == gateway.ProjectStatusBuilding {
		return nil
	}
	updated, err := s.dependencies.Projects.UpdateStatus(ctx, project.ID, gateway.ProjectStatusPatch{
		Status:    stringPointer(gateway.ProjectStatusWizard),
		LastError: stringPointer(""),
	})
	if err != nil {
		return edenerrors.Wrap(edenerrors.KindUnavailable, "projectcreate: flip project to wizard", err)
	}
	*project = updated
	s.logInfo("projectcreate: saga complete", "project", project.ID, "supervisorAgent", project.SupervisorAgentID)
	return nil
}

// resumePoint replays the step ledger to find the index of the first not-yet-DONE step — the resume
// point. A fresh saga (empty ledger) resumes at 0; a crash mid-step resumes at the in-flight step
// (whose pending/failed ledger row is not done, so it is re-attempted, idempotently); a completed saga
// returns len(orderedSteps). It reads the ledger as the machine truth, never the project status (which
// is the user-visible projection, recomputed from the ledger on resume).
func (s *Saga) resumePoint(ctx context.Context, projectUUID string) (int, error) {
	steps, err := s.dependencies.Steps.List(ctx, projectUUID)
	if err != nil {
		return 0, edenerrors.Wrap(edenerrors.KindUnavailable, "projectcreate: list step ledger for resume", err)
	}
	done := make(map[string]struct{}, len(steps))
	for i := range steps {
		if steps[i].Status == gateway.CreateStepStatusDone {
			done[steps[i].Step] = struct{}{}
		}
	}
	// The resume point is the first step in saga order that is not yet done. A done step late in the
	// order with an earlier step not-done cannot occur (steps run in order), but scanning in order is
	// correct regardless: it returns the earliest incomplete step.
	for index := range orderedSteps {
		if _, ok := done[orderedSteps[index].Step]; !ok {
			return index, nil
		}
	}
	return len(orderedSteps), nil
}

// edenTenancyNamespace is the fixed RFC-4122 namespace the saga derives stable tenancy UUIDs in. The
// orchestrator's desired-state store types org_id/project_id as UUID (07 §6), but the gateway mints
// human-meaningful identifiers (an org slug; a "project-<hex>" id, never a UUID). deriveTenancyUUID maps
// those names to STABLE, collision-resistant UUIDv5 values — the boundary between the gateway's id space
// and the orchestrator's UUID-typed tenancy. The 16 bytes are an arbitrary fixed namespace seed.
var edenTenancyNamespace = [16]byte{0xed, 0xed, 0x00, 0x00, 0x00, 0x00, 0x40, 0x00, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01}

// deriveTenancyUUID maps a human-meaningful tenancy identifier (the org slug or a "project-<hex>" id) to
// the stable RFC-4122 v5 UUID the orchestrator's UUID tenancy columns require. v5 is defined as
// SHA-1(namespace || name) with the version/variant bits set; deterministic, so a saga replay re-Spawns
// under the IDENTICAL (org, project) tenancy and lands on the existing (Tenant, Template) admission class
// rather than a second supervisor.
func deriveTenancyUUID(name string) string {
	sum := sha1.Sum(append(append([]byte{}, edenTenancyNamespace[:]...), name...)) //nolint:gosec // RFC-4122 v5 is defined over SHA-1; name->UUID mapping, not security.
	var u [16]byte
	copy(u[:], sum[:16])
	u[6] = (u[6] & 0x0f) | 0x50 // version 5
	u[8] = (u[8] & 0x3f) | 0x80 // RFC-4122 variant
	return fmt.Sprintf("%x-%x-%x-%x-%x", u[0:4], u[4:6], u[6:8], u[8:10], u[10:16])
}

// supervisorTenancy is the orchestrator tenancy keys the supervisor spawns under: the configured org +
// THIS project's id, each mapped to the stable tenancy UUID the orchestrator store requires (07 §6). One
// supervisor per (org, project).
func (s *Saga) supervisorTenancy(projectID string) orchestrator.Tenancy {
	return orchestrator.Tenancy{
		OrganizationID: deriveTenancyUUID(s.configuration.OrganizationID),
		ProjectID:      deriveTenancyUUID(projectID),
	}
}

// idempotencyKey is the saga's per-step idempotency key: projectUUID + ":" + step. It is recorded on
// the ledger row so a replay of a step is provably the same logical effect (the ledger's natural key is
// (projectUUID, step); this is the human-readable mirror the contract documents).
func idempotencyKey(projectID, step string) string { return projectID + ":" + step }

// stringPointer returns a pointer to s — the ProjectStatusPatch idiom (a non-nil pointer is "set this
// field", a pointer to "" is "clear it").
func stringPointer(s string) *string { return &s }

// humanReason renders a step fault into a short, operator-safe reason for Project.LastError. It is the
// Eden error's message (which is redaction-safe by the errors contract — never a secret), so the
// dashboard surfaces a real cause without leaking a credential or a stack.
func humanReason(err error) string {
	var edenError *edenerrors.Error
	if errors.As(err, &edenError) {
		return edenError.Error()
	}
	return err.Error()
}

// mustJSON marshals a redaction-safe map into RawJSON for a ledger Output. The input is always a small
// string map the saga authors (never a credential), so a marshal error is impossible in practice; on
// the impossible fault it falls back to a JSON null rather than panicking on a load path.
func mustJSON(value any) gateway.RawJSON {
	blob, err := json.Marshal(value)
	if err != nil {
		return gateway.RawJSON("null")
	}
	return blob
}
