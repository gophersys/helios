package composition

// export_test.go is the white-box seam (the canonical Go idiom): it re-exports the PURE,
// unexported composition-root wiring helpers to the black-box composition_test package so the
// supervisor route, the role-threaded Spec, and the Advisor wiring are provable WITHOUT exporting
// app-internal wiring from the (already internal) package. These are test-only; they do not ship.

import (
	"context"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/gitrepository"
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

// PrepareWorkdirWithBackendForTest exposes the in-pod clone-on-boot seam with an INJECTED
// gitrepository.Backend (the in-memory gitrepositorytest.Backend fake), so a UNIT test proves the
// pure cloner logic — the credential REFERENCE is resolved server-side and threaded to Clone, and the
// credential VALUE never reaches a process-argument surface — WITHOUT a real git binary or a real
// clone (the on-disk overlay+clean-tree half is the real-system-git test PrepareWorkdirForTest drives).
// It mirrors the production newWorkdirCloner exactly but for the backend (the one substrate seam): the
// SAME injected secrets Mediator, the SAME manualSourceDir resolution, the SAME system clock.
//
//nolint:gocritic // Environment is the frozen, copyable pod-environment input; the test seam takes it by value, mirroring Run.
func PrepareWorkdirWithBackendForTest(ctx context.Context, environment Environment, secretsProvider secrets.Provider, backend gitrepository.Backend) (string, error) {
	cloner := newWorkdirCloner(secretsProvider)
	cloner.backend = backend // inject the in-memory fake in place of the production SystemGit backend (the lone substrate seam).
	return cloner.prepareWorkdir(ctx, &environment)
}
