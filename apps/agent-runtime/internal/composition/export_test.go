package composition

// export_test.go is the white-box seam (the canonical Go idiom): it re-exports the PURE,
// unexported composition-root wiring helpers to the black-box composition_test package so the
// supervisor route, the role-threaded Spec, and the Advisor wiring are provable WITHOUT exporting
// app-internal wiring from the (already internal) package. These are test-only; they do not ship.

import (
	"context"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/secrets"
)

// Test-visible aliases for the role/model/budget constants the wiring asserts against, so a test
// pins the EXACT values the composition root binds (one home: the test reads them, never re-spells).
const (
	RoleAssistantForTest   = roleAssistant
	RoleSupervisorForTest  = roleSupervisor
	SupervisorModelForTest = supervisorModel
)

// SupervisorBudgetForTest exposes the supervisor route's soft Budget so a test asserts it is the
// larger ceiling the supervisor launches with.
var SupervisorBudgetForTest = supervisorBudget

// BuildRoutingForTest exposes the pure agentconfiguration routing projection (RouteKey -> Route).
//
//nolint:gocritic // Environment is the frozen, copyable pod-environment input (the configuration pattern); the test seam takes it by value, mirroring Run.
func BuildRoutingForTest(environment Environment) map[agentsession.RouteKey]agentsession.Route {
	return buildRouting(&environment)
}

// BuildSpecForTest exposes the pure Spec builder (the role/phase/budget threading from the env).
//
//nolint:gocritic // Environment is the frozen, copyable pod-environment input (the configuration pattern); the test seam takes it by value, mirroring Run.
func BuildSpecForTest(environment Environment) agentsession.Spec {
	return buildSpec(&environment)
}

// BuildAdvisorForTest exposes the pure Advisor wiring so a test asserts the Advisor is wired (a
// non-nil agentsession.PermissionAdvisor) when a credential is configured, and is a TRUE nil
// interface (the documented degrade) when it is not.
//
//nolint:ireturn,gocritic // ireturn: the seam returns the PermissionAdvisor port so a test asserts the absent case is a true nil interface; gocritic: Environment is the frozen copyable input taken by value, mirroring Run.
func BuildAdvisorForTest(environment Environment, provider observability.Provider, sessions agentsession.Factory) (agentsession.PermissionAdvisor, error) {
	return buildAdvisor(&environment, provider, sessions)
}

// PrepareWorkdirForTest exposes the in-pod clone-on-boot seam (workdir.go) so a test proves both its
// additive guard (an empty WorkdirRepo returns Workspace verbatim — the existing boot, byte-unchanged)
// and the real clone+overlay+commit structure against a LOCAL git remote (real system git, no mock,
// no network). The secrets provider is injected so the test passes a no-network resolver for the
// public/unauthenticated local-clone case.
//
//nolint:gocritic // Environment is the frozen, copyable pod-environment input; the test seam takes it by value, mirroring Run.
func PrepareWorkdirForTest(ctx context.Context, environment Environment, secretsProvider secrets.Provider) (string, error) {
	return newWorkdirCloner(secretsProvider).prepareWorkdir(ctx, &environment)
}
