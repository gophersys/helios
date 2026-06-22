package gateway

import (
	"context"
	"encoding/json"
	"time"
)

// This file is the DB-first create-saga's durable ledger contract: the CreateStep record (one row per
// saga step — the idempotency + replay ledger), the AuditEvent record (the append-only history of
// everything that happened to a project), and the two consumer-defined ports the saga drives them
// through (CreateStepStore, AuditStore). Both are OPTIONAL on Deps exactly like ProjectStore: a
// composition without the saga wires neither. A real Postgres adapter backs each in liveserve; an
// in-memory fake backs each in devserve — the same real-vs-fake mirror ProjectStore uses. No field is
// a credential: a step's Output and an event's Detail are redaction-safe JSON the saga itself
// authors, never a resolved secret.

// The closed CreateStep status set. A step is PENDING when first recorded (the saga claimed it), DONE
// when its effect committed, or FAILED when it faulted (LastError on the Project carries the human
// reason; the step's Output carries the machine detail). The set widens only via a contract revision.
const (
	CreateStepStatusPending = "pending"
	CreateStepStatusDone    = "done"
	CreateStepStatusFailed  = "failed"
)

// createStepStatuses is the closed set of legal CreateStep.Status tokens. It backs
// ValidCreateStepStatus so the ledger cannot record an off-contract step status.
var createStepStatuses = map[string]struct{}{
	CreateStepStatusPending: {},
	CreateStepStatusDone:    {},
	CreateStepStatusFailed:  {},
}

// ValidCreateStepStatus reports whether status is a member of the closed CreateStep status set.
func ValidCreateStepStatus(status string) bool {
	_, ok := createStepStatuses[status]
	return ok
}

// CreateStep is one row of the create-saga ledger: the durable record that a named Step of one
// Project's create-saga was attempted, with its current Status and an IdempotencyKey that makes a
// retried step a no-op (the saga keys each effect — repo creation, template seed — by this so a crash
// + replay never double-applies). Output is the step's redaction-safe machine result (e.g. the
// created repo's node id) the next step reads; it is raw JSON so a forward-compatible step shape never
// breaks the row. StartedAt is stamped when the step is first recorded; FinishedAt is set only when
// the step reaches a terminal Status (done/failed).
type CreateStep struct {
	ProjectID      string    `json:"projectId"`
	Step           string    `json:"step"`
	Status         string    `json:"status"`
	IdempotencyKey string    `json:"idempotencyKey"`
	Output         RawJSON   `json:"output,omitempty"`
	StartedAt      time.Time `json:"startedAt"`
	FinishedAt     time.Time `json:"finishedAt,omitempty"`
}

// RawJSON is a redaction-safe, opaque JSON document the saga authors and the next step reads (a
// step's machine Output, an audit event's structured Detail). It is a []byte holding valid JSON,
// stored verbatim in the JSONB column and round-tripped without a schema, so a step/event payload can
// evolve without a migration. A nil/empty RawJSON marshals to JSON null. It is NEVER a credential: the
// saga resolves any secret server-side and records only references/ids here.
type RawJSON = json.RawMessage

// CreateStepStore is the create-saga's ledger port: append/advance one Project's saga steps and read
// them back for replay. It is OPTIONAL on Deps (nil → the saga is not composed). The surface is four
// methods (the 5-method ceiling, 10 §9):
//
//   - Record inserts a PENDING step keyed by (ProjectID, Step) — idempotent on that key, so a replay
//     of an already-recorded step returns the stored row rather than a duplicate (the IdempotencyKey
//     and StartedAt of the first record win).
//   - Advance transitions a recorded step to a terminal Status (done/failed) with its Output,
//     stamping FinishedAt; a wrapped KindNotFound when the step was never recorded, KindInvalid when
//     the status is off-contract.
//   - Get returns one step by (ProjectID, Step) (a wrapped KindNotFound when absent) — the saga's
//     "have I already done this?" probe.
//   - List returns every step of one Project in StartedAt order (the saga's replay/inspection read).
type CreateStepStore interface {
	Record(ctx context.Context, step CreateStep) (CreateStep, error)
	Advance(ctx context.Context, projectID, step, status string, output RawJSON) (CreateStep, error)
	Get(ctx context.Context, projectID, step string) (CreateStep, error)
	List(ctx context.Context, projectID string) ([]CreateStep, error)
}

// AuditEvent is one append-only row of a project's history: at OccurredAt, an Action (a stable verb
// token, e.g. "project.created", "saga.step.failed") happened to the project named by ProjectID,
// optionally with an Actor (who/what caused it — an agent id, a user id, or "system") and a
// redaction-safe Detail (structured JSON the action authors). The append-only store assigns Seq (the
// monotonic order + cursor key). It is a forensic record, never a credential: Detail carries ids and
// references the saga resolves server-side, never a token value.
type AuditEvent struct {
	Seq        int64     `json:"seq"`
	ProjectID  string    `json:"projectId"`
	Action     string    `json:"action"`
	Actor      string    `json:"actor,omitempty"`
	Detail     RawJSON   `json:"detail,omitempty"`
	OccurredAt time.Time `json:"occurredAt"`
}

// AuditFilter bounds an audit read: scope to one ProjectID (empty = every project), a page Limit, and
// an opaque Cursor (the Seq boundary returned as a prior page's Next). The zero value lists the newest
// page across all projects.
type AuditFilter struct {
	ProjectID string
	Limit     int
	Cursor    string
}

// AuditPage is one page of audit events, newest first, plus the opaque Next cursor (empty when the
// page is the last) — the same cursor-pagination shape as ProjectPage.
type AuditPage struct {
	Events []AuditEvent
	Next   string
}

// AuditStore is the append-only audit port: append one event and read the history back, newest first,
// with cursor pagination. It is OPTIONAL on Deps (nil → no audit trail is recorded). The surface is
// two methods (well under the 5-method ceiling): Append assigns Seq + OccurredAt is taken as given by
// the caller's Clock and returns the stored copy; List returns the newest page matching the filter.
// There is intentionally no update/delete — an audit trail is immutable by construction.
type AuditStore interface {
	Append(ctx context.Context, event AuditEvent) (AuditEvent, error)
	List(ctx context.Context, filter AuditFilter) (AuditPage, error)
}
