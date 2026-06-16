package devserve

import (
	"context"
	"strconv"
	"sync"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/libs/go/errors"
)

// inMemoryProjectStore is the DEV-ONLY gateway.ProjectStore: a mutex-guarded in-memory list with an
// insertion-order seq, mirroring the Postgres adapter's semantics (newest-first list + cursor
// pagination, upsert-on-id) WITHOUT a database. It is the dev counterpart of
// projectpersistence.PostgresProjectStore — the same real-vs-fake mirror the Proposer uses — so the
// create-flow E2E exercises the SAME /projects surface the live demo runs. State is per-process and
// resets on restart (the deterministic dev plane).
type inMemoryProjectStore struct {
	mutex    sync.Mutex
	nextSeq  int64
	projects []storedProject // append-only, in insertion order (newest last)
}

// storedProject pairs a Project with its monotonic seq (the order + cursor key).
type storedProject struct {
	seq     int64
	project gateway.Project
}

// newInMemoryProjectStore returns an empty dev ProjectStore.
func newInMemoryProjectStore() *inMemoryProjectStore { return &inMemoryProjectStore{} }

// Create appends (or upserts on id) a Project and returns the stored copy.
//
//nolint:gocritic // gateway.Project is the copyable persisted record; the store keeps its own copy.
func (s *inMemoryProjectStore) Create(_ context.Context, project gateway.Project) (gateway.Project, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	for i := range s.projects {
		if s.projects[i].project.ID == project.ID {
			s.projects[i].project = project
			return project, nil
		}
	}
	s.nextSeq++
	s.projects = append(s.projects, storedProject{seq: s.nextSeq, project: project})
	return project, nil
}

// Get returns one Project by id (a wrapped KindNotFound when absent).
func (s *inMemoryProjectStore) Get(_ context.Context, id string) (gateway.Project, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	for i := range s.projects {
		if s.projects[i].project.ID == id {
			return s.projects[i].project, nil
		}
	}
	return gateway.Project{}, errors.New(errors.KindNotFound, "devserve: no project with id "+id)
}

// List returns the newest page (highest seq first), bounded by filter.Limit, with the opaque Next
// cursor (the last kept row's seq) set when more rows remain. A cursor scopes the page to rows older
// than it (seq < cursor); a blank/malformed cursor lists from the top.
//
//nolint:gocritic // gateway.ProjectFilter is the frozen, copyable port input.
func (s *inMemoryProjectStore) List(_ context.Context, filter gateway.ProjectFilter) (gateway.ProjectPage, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	limit := filter.Limit
	if limit <= 0 {
		limit = len(s.projects)
	}
	cursor, hasCursor := parseCursor(filter.Cursor)

	// Collect up to limit+1 matches newest → oldest (the slice is oldest → newest); the extra match
	// signals a further page, mirroring the Postgres adapter's limit+1 probe.
	matches := make([]storedProject, 0, limit+1)
	for i := len(s.projects) - 1; i >= 0 && len(matches) <= limit; i-- {
		entry := s.projects[i]
		if hasCursor && entry.seq >= cursor {
			continue
		}
		matches = append(matches, entry)
	}

	page := gateway.ProjectPage{Projects: make([]gateway.Project, 0, limit)}
	for index, match := range matches {
		if index == limit {
			page.Next = strconv.FormatInt(matches[limit-1].seq, 10)
			break
		}
		page.Projects = append(page.Projects, match.project)
	}
	return page, nil
}

// parseCursor decodes an opaque list cursor (a seq boundary). A blank or malformed cursor lists from
// the top (ok=false) rather than erroring — a stale cursor degrades to "from the newest".
func parseCursor(cursor string) (int64, bool) {
	if cursor == "" {
		return 0, false
	}
	value, err := strconv.ParseInt(cursor, 10, 64)
	if err != nil || value <= 0 {
		return 0, false
	}
	return value, true
}

// compile-time assertion: *inMemoryProjectStore satisfies the gateway.ProjectStore port.
var _ gateway.ProjectStore = (*inMemoryProjectStore)(nil)
