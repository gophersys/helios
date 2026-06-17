package ping

// validate checks the parsed Request is well-formed. The VALIDATE stage owns ONLY input
// well-formedness — it returns a bare error (which the pipeline maps to a 400) for a malformed input,
// and it touches NO port (no persistence, no clock) so it is pure and trivially testable. GET
// /v1/ping has no input to validate, so it accepts unconditionally; a resource with a body validates
// its fields here (required-present, in-range, well-shaped) before execute ever runs.
func validate(_ Request) error {
	return nil
}
