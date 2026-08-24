package agentsession

// export_test.go is the white-box seam (the canonical Go idiom): it re-exports the pure,
// unexported permission internals to the black-box agentsession_test package so the
// risk-class table and the clamp are provable WITHOUT widening the public API surface (the
// frozen .apibaseline). These are test-only; they do not ship.

// RiskClassForTest exposes the pure data-derived risk classifier.
func RiskClassForTest(tool string, scopes []string) RiskLevel { return riskClass(tool, scopes) }

// ClampToRiskForTest exposes the pure risk-class clamp (the prompt-injection wall).
//
//nolint:gocritic // Decision is the contract's copyable value record (§2); the test seam mirrors the internal signature.
func ClampToRiskForTest(tool string, scopes []string, decision Decision) Decision {
	return clampToRisk(tool, scopes, decision)
}

// PeerHostToolsForTest builds the peer host-tool set the library injects into its OWN copy of
// Spec.HostTools at Open, given the session's name, the plane it joined, and the link Join
// returned. It is the ONLY way a test can reach the PRE-JOIN state: through Pool.Open the link
// always exists by the time anything can call a handler, so the nil-link arm — the window
// between Spawn (pool.go:81) and joinPeer (pool.go:95) — is unreachable from the public path
// and would ship unproven.
//
// A nil link MUST yield a typed errors.KindUnavailable from the handler, never a nil-pointer
// panic: a panic inside a host-tool handler crosses back into the harness's tool router, where
// it is a broken transport rather than a failed tool.
//
// SEAM REQUIRED FROM THE IMPLEMENTER: the unexported builder in agentsession/peer_hosttool.go
//
//	peerHostTools(name string, plane PeerPlane, link PeerLink) []HostTool
func PeerHostToolsForTest(name string, plane PeerPlane, link PeerLink) []HostTool {
	return peerHostTools(name, plane, link)
}

// GuardControlForTest runs guardControl on a session FORCED into state with the given CapSteer status,
// so the (state × command) legality the guard enforces is provable across ALL 8 states without
// scripting the transitions to reach them — the exhaustive matrix the conformance transition-mirror
// never covered. Test-only; does not ship.
func GuardControlForTest(state State, steer CapStatus, command Command) error {
	s := &session{
		state:    state,
		manifest: CapabilityManifest{Capabilities: map[Capability]CapStatus{CapSteer: steer}},
	}
	return s.guardControl(command)
}
