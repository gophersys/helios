package me

// validate checks the parsed Request is well-formed. /me has no input to validate (the caller is the
// verified token's subject, not a request field), so validate accepts. It touches NO port, staying
// pure (the VALIDATE stage contract).
func validate(_ Request) error {
	return nil
}
