package list

import (
	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// validate checks the resolved pagination window is well-formed: a negative limit or offset is a
// malformed request (parse defaults/clamps the upper bound, but a caller may pass a negative value).
// It returns a typed KindInvalid (→ 400) and touches NO port — the VALIDATE stage stays pure, so
// execute never issues a query with a negative window.
func validate(input Request) error {
	if input.Limit < 0 {
		return errors.Wrap(errors.KindInvalid, "list: validate",
			edenhttp.RequestError{Reason: "limit must not be negative"})
	}
	if input.Offset < 0 {
		return errors.Wrap(errors.KindInvalid, "list: validate",
			edenhttp.RequestError{Reason: "offset must not be negative"})
	}
	return nil
}
