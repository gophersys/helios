package devserve

import (
	"context"
	"strconv"
	"sync"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// inMemoryAuditStore is the DEV-ONLY gateway.AuditStore: a mutex-guarded append-only in-memory log of
// project audit events with an assigned monotonic Seq, mirroring the Postgres adapter's semantics
// (append-only, newest-first list scoped by project, cursor pagination) WITHOUT a database. It is the
// dev counterpart of auditpersistence.PostgresAuditStore. State is per-process and resets on restart.
type inMemoryAuditStore struct {
	mutex   sync.Mutex
	nextSeq int64
	events  []gateway.AuditEvent // append-only in insertion (Seq) order (newest last)
}

// devAuditPageFloor mirrors the Postgres adapter's no-limit page floor, kept identical so the fake and
// the real store agree on the unbounded-request path too.
const devAuditPageFloor = 100

// newInMemoryAuditStore returns an empty dev AuditStore. The caller stamps OccurredAt (from its
// Clock) on each Append, exactly as the real store takes OccurredAt as given.
func newInMemoryAuditStore() *inMemoryAuditStore { return &inMemoryAuditStore{} }

// Append assigns the next Seq, stores the event verbatim (OccurredAt as the caller stamped it), and
// returns the stored copy. There is no upsert and no delete — an audit trail is immutable.
//
//nolint:gocritic // gateway.AuditEvent is the copyable record; the store keeps its own copy.
func (s *inMemoryAuditStore) Append(_ context.Context, event gateway.AuditEvent) (gateway.AuditEvent, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	s.nextSeq++
	event.Seq = s.nextSeq
	s.events = append(s.events, event)
	return event, nil
}

// List returns the newest page (highest Seq first), scoped to filter.ProjectID when set, bounded by
// filter.Limit, with the opaque Next cursor (the last kept row's Seq) set when more rows remain. A
// cursor scopes the page to events older than it (Seq < cursor); a blank/malformed cursor lists from
// the top — the SAME cursor semantics as the project store.
//
//nolint:gocritic // gateway.AuditFilter is the frozen, copyable port input.
func (s *inMemoryAuditStore) List(_ context.Context, filter gateway.AuditFilter) (gateway.AuditPage, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	limit := filter.Limit
	if limit <= 0 {
		limit = devAuditPageFloor
	}
	cursor, hasCursor := parseCursor(filter.Cursor)

	matches := make([]gateway.AuditEvent, 0, limit+1)
	for i := len(s.events) - 1; i >= 0 && len(matches) <= limit; i-- {
		event := s.events[i]
		if filter.ProjectID != "" && event.ProjectID != filter.ProjectID {
			continue
		}
		if hasCursor && event.Seq >= cursor {
			continue
		}
		matches = append(matches, event)
	}

	page := gateway.AuditPage{Events: make([]gateway.AuditEvent, 0, limit)}
	for index := range matches {
		if index == limit {
			page.Next = strconv.FormatInt(matches[limit-1].Seq, 10)
			break
		}
		page.Events = append(page.Events, matches[index])
	}
	return page, nil
}

// compile-time assertion: *inMemoryAuditStore satisfies the gateway.AuditStore port.
var _ gateway.AuditStore = (*inMemoryAuditStore)(nil)
