package update

import (
	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// validate checks the parsed Request is well-formed: the new credential value is non-empty (a PUT
// with no value is a malformed request — there is nothing to re-seal). The VALIDATE stage touches NO
// port and never inspects the value beyond "is it present". The id was already parsed to a uuid.
func validate(input Request) error {
	if input.Value == "" {
		return errors.Wrap(errors.KindInvalid, "update: validate value",
			edenhttp.RequestError{Reason: "value (the new credential) is required"})
	}
	return nil
}
