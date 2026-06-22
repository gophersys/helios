package postgresstore

import (
	"strconv"
	"strings"

	"github.com/gophersys/libs/go/orchestrator"
)

// idPrefix is the stable namespace token every orchestrated agent id carries (the v0 minter
// uses it too: `agent-<n>`). The production store extends it with the project segment so the
// id is globally unique across projects sharing one store.
const idPrefix = "agent-"

// MintAgentID builds the globally-unique, project-namespaced, DETERMINISTIC agent id this
// store keys on: `agent-<projectID>-<sequence>`. It is the cross-project-collision fix.
//
// The v0 single-node minter (orchestrator.Pool.newAgentID) stamps `agent-<n>` from a per-Pool
// counter, so two control planes — or two projects served by the SAME multi-node store — both
// mint `agent-1`, and an id-PK upsert would have the second Put CLOBBER the first. Folding the
// project id into the id namespaces the sequence per project, so `agent-1` of project A and
// `agent-1` of project B are distinct rows that cannot collide. Determinism (no random suffix)
// preserves the re-adopt property: a recycled node re-deriving the same (project, sequence)
// computes the SAME id, so reconcile re-attaches the existing record rather than orphaning it.
//
// The production composition root mints through this when it wires the Postgres store (instead
// of the Pool's bare per-node counter); a SpawnRequest already carries the project id in
// Tenant, so the minter needs no new input. The function is PURE.
func MintAgentID(tenant orchestrator.Tenancy, sequence uint64) orchestrator.AgentID {
	return orchestrator.AgentID(idPrefix + tenant.ProjectID + "-" + strconv.FormatUint(sequence, 10))
}

// isProjectNamespaced reports whether id is namespaced with project's id (the form MintAgentID
// produces). The store's Put admits ONLY a project-namespaced id, so a bare `agent-<n>` from the
// v0 single-node minter (collision-prone in a shared store) is rejected before it can clobber a
// peer project's row. An empty project id can never be namespaced, so it is rejected too.
func isProjectNamespaced(id orchestrator.AgentID, tenant orchestrator.Tenancy) bool {
	if tenant.ProjectID == "" {
		return false
	}
	return strings.HasPrefix(string(id), idPrefix+tenant.ProjectID+"-")
}
