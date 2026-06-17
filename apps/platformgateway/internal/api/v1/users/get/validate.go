package get

// validate checks the parsed Request is well-formed. The id was already parsed (and thereby validated
// as a well-formed uuid) in parse via the shared view.ParseID rule, so there is nothing further to
// check here — get accepts. It touches NO port, staying pure (the VALIDATE stage contract).
func validate(_ Request) error {
	return nil
}
