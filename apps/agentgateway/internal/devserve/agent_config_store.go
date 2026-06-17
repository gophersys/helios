package devserve

import (
	"context"
	"sort"
	"sync"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/libs/go/errors"
)

// inMemoryAgentConfigStore is the DEV-ONLY gateway.AgentConfigStore: a mutex-guarded map keyed by
// agent type, mirroring the Postgres adapter's semantics (upsert + sorted list) WITHOUT a database.
// It is the dev counterpart of agentconfigpersistence.PostgresAgentConfigStore, so the Settings →
// Agents surface is exercised by the same E2E the live demo runs. State resets on restart.
type inMemoryAgentConfigStore struct {
	mutex   sync.Mutex
	configs map[string]gateway.AgentConfig
}

// newInMemoryAgentConfigStore returns an empty dev AgentConfigStore.
func newInMemoryAgentConfigStore() *inMemoryAgentConfigStore {
	return &inMemoryAgentConfigStore{configs: map[string]gateway.AgentConfig{}}
}

// Put upserts the configuration for its agent type and returns the stored copy.
//
//nolint:gocritic // gateway.AgentConfig is the copyable persisted record; the store keeps its own copy.
func (s *inMemoryAgentConfigStore) Put(_ context.Context, configuration gateway.AgentConfig) (gateway.AgentConfig, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	s.configs[configuration.AgentType] = configuration
	return configuration, nil
}

// Get returns one configuration by agent type (a wrapped KindNotFound when absent).
func (s *inMemoryAgentConfigStore) Get(_ context.Context, agentType string) (gateway.AgentConfig, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	configuration, ok := s.configs[agentType]
	if !ok {
		return gateway.AgentConfig{}, errors.New(errors.KindNotFound, "devserve: no configuration for agent type "+agentType)
	}
	return configuration, nil
}

// List returns every saved configuration, sorted by agent type for a deterministic render.
func (s *inMemoryAgentConfigStore) List(_ context.Context) ([]gateway.AgentConfig, error) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	configs := make([]gateway.AgentConfig, 0, len(s.configs))
	for _, configuration := range s.configs {
		configs = append(configs, configuration)
	}
	sort.Slice(configs, func(i, j int) bool { return configs[i].AgentType < configs[j].AgentType })
	return configs, nil
}

// compile-time assertion: *inMemoryAgentConfigStore satisfies the gateway.AgentConfigStore port.
var _ gateway.AgentConfigStore = (*inMemoryAgentConfigStore)(nil)
