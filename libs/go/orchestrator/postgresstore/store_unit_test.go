package postgresstore_test

import (
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/orchestrator/postgresstore"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// These are the FAST, mock-free, no-substrate unit tests over the pure pieces of the store: the
// cross-project id minter, the project-namespace boundary check, the record round-trip (the
// opaque Handle + zero-time mapping), the SQL filter builder, and the offset-cursor pagination.
// The REAL-postgres conformance over Put/Get/List/Delete lives in store_integration_test.go
// behind //go:build integration. Black-box (postgresstore_test); the unexported helpers are
// reached through the export_test.go white-box seams (the house idiom the testpackage rule wants).

var (
	unitTenantA = orchestrator.Tenancy{OrganizationID: "11111111-1111-1111-1111-111111111111", ProjectID: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}
	unitTenantB = orchestrator.Tenancy{OrganizationID: "22222222-2222-2222-2222-222222222222", ProjectID: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"}
)

// TestMintAgentID_DeterministicAndProjectScoped asserts the minter is pure/deterministic AND
// that the SAME local sequence in two different projects yields DISTINCT ids — the cross-project
// collision fix. A non-deterministic id would break re-adopt across a node recycle; a colliding
// id would let project B's Put clobber project A's row.
func TestMintAgentID_DeterministicAndProjectScoped(t *testing.T) {
	t.Parallel()

	first := postgresstore.MintAgentID(unitTenantA, 1)
	again := postgresstore.MintAgentID(unitTenantA, 1)
	if first != again {
		t.Fatalf("MintAgentID is not deterministic: %q != %q (breaks re-adopt across a recycle)", first, again)
	}
	if want := orchestrator.AgentID("agent-" + unitTenantA.ProjectID + "-1"); first != want {
		t.Fatalf("MintAgentID(tenantA, 1) = %q, want %q", first, want)
	}

	// The SAME sequence in a different project must NOT collide — the whole point of the fix.
	collisionProneSeq := uint64(1)
	if a, b := postgresstore.MintAgentID(unitTenantA, collisionProneSeq), postgresstore.MintAgentID(unitTenantB, collisionProneSeq); a == b {
		t.Fatalf("MintAgentID collided across projects at sequence %d: both = %q", collisionProneSeq, a)
	}
}

// TestIsProjectNamespaced_AdmitsOnlyMintedIDs asserts Put's boundary guard admits ONLY an id the
// store's own minter produced for that tenant, and rejects the v0 single-node `agent-<n>` form,
// an id minted for a different project, and the empty-project case.
func TestIsProjectNamespaced_AdmitsOnlyMintedIDs(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name   string
		id     orchestrator.AgentID
		tenant orchestrator.Tenancy
		want   bool
	}{
		{"minted-for-this-project", postgresstore.MintAgentID(unitTenantA, 7), unitTenantA, true},
		{"bare-v0-single-node-id", "agent-7", unitTenantA, false},
		{"minted-for-other-project", postgresstore.MintAgentID(unitTenantB, 7), unitTenantA, false},
		{"empty-id", "", unitTenantA, false},
		{"empty-project-tenant", postgresstore.MintAgentID(unitTenantA, 7), orchestrator.Tenancy{OrganizationID: "o"}, false},
		{"prefix-without-separator", orchestrator.AgentID("agent-" + unitTenantA.ProjectID), unitTenantA, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			if got := postgresstore.IsProjectNamespacedForTest(tc.id, tc.tenant); got != tc.want {
				t.Fatalf("isProjectNamespaced(%q, project=%q) = %v, want %v", tc.id, tc.tenant.ProjectID, got, tc.want)
			}
		})
	}
}

// TestRecordRoundTrip_PreservesEveryField asserts a fully-populated Agent survives
// toRecord→JSON→decode byte-identical, including the OPAQUE workspace Handle (re-parsed) and
// the zero-time mapping. A drift here is a silent data-loss bug across a node recycle.
func TestRecordRoundTrip_PreservesEveryField(t *testing.T) {
	t.Parallel()

	handle, err := workspaceprovider.ParseHandle(workspaceprovider.EncodeHandle(
		workspaceprovider.SubstrateKubernetes, "eden-agents", unitTenantA.OrganizationID, unitTenantA.ProjectID, "agent-x", "/workspace",
	))
	if err != nil {
		t.Fatalf("build fixture handle: %v", err)
	}
	created := time.Date(2026, 6, 22, 10, 0, 0, 0, time.UTC)
	original := orchestrator.Agent{
		ID:       postgresstore.MintAgentID(unitTenantA, 42),
		Tenant:   unitTenantA,
		Template: orchestrator.TemplateRef{Name: "implementer-go", Version: "1.4.0"},
		RunID:    "run-abc",
		Desired:  orchestrator.DesiredStopped,
		Status:   orchestrator.StatusRunning,
		Limits: orchestrator.Limits{
			MaxConcurrent: 5,
			Budget:        agentsession.Budget{MaxCostMicros: 9000},
		},
		Cluster:   orchestrator.ClusterRef{ID: "cluster-prod-1"},
		Workspace: handle,
		Session:   orchestrator.SessionRef("session-xyz"),
		Ledger: agentsession.TokenLedger{
			UsageMeter: agentsession.UsageMeter{Model: "claude-fable-5", Harness: "claude-code", InputTokens: 1200, OutputTokens: 340, CostMicros: 5500},
			Turns:      3,
			ToolUses:   7,
		},
		By:        "operator-7",
		CreatedAt: created,
		UpdatedAt: created.Add(time.Minute),
		Detail:    "running",
	}

	roundTripped, err := postgresstore.RoundTripForTest(t, original)
	if err != nil {
		t.Fatalf("decode round-trip: %v", err)
	}
	assertAgentEqual(t, &original, &roundTripped)
}

// TestRecordRoundTrip_ZeroValuesAndEmptyHandle asserts a fresh (not-yet-provisioned) record —
// zero timestamps, empty handle, empty session — round-trips to the zero Handle and the zero
// time (not the Unix epoch), the not-yet-reconciled shape.
func TestRecordRoundTrip_ZeroValuesAndEmptyHandle(t *testing.T) {
	t.Parallel()
	fresh := orchestrator.Agent{
		ID:       postgresstore.MintAgentID(unitTenantA, 1),
		Tenant:   unitTenantA,
		Template: orchestrator.TemplateRef{Name: "assistant", Version: "0.1.0"},
		Desired:  orchestrator.DesiredRunning,
		Status:   orchestrator.StatusPending,
	}
	roundTripped, err := postgresstore.RoundTripForTest(t, fresh)
	if err != nil {
		t.Fatalf("decode fresh round-trip: %v", err)
	}
	if !roundTripped.Workspace.IsZero() {
		t.Fatalf("empty handle round-tripped non-zero: %q", roundTripped.Workspace.String())
	}
	if !roundTripped.CreatedAt.IsZero() || !roundTripped.UpdatedAt.IsZero() {
		t.Fatalf("zero timestamps round-tripped non-zero: created=%v updated=%v", roundTripped.CreatedAt, roundTripped.UpdatedAt)
	}
	assertAgentEqual(t, &fresh, &roundTripped)
}

// TestBuildWhere_MirrorsTheFilter asserts the SQL WHERE clause + positional args for every
// Filter axis, including the empty filter (no clause) and the combined filter (AND-joined,
// stably ordered) — the closure the in-memory store's matchesFilter holds.
func TestBuildWhere_MirrorsTheFilter(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name      string
		filter    orchestrator.Filter
		wantWhere string
		wantArgs  int
	}{
		{"empty", orchestrator.Filter{}, "", 0},
		{"tenant-only", orchestrator.Filter{Tenant: unitTenantA}, " WHERE org_id=$1 AND project_id=$2", 2},
		{"template-name", orchestrator.Filter{Template: orchestrator.TemplateRef{Name: "implementer-go"}}, " WHERE template_name=$1", 1},
		{"template-name-and-version", orchestrator.Filter{Template: orchestrator.TemplateRef{Name: "x", Version: "2.0.0"}}, " WHERE template_name=$1 AND template_version=$2", 2},
		{"only-active", orchestrator.Filter{OnlyActive: true}, " WHERE terminal = false", 0},
		{"statuses", orchestrator.Filter{Statuses: []orchestrator.Status{orchestrator.StatusRunning, orchestrator.StatusPending}}, " WHERE status = ANY($1)", 1},
		{
			"combined",
			orchestrator.Filter{Tenant: unitTenantA, Template: orchestrator.TemplateRef{Name: "x"}, OnlyActive: true, Statuses: []orchestrator.Status{orchestrator.StatusRunning}},
			" WHERE org_id=$1 AND project_id=$2 AND template_name=$3 AND terminal = false AND status = ANY($4)",
			4,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			filter := tc.filter
			gotWhere, gotArgs := postgresstore.BuildWhereForTest(&filter)
			if gotWhere != tc.wantWhere {
				t.Fatalf("buildWhere clause = %q, want %q", gotWhere, tc.wantWhere)
			}
			if len(gotArgs) != tc.wantArgs {
				t.Fatalf("buildWhere args = %d, want %d (%#v)", len(gotArgs), tc.wantArgs, gotArgs)
			}
		})
	}
}

// TestPaginate_OffsetCursorSemantics asserts paginate matches the in-memory store's offset-cursor
// contract exactly: a Limit slices and emits the last id as Next; the cursor resumes after that
// id; the last page has an empty Next; Limit<=0 returns the rest.
func TestPaginate_OffsetCursorSemantics(t *testing.T) {
	t.Parallel()
	matched := make([]orchestrator.Agent, 5)
	for i := range matched {
		matched[i] = orchestrator.Agent{ID: postgresstore.MintAgentID(unitTenantA, uint64(i+1))}
	}

	first := postgresstore.PaginateForTest(matched, &orchestrator.Filter{Limit: 2})
	if len(first.Agents) != 2 || first.Agents[0].ID != matched[0].ID || first.Agents[1].ID != matched[1].ID {
		t.Fatalf("first page = %v, want the first two", idsOf(first.Agents))
	}
	if first.Next != string(matched[1].ID) {
		t.Fatalf("first page Next = %q, want %q (the last id of the page)", first.Next, matched[1].ID)
	}

	second := postgresstore.PaginateForTest(matched, &orchestrator.Filter{Limit: 2, Cursor: first.Next})
	if len(second.Agents) != 2 || second.Agents[0].ID != matched[2].ID {
		t.Fatalf("second page = %v, want items 3-4", idsOf(second.Agents))
	}

	last := postgresstore.PaginateForTest(matched, &orchestrator.Filter{Limit: 2, Cursor: second.Next})
	if len(last.Agents) != 1 || last.Agents[0].ID != matched[4].ID {
		t.Fatalf("last page = %v, want item 5", idsOf(last.Agents))
	}
	if last.Next != "" {
		t.Fatalf("last page Next = %q, want empty (no further pages)", last.Next)
	}

	all := postgresstore.PaginateForTest(matched, &orchestrator.Filter{Limit: 0})
	if len(all.Agents) != 5 || all.Next != "" {
		t.Fatalf("Limit<=0 page = %d agents, Next %q, want all 5 and empty Next", len(all.Agents), all.Next)
	}
}

// ── helpers ────────────────────────────────────────────────────────────────────────────────.

func idsOf(agents []orchestrator.Agent) []orchestrator.AgentID {
	out := make([]orchestrator.AgentID, len(agents))
	for i := range agents {
		out[i] = agents[i].ID
	}
	return out
}

// assertAgentEqual asserts every persisted field round-trips, delegating to focused checks so no
// single helper exceeds the strict cyclomatic ceiling.
func assertAgentEqual(t *testing.T, want, got *orchestrator.Agent) {
	t.Helper()
	assertAgentIdentity(t, want, got)
	assertAgentReconcileState(t, want, got)
	assertAgentLedgerAndStamps(t, want, got)
}

func assertAgentIdentity(t *testing.T, want, got *orchestrator.Agent) {
	t.Helper()
	if got.ID != want.ID || got.Tenant != want.Tenant || got.Template != want.Template || got.RunID != want.RunID {
		t.Fatalf("identity fields drifted:\n got %+v\nwant %+v", got, want)
	}
}

func assertAgentReconcileState(t *testing.T, want, got *orchestrator.Agent) {
	t.Helper()
	if got.Desired != want.Desired || got.Status != want.Status || got.Cluster != want.Cluster {
		t.Fatalf("desired/status/cluster drifted: got (%v,%v,%v) want (%v,%v,%v)", got.Desired, got.Status, got.Cluster, want.Desired, want.Status, want.Cluster)
	}
	if got.Session != want.Session || got.By != want.By || got.Detail != want.Detail {
		t.Fatalf("session/by/detail drifted: got (%q,%q,%q) want (%q,%q,%q)", got.Session, got.By, got.Detail, want.Session, want.By, want.Detail)
	}
	if got.Workspace.String() != want.Workspace.String() {
		t.Fatalf("opaque workspace handle drifted: got %q want %q", got.Workspace.String(), want.Workspace.String())
	}
}

func assertAgentLedgerAndStamps(t *testing.T, want, got *orchestrator.Agent) {
	t.Helper()
	if got.Limits != want.Limits {
		t.Fatalf("limits drifted: got %+v want %+v", got.Limits, want.Limits)
	}
	if got.Ledger.CostMicros != want.Ledger.CostMicros || got.Ledger.InputTokens != want.Ledger.InputTokens || got.Ledger.Turns != want.Ledger.Turns {
		t.Fatalf("ledger drifted: got %+v want %+v", got.Ledger, want.Ledger)
	}
	if !got.CreatedAt.Equal(want.CreatedAt) || !got.UpdatedAt.Equal(want.UpdatedAt) {
		t.Fatalf("timestamps drifted: got (%v,%v) want (%v,%v)", got.CreatedAt, got.UpdatedAt, want.CreatedAt, want.UpdatedAt)
	}
}
