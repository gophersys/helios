package removal

// validate checks the parsed Request is well-formed. The VALIDATE stage owns ONLY input
// well-formedness and touches no port. The id was already parsed to a uuid in parse (a malformed id
// is a 400 there), so a parsed Request is well-formed and validate accepts unconditionally.
func validate(_ Request) error {
	return nil
}
