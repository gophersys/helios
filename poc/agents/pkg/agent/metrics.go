package agent

import (
	"encoding/json"
	"fmt"
	"io"
	"sync"
	"sync/atomic"
	"time"
)

// MetricsEvent is a wire-format event for SSE streaming.
type MetricsEvent struct {
	ID        string            `json:"id"`
	AgentID   string            `json:"agent_id"`
	Type      MetricType        `json:"type"`
	Timestamp time.Time         `json:"timestamp"`
	Duration  time.Duration     `json:"duration_ns,omitempty"`
	Labels    map[string]string `json:"labels,omitempty"`
	Payload   json.RawMessage   `json:"payload,omitempty"`
	ToolName  string            `json:"tool_name,omitempty"`
	ModelID   string            `json:"model_id,omitempty"`

	// Token tracking — always present so JS sees 0 instead of undefined
	InputTokens   int64   `json:"input_tokens"`
	OutputTokens  int64   `json:"output_tokens"`
	CostUSD       float64 `json:"cost_usd"`

	// Lifecycle counters
	TurnCount     int64 `json:"turn_count"`
	ToolCallCount int64 `json:"tool_call_count"`
	FileSystemOps int64 `json:"filesystem_ops"`

	// File system
	FSPath      string `json:"fs_path,omitempty"`
	FSOperation string `json:"fs_operation,omitempty"`

	// State transitions
	StateFrom string `json:"state_from,omitempty"`
	StateTo   string `json:"state_to,omitempty"`

	// Errors
	ErrorMessage string `json:"error_message,omitempty"`
}

// SSEEvent formats an event for Server-Sent Events protocol.
type SSEEvent struct {
	Event string
	Data  string
	ID    string
}

// WriteTo writes the SSE event to the writer in SSE wire format.
func (e *SSEEvent) WriteTo(w io.Writer) (int64, error) {
	var n int64
	if e.ID != "" {
		nn, _ := fmt.Fprintf(w, "id: %s\n", e.ID)
		n += int64(nn)
	}
	if e.Event != "" {
		nn, _ := fmt.Fprintf(w, "event: %s\n", e.Event)
		n += int64(nn)
	}
	// SSE spec: prefix each data line with "data: "
	nn, _ := fmt.Fprintf(w, "data: %s\n\n", e.Data)
	n += int64(nn)
	return n, nil
}

// subscriber represents a single SSE consumer with delivery guarantees.
type subscriber struct {
	id       string
	ch       chan MetricsEvent
	bufSz    int
	created  time.Time
	dropped  atomic.Int64
	sent     atomic.Int64
	lastID   string
	done     chan struct{}
}

// MetricsBus is a high-throughput metrics bus with SSE-aware ring buffer.
type MetricsBus struct {
	agentID string

	mu          sync.RWMutex
	ring        []MetricsEvent
	ringHead    int64
	ringTail    int64
	ringCap     int64
	ringMask    int64 // power-of-two: cap-1

	subs     map[string]*subscriber
	subSeq   atomic.Int64

	seq      atomic.Int64
	totalEmitted atomic.Int64

	done    chan struct{}
}

// NewMetricsBus creates a metrics bus with a power-of-two ring buffer.
// maxSize is rounded up to the next power of two.
func NewMetricsBus(agentID string, maxSize int) *MetricsBus {
	if maxSize < 8 {
		maxSize = 8
	}
	// Round to power of two
	cap := int64(1)
	for cap < int64(maxSize) {
		cap <<= 1
	}
	return &MetricsBus{
		agentID:  agentID,
		ring:     make([]MetricsEvent, cap),
		ringMask: cap - 1,
		ringCap:  cap,
		subs:     make(map[string]*subscriber),
		done:     make(chan struct{}),
	}
}

// nextID generates a unique, ordered metric ID.
func (mb *MetricsBus) nextID() string {
	n := mb.seq.Add(1)
	ts := time.Now().UnixNano()
	return fmt.Sprintf("%s_%016x_%04x", mb.agentID, ts, n)
}

// Emit records a metric and broadcasts to subscribers. Non-blocking.
func (mb *MetricsBus) Emit(m Metric) MetricsEvent {
	ev := mb.toEvent(m)
	if ev.ID == "" {
		ev.ID = mb.nextID()
	}

	mb.mu.Lock()
	// Write to ring buffer
	head := mb.ringHead
	idx := head & mb.ringMask
	mb.ring[idx] = ev
	mb.ringHead = head + 1
	if mb.ringHead-mb.ringTail > mb.ringCap {
		mb.ringTail = mb.ringHead - mb.ringCap // evict oldest
	}

	// Broadcast to subscribers (non-blocking per sub)
	for _, sub := range mb.subs {
		select {
		case sub.ch <- ev:
			sub.sent.Add(1)
			sub.lastID = ev.ID
		default:
			sub.dropped.Add(1)
			// Slow consumer — skip this event
		}
	}
	mb.totalEmitted.Add(1)
	mb.mu.Unlock()

	return ev
}

// SubscribeSSE creates a subscriber for SSE streaming with replay support.
// bufSz is the channel buffer; replayCount replays that many recent events.
// Returns the subscriber, a channel to read events from, and a cleanup func.
func (mb *MetricsBus) SubscribeSSE(bufSz, replayCount int) (*subscriber, <-chan MetricsEvent, func()) {
	if bufSz <= 0 {
		bufSz = 256
	}
	if replayCount <= 0 {
		replayCount = 0
	}
	id := fmt.Sprintf("sub_%d", mb.subSeq.Add(1))
	ch := make(chan MetricsEvent, bufSz)
	sub := &subscriber{
		id:      id,
		ch:      ch,
		bufSz:   bufSz,
		created: time.Now(),
		done:    make(chan struct{}),
	}

	mb.mu.Lock()
	mb.subs[id] = sub

	// Replay recent events
	if replayCount > 0 && mb.ringHead > mb.ringTail {
		start := mb.ringHead - int64(replayCount)
		if start < mb.ringTail {
			start = mb.ringTail
		}
		for i := start; i < mb.ringHead; i++ {
			ch <- mb.ring[i&mb.ringMask]
		}
	}
	mb.mu.Unlock()

	var unsubOnce sync.Once
	unsub := func() {
		unsubOnce.Do(func() {
			mb.mu.Lock()
			delete(mb.subs, id)
			mb.mu.Unlock()
			close(ch)
			close(sub.done)
		})
	}

	return sub, ch, unsub
}

// Subscribe returns a channel receiving all new metrics.
func (mb *MetricsBus) Subscribe(bufSize int) (<-chan Metric, func()) {
	if bufSize <= 0 {
		bufSize = 100
	}
	ch := make(chan Metric, bufSize)

	// Create SSE sub, then filter to Metric format
	_, evCh, unsub := mb.SubscribeSSE(256, 0)
	go func() {
		for ev := range evCh {
			m := MetricsEventToMetric(ev)
			select {
			case ch <- m:
			default:
			}
		}
	}()

	return ch, unsub
}

// WriteSSE writes all events from the subscriber as SSE to the writer.
// Blocks until subscriber is closed or context is cancelled.
// Call in a goroutine per HTTP SSE connection.
func (mb *MetricsBus) WriteSSE(sub *subscriber, w io.Writer, done <-chan struct{}) error {
	ticker := time.NewTicker(15 * time.Second) // keepalive
	defer ticker.Stop()

	for {
		select {
		case ev, ok := <-sub.ch:
			if !ok {
				return nil
			}
			data, err := json.Marshal(ev)
			if err != nil {
				continue
			}
			sse := SSEEvent{Event: "metrics", Data: string(data), ID: ev.ID}
			if _, err := sse.WriteTo(w); err != nil {
				flusher, flushOk := w.(interface{ Flush() })
				if flushOk {
					flusher.Flush()
				}
				return err
			}
			flusher, flushOk := w.(interface{ Flush() })
			if flushOk {
				flusher.Flush()
			}

		case <-ticker.C:
			// SSE keepalive comment
			sse := SSEEvent{Event: "keepalive", Data: fmt.Sprintf(`{"time":"%s"}`, time.Now().Format(time.RFC3339Nano))}
			sse.WriteTo(w)
			flusher, flushOk := w.(interface{ Flush() })
			if flushOk {
				flusher.Flush()
			}

		case <-sub.done:
			return nil

		case <-done:
			return nil

		case <-mb.done:
			return nil
		}
	}
}

// Snapshot returns a copy of the ring buffer contents in order.
func (mb *MetricsBus) Snapshot() []Metric {
	mb.mu.RLock()
	defer mb.mu.RUnlock()

	count := mb.ringHead - mb.ringTail
	if count <= 0 {
		return nil
	}
	result := make([]Metric, 0, count)
	for i := mb.ringTail; i < mb.ringHead; i++ {
		ev := mb.ring[i&mb.ringMask]
		result = append(result, MetricsEventToMetric(ev))
	}
	return result
}

// SnapshotEvents returns raw MetricsEvents in order.
func (mb *MetricsBus) SnapshotEvents() []MetricsEvent {
	mb.mu.RLock()
	defer mb.mu.RUnlock()

	count := mb.ringHead - mb.ringTail
	if count <= 0 {
		return nil
	}
	result := make([]MetricsEvent, 0, count)
	for i := mb.ringTail; i < mb.ringHead; i++ {
		result = append(result, mb.ring[i&mb.ringMask])
	}
	return result
}

// Clear resets the ring buffer.
func (mb *MetricsBus) Clear() {
	mb.mu.Lock()
	mb.ringHead = 0
	mb.ringTail = 0
	mb.mu.Unlock()
}

// ExportJSON returns accumulated metrics as indented JSON.
func (mb *MetricsBus) ExportJSON() ([]byte, error) {
	snap := mb.Snapshot()
	return json.MarshalIndent(snap, "", "  ")
}

// Len returns event count in ring buffer.
func (mb *MetricsBus) Len() int {
	mb.mu.RLock()
	defer mb.mu.RUnlock()
	return int(mb.ringHead - mb.ringTail)
}

// TotalEmitted returns lifetime metric count.
func (mb *MetricsBus) TotalEmitted() int64 {
	return mb.totalEmitted.Load()
}

// SubscriberStats returns stats for all subscribers.
func (mb *MetricsBus) SubscriberStats() []map[string]interface{} {
	mb.mu.RLock()
	defer mb.mu.RUnlock()
	var stats []map[string]interface{}
	for _, sub := range mb.subs {
		stats = append(stats, map[string]interface{}{
			"id":       sub.id,
			"sent":     sub.sent.Load(),
			"dropped":  sub.dropped.Load(),
			"uptime":   time.Since(sub.created).String(),
			"buffer":   sub.bufSz,
		})
	}
	return stats
}

// Close stops the metrics bus.
func (mb *MetricsBus) Close() {
	select {
	case <-mb.done:
	default:
		close(mb.done)
	}
}

// toEvent converts a Metric to the wire-format MetricsEvent.
func (mb *MetricsBus) toEvent(m Metric) MetricsEvent {
	return MetricsEvent{
		ID:            m.ID,
		AgentID:       m.AgentID,
		Type:          m.Type,
		Timestamp:     m.Timestamp,
		Duration:      m.Duration,
		Labels:        m.Labels,
		Payload:       m.Payload,
		ToolName:      m.ToolName,
		ModelID:       m.ModelID,
		InputTokens:   m.InputTokens,
		OutputTokens:  m.OutputTokens,
		CostUSD:       m.CostUSD,
		TurnCount:     m.TurnCount,
		ToolCallCount: m.ToolCallCount,
		FileSystemOps: m.FileSystemOps,
		FSPath:        m.FSPath,
		FSOperation:   m.FSOperation,
		StateFrom:     m.StateFrom,
		StateTo:       m.StateTo,
		ErrorMessage:  m.ErrorMessage,
	}
}

// MetricsEventToMetric converts back.
func MetricsEventToMetric(ev MetricsEvent) Metric {
	return Metric{
		ID:            ev.ID,
		AgentID:       ev.AgentID,
		Type:          ev.Type,
		Timestamp:     ev.Timestamp,
		Duration:      ev.Duration,
		Labels:        ev.Labels,
		Payload:       ev.Payload,
		ToolName:      ev.ToolName,
		ModelID:       ev.ModelID,
		InputTokens:   ev.InputTokens,
		OutputTokens:  ev.OutputTokens,
		CostUSD:       ev.CostUSD,
		TurnCount:     ev.TurnCount,
		ToolCallCount: ev.ToolCallCount,
		FileSystemOps: ev.FileSystemOps,
		FSPath:        ev.FSPath,
		FSOperation:   ev.FSOperation,
		StateFrom:     ev.StateFrom,
		StateTo:       ev.StateTo,
		ErrorMessage:  ev.ErrorMessage,
	}
}
