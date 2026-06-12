package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"
)

// SupervisorWorkerBridge connects a supervisor agent and a worker agent.
// The worker can ask questions via a host tool, and the bridge routes them
// to the supervisor for answers.
type SupervisorWorkerBridge struct {
	mu           sync.Mutex
	supervisor   *Agent
	worker       *Agent
	questions    map[string]*PendingQuestion
	seq          int64
	maxRetries   int
	log          []BridgeLogEntry
}

type PendingQuestion struct {
	ID          string
	Question    string
	AskedAt     time.Time
	AnsweredAt  time.Time
	Answer      string
	Error       string
	Attempts    int
	Status      string // pending | answered | failed
}

type BridgeLogEntry struct {
	Timestamp   time.Time `json:"timestamp"`
	Direction   string    `json:"direction"` // worker->supervisor | supervisor->worker
	QuestionID  string    `json:"question_id"`
	Question    string    `json:"question"`
	Answer      string    `json:"answer,omitempty"`
	Duration    string    `json:"duration,omitempty"`
	Error       string    `json:"error,omitempty"`
}

// NewSupervisorWorkerBridge creates a new bridge between supervisor and worker agents.
// Both agents must have been started (rpc client non-nil).
func NewSupervisorWorkerBridge(supervisor, worker *Agent) *SupervisorWorkerBridge {
	if supervisor.rpc == nil {
		panic("NewSupervisorWorkerBridge: supervisor agent not started (rpc is nil)")
	}
	if worker.rpc == nil {
		panic("NewSupervisorWorkerBridge: worker agent not started (rpc is nil)")
	}
	bridge := &SupervisorWorkerBridge{
		supervisor: supervisor,
		worker:     worker,
		questions:  make(map[string]*PendingQuestion),
		maxRetries: 3,
	}
	worker.rpc.SetHostToolHandler(bridge.handleWorkerQuestion)
	return bridge
}

// handleWorkerQuestion processes a host tool call from the worker agent.
func (b *SupervisorWorkerBridge) handleWorkerQuestion(ctx context.Context, req RpcHostToolRequest) (interface{}, error) {
	// Parse the arguments
	var args struct {
		Question string `json:"question"`
	}
	if err := json.Unmarshal(req.Arguments, &args); err != nil {
		return map[string]interface{}{
			"isError": true,
			"content": []map[string]interface{}{
				{"type": "text", "text": fmt.Sprintf("Failed to parse question: %s", err.Error())},
			},
		}, nil
	}

	if args.Question == "" {
		return map[string]interface{}{
			"isError": true,
			"content": []map[string]interface{}{
				{"type": "text", "text": "Question cannot be empty"},
			},
		}, nil
	}

	// Record the question
	b.mu.Lock()
	b.seq++
	qID := fmt.Sprintf("q_%d", b.seq)
	pq := &PendingQuestion{
		ID:       qID,
		Question: args.Question,
		AskedAt:  time.Now(),
		Status:   "pending",
	}
	b.questions[qID] = pq
	b.mu.Unlock()

	b.logEntry("worker->supervisor", qID, args.Question, "", "")

	// Send to supervisor
	answer, err := b.askSupervisor(ctx, qID, args.Question)
	if err != nil {
		b.mu.Lock()
		pq.Status = "failed"
		pq.Error = err.Error()
		pq.Attempts++
		b.mu.Unlock()

		b.logEntry("worker->supervisor", qID, args.Question, "", err.Error())

		return map[string]interface{}{
			"isError": true,
			"content": []map[string]interface{}{
				{"type": "text", "text": fmt.Sprintf("Failed to get answer: %s", err.Error())},
			},
		}, nil
	}

	b.mu.Lock()
	pq.Status = "answered"
	pq.Answer = answer
	pq.AnsweredAt = time.Now()
	b.mu.Unlock()

	// Stream partial results back to worker (will show thinking)
	// Then final result
	go func() {
		// Send partial update
		b.mu.Lock()
		workerRPC := b.worker.rpc
		b.mu.Unlock()

		if workerRPC != nil {
			// Send partial update
			workerRPC.SendHostToolUpdate(req.ID, map[string]interface{}{
				"content": []map[string]interface{}{
					{"type": "text", "text": "Consulting supervisor..."},
				},
			})
		}
	}()

	b.logEntry("worker->supervisor", qID, args.Question, truncate(answer, 500), "")

	return map[string]interface{}{
		"content": []map[string]interface{}{
			{"type": "text", "text": answer},
		},
	}, nil
}

// askSupervisor sends a question to the supervisor agent and returns the answer.
func (b *SupervisorWorkerBridge) askSupervisor(ctx context.Context, qID, question string) (string, error) {
	promptMsg := fmt.Sprintf(`You are acting as a supervisor for a worker agent. The worker asks:

%s

Please provide a clear, concise, and helpful answer. Focus on being practical and actionable.`, question)

	supervisor := b.supervisor
	eventCh := supervisor.rpc.Subscribe(EventMessageUpdate)

	if err := supervisor.Prompt(ctx, promptMsg); err != nil {
		supervisor.rpc.Unsubscribe(eventCh)
		return "", fmt.Errorf("supervisor prompt: %w", err)
	}

	var fullAnswer string
	done := make(chan struct{})
	stop := make(chan struct{}) // signals the collector goroutine to stop

	go func() {
		defer close(done)
		for {
			select {
			case frame, ok := <-eventCh:
				if !ok {
					return
				}
				if frame.MessageEvent != nil {
					var msgEvt struct {
						Type  string `json:"type"`
						Delta string `json:"delta"`
					}
					if err := json.Unmarshal(frame.MessageEvent, &msgEvt); err == nil {
						if msgEvt.Type == "text_delta" || msgEvt.Type == "" {
							fullAnswer += msgEvt.Delta
						}
					}
				}
			case <-stop:
				return
			}
		}
	}()

	select {
	case <-done:
	case <-time.After(5 * time.Minute):
		close(stop)
		supervisor.rpc.Unsubscribe(eventCh)
		<-done // wait for collector to finish
		return fullAnswer + "\n[Answer truncated - timeout]",
			fmt.Errorf("supervisor answer timed out")
	case <-ctx.Done():
		close(stop)
		supervisor.rpc.Unsubscribe(eventCh)
		<-done // wait for collector to finish
		return fullAnswer + "\n[Answer interrupted]",
			ctx.Err()
	}

	if fullAnswer == "" {
		return "I don't have enough context to answer that question.", nil
	}
	return fullAnswer, nil
}

// AskWorker sends a prompt to the worker agent.
func (b *SupervisorWorkerBridge) AskWorker(ctx context.Context, message string) error {
	return b.worker.Prompt(ctx, message)
}

// GetQuestions returns all pending and answered questions.
func (b *SupervisorWorkerBridge) GetQuestions() []*PendingQuestion {
	b.mu.Lock()
	defer b.mu.Unlock()
	result := make([]*PendingQuestion, 0, len(b.questions))
	for _, q := range b.questions {
		result = append(result, q)
	}
	return result
}

// GetLog returns the bridge activity log.
func (b *SupervisorWorkerBridge) GetLog() []BridgeLogEntry {
	b.mu.Lock()
	defer b.mu.Unlock()
	log := make([]BridgeLogEntry, len(b.log))
	copy(log, b.log)
	return log
}

func (b *SupervisorWorkerBridge) logEntry(direction, qID, question, answer, errStr string) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.log = append(b.log, BridgeLogEntry{
		Timestamp:  time.Now(),
		Direction:  direction,
		QuestionID: qID,
		Question:   truncate(question, 200),
		Answer:     truncate(answer, 500),
		Error:      errStr,
	})
}

// Supervisor returns the supervisor agent.
func (b *SupervisorWorkerBridge) Supervisor() *Agent { return b.supervisor }

// Worker returns the worker agent.
func (b *SupervisorWorkerBridge) Worker() *Agent { return b.worker }