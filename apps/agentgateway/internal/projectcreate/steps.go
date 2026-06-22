package projectcreate

import (
	"context"
	"time"

	edenerrors "github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// This file holds the four saga step workers — the actual effect of each step. Each is idempotent (it
// either does its effect through an idempotent port, or skips when the durable project row already
// records the prior outcome) and returns the saga-scratch patch + ledger Output the driver records on
// success. None resolves a credential: the gh-token rides the opaque secrets.Reference into the bound
// forge/seeder adapters.

// runProvisionRepository is step 1: create the project's GitHub repository (idempotently) and record
// its coordinates. The slug is derived from the project name + its unique id so two like-named projects
// never collide. The forge's CreateRepository is idempotent (a pre-existing repo is read back via GET),
// so a saga replay of step 1 converges. It records GitHubOwner/GitHubRepo/RepoURL/DefaultBranch.
func (s *Saga) runProvisionRepository(ctx context.Context, project *gateway.Project) (stepOutcome, error) {
	// Idempotent fast path: if the project row already carries the repo URL (a prior run advanced this
	// step but the ledger advance lost the race to a crash), trust it and skip the forge round-trip.
	if project.RepoURL != "" && project.GitHubRepo != "" {
		return stepOutcome{
			Patch:  gateway.ProjectStatusPatch{},
			Output: mustJSON(map[string]string{"owner": project.GitHubOwner, "repo": project.GitHubRepo, "repoUrl": project.RepoURL, "resumed": "true"}),
		}, nil
	}

	slug := deriveRepositorySlug(project.Name, project.ID)
	coordinates, err := s.dependencies.Forge.CreateRepository(ctx, CreateRepositoryInput{
		Owner:       s.configuration.RepositoryOwner,
		Name:        slug,
		Private:     s.configuration.PrivateRepository,
		Description: repositoryDescription(project),
		Credential:  s.configuration.ForgeCredential,
	})
	if err != nil {
		return stepOutcome{}, edenerrors.Wrap(edenerrors.KindOf(err), "projectcreate: create repository", err)
	}

	defaultBranch := coordinates.DefaultBranch
	if defaultBranch == "" {
		defaultBranch = "main"
	}
	patch := gateway.ProjectStatusPatch{
		GitHubOwner:   stringPointer(coordinates.Owner),
		GitHubRepo:    stringPointer(coordinates.Name),
		RepoURL:       stringPointer(coordinates.CloneURL),
		DefaultBranch: stringPointer(defaultBranch),
	}
	output := mustJSON(map[string]string{
		"owner": coordinates.Owner, "repo": coordinates.Name,
		"repoUrl": coordinates.CloneURL, "defaultBranch": defaultBranch,
	})
	return stepOutcome{Patch: patch, Output: output}, nil
}

// runSeedTemplate is step 2: seed the new, empty repository from the template (clone -> flatten ->
// re-point origin -> push the seed), idempotently. It requires step 1's RepoURL on the project (the
// driver guarantees it ran first). The seeder is idempotent (a repo whose origin/main already carries
// the seed is a no-op), so a saga replay of step 2 converges. It records DefaultBranch + TemplateRef.
func (s *Saga) runSeedTemplate(ctx context.Context, project *gateway.Project) (stepOutcome, error) {
	if project.RepoURL == "" {
		return stepOutcome{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: seed step has no repository URL (step 1 did not record one)")
	}

	result, err := s.dependencies.Seeder.SeedRepository(ctx, SeedInput{
		ProjectID:     project.ID,
		TemplateURL:   s.configuration.TemplateRepositoryURL,
		RepositoryURL: project.RepoURL,
		Credential:    s.configuration.ForgeCredential,
	})
	if err != nil {
		return stepOutcome{}, edenerrors.Wrap(edenerrors.KindOf(err), "projectcreate: seed repository from template", err)
	}

	defaultBranch := result.DefaultBranch
	if defaultBranch == "" {
		defaultBranch = project.DefaultBranch
	}
	if defaultBranch == "" {
		defaultBranch = "main"
	}
	patch := gateway.ProjectStatusPatch{
		DefaultBranch: stringPointer(defaultBranch),
		TemplateRef:   stringPointer(s.configuration.TemplateReference),
	}
	output := mustJSON(map[string]string{
		"defaultBranch": defaultBranch, "templateRef": s.configuration.TemplateReference, "seedCommit": result.CommitID,
	})
	return stepOutcome{Patch: patch, Output: output}, nil
}

// runLaunchSupervisor is step 3: Spawn the project's supervisor on the orchestrator (a workspace
// container that clones the new repo into its WorkDir, mounts the supervisor .claude, and opens a
// Role:supervisor opus-4.8 session — the orchestrator service performs that fold; the saga RECORDS the
// admitted agent). Spawn is idempotent at the orchestrator's (Tenant, Template) class ceiling
// (MaxConcurrent=1 for the supervisor) — a re-Spawn for an already-launched supervisor returns the
// existing admission rather than a second container. It records WorkspaceHandle/SupervisorAgentID/
// SessionRef.
func (s *Saga) runLaunchSupervisor(ctx context.Context, project *gateway.Project) (stepOutcome, error) {
	// Idempotent fast path: a prior run already recorded the supervisor agent — trust it on replay
	// rather than re-Spawning (the orchestrator would admit at the class ceiling, but skipping avoids a
	// needless round-trip and a duplicate observation).
	if project.SupervisorAgentID != "" {
		return stepOutcome{
			Output: mustJSON(map[string]string{"supervisorAgentId": project.SupervisorAgentID, "resumed": "true"}),
		}, nil
	}

	agent, err := s.dependencies.Supervisor.Spawn(ctx, orchestrator.SpawnRequest{
		Tenant:     s.supervisorTenancy(project.ID),
		Template:   s.configuration.SupervisorTemplate,
		Credential: s.configuration.ForgeCredential,
		By:         "projectcreate-saga",
		Cluster:    s.configuration.SupervisorCluster,
	})
	if err != nil {
		return stepOutcome{}, edenerrors.Wrap(edenerrors.KindOf(err), "projectcreate: spawn supervisor", err)
	}

	patch := gateway.ProjectStatusPatch{
		WorkspaceHandle:   stringPointer(agent.Workspace.String()),
		SupervisorAgentID: stringPointer(string(agent.ID)),
		SessionRef:        stringPointer(string(agent.Session)),
	}
	output := mustJSON(map[string]string{
		"supervisorAgentId": string(agent.ID),
		"workspaceHandle":   agent.Workspace.String(),
		"sessionRef":        string(agent.Session),
		"status":            agent.Status.String(),
	})
	return stepOutcome{Patch: patch, Output: output}, nil
}

// runSupervisorReady is step 4: wait on the supervisor's health heartbeat to report ready (the
// orchestrator drives Pending -> Provisioning -> Running as the workspace comes up and the session
// Opens; StatusRunning is "session live"). It polls Manager.Get at the configured cadence until the
// agent reaches StatusRunning, a terminal-failed status (a fault), or the readiness deadline. On ready
// it records nothing new (the refs are already on the project) and returns — the driver's finish flips
// the project to WIZARD.
func (s *Saga) runSupervisorReady(ctx context.Context, project *gateway.Project) (stepOutcome, error) {
	agentID := orchestrator.AgentID(project.SupervisorAgentID)
	if agentID == "" {
		return stepOutcome{}, edenerrors.New(edenerrors.KindInvalid, "projectcreate: readiness step has no supervisor agent id (step 3 did not record one)")
	}

	waitCtx := ctx
	if s.configuration.SupervisorReadyTimeout > 0 {
		var cancel context.CancelFunc
		waitCtx, cancel = context.WithTimeout(ctx, s.configuration.SupervisorReadyTimeout)
		defer cancel()
	}

	ticker := s.newReadyTicker()
	defer ticker.Stop()

	for {
		agent, err := s.dependencies.Supervisor.Get(waitCtx, agentID)
		if err != nil {
			return stepOutcome{}, edenerrors.Wrap(edenerrors.KindOf(err), "projectcreate: probe supervisor readiness", err)
		}
		switch agent.Status {
		case orchestrator.StatusRunning:
			return stepOutcome{
				Output: mustJSON(map[string]string{"supervisorAgentId": string(agent.ID), "status": agent.Status.String()}),
			}, nil
		case orchestrator.StatusFailed:
			return stepOutcome{}, edenerrors.New(edenerrors.KindUnavailable, "projectcreate: supervisor reached terminal failed status: "+supervisorDetail(&agent))
		case orchestrator.StatusStopped:
			return stepOutcome{}, edenerrors.New(edenerrors.KindUnavailable, "projectcreate: supervisor was stopped before it became ready")
		case orchestrator.StatusPending, orchestrator.StatusProvisioning, orchestrator.StatusSuspended, orchestrator.StatusResuming, orchestrator.StatusStopping:
			// Still coming up — keep polling below.
		}

		select {
		case <-waitCtx.Done():
			return stepOutcome{}, edenerrors.Wrap(edenerrors.KindDeadline, "projectcreate: timed out waiting for supervisor to become ready", waitCtx.Err())
		case <-ticker.C:
		}
	}
}

// newReadyTicker is the step-4 poll ticker at Config.SupervisorPollInterval (defaulted at New). It is a
// method so a white-box test can inject a fast tick without exposing the cadence on the public surface.
func (s *Saga) newReadyTicker() *time.Ticker {
	return time.NewTicker(s.configuration.SupervisorPollInterval)
}

// repositoryDescription renders an operator-safe repository description from the project (its kind +
// name); never a credential. An empty idea yields a terse default so the forge always receives a stable
// description.
func repositoryDescription(project *gateway.Project) string {
	kind := project.Product.ProductKind
	if kind == "" {
		kind = "project"
	}
	return "Eden-built " + kind + ": " + project.Name
}

// supervisorDetail returns the agent's last-transition detail (a REDACTED reason on a failure; never a
// credential — orchestrator guarantees it) for the readiness fault message, or a terse default when the
// orchestrator recorded none.
func supervisorDetail(agent *orchestrator.Agent) string {
	if agent.Detail == "" {
		return "no detail reported"
	}
	return agent.Detail
}
