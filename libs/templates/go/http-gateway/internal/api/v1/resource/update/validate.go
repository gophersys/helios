package update

import (
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/libs/templates/go/http-gateway/internal/api/v1/resource/view"
)

// validate checks the parsed Request is well-formed: the new name must be present and within bounds.
// It cites the shared view.ValidateName rule (the SAME rule create uses — one home for the name
// constraint), wraps its typed KindInvalid (→ 400) with the route+stage context, and touches NO port
// (the VALIDATE stage stays pure). The id was already validated as a well-formed uuid in parse.
func validate(input Request) error {
	if err := view.ValidateName(input.Name); err != nil {
		return errors.Wrap(errors.KindOf(err), "update: validate", err)
	}
	return nil
}
