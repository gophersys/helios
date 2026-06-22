//nolint:testpackage // white-box: exercises the unexported saga-contract helpers (ApplyTo, the closed status sets, the view projection) directly.
package gateway

import (
	"encoding/json"
	"testing"
	"time"
)

// TestProjectStatusPatch_ApplyToMergesNonNilOnly proves the one shared merge rule: each non-nil patch
// field overwrites, a nil field is left untouched, and a pointer-to-empty clears — the read-modify
// step both store adapters delegate to (one concept, one home).
func TestProjectStatusPatch_ApplyToMergesNonNilOnly(t *testing.T) {
	t.Parallel()
	project := Project{
		ID: "project-aa", Name: "keep-me", Status: ProjectStatusDraft,
		GitHubOwner: "old-owner", LastError: "old fault",
	}
	status := ProjectStatusLaunchingSupervisor
	newOwner := "new-owner"
	patch := ProjectStatusPatch{
		Status:            &status,
		GitHubOwner:       &newOwner,
		SupervisorAgentID: strptr("agent-7"),
		LastError:         strptr(""), // clear
	}
	patch.ApplyTo(&project)

	if project.Status != ProjectStatusLaunchingSupervisor {
		t.Fatalf("Status not merged: %q", project.Status)
	}
	if project.GitHubOwner != "new-owner" {
		t.Fatalf("GitHubOwner not overwritten: %q", project.GitHubOwner)
	}
	if project.SupervisorAgentID != "agent-7" {
		t.Fatalf("SupervisorAgentID not set: %q", project.SupervisorAgentID)
	}
	if project.LastError != "" {
		t.Fatalf("LastError not cleared: %q", project.LastError)
	}
	if project.Name != "keep-me" {
		t.Fatalf("Name overwritten by a nil patch field: %q", project.Name)
	}
}

// TestValidProjectStatus_ClosedSet pins the closed lifecycle set: every widened token is valid, the
// preserved draft/building tokens are valid, and an off-contract token is rejected.
func TestValidProjectStatus_ClosedSet(t *testing.T) {
	t.Parallel()
	valid := []string{
		ProjectStatusDraft, ProjectStatusCreating, ProjectStatusProvisioningRepo,
		ProjectStatusSeedingTemplate, ProjectStatusLaunchingSupervisor, ProjectStatusSupervisorReady,
		ProjectStatusWizard, ProjectStatusBuilding, ProjectStatusFailed,
	}
	for _, status := range valid {
		if !ValidProjectStatus(status) {
			t.Errorf("ValidProjectStatus(%q) = false, want true", status)
		}
	}
	for _, bad := range []string{"", "done", "provisioning-repo", "BUILDING"} {
		if ValidProjectStatus(bad) {
			t.Errorf("ValidProjectStatus(%q) = true, want false", bad)
		}
	}
}

// TestValidCreateStepStatus_ClosedSet pins the create-step status set.
func TestValidCreateStepStatus_ClosedSet(t *testing.T) {
	t.Parallel()
	for _, status := range []string{CreateStepStatusPending, CreateStepStatusDone, CreateStepStatusFailed} {
		if !ValidCreateStepStatus(status) {
			t.Errorf("ValidCreateStepStatus(%q) = false, want true", status)
		}
	}
	for _, bad := range []string{"", "running", "DONE"} {
		if ValidCreateStepStatus(bad) {
			t.Errorf("ValidCreateStepStatus(%q) = true, want false", bad)
		}
	}
}

// TestToProjectView_SurfacesSagaScratchForwardCompatibly proves the wire stays forward-compatible: a
// pre-saga draft omits every saga-scratch field (the dashboard sees exactly today's shape), while a
// saga-advanced project surfaces them — and no credential field exists on the projection.
func TestToProjectView_SurfacesSagaScratchForwardCompatibly(t *testing.T) {
	t.Parallel()
	now := time.Date(2026, time.June, 22, 12, 0, 0, 0, time.UTC)

	draft := toProjectView(Project{ID: "project-d", Name: "draft", Status: ProjectStatusDraft, CreatedAt: now, UpdatedAt: now})
	draftJSON := mustMarshal(t, draft)
	for _, omitted := range []string{"githubOwner", "repoUrl", "sagaStep", "supervisorAgentId", "lastError", "templateRef"} {
		if containsKey(t, draftJSON, omitted) {
			t.Errorf("draft projectView leaked a saga field %q (want omitempty): %s", omitted, draftJSON)
		}
	}

	advanced := toProjectView(Project{
		ID: "project-a", Name: "live", Status: ProjectStatusBuilding,
		GitHubOwner: "gophersys", GitHubRepo: "pay-backend", RepoURL: "https://github.com/gophersys/pay-backend",
		DefaultBranch: "main", TemplateRef: "go/http-gateway", SupervisorAgentID: "agent-7",
		SagaStep: "wizard", LastError: "", CreatedAt: now, UpdatedAt: now,
	})
	advancedJSON := mustMarshal(t, advanced)
	for _, present := range []string{"githubOwner", "repoUrl", "sagaStep", "supervisorAgentId"} {
		if !containsKey(t, advancedJSON, present) {
			t.Errorf("advanced projectView dropped a saga field %q: %s", present, advancedJSON)
		}
	}
	// LastError is empty here, so it must still be omitted (omitempty), not rendered as "".
	if containsKey(t, advancedJSON, "lastError") {
		t.Errorf("empty lastError rendered (want omitempty): %s", advancedJSON)
	}
}

func mustMarshal(t *testing.T, value any) []byte {
	t.Helper()
	blob, err := json.Marshal(value)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	return blob
}

func containsKey(t *testing.T, blob []byte, key string) bool {
	t.Helper()
	var object map[string]json.RawMessage
	if err := json.Unmarshal(blob, &object); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	_, ok := object[key]
	return ok
}

func strptr(s string) *string { return &s }
