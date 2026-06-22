package postgresstore

// export_test.go is the white-box seam (the house idiom): it re-exports the pure, unexported
// helpers to the black-box postgresstore_test unit suite so the SQL filter builder, the
// offset-cursor pagination, the record round-trip, and the project-namespace boundary check are
// table-testable WITHOUT widening the public API surface. These are compiled only in tests; they
// do not ship.

import (
	"encoding/json"
	"testing"

	"github.com/gophersys/libs/go/orchestrator"
)

// IsProjectNamespacedForTest exposes the unexported Put-boundary guard (only a project-namespaced
// id may enter the store) to the unit suite.
func IsProjectNamespacedForTest(id orchestrator.AgentID, tenant orchestrator.Tenancy) bool {
	return isProjectNamespaced(id, tenant)
}

// BuildWhereForTest exposes the unexported SQL filter builder to the unit suite.
//
//nolint:nonamedreturns // the named results document the (whereClause, positionalArgs) pair under test.
func BuildWhereForTest(filter *orchestrator.Filter) (whereClause string, positionalArgs []any) {
	return buildWhere(filter)
}

// PaginateForTest exposes the unexported offset-cursor pagination to the unit suite.
func PaginateForTest(matched []orchestrator.Agent, filter *orchestrator.Filter) orchestrator.Page {
	return paginate(matched, filter)
}

// RoundTripForTest projects an Agent to its persisted record, marshals it the way Put persists
// it (to the JSONB `record` column), and reads it back through the REAL decodeAgent path — so the
// unit round-trip exercises the same marshal/unmarshal the store uses against Postgres, mock-free
// and substrate-free.
//
//nolint:gocritic // Agent is the contract's copyable serializable record; the seam mirrors the by-value store signature.
func RoundTripForTest(t *testing.T, agent orchestrator.Agent) (orchestrator.Agent, error) {
	t.Helper()
	recordJSON, err := json.Marshal(toRecord(agent))
	if err != nil {
		t.Fatalf("marshal record fixture: %v", err)
	}
	return decodeAgent(recordJSON)
}
