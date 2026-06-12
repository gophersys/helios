package agent

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"math"
	"math/rand"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestMetricsBus_PowerOfTwoRing(t *testing.T) {
	for _, sz := range []int{0, 1, 7, 8, 9, 100, 1000} {
		mb := NewMetricsBus("t", sz)
		if cap := mb.ringCap; cap < 8 || (cap&(cap-1)) != 0 {
			t.Errorf("size %d -> cap %d", sz, cap)
		}
		mb.Close()
	}
}

func TestMetricsBus_RingOverwrite(t *testing.T) {
	mb := NewMetricsBus("t", 4)
	for i := 0; i < 100; i++ {
		mb.Emit(Metric{Type: MetricLLM, ToolName: fmt.Sprintf("t%d", i)})
	}
	if n := mb.TotalEmitted(); n != 100 {
		t.Errorf("emitted %d", n)
	}
	if n := mb.Len(); n > 8 {
		t.Errorf("snap %d > 8", n)
	}
}

func TestMetricsBus_ConcurrentEmit(t *testing.T) {
	mb := NewMetricsBus("conc", 1000)
	var wg sync.WaitGroup
	n := 1000
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(j int) {
			defer wg.Done()
			mb.Emit(Metric{Type: MetricToolCall, ToolName: fmt.Sprintf("t%d", j), InputTokens: int64(j)})
		}(i)
	}
	wg.Wait()
	if mb.TotalEmitted() != int64(n) {
		t.Errorf("emitted %d", mb.TotalEmitted())
	}
}

func TestMetricsBus_SubscriberSlowConsumer(t *testing.T) {
	mb := NewMetricsBus("slow", 100)
	_, ch, unsub := mb.SubscribeSSE(2, 0)
	defer unsub()
	for i := 0; i < 100; i++ {
		mb.Emit(Metric{Type: MetricLLM})
	}
	if n := len(mb.SubscriberStats()); n == 0 {
		t.Fatal("no subs")
	}
	drained := 0
	for {
		select {
		case <-ch:
			drained++
		default:
			goto done
		}
	}
done:
	_ = drained
}

func TestMetricsBus_SubscriberReplay(t *testing.T) {
	mb := NewMetricsBus("replay", 100)
	for i := 0; i < 10; i++ {
		mb.Emit(Metric{Type: MetricLLM, ToolName: fmt.Sprintf("pre%d", i)})
	}
	_, ch, unsub := mb.SubscribeSSE(100, 5)
	defer unsub()
	replayed := 0
	for {
		select {
		case <-ch:
			replayed++
			if replayed == 5 {
				return
			}
		case <-time.After(time.Second):
			t.Fatal("timeout")
		}
	}
}

func TestMetricsBus_SSEFormat(t *testing.T) {
	mb := NewMetricsBus("sse", 10)
	ev := mb.Emit(Metric{Type: MetricLLM, ModelID: "m", InputTokens: 100, OutputTokens: 50})
	sse := SSEEvent{Event: "metrics", Data: `{"x":1}`, ID: ev.ID}
	var buf bytes.Buffer
	sse.WriteTo(&buf)
	out := buf.String()
	if !strings.Contains(out, "event: metrics") {
		t.Error("missing event")
	}
	if !strings.Contains(out, "id: ") {
		t.Error("missing id")
	}
	if !strings.Contains(out, "data: ") {
		t.Error("missing data")
	}
}

func TestMetricsBus_ConcurrentSubscribeUnsubscribe(t *testing.T) {
	mb := NewMetricsBus("sub", 1000)
	var subs []func()
	var mu sync.Mutex
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _, unsub := mb.SubscribeSSE(10, 0)
			mu.Lock()
			subs = append(subs, unsub)
			mu.Unlock()
		}()
	}
	wg.Wait()
	for i := 0; i < 100; i++ {
		mb.Emit(Metric{Type: MetricLLM})
	}
	var uwg sync.WaitGroup
	mu.Lock()
	for _, u := range subs {
		uwg.Add(1)
		go func(un func()) { defer uwg.Done(); un() }(u)
	}
	mu.Unlock()
	uwg.Wait()
	if n := len(mb.SubscriberStats()); n != 0 {
		t.Errorf("got %d subs", n)
	}
}

func TestMetricsBus_SnapshotEmpty(t *testing.T) {
	mb := NewMetricsBus("empty", 10)
	if len(mb.Snapshot()) != 0 {
		t.Error("expected empty")
	}
	mb.Close()
}

func TestMetricsBus_ExportJSONValid(t *testing.T) {
	mb := NewMetricsBus("json", 10)
	mb.Emit(Metric{Type: MetricLLM, InputTokens: 1, OutputTokens: 2, CostUSD: 0.0001})
	mb.Emit(Metric{Type: MetricToolCall, ToolName: "read", Duration: time.Second})
	b, err := mb.ExportJSON()
	if err != nil {
		t.Fatal(err)
	}
	var parsed []Metric
	if err := json.Unmarshal(b, &parsed); err != nil {
		t.Fatalf("bad JSON: %v", err)
	}
	if len(parsed) != 2 {
		t.Errorf("got %d", len(parsed))
	}
}

func TestMetricsEventToMetric_Roundtrip(t *testing.T) {
	mt := Metric{
		ID: "t1", Type: MetricLLM, Timestamp: time.Now(),
		InputTokens: 100, OutputTokens: 50, CostUSD: 0.01,
		ToolName: "read", ModelID: "m",
	}
	ev := MetricsEvent{
		ID: mt.ID, AgentID: mt.AgentID, Type: mt.Type, Timestamp: mt.Timestamp,
		Duration: mt.Duration, Labels: mt.Labels, Payload: mt.Payload,
		ToolName: mt.ToolName, ModelID: mt.ModelID,
		InputTokens: mt.InputTokens, OutputTokens: mt.OutputTokens, CostUSD: mt.CostUSD,
		FSPath: mt.FSPath, FSOperation: mt.FSOperation,
		StateFrom: mt.StateFrom, StateTo: mt.StateTo, ErrorMessage: mt.ErrorMessage,
	}
	back := MetricsEventToMetric(ev)
	if back.ID != mt.ID || back.InputTokens != mt.InputTokens {
		t.Error("roundtrip failed")
	}
}

func TestStateMachine_FuzzTransitions(t *testing.T) {
	all := []AgentState{StateCreated, StateInitializing, StateReady, StateRunning,
		StatePaused, StateCompleted, StateFailed, StateCancelled}
	for i := 0; i < 1000; i++ {
		sm := NewStateMachine(nil)
		for j := 0; j < 20; j++ {
			sm.Transition(all[rand.Intn(len(all))])
		}
	}
}

func TestStateMachine_ConcurrentTransitions(t *testing.T) {
	sm := NewStateMachine(nil)
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			sm.Transition(StateInitializing)
			sm.Transition(StateReady)
			sm.Transition(StateRunning)
			sm.Transition(StatePaused)
			sm.CanTransition(StateCompleted)
			sm.Current()
			sm.Uptime()
		}()
	}
	wg.Wait()
}

func TestStateMachine_AllLegalPaths(t *testing.T) {
	type pc struct{ prep, path []AgentState }
	for _, c := range []pc{
		{nil, []AgentState{StateInitializing, StateReady}},
		{nil, []AgentState{StateInitializing, StateFailed}},
		{[]AgentState{StateInitializing, StateReady}, []AgentState{StateRunning, StatePaused}},
		{[]AgentState{StateInitializing, StateReady}, []AgentState{StateRunning, StateCompleted}},
		{[]AgentState{StateInitializing, StateReady}, []AgentState{StateRunning, StateFailed}},
		{[]AgentState{StateInitializing, StateReady}, []AgentState{StateRunning, StateCancelled}},
		{[]AgentState{StateInitializing, StateReady}, []AgentState{StateCancelled}},
		{[]AgentState{StateInitializing, StateReady, StateRunning, StatePaused}, []AgentState{StateRunning, StateCompleted}},
		{[]AgentState{StateInitializing, StateReady, StateRunning, StatePaused}, []AgentState{StateCancelled}},
	} {
		sm := NewStateMachine(nil)
		for _, s := range c.prep {
			if err := sm.Transition(s); err != nil {
				t.Fatalf("prep %v at %s: %v", c.prep, s, err)
			}
		}
		for _, s := range c.path {
			if err := sm.Transition(s); err != nil {
				t.Fatalf("path %v at %s: %v", c.path, s, err)
			}
		}
	}
}

func TestStateMachine_ConcurrentReadState(t *testing.T) {
	sm := NewStateMachine(nil)
	sm.MustTransition(StateInitializing)
	sm.MustTransition(StateReady)
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				sm.Current()
				sm.CanTransition(StateRunning)
				sm.Uptime()
			}
		}()
	}
	wg.Wait()
	if sm.Current() != StateReady {
		t.Errorf("state %s", sm.Current())
	}
}

func TestStateMachine_IllegalTransitionPanic(t *testing.T) {
	defer func() {
		if r := recover(); r == nil {
			t.Error("expected panic")
		}
	}()
	NewStateMachine(nil).MustTransition(StateReady)
}

func TestTokenTracker_FloatEdgeCases(t *testing.T) {
	tt := NewTokenTracker(ModelInfo{ID: "e", Cost: ModelCost{Input: math.MaxFloat64 / 1e6}})
	tt.RecordUsage(1, 0)
	if tt.TotalCost() == 0 || math.IsInf(tt.TotalCost(), 0) {
		t.Errorf("unexpected cost %v", tt.TotalCost())
	}
}

func TestTokenTracker_ConcurrentUpdates(t *testing.T) {
	tt := NewTokenTracker(ModelInfo{ID: "c", Cost: ModelCost{Input: 1, Output: 3}})
	var wg sync.WaitGroup
	n := 1000
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			tt.RecordUsage(1000, 500)
			tt.IncrementTurn()
			tt.IncrementToolCall()
			tt.IncrementFSOp()
		}()
	}
	wg.Wait()
	u := tt.Snapshot()
	if u.InputTokens != int64(n)*1000 {
		t.Errorf("input %d", u.InputTokens)
	}
	if u.OutputTokens != int64(n)*500 {
		t.Errorf("output %d", u.OutputTokens)
	}
	if u.TurnCount != int64(n) {
		t.Errorf("turns %d", u.TurnCount)
	}
}

func TestTokenTracker_NegativeInput(t *testing.T) {
	tt := NewTokenTracker(ModelInfo{ID: "n", Cost: ModelCost{Input: 1, Output: 1}})
	tt.RecordUsage(-100, 50)
	u := tt.Snapshot()
	if u.InputTokens != 0 || u.OutputTokens != 50 {
		t.Errorf("got %d/%d", u.InputTokens, u.OutputTokens)
	}
}

func TestTokenTracker_ZeroCostModel(t *testing.T) {
	tt := NewTokenTracker(ModelInfo{ID: "z"})
	tt.RecordUsage(1_000_000, 500_000)
	if tt.TotalCost() != 0 {
		t.Errorf("cost %f", tt.TotalCost())
	}
}

func TestTokenTracker_SummaryFormat(t *testing.T) {
	tt := NewTokenTracker(ModelInfo{ID: "m", Cost: ModelCost{Input: 1, Output: 3}})
	tt.RecordUsage(1000, 500)
	tt.IncrementTurn()
	tt.IncrementToolCall()
	s := tt.Summary()
	if !strings.Contains(s, "Tokens:") || !strings.Contains(s, "Cost:") {
		t.Errorf("bad summary: %s", s)
	}
}

func TestRPCError_Format(t *testing.T) {
	err := &RPCError{Command: "gs", Message: "not found"}
	s := err.Error()
	if !strings.Contains(s, "gs") || !strings.Contains(s, "not found") {
		t.Errorf("bad: %s", s)
	}
}

func TestFrameParsing_Raw(t *testing.T) {
	for _, c := range []string{
		`{"type":"ready"}`,
		`{"type":"response","id":"r1","command":"gs","success":true,"data":{}}`,
		`{"type":"agent_start"}`,
		`{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"Hello"}}`,
		`{"type":"extension_ui_request","id":"u1","method":"confirm"}`,
	} {
		var f RpcFrame
		if err := json.Unmarshal([]byte(c), &f); err != nil {
			t.Errorf("parse fail: %s: %v", c, err)
		}
	}
}

func TestRPCHostToolRequest_Parse(t *testing.T) {
	raw := `{"type":"host_tool_call","id":"ht1","toolCallId":"tc1","toolName":"cs","arguments":{"q":"test"}}`
	var req RpcHostToolRequest
	if err := json.Unmarshal([]byte(raw), &req); err != nil {
		t.Fatal(err)
	}
	if req.ToolName != "cs" {
		t.Errorf("got %s", req.ToolName)
	}
}

func TestAgent_DoubleStart(t *testing.T) {
	a := NewAgent("ds", DefaultConfig())
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if err := a.Start(ctx); err == nil {
		if err := a.Start(ctx); err == nil {
			t.Error("expected error on double start")
		}
	}
}

func TestAgent_PromptBeforeStart(t *testing.T) {
	a := NewAgent("ep", DefaultConfig())
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if err := a.Prompt(ctx, "hi"); err == nil {
		t.Error("expected error")
	}
}

func TestAgent_AbortBeforeStart(t *testing.T) {
	a := NewAgent("ea", DefaultConfig())
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if err := a.Abort(ctx); err == nil {
		t.Error("expected error")
	}
}

func TestAgent_ConcurrentStateAccess(t *testing.T) {
	a := NewAgent("csa", DefaultConfig())
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 50; j++ {
				a.State()
				a.TokenUsage()
				a.Uptime()
			}
		}()
	}
	wg.Wait()
}

func TestGenerateReport_WithMetrics(t *testing.T) {
	a := NewAgent("rpt", DefaultConfig())
	a.Metrics().Emit(Metric{Type: MetricLLM, InputTokens: 500})
	a.Metrics().Emit(Metric{Type: MetricToolCall, ToolName: "read"})
	a.Metrics().Emit(Metric{Type: MetricFileSystem, FSPath: "/tmp/t", FSOperation: "read"})
	r := a.GenerateReport()
	if len(r.Metrics) != 3 || r.State != StateCreated {
		t.Errorf("got %d metrics, state %s", len(r.Metrics), r.State)
	}
}

func TestBridgeLogEntry_AllFields(t *testing.T) {
	e := BridgeLogEntry{Timestamp: time.Now(), Direction: "w->s", QuestionID: "q42", Question: "Q?", Answer: "42", Duration: "5s"}
	b, _ := json.Marshal(e)
	var e2 BridgeLogEntry
	json.Unmarshal(b, &e2)
	if e2.QuestionID != "q42" {
		t.Errorf("got %s", e2.QuestionID)
	}
}

func TestNewConsultSupervisorTool_JSON(t *testing.T) {
	d := NewConsultSupervisorTool()
	b, _ := json.Marshal(d)
	var d2 HostToolDefinition
	json.Unmarshal(b, &d2)
	if d2.Name != "consult_supervisor" {
		t.Errorf("got %s", d2.Name)
	}
}

func TestHostToolManager_RegisterDuplicate(t *testing.T) {
	tm := NewHostToolManager(NewAgent("dup", DefaultConfig()))
	h := func(_ context.Context, _ json.RawMessage) (interface{}, error) { return "ok", nil }
	if err := tm.RegisterTool(HostToolDefinition{Name: "dup"}, h); err != nil {
		t.Fatal(err)
	}
	if err := tm.RegisterTool(HostToolDefinition{Name: "dup"}, h); err != nil {
		t.Fatal(err)
	}
	if n := len(tm.ListTools()); n != 1 {
		t.Errorf("got %d", n)
	}
}

func TestLoadConfig_NotExist(t *testing.T) {
	cm, err := LoadConfig("/tmp/does_not_exist_xyz.json")
	if err != nil {
		t.Fatal(err)
	}
	if cm.Config().OMPPath != "omp" {
		t.Error("expected default")
	}
}

func TestLoadConfig_InvalidJSON(t *testing.T) {
	p := filepath.Join(t.TempDir(), "bad.json")
	os.WriteFile(p, []byte("{bad}"), 0644)
	if _, err := LoadConfig(p); err == nil {
		t.Error("expected error")
	}
}

func TestConfigManager_ValidateDefaults(t *testing.T) {
	cm := NewConfigManager(AgentConfig{})
	cm.Validate()
	c := cm.Config()
	if c.Model != "openrouter/deepseek/deepseek-v4-flash" {
		t.Errorf("model %s", c.Model)
	}
	if c.ThinkingLevel == "" {
		t.Error("thinking empty")
	}
	if c.MaxRunTime == 0 {
		t.Error("runtime zero")
	}
}

func TestConfigManager_SaveWithoutPath(t *testing.T) {
	if err := NewConfigManager(DefaultConfig()).Save(); err == nil {
		t.Error("expected error")
	}
}

func TestFileCredentialProvider_Comments(t *testing.T) {
	p := filepath.Join(t.TempDir(), "creds")
	os.WriteFile(p, []byte("# c\nopenrouter=sk-real-key\n"), 0644)
	fp, err := NewFileCredentialProvider(p)
	if err != nil {
		t.Fatal(err)
	}
	k, ok := fp.GetApiKey("openrouter")
	if !ok || k != "sk-real-key" {
		t.Errorf("got %s/%v", k, ok)
	}
}

// ──────────────────────────────────────────────
//  Integration
// ──────────────────────────────────────────────

func TestIntegration_RPCGetStateConcurrent(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	c, err := NewRPCClient(ctx, "conc_state", omp)
	if err != nil { t.Fatalf("spawn: %v", err) }
	defer c.Close()
	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(j int) {
			defer wg.Done()
			s, err := c.GetState(ctx)
			if err != nil && ctx.Err() == nil {
				t.Errorf("g%d: %v", j, err)
			}
			if s != nil {
				if m, ok := s["model"].(map[string]interface{}); ok {
					if id, _ := m["id"].(string); id == "" {
						t.Errorf("g%d: empty model", j)
					}
				}
			}
		}(i)
	}
	wg.Wait()
}

func TestIntegration_RPCRapidCommands(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	c, err := NewRPCClient(ctx, "rapid", omp)
	if err != nil { t.Fatalf("spawn: %v", err) }
	defer c.Close()
	var wg sync.WaitGroup
	for j := 0; j < 10; j++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for _, cmd := range []string{"get_state", "abort", "get_state"} {
				c.Send(ctx, RpcCommand{Type: cmd})
			}
		}()
	}
	wg.Wait()
}

func TestIntegration_SPAWNAndGetModelInfo(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	c, err := NewRPCClient(ctx, "model_info", omp)
	if err != nil { t.Fatalf("spawn: %v", err) }
	defer c.Close()
	s, err := c.GetState(ctx)
	if err != nil { t.Fatalf("gs: %v", err) }
	m, ok := s["model"].(map[string]interface{})
	if !ok { t.Fatal("model missing") }
	if id, _ := m["id"].(string); id == "" {
		t.Error("model.id empty")
	} else {
		t.Logf("Model: %s", id)
	}
}

func TestIntegration_AgentStartStopConcurrent(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	var agents []*Agent
	for i := 0; i < 3; i++ {
		cfg := DefaultConfig()
		cfg.InMemory = true
		cfg.OMPPath = omp
		a := NewAgent(fmt.Sprintf("c_%d", i), cfg)
		agents = append(agents, a)
	}
	var wg sync.WaitGroup
	for _, a := range agents {
		wg.Add(1)
		go func(ag *Agent) {
			defer wg.Done()
			if err := ag.Start(ctx); err != nil {
				t.Errorf("start %s: %v", ag.ID, err)
				return
			}
			if ag.State() != StateReady {
				t.Errorf("%s state %s", ag.ID, ag.State())
			}
		}(a)
	}
	wg.Wait()
	for _, a := range agents {
		if s, _ := a.GetState(ctx); s != nil {
			t.Logf("%s ok", a.ID)
		}
		a.Shutdown(ctx)
	}
}

func TestIntegration_RPCReconnect(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx1, cancel1 := context.WithTimeout(context.Background(), 10*time.Second)
	c1, err := NewRPCClient(ctx1, "r1", omp)
	if err != nil { t.Fatalf("first: %v", err) }
	if _, err := c1.GetState(ctx1); err != nil { t.Errorf("first gs: %v", err) }
	c1.Close()
	cancel1()
	ctx2, cancel2 := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel2()
	c2, err := NewRPCClient(ctx2, "r2", omp)
	if err != nil { t.Fatalf("second: %v", err) }
	defer c2.Close()
	if _, err := c2.GetState(ctx2); err != nil {
		t.Errorf("second gs: %v", err)
	}
}

func TestIntegration_AbortDuringStream(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	c, err := NewRPCClient(ctx, "abort", omp)
	if err != nil { t.Fatalf("spawn: %v", err) }
	defer c.Close()
	c.Prompt(ctx, "Write a detailed analysis of Go's concurrency model...")
	time.Sleep(500 * time.Millisecond)
	ac, acancel := context.WithTimeout(ctx, 5*time.Second)
	defer acancel()
	if _, err := c.Abort(ac); err != nil {
		t.Logf("Abort: %v (expected)", err)
	} else {
		t.Log("Abort succeeded")
	}
}

func TestLLMIntegration_FullPromptWithEventCapture(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	c, err := NewRPCClient(ctx, "fp", omp)
	if err != nil { t.Fatalf("spawn: %v", err) }
	defer c.Close()

	recCh := c.Subscribe()
	waitCh := c.Subscribe()
	var recs []string
	var mu sync.Mutex
	go func() {
		for f := range recCh {
			mu.Lock()
			recs = append(recs, f.Type)
			mu.Unlock()
		}
	}()

	r, err := c.Prompt(ctx, "Reply with exactly one word: DONE")
	if err != nil { t.Fatalf("prompt: %v", err) }
	if r.Success == nil || !*r.Success { t.Fatalf("failed: %s", r.Error) }

	to := time.After(60 * time.Second)
	hasEnd := false
	for {
		select {
		case f, ok := <-waitCh:
			if !ok { goto fpDone }
			if f.Type == "agent_end" { hasEnd = true; goto fpDone }
		case <-to: goto fpDone
		case <-ctx.Done(): goto fpDone
		}
	}
fpDone:
	time.Sleep(500 * time.Millisecond)

	mu.Lock()
	counts := map[string]int{}
	for _, t := range recs { counts[t]++ }
	mu.Unlock()

	for _, e := range []string{"agent_start", "agent_end", "message_start", "message_end"} {
		if counts[e] == 0 { t.Errorf("missing: %s", e) }
	}
	t.Logf("Events: %d, types=%v, end=%v", len(recs), counts, hasEnd)
}

func TestLLMIntegration_StreamMetricsBusIntegration(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	c, err := NewRPCClient(ctx, "mb", omp)
	if err != nil { t.Fatalf("spawn: %v", err) }
	defer c.Close()

	cfg := DefaultConfig()
	cfg.InMemory = true
	cfg.OMPPath = omp
	a := NewAgent("mbt", cfg)

	evCh := c.Subscribe()
	go func() {
		for f := range evCh {
			a.Metrics().Emit(Metric{Type: MetricEvent, Timestamp: time.Now(), EventType: f.Type, AgentID: "mbt"})
		}
	}()

	_, ch, unsub := a.Metrics().SubscribeSSE(100, 5)
	defer unsub()

	r, err := c.Prompt(ctx, "Reply with exactly: OK")
	if err != nil { t.Fatalf("prompt: %v", err) }
	if r.Success == nil || !*r.Success { t.Fatalf("failed: %s", r.Error) }

	to := time.After(60 * time.Second)
	var sseEvs []MetricsEvent
	done := make(chan struct{})
	go func() {
		for ev := range ch { sseEvs = append(sseEvs, ev) }
		close(done)
	}()

	wtCh := c.Subscribe()
	for {
		select {
		case f, ok := <-wtCh:
			if !ok || f.Type == "agent_end" { goto mbDone }
		case <-to: goto mbDone
		}
	}
mbDone:
	time.Sleep(500 * time.Millisecond)
	unsub()
	<-done

	t.Logf("SSE events: %d, total emitted: %d", len(sseEvs), a.Metrics().TotalEmitted())
	if len(sseEvs) == 0 {
		t.Error("no SSE events")
	}
}