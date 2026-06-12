package agent
import (
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"
)

func TestStateMachine_ValidTransitions(t *testing.T) {
	tests := []struct{ from, to AgentState; ok bool }{
		{StateCreated, StateInitializing, true},
		{StateCreated, StateReady, false},
		{StateInitializing, StateReady, true},
		{StateInitializing, StateFailed, true},
		{StateReady, StateRunning, true},
		{StateReady, StateFailed, true},
		{StateReady, StateCancelled, true},
		{StateRunning, StatePaused, true},
		{StateRunning, StateCompleted, true},
		{StateRunning, StateFailed, true},
		{StateRunning, StateCancelled, true},
		{StateRunning, StateReady, false},
		{StatePaused, StateRunning, true},
		{StatePaused, StateCancelled, true},
		{StateCompleted, StateRunning, false},
		{StateFailed, StateReady, false},
		{StateCancelled, StateRunning, false},
	}
	for _, tt := range tests {
		sm := NewStateMachine(nil)
		switch tt.from {
		case StateCreated:
		case StateInitializing:
			sm.MustTransition(StateInitializing)
		case StateReady:
			sm.MustTransition(StateInitializing)
			sm.MustTransition(StateReady)
		case StateRunning:
			sm.MustTransition(StateInitializing)
			sm.MustTransition(StateReady)
			sm.MustTransition(StateRunning)
		case StatePaused:
			sm.MustTransition(StateInitializing)
			sm.MustTransition(StateReady)
			sm.MustTransition(StateRunning)
			sm.MustTransition(StatePaused)
		case StateCompleted:
			sm.MustTransition(StateInitializing)
			sm.MustTransition(StateReady)
			sm.MustTransition(StateRunning)
			sm.MustTransition(StateCompleted)
		case StateFailed:
			sm.MustTransition(StateInitializing)
			sm.MustTransition(StateFailed)
		case StateCancelled:
			sm.MustTransition(StateInitializing)
			sm.MustTransition(StateReady)
			sm.MustTransition(StateCancelled)
		}
		err := sm.Transition(tt.to)
		if (err == nil) != tt.ok {
			t.Errorf("%s -> %s: ok=%v, err=%v", tt.from, tt.to, tt.ok, err)
		}
	}
}

func TestStateMachine_Callback(t *testing.T) {
	var from, to AgentState
	sm := NewStateMachine(func(f, t AgentState) { from, to = f, t })
	sm.MustTransition(StateInitializing)
	if from != StateCreated || to != StateInitializing {
		t.Errorf("got (%s, %s)", from, to)
	}
}

func TestStateMachine_Terminal(t *testing.T) {
	for _, s := range []AgentState{StateCompleted, StateFailed, StateCancelled} {
		sm := NewStateMachine(nil)
		sm.MustTransition(StateInitializing)
		switch s {
		case StateFailed:
			sm.MustTransition(StateFailed)
		case StateCancelled:
			sm.MustTransition(StateReady)
			sm.MustTransition(StateCancelled)
		default:
			sm.MustTransition(StateReady)
			sm.MustTransition(StateRunning)
			sm.MustTransition(s)
		}
		if !sm.IsTerminal() {
			t.Errorf("%s should be terminal", s)
		}
	}
	// Non-terminal states
	sm := NewStateMachine(nil)
	if sm.IsTerminal() {
		t.Error("created should not be terminal")
	}
	sm.MustTransition(StateInitializing)
	if sm.IsTerminal() {
		t.Error("initializing should not be terminal")
	}
}

func TestStateMachine_CanTransition(t *testing.T) {
	sm := NewStateMachine(nil)
	if !sm.CanTransition(StateInitializing) {
		t.Error("should allow -> initializing")
	}
	if sm.CanTransition(StateReady) {
		t.Error("should NOT allow -> ready")
	}
}

func TestStateMachine_Uptime(t *testing.T) {
	if NewStateMachine(nil).Uptime() < 0 {
		t.Error("uptime should be positive")
	}
}

func TestTokenTracker_Basic(t *testing.T) {
	tt := NewTokenTracker(ModelInfo{ID: "m", Cost: ModelCost{Input: 3, Output: 15}})
	tt.RecordUsage(1000, 500)
	u := tt.Snapshot()
	if u.InputTokens != 1000 || u.OutputTokens != 500 {
		t.Errorf("got %d/%d", u.InputTokens, u.OutputTokens)
	}
	want := 1000.0/1_000_000*3 + 500.0/1_000_000*15
	if u.CostUSD != want {
		t.Errorf("cost %.6f", u.CostUSD)
	}
	tt.RecordUsage(2000, 1000)
	if u := tt.Snapshot(); u.InputTokens != 3000 {
		t.Errorf("got %d", u.InputTokens)
	}
}

func TestTokenTracker_Cache(t *testing.T) {
	tt := NewTokenTracker(ModelInfo{ID: "c", Cost: ModelCost{CacheRead: 0.3}})
	tt.RecordCacheUsage(5000, 0)
	if tt.TotalCost() != 5000.0/1_000_000*0.3 {
		t.Error("cache cost mismatch")
	}
}

func TestTokenTracker_Empty(t *testing.T) {
	u := NewTokenTracker(ModelInfo{ID: "e"}).Snapshot()
	if u.InputTokens != 0 || u.OutputTokens != 0 {
		t.Error("expected zero")
	}
}

func TestEstimateCostForTokens_Zero(t *testing.T) {
	if c := EstimateCostForTokens(ModelInfo{ID: "z"}, 0, 0); c != 0 {
		t.Errorf("want 0, got %f", c)
	}
}

func TestEstimateCostForTokens_Large(t *testing.T) {
	model := ModelInfo{ID: "l", Cost: ModelCost{Input: 0.15, Output: 0.60}}
	c := EstimateCostForTokens(model, 10_000_000, 5_000_000)
	if want := 10.0*0.15 + 5.0*0.60; c != want {
		t.Errorf("got %.2f, want %.2f", c, want)
	}
}

func TestMetricsBus_EmitAndSubscribe(t *testing.T) {
	mb := NewMetricsBus("a", 100)
	ch, unsub := mb.Subscribe(10)
	defer unsub()
	mb.Emit(Metric{Type: MetricLLM, ToolName: "x"})
	select {
	case m := <-ch:
		if m.Type != MetricLLM || m.ToolName != "x" {
			t.Errorf("got %s/%s", m.Type, m.ToolName)
		}
	case <-time.After(time.Second):
		t.Fatal("timeout")
	}
}

func TestMetricsBus_ExportJSON(t *testing.T) {
	mb := NewMetricsBus("j", 100)
	mb.Emit(Metric{Type: MetricLLM, ModelID: "m"})
	mb.Emit(Metric{Type: MetricToolCall, ToolName: "r"})
	b, _ := mb.ExportJSON()
	var m []Metric
	if err := json.Unmarshal(b, &m); err != nil {
		t.Fatal(err)
	}
	if len(m) != 2 {
		t.Errorf("got %d, want 2", len(m))
	}
}

func TestMetricsBus_MultipleSubscribers(t *testing.T) {
	mb := NewMetricsBus("m", 100)
	c1, u1 := mb.Subscribe(10); defer u1()
	c2, u2 := mb.Subscribe(10); defer u2()
	mb.Emit(Metric{Type: MetricEvent, EventType: "t"})
	for i, c := range []<-chan Metric{c1, c2} {
		select {
		case <-c:
		case <-time.After(time.Second):
			t.Errorf("sub %d missed", i)
		}
	}
}

func TestMetricsBus_Clear(t *testing.T) {
	mb := NewMetricsBus("c", 100)
	mb.Emit(Metric{Type: MetricLLM})
	mb.Emit(Metric{Type: MetricToolCall})
	if mb.Len() != 2 {
		t.Fatalf("got %d, want 2", mb.Len())
	}
	mb.Clear()
	if mb.Len() != 0 {
		t.Errorf("got %d, want 0", mb.Len())
	}
}

func TestConfigManager_Defaults(t *testing.T) {
	if NewConfigManager(AgentConfig{}).Config().OMPPath != "" {
		t.Error("expected empty OMPPath")
	}
}

func TestConfigManager_WithMethods(t *testing.T) {
	cm := NewConfigManager(DefaultConfig()).WithModel("m").WithThinkingLevel("low").WithInMemory()
	c := cm.Config()
	if c.Model != "m" || !c.InMemory || c.ThinkingLevel != "low" {
		t.Error("With methods not applied")
	}
}

func TestConfigManager_Validate(t *testing.T) {
	cm := NewConfigManager(AgentConfig{Model: "m"})
	if err := cm.Validate(); err != nil {
		t.Fatal(err)
	}
	c := cm.Config()
	if c.ThinkingLevel == "" || c.MaxRunTime == 0 {
		t.Error("defaults missing after validate")
	}
}

func TestConfig_SaveAndLoad(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "c.json")
	cm := NewConfigManager(AgentConfig{
		OMPPath: "/bin/omp", Model: "openrouter/deepseek/deepseek-v4-flash",
		ThinkingLevel: "high", InMemory: true,
	})
	cm.path = p
	if err := cm.Save(); err != nil {
		t.Fatal(err)
	}
	loaded, err := LoadConfig(p)
	if err != nil {
		t.Fatal(err)
	}
	if loaded.Config().Model != "openrouter/deepseek/deepseek-v4-flash" {
		t.Error("load mismatch")
	}
}

func TestConfigTemplate_ValidJSON(t *testing.T) {
	if err := json.Unmarshal([]byte(GenerateConfigTemplate()), &json.RawMessage{}); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
}

func TestAgent_Create(t *testing.T) {
	a := NewAgent("test", DefaultConfig())
	if a.State() != StateCreated || a.ID != "test" {
		t.Errorf("got %s/%s", a.State(), a.ID)
	}
}

func TestAgent_EmptyTokenUsage(t *testing.T) {
	if u := NewAgent("t", DefaultConfig()).TokenUsage(); u.InputTokens != 0 {
		t.Error("expected zero")
	}
}

func TestAgent_Report(t *testing.T) {
	a := NewAgent("r", DefaultConfig())
	a.Metrics().Emit(Metric{Type: MetricLLM, ModelID: "m", InputTokens: 100})
	r := a.GenerateReport()
	if r.AgentID != "r" || len(r.Metrics) != 1 {
		t.Errorf("got %s, %d metrics", r.AgentID, len(r.Metrics))
	}
}

func TestReport_JSONRoundtrip(t *testing.T) {
	a := NewAgent("rt", DefaultConfig())
	a.Metrics().Emit(Metric{Type: MetricLLM})
	a.Metrics().Emit(Metric{Type: MetricToolCall, ToolName: "x"})
	r := a.GenerateReport()
	b, _ := json.MarshalIndent(r, "", "  ")
	os.WriteFile(filepath.Join(t.TempDir(), "report.json"), b, 0644)
	var r2 AgentRunReport
	json.Unmarshal(b, &r2)
	if r2.AgentID != "rt" || len(r2.Metrics) != 2 {
		t.Error("roundtrip mismatch")
	}
}

type mockKeyProvider struct{ keys map[string]string }

func (m *mockKeyProvider) GetApiKey(p string) (string, bool) {
	k, ok := m.keys[p]; return k, ok
}
func (m *mockKeyProvider) ListProviders() []string {
	var pp []string
	for k := range m.keys { pp = append(pp, k) }
	return pp
}

func TestEnvCredentialProvider(t *testing.T) {
	os.Setenv("TESTPROV_API_KEY", "k123")
	defer os.Unsetenv("TESTPROV_API_KEY")
	ep := &EnvCredentialProvider{}
	k, ok := ep.GetApiKey("testprov")
	if !ok || k != "k123" {
		t.Errorf("got %s/%v", k, ok)
	}
	if _, ok := ep.GetApiKey("missing"); ok {
		t.Error("should be missing")
	}
}

func TestFileCredentialProvider(t *testing.T) {
	dir := t.TempDir()
	f := filepath.Join(dir, "creds")
	os.WriteFile(f, []byte("openrouter=sk-or-key\n"), 0644)
	fp, err := NewFileCredentialProvider(f)
	if err != nil { t.Fatal(err) }
	k, ok := fp.GetApiKey("openrouter")
	if !ok || k != "sk-or-key" {
		t.Errorf("got %s/%v", k, ok)
	}
}

func TestChainCredentialProvider(t *testing.T) {
	chain := NewChainCredentialProvider(
		&mockKeyProvider{map[string]string{"a": "ka"}},
		&mockKeyProvider{map[string]string{"b": "kb"}},
	)
	k, ok := chain.GetApiKey("a")
	if !ok || k != "ka" { t.Errorf("got %s/%v", k, ok) }
	k, ok = chain.GetApiKey("b")
	if !ok || k != "kb" { t.Errorf("got %s/%v", k, ok) }
}

func TestConsultSupervisorTool(t *testing.T) {
	d := NewConsultSupervisorTool()
	if d.Name != "consult_supervisor" || len(d.Parameters.Required) != 1 || d.Parameters.Required[0] != "question" {
		t.Errorf("bad tool def: %+v", d)
	}
}

func TestHostToolManager_RegisterAndList(t *testing.T) {
	tm := NewHostToolManager(NewAgent("x", DefaultConfig()))
	err := tm.RegisterTool(HostToolDefinition{
		Name: "ping", Description: "ping", Parameters: HostToolParam{Type: "object"},
	}, func(_ context.Context, _ json.RawMessage) (interface{}, error) {
		return map[string]string{"pong": "ok"}, nil
	})
	if err != nil { t.Fatal(err) }
	if _, ok := tm.GetTool("ping"); !ok { t.Error("ping not found") }
	if len(tm.ListTools()) != 1 { t.Error("expected 1 tool") }
}

func TestBridgeLogEntry_JSON(t *testing.T) {
	e := BridgeLogEntry{
		Timestamp: time.Now(), Direction: "w->s",
		QuestionID: "q1", Question: "what?", Answer: "42",
	}
	b, _ := json.Marshal(e)
	var e2 BridgeLogEntry
	json.Unmarshal(b, &e2)
	if e2.Question != "what?" { t.Errorf("got %s", e2.Question) }
}

// ──────────────────────────────────────────────
//  Integration
// ──────────────────────────────────────────────

func skipNoOMP(t *testing.T) string {
	t.Helper()
	p := "omp"
	if v := os.Getenv("OMP_PATH"); v != "" { p = v }
	path, err := exec.LookPath(p)
	if err != nil { t.Skipf("OMP not found: %v", err) }
	return path
}

func TestIntegration_RPCClientSpawn(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	c, err := NewRPCClient(ctx, "i1", omp)
	if err != nil { t.Fatalf("spawn: %v", err) }
	defer c.Close()
	r, err := c.Send(ctx, RpcCommand{Type: "get_state"})
	if err != nil { t.Fatalf("get_state: %v", err) }
	if r.Data == nil { t.Error("data is nil") }
	t.Logf("OMP PID=%d", c.PID())
}

func TestIntegration_SetThinkingLevel(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	c, err := NewRPCClient(ctx, "i2", omp)
	if err != nil { t.Fatalf("spawn: %v", err) }
	defer c.Close()
	r, err := c.SetThinkingLevel(ctx, "low")
	if err != nil { t.Fatalf("set: %v", err) }
	if r.Success == nil || !*r.Success { t.Fatalf("set failed: %s", r.Error) }
}

func TestIntegration_ModelInfo(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	c, err := NewRPCClient(ctx, "i3", omp)
	if err != nil { t.Fatalf("spawn: %v", err) }
	defer c.Close()
	s, err := c.GetState(ctx)
	if err != nil { t.Fatalf("get_state: %v", err) }
	if m, ok := s["model"].(map[string]interface{}); ok {
		if id, _ := m["id"].(string); id != "" { t.Logf("Model: %s", id) }
	}
}

func TestIntegration_MultipleClients(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	c1, err := NewRPCClient(ctx, "i4a", omp)
	if err != nil { t.Fatalf("c1: %v", err) }
	defer c1.Close()
	c2, err := NewRPCClient(ctx, "i4b", omp)
	if err != nil { t.Fatalf("c2: %v", err) }
	defer c2.Close()
	if _, err = c1.GetState(ctx); err != nil { t.Errorf("c1: %v", err) }
	if _, err = c2.GetState(ctx); err != nil { t.Errorf("c2: %v", err) }
}

func TestIntegration_AgentLifecycle(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	cfg := DefaultConfig()
	cfg.InMemory = true
	cfg.OMPPath = omp
	a := NewAgent("lifecycle", cfg)
	if err := a.Start(ctx); err != nil { t.Fatalf("start: %v", err) }
	if a.State() != StateReady { t.Fatalf("state %s", a.State()) }
	if s, _ := a.GetState(ctx); s != nil { t.Logf("ok, model=%v", s["model"]) }
	if err := a.Shutdown(ctx); err != nil { t.Fatalf("shutdown: %v", err) }
}

// ──────────────────────────────────────────────
//  LLM Integration
// ──────────────────────────────────────────────

func TestLLMIntegration_BasicPrompt(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	c, err := NewRPCClient(ctx, "llm1", omp)
	if err != nil { t.Fatalf("spawn: %v", err) }
	defer c.Close()

	recCh := c.Subscribe()
	waitCh := c.Subscribe()
	type eventRec struct{ Type string }
	var recs []eventRec
	go func() {
		for f := range recCh {
			recs = append(recs, eventRec{Type: f.Type})
		}
	}()

	r, err := c.Prompt(ctx, "Reply with exactly one word: HELLO")
	if err != nil { t.Fatalf("prompt: %v", err) }
	if r.Success == nil || !*r.Success { t.Fatalf("prompt failed: %s", r.Error) }

	timeout := time.After(60 * time.Second)
	hasEnd := false
	for {
		select {
		case f, ok := <-waitCh:
			if !ok { goto done }
			if f.Type == "agent_end" { hasEnd = true; goto done }
		case <-timeout: goto done
		}
	}
done:
	time.Sleep(500 * time.Millisecond)

	counts := map[string]int{}
	hasStart := false
	for _, r := range recs {
		counts[r.Type]++
		if r.Type == "agent_start" { hasStart = true }
	}
	t.Logf("Events: %d, start=%v, end=%v", len(recs), hasStart, hasEnd)
	if !hasStart { t.Error("missing agent_start") }
	if !hasEnd { t.Error("missing agent_end") }
}

func TestLLMIntegration_StreamCapture(t *testing.T) {
	if testing.Short() { t.Skip() }
	omp := skipNoOMP(t)
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	c, err := NewRPCClient(ctx, "llm2", omp)
	if err != nil { t.Fatalf("spawn: %v", err) }
	defer c.Close()

	recCh := c.Subscribe()
	waitCh := c.Subscribe()
	type eventRec struct{ Type string }
	var recs []eventRec
	go func() {
		for f := range recCh {
			recs = append(recs, eventRec{Type: f.Type})
		}
	}()

	r, err := c.Prompt(ctx, "Reply with exactly: OK")
	if err != nil { t.Fatalf("prompt: %v", err) }
	if r.Success == nil || !*r.Success { t.Fatalf("prompt failed: %s", r.Error) }

	timeout := time.After(60 * time.Second)
	for {
		select {
		case f, ok := <-waitCh:
			if !ok { goto done2 }
			if f.Type == "agent_end" { goto done2 }
		case <-timeout: goto done2
		}
	}
done2:
	time.Sleep(500 * time.Millisecond)

	counts := map[string]int{}
	for _, r := range recs { counts[r.Type]++ }
	t.Logf("Events: %d, types=%v", len(recs), counts)
	if len(recs) == 0 { t.Error("no events") }
	if counts["message_update"] == 0 { t.Error("no message_update") }
}