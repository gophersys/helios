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
