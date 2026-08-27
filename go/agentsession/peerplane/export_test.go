package peerplane

// export_test.go is the white-box seam (the canonical Go idiom): it exposes the root's recorded
// UndeliveredError set to the same-package reconciler test WITHOUT widening the public API surface
// (the frozen .apibaseline). Test-only; it does not ship.

// recordedUndelivered snapshots the reconciler's durable record of accepted-but-undelivered
// messages, so a test can assert the bounce was RECORDED (an errors.AsType-branchable row), not
// only sent in band.
func recordedUndelivered(o *Orchestrator) []UndeliveredError {
	o.mu.Lock()
	defer o.mu.Unlock()
	out := make([]UndeliveredError, len(o.undelivered))
	copy(out, o.undelivered)
	return out
}
