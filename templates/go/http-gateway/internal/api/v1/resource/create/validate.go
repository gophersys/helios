package create

import (
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
)

// validate checks the parsed Request is well-formed: the name must be present and within bounds. It
// cites the shared view.ValidateName rule (one home for the name constraint), wraps its typed
// KindInvalid (→ 400) with the route+stage context, and touches NO port — the VALIDATE stage stays
// pure, so execute never runs on a blank name.
func validate(input Request) error {
	if err := view.ValidateName(input.Name); err != nil {
		return errors.Wrap(errors.KindOf(err), "create: validate", err)
	}
	return nil
}
