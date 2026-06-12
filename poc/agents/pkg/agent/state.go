package agent

import (
	"fmt"
	"sync"
	"time"
)

// StateMachine implements a simple event-driven agent lifecycle state machine.
type StateMachine struct {
	mu       sync.RWMutex
	current  AgentState
	transitions map[AgentState][]AgentState
	onChange func(from, to AgentState)
	createdAt time.Time
}

// NewStateMachine creates a new state machine starting in StateCreated.
func NewStateMachine(onChange func(from, to AgentState)) *StateMachine {
	sm := &StateMachine{
		current:  StateCreated,
		onChange: onChange,
		createdAt: time.Now(),
	}
	sm.transitions = map[AgentState][]AgentState{
		StateCreated:      {StateInitializing},
		StateInitializing: {StateReady, StateFailed},
		StateReady:        {StateRunning, StateFailed, StateCancelled},
		StateRunning:      {StatePaused, StateRunning, StateCompleted, StateFailed, StateCancelled},
		StatePaused:       {StateRunning, StateCancelled, StateFailed},
		StateCompleted:    {},
		StateFailed:       {},
		StateCancelled:    {},
	}
	return sm
}

// Current returns the current state.
func (sm *StateMachine) Current() AgentState {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return sm.current
}

// Transition attempts to move to the target state. Returns error if illegal.
func (sm *StateMachine) Transition(target AgentState) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	allowed, ok := sm.transitions[sm.current]
	if !ok {
		return fmt.Errorf("unknown current state: %s", sm.current)
	}

	valid := false
	for _, s := range allowed {
		if s == target {
			valid = true
			break
		}
	}
	if !valid {
		return fmt.Errorf("illegal transition: %s -> %s", sm.current, target)
	}

	from := sm.current
	sm.current = target

	if sm.onChange != nil {
		sm.onChange(from, target)
	}

	return nil
}

// MustTransition panics on illegal transition (for tests).
func (sm *StateMachine) MustTransition(target AgentState) {
	if err := sm.Transition(target); err != nil {
		panic(err)
	}
}

// CanTransition checks whether the transition is legal without applying it.
func (sm *StateMachine) CanTransition(target AgentState) bool {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	allowed, ok := sm.transitions[sm.current]
	if !ok {
		return false
	}
	for _, s := range allowed {
		if s == target {
			return true
		}
	}
	return false
}

// Uptime returns the time since the state machine was created.
func (sm *StateMachine) Uptime() time.Duration {
	return time.Since(sm.createdAt)
}

// IsTerminal returns true if the state cannot transition further.
func (sm *StateMachine) IsTerminal() bool {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	allowed, ok := sm.transitions[sm.current]
	return !ok || len(allowed) == 0
}
