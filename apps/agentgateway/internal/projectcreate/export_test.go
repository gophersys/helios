package projectcreate

// export_test.go is the white-box seam (the house idiom): it re-exports the package's PURE unexported
// helpers so the external _test package exercises them WITHOUT widening the public surface. Only the
// pure slug helpers are exposed — no port, no I/O.

// DeriveRepositorySlugForTest re-exports deriveRepositorySlug for the external test.
func DeriveRepositorySlugForTest(name, projectID string) string {
	return deriveRepositorySlug(name, projectID)
}

// SlugifyHNS1ForTest re-exports slugifyHNS1 for the external test.
func SlugifyHNS1ForTest(name string) string { return slugifyHNS1(name) }

// DeriveTenancyUUIDForTest re-exports deriveTenancyUUID for the external test (the name->UUID mapping the
// orchestrator's UUID tenancy columns require).
func DeriveTenancyUUIDForTest(name string) string { return deriveTenancyUUID(name) }

// FSMTransitionForTest is the parsed commit-transition trailer, re-exported for the white-box test.
type FSMTransitionForTest struct{ From, To, Transition, Artifact, Guard string }

// ParseFSMTrailerForTest re-exports parseFSMTrailer (the fsm: trailer grammar parser).
func ParseFSMTrailerForTest(line string) (FSMTransitionForTest, error) {
	transition, err := parseFSMTrailer(line)
	return FSMTransitionForTest(transition), err
}

// ValidateFSMTransitionForTest re-exports validateFSMTransition (the server-side FSM-table wall).
func ValidateFSMTransitionForTest(workspaceDir, from, to, transition, artifact, guard string) error {
	return validateFSMTransition(workspaceDir, &fsmTransition{
		From: from, To: to, Transition: transition, Artifact: artifact, Guard: guard,
	})
}

// ProjectStatusForFSMStateForTest re-exports projectStatusForFSMState (the FSM-state -> Project.Status map).
func ProjectStatusForFSMStateForTest(state string) string { return projectStatusForFSMState(state) }
