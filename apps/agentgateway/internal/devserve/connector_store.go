package devserve

import (
	"context"
	"sort"
	"sync"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/libs/go/errors"
)

// inMemoryConnectorStore is the DEV-ONLY gateway.ConnectorStore: a mutex-guarded slice of connectors,
// mirroring the (future) platformgateway domain's semantics (upsert keyed by (kind, name) + list +
// delete) WITHOUT a database. It is the dev counterpart of the envelope-encrypted /v1/connectors
// domain (design §2), so the Settings → Connectors section is exercised by the same E2E the live demo
// runs. State resets on restart.
//
// It NEVER holds a plaintext credential: a gateway.Connector carries only the one-way fingerprint +
// the non-secret account hint (the plaintext is digested and discarded in the handler before it ever
// reaches this store). The write-only invariant therefore holds by construction on the dev backend
// too — there is no plaintext for any read path to leak.
type inMemoryConnectorStore struct {
	mutex      sync.Mutex
	connectors []gateway.Connector
}

// newInMemoryConnectorStore returns an empty dev ConnectorStore.
func newInMemoryConnectorStore() *inMemoryConnectorStore {
	return &inMemoryConnectorStore{}
}

// Put upserts the connector keyed by (Kind, Name) and returns the stored copy (mirroring the
// platform domain's UNIQUE (organization_id, kind, name) upsert). A new connector is appended;
// an existing (kind, name) is replaced (a rotation re-seals under the same identity).
//
//nolint:gocritic // gateway.Connector is the copyable persisted record; the store keeps its own copy.
func (s *inMemoryConnectorStore) Put(_ context.Context, connector gateway.Connector) (gateway.Connector, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	for i := range s.connectors {
		if s.connectors[i].Kind == connector.Kind && s.connectors[i].Name == connector.Name {
			// Preserve the existing id on a rotation (same identity, fresh fingerprint).
			connector.ID = s.connectors[i].ID
			s.connectors[i] = connector
			return connector, nil
		}
	}
	s.connectors = append(s.connectors, connector)
	return connector, nil
}

// List returns every stored connector, sorted by kind then name for a deterministic render.
func (s *inMemoryConnectorStore) List(_ context.Context) ([]gateway.Connector, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	out := make([]gateway.Connector, len(s.connectors))
	copy(out, s.connectors)
	sort.Slice(out, func(i, j int) bool {
		if out[i].Kind != out[j].Kind {
			return out[i].Kind < out[j].Kind
		}
		return out[i].Name < out[j].Name
	})
	return out, nil
}

// Delete removes one connector by id (a wrapped KindNotFound when absent).
func (s *inMemoryConnectorStore) Delete(_ context.Context, id string) error {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	for i := range s.connectors {
		if s.connectors[i].ID == id {
			s.connectors = append(s.connectors[:i], s.connectors[i+1:]...)
			return nil
		}
	}
	return errors.New(errors.KindNotFound, "devserve: no connector "+id)
}

// compile-time assertion: *inMemoryConnectorStore satisfies the gateway.ConnectorStore port.
var _ gateway.ConnectorStore = (*inMemoryConnectorStore)(nil)
