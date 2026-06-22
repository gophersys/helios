package postgresstore

import (
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// agentRecord is the JSON-serializable projection of an orchestrator.Agent persisted in the
// `record` JSONB column. It carries ONLY plain values and OPAQUE refs (the workspaceprovider
// Handle as its loggable canonical string, the opaque SessionRef) — never a live handle, never
// a secret value (07 §2) — so the whole record round-trips through one row unchanged and a
// forward-compatible field added to Agent never breaks an existing row (contract §6).
type agentRecord struct {
	ID              string                   `json:"id"`
	OrganizationID  string                   `json:"organizationId"`
	ProjectID       string                   `json:"projectId"`
	TemplateName    string                   `json:"templateName"`
	TemplateVersion string                   `json:"templateVersion"`
	RunID           string                   `json:"runId"`
	Desired         uint8                    `json:"desired"`
	Status          uint8                    `json:"status"`
	ClusterID       string                   `json:"clusterId"`
	WorkspaceHandle string                   `json:"workspaceHandle"` // opaque, loggable Handle string (re-parsed on read)
	SessionRef      string                   `json:"sessionRef"`
	Ledger          agentsession.TokenLedger `json:"ledger"`
	Limits          orchestrator.Limits      `json:"limits"`
	CreatedBy       string                   `json:"createdBy"`
	CreatedAtUnixNs int64                    `json:"createdAt"`
	UpdatedAtUnixNs int64                    `json:"updatedAt"`
	Detail          string                   `json:"detail"`
}

// promotedColumns is the row form of an Agent: the scalar reconcile/List filter keys lifted out
// of the record so List is an indexed SQL query, plus the JSONB record itself. The store writes
// the columns and the record from this one value, so the two can never drift.
type promotedColumns struct {
	id              string
	organizationID  string
	projectID       string
	templateName    string
	templateVersion string
	runID           string
	desired         int16
	status          int16
	terminal        bool
	clusterID       string
	workspaceHandle string
	sessionRef      string
	ledgerJSON      []byte
	limitsJSON      []byte
	createdBy       string
	createdAt       time.Time
	updatedAt       time.Time
	detail          string
	recordJSON      []byte
}

// toRecord projects an Agent onto its serializable record form (the Handle flattens to its
// opaque canonical string; everything else is already a plain value).
//
//nolint:gocritic // Agent is the contract's copyable serializable record; the store persists its own copy by value.
func toRecord(agent orchestrator.Agent) agentRecord {
	return agentRecord{
		ID:              string(agent.ID),
		OrganizationID:  agent.Tenant.OrganizationID,
		ProjectID:       agent.Tenant.ProjectID,
		TemplateName:    agent.Template.Name,
		TemplateVersion: agent.Template.Version,
		RunID:           agent.RunID,
		Desired:         uint8(agent.Desired),
		Status:          uint8(agent.Status),
		ClusterID:       agent.Cluster.ID,
		WorkspaceHandle: agent.Workspace.String(),
		SessionRef:      string(agent.Session),
		Ledger:          agent.Ledger,
		Limits:          agent.Limits,
		CreatedBy:       agent.By,
		CreatedAtUnixNs: timeToUnixNano(agent.CreatedAt),
		UpdatedAtUnixNs: timeToUnixNano(agent.UpdatedAt),
		Detail:          agent.Detail,
	}
}

// fromRecord reconstructs an Agent from its persisted record, re-parsing the opaque Handle
// string (a zero string round-trips to the zero Handle — a not-yet-provisioned agent).
func fromRecord(record *agentRecord) (orchestrator.Agent, error) {
	handle, err := parseHandle(record.WorkspaceHandle)
	if err != nil {
		return orchestrator.Agent{}, err
	}
	return orchestrator.Agent{
		ID:        orchestrator.AgentID(record.ID),
		Tenant:    orchestrator.Tenancy{OrganizationID: record.OrganizationID, ProjectID: record.ProjectID},
		Template:  orchestrator.TemplateRef{Name: record.TemplateName, Version: record.TemplateVersion},
		RunID:     record.RunID,
		Desired:   orchestrator.Desired(record.Desired),
		Status:    orchestrator.Status(record.Status),
		Limits:    record.Limits,
		Cluster:   orchestrator.ClusterRef{ID: record.ClusterID},
		Workspace: handle,
		Session:   orchestrator.SessionRef(record.SessionRef),
		Ledger:    record.Ledger,
		By:        record.CreatedBy,
		CreatedAt: unixNanoToTime(record.CreatedAtUnixNs),
		UpdatedAt: unixNanoToTime(record.UpdatedAtUnixNs),
		Detail:    record.Detail,
	}, nil
}

// parseHandle re-parses the opaque Handle string; the empty string round-trips to the zero
// Handle (a not-yet-provisioned or session-only agent). A malformed PERSISTED handle is
// corruption, not a not-found — it is surfaced as a wrapped internal error.
func parseHandle(raw string) (workspaceprovider.Handle, error) {
	if raw == "" {
		return workspaceprovider.Handle{}, nil
	}
	handle, err := workspaceprovider.ParseHandle(raw)
	if err != nil {
		return workspaceprovider.Handle{}, errors.Wrap(errors.KindInternal,
			"orchestrator/postgresstore: re-parse persisted workspace handle", err)
	}
	return handle, nil
}

// timeToUnixNano maps a time to its UnixNano stamp, mapping the zero time to the zero stamp (so
// a not-yet-set timestamp round-trips as 0 rather than the Unix epoch's huge negative nanos).
func timeToUnixNano(t time.Time) int64 {
	if t.IsZero() {
		return 0
	}
	return t.UnixNano()
}

// unixNanoToTime reconstructs a time from its UnixNano stamp, mapping the zero stamp back to
// the zero time (the not-yet-set timestamp on a fresh record).
func unixNanoToTime(nanos int64) time.Time {
	if nanos == 0 {
		return time.Time{}
	}
	return time.Unix(0, nanos).UTC()
}
