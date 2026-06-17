package list

import "github.com/gophersys/libs/go/edenhttp"

// validate checks the resolved pagination window is in range: a negative offset is malformed (→ 400).
// limit is already defaulted+clamped in parse, so only offset's lower bound is checked here. It
// touches NO port, staying pure (the VALIDATE stage contract).
func validate(request Request) error {
	if request.Offset < 0 {
		return edenhttp.RequestError{Reason: "offset must not be negative"}
	}
	return nil
}
