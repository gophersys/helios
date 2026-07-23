package create

import (
	"strings"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors/view"
)

// validate checks the parsed Request is well-formed. The VALIDATE stage owns ONLY input
// well-formedness — it returns a bare error (which the pipeline maps to a 400) for a malformed input,
// and it touches NO port (no persistence, no clock), so it is pure and trivially testable. It
// enforces: the kind is a member of the closed v1 vocabulary (honest chrome — P-D6), the name is
// non-empty, the credential value is non-empty, and the scope is well-formed (a valid level, and a
// parseable target id when user-scoped). It NEVER logs or inspects the value beyond "is it present".
func validate(input Request) error {
	if !view.IsValidKind(input.Kind) {
		return errors.Wrap(errors.KindInvalid, "create: validate kind",
			edenhttp.RequestError{Reason: "kind must be one of claude-api, github, openrouter"})
	}
	if strings.TrimSpace(input.Name) == "" {
		return errors.Wrap(errors.KindInvalid, "create: validate name",
			edenhttp.RequestError{Reason: "name is required"})
	}
	if input.Value == "" {
		return errors.Wrap(errors.KindInvalid, "create: validate value",
			edenhttp.RequestError{Reason: "value (the credential) is required"})
	}
	return validateScope(input.Scope)
}

// validateScope checks the scope selector: the level is a member of the closed vocabulary, and a
// user-scoped connector carries a parseable target user id. An org-scoped connector ignores TargetID.
func validateScope(scope view.ScopeInput) error {
	if !view.IsValidScopeLevel(scope.Level) {
		return errors.Wrap(errors.KindInvalid, "create: validate scope level",
			edenhttp.RequestError{Reason: "scope.level must be one of org, user"})
	}
	if scope.Level == view.ScopeUser {
		if _, err := uuid.Parse(scope.TargetID); err != nil {
			return errors.Wrap(errors.KindInvalid, "create: validate scope targetId",
				edenhttp.RequestError{Reason: "scope.targetId must be a valid uuid for a user-scoped connector"})
		}
	}
	return nil
}
