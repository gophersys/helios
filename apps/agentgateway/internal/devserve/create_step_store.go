package devserve

import (
	"context"
	"strconv"
	"sync"
	"time"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/libs/go/errors"
)

// inMemoryCreateStepStore is the DEV-ONLY gateway.CreateStepStore: a mutex-guarded in-memory ledger
// of the create-saga's steps, mirroring the Postgres adapter's semantics (idempotent Record on
// (projectID, step), terminal Advance, StartedAt-ordered List) WITHOUT a database. It is the dev
// counterpart of createsteppersistence.PostgresCreateStepStore — the same real-vs-fake mirror
// ProjectStore uses — so a saga-driven dev run exercises the SAME ledger surface the live demo runs.
// State is per-process and resets on restart.
type inMemoryCreateStepStore struct {
	mutex sync.Mutex
	steps []gateway.CreateStep // append-only in StartedAt order (first-recorded first)
	clock gateway.Clock        // stamps StartedAt on Record + FinishedAt on Advance (the fixed dev clock).
}

// newInMemoryCreateStepStore returns an empty dev CreateStepStore stamping its times from clock.
func newInMemoryCreateStepStore(clock gateway.Clock) *inMemoryCreateStepStore {
	return &inMemoryCreateStepStore{clock: clock}
}

// Record inserts a PENDING step keyed by (ProjectID, Step) — idempotent on that key, so a replay of
// an already-recorded step returns the stored row unchanged (the first record's IdempotencyKey +
// StartedAt win). Status is forced to PENDING and StartedAt stamped from the dev clock.
//
//nolint:gocritic // gateway.CreateStep is the copyable ledger record; the store keeps its own copy.
func (s *inMemoryCreateStepStore) Record(_ context.Context, step gateway.CreateStep) (gateway.CreateStep, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	for i := range s.steps {
		if s.steps[i].ProjectID == step.ProjectID && s.steps[i].Step == step.Step {
			return s.steps[i], nil
		}
	}
	step.Status = gateway.CreateStepStatusPending
	step.StartedAt = s.clock.Now()
	step.FinishedAt = time.Time{}
	s.steps = append(s.steps, step)
	return step, nil
}

// Advance transitions a recorded step to a terminal status (done/failed) with its Output, stamping
// FinishedAt from the dev clock. An off-contract or non-terminal status is a wrapped KindInvalid; a
// step never recorded is a wrapped KindNotFound.
func (s *inMemoryCreateStepStore) Advance(_ context.Context, projectID, step, status string, output gateway.RawJSON) (gateway.CreateStep, error) {
	if !gateway.ValidCreateStepStatus(status) || status == gateway.CreateStepStatusPending {
		return gateway.CreateStep{}, errors.New(errors.KindInvalid,
			"devserve: advance create step to a non-terminal status "+strconv.Quote(status))
	}
	s.mutex.Lock()
	defer s.mutex.Unlock()
	for i := range s.steps {
		if s.steps[i].ProjectID == projectID && s.steps[i].Step == step {
			s.steps[i].Status = status
			s.steps[i].Output = output
			s.steps[i].FinishedAt = s.clock.Now()
			return s.steps[i], nil
		}
	}
	return gateway.CreateStep{}, errors.New(errors.KindNotFound,
		"devserve: no create step "+strconv.Quote(step)+" for project "+projectID)
}

// Get returns one step by (ProjectID, Step) (a wrapped KindNotFound when absent).
func (s *inMemoryCreateStepStore) Get(_ context.Context, projectID, step string) (gateway.CreateStep, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	for i := range s.steps {
		if s.steps[i].ProjectID == projectID && s.steps[i].Step == step {
			return s.steps[i], nil
		}
	}
	return gateway.CreateStep{}, errors.New(errors.KindNotFound,
		"devserve: no create step "+strconv.Quote(step)+" for project "+projectID)
}

// List returns every step of one project in StartedAt (record) order.
func (s *inMemoryCreateStepStore) List(_ context.Context, projectID string) ([]gateway.CreateStep, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	out := make([]gateway.CreateStep, 0)
	for i := range s.steps {
		if s.steps[i].ProjectID == projectID {
			out = append(out, s.steps[i])
		}
	}
	return out, nil
}

// compile-time assertion: *inMemoryCreateStepStore satisfies the gateway.CreateStepStore port.
var _ gateway.CreateStepStore = (*inMemoryCreateStepStore)(nil)
