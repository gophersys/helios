package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

var globalPort string
var globalHTTP = &http.Client{Timeout: 120 * time.Second, Transport: &http.Transport{MaxIdleConns: 100, MaxConnsPerHost: 100}}

func TestMain(m *testing.M) {
	port := findExisting()
	if port == "" {
		port = startServer()
	}
	globalPort = port
	os.Exit(m.Run())
}

func findExisting() string {
	for _, p := range []string{"18080", "18081"} {
		if r, e := http.Get(fmt.Sprintf("http://127.0.0.1:%s/api/v1/health", p)); e == nil {
			r.Body.Close()
			return p
		}
	}
	return ""
}

func startServer() string {
	bin := "/tmp/agentd"
	if _, e := os.Stat(bin); e != nil {
		tmp := filepath.Join(os.TempDir(), "agentd_e2e")
		if o, e := exec.Command("go", "build", "-o", tmp, "./cmd/agentd/").CombinedOutput(); e != nil {
			fmt.Fprintf(os.Stderr, "build agentd: %v\n%s\n", e, o)
			os.Exit(1)
		}
		bin = tmp
	}
	cmd := exec.Command(bin)
	cmd.Env = append(os.Environ(), "PORT=18080")
	cmd.Stderr = os.Stderr
	cmd.Start()
	for i := 0; i < 30; i++ {
		time.Sleep(300 * time.Millisecond)
		if r, e := http.Get("http://127.0.0.1:18080/api/v1/health"); e == nil {
			r.Body.Close()
			fmt.Fprintf(os.Stderr, "Server PID=%d\n", cmd.Process.Pid)
			return "18080"
		}
	}
	fmt.Fprintf(os.Stderr, "server timeout\n")
	os.Exit(1)
	return ""
}

type client struct{ t *testing.T }

func cl(t *testing.T) *client { return &client{t: t} }
func (c *client) url(p string) string { return fmt.Sprintf("http://127.0.0.1:%s%s", globalPort, p) }

func (c *client) do(m, p string, body interface{}) *http.Response {
	var r io.Reader
	if body != nil {
		switch v := body.(type) {
		case io.Reader:
			r = v
		default:
			b, e := json.Marshal(body)
			if e != nil { c.t.Fatal(e) }
			r = bytes.NewReader(b)
		}
	}
	req, e := http.NewRequest(m, c.url(p), r)
	if e != nil { c.t.Fatal(e) }
	req.Header.Set("Content-Type", "application/json")
	resp, e := globalHTTP.Do(req)
	if e != nil { c.t.Fatalf("%s %s: %v", m, p, e) }
	return resp
}

func (c *client) json(m, p string, body, into interface{}) {
	c.t.Helper()
	resp := c.do(m, p, body)
	defer resp.Body.Close()
	data, e := io.ReadAll(resp.Body)
	if e != nil { c.t.Fatal(e) }
	if resp.StatusCode >= 400 { c.t.Fatalf("%s %s: HTTP %d: %s", m, p, resp.StatusCode, string(data)) }
	if into != nil {
		if e := json.Unmarshal(data, into); e != nil { c.t.Fatalf("JSON: %v\n%s", e, string(data)) }
	}
}

func (c *client) create(id *string) {
	var r struct{ ID string }
	c.json("POST", "/api/v1/agents", map[string]interface{}{"model": "openrouter/deepseek/deepseek-v4-flash", "in_memory": true}, &r)
	*id = r.ID
}

func (c *client) start(id string)   { c.json("POST", "/api/v1/agents/"+id+"/start", nil, nil) }
func (c *client) prompt(id, msg string) { c.json("POST", "/api/v1/agents/"+id+"/prompt", map[string]string{"message": msg}, nil) }
func (c *client) shutdown(id string)  { c.json("POST", "/api/v1/agents/"+id+"/shutdown", nil, nil) }

// ── Test: Full lifecycle ─────────────────────

func TestE2E_FullLifecycle(t *testing.T) {
	c := cl(t)
	var id string
	c.create(&id)

	var cr struct{ State string }
	c.json("GET", "/api/v1/agents/"+id, nil, &cr)
	if cr.State != "created" { t.Errorf("state=%s", cr.State) }

	c.start(id)
	c.json("GET", "/api/v1/agents/"+id, nil, &cr)
	if cr.State != "ready" { t.Errorf("state=%s", cr.State) }

	c.prompt(id, "Reply exactly: HELLO_WORLD")

	var tu struct{ InputTokens, OutputTokens int64; CostUSD float64 }
	c.json("GET", "/api/v1/agents/"+id+"/token-usage", nil, &tu)
	t.Logf("Tokens: in=%d out=%d cost=$%.6f", tu.InputTokens, tu.OutputTokens, tu.CostUSD)

	var rp struct{ State string `json:"final_state"` }
	c.json("GET", "/api/v1/agents/"+id+"/report", nil, &rp)
	t.Logf("Report state: %s", rp.State)

	c.shutdown(id)
}

// ── Test: Error paths ────────────────────────

func TestE2E_Errors(t *testing.T) {
	c := cl(t)
	check := func(m, p string, body interface{}, w int) {
		t.Helper()
		resp := c.do(m, p, body)
		resp.Body.Close()
		if resp.StatusCode != w { t.Errorf("%s %s: got %d", m, p, resp.StatusCode) }
	}
	check("GET", "/api/v1/agents/nope", nil, 404)
	check("POST", "/api/v1/agents/nope/shutdown", nil, 404)
	check("POST", "/api/v1/bridge", map[string]string{"supervisor_id": "x", "worker_id": "y"}, 404)
	check("POST", "/api/v1/agents", bytes.NewReader([]byte("not json")), 400)

	var id string
	c.create(&id)
	resp := c.do("POST", "/api/v1/agents/"+id+"/prompt", map[string]string{"message": "hi"})
	resp.Body.Close()
	if resp.StatusCode != 409 { t.Errorf("prompt before start: %d", resp.StatusCode) }
	c.shutdown(id)
}

// ── Test: SSE protocol contract + event completeness ──

func TestE2E_SSE(t *testing.T) {
	c := cl(t)
	var id string
	c.create(&id)
	c.start(id)

	// Helper: connect SSE, parse events into (event, data) pairs
	connectSSE := func(path string) (*http.Response, context.CancelFunc, <-chan struct{ event, data string }) {
		u := c.url(path)
		req, _ := http.NewRequest("GET", u, nil)
		req.Header.Set("Accept", "text/event-stream")
		ctx, ca := context.WithCancel(context.Background())
		req = req.WithContext(ctx)
		resp, e := globalHTTP.Do(req)
		if e != nil { t.Fatalf("connect %s: %v", path, e) }
		ch := make(chan struct{ event, data string }, 500)
		go func() {
			sc := NewScanner(resp.Body)
			var cur struct{ event, data string }
			for sc.Scan() {
				l := sc.Text()
				if strings.HasPrefix(l, "event: ") {
					cur.event = strings.TrimPrefix(l, "event: ")
				} else if strings.HasPrefix(l, "data: ") {
					cur.data = strings.TrimPrefix(l, "data: ")
				} else if l == "" && cur.event != "" {
					ch <- cur
					cur = struct{ event, data string }{}
				}
			}
			close(ch)
		}()
		return resp, ca, ch
	}

	t.Run("events_protocol", func(t *testing.T) {
		resp, ca, ch := connectSSE("/api/v1/agents/" + id + "/events/stream")
		defer ca()
		defer resp.Body.Close()

		// Verify SSE headers
		if resp.StatusCode != 200 { t.Fatalf("status %d", resp.StatusCode) }
		if ct := resp.Header.Get("Content-Type"); !strings.Contains(ct, "event-stream") {
			t.Errorf("Content-Type: %s", ct)
		}
		if cc := resp.Header.Get("Cache-Control"); !strings.Contains(cc, "no-cache") {
			t.Errorf("Cache-Control: %s", cc)
		}
		if cn := resp.Header.Get("Connection"); !strings.Contains(cn, "keep-alive") {
			t.Errorf("Connection: %s", cn)
		}

		go c.prompt(id, "Reply exactly: SSE_PROTOCOL_TEST")

		var events []struct{ event, data string }
		seq := []string{"agent_start", "turn_start", "message_start", "message_update", "message_end", "turn_end", "agent_end"}
		seqIdx := 0
		to := time.After(30 * time.Second)
		agentEnd := false

	collect:
		for {
			select {
			case e, ok := <-ch:
				if !ok { break collect }
				events = append(events, e)

				// 1. Every event must use "message" event type (not named)
				if e.event != "message" && e.event != "keepalive" {
					t.Errorf("expected event type 'message', got %q (data: %s)", e.event, e.data)
				}

				// 2. Parse data JSON and verify "type" field
				if e.event == "message" && e.data != "" {
					var p struct {
						Type   string `json:"type"`
						ToolName string `json:"toolName,omitempty"`
						Msg     json.RawMessage `json:"assistantMessageEvent,omitempty"`
					}
					if err := jsonParse(e.data, &p); err != nil {
						t.Errorf("invalid event JSON: %v — data: %s", err, e.data)
						continue
					}
					if p.Type == "" {
						t.Errorf("event data missing 'type' field: %s", e.data)
						continue
					}

					// 3. Check sequence order for core lifecycle events
					for seqIdx < len(seq) && p.Type == seq[seqIdx] {
						t.Logf("  ✓ %s", seq[seqIdx])
						seqIdx++
					}

					// 4. Verify message_update has assistantMessageEvent
					if p.Type == "message_update" && p.Msg == nil {
						t.Errorf("message_update missing assistantMessageEvent: %s", e.data)
					}

					// 5. Stop when we reach agent_end
					if p.Type == "agent_end" {
						agentEnd = true
						time.Sleep(1 * time.Second)
						break collect
					}
				}
			case <-to:
				break collect
			}
		}
		ca()

		// 6. Verify all core lifecycle events were seen
		seen := map[string]int{}
		for _, e := range events {
			if e.event == "message" {
				var p struct{ Type string `json:"type"` }
				jsonParse(e.data, &p)
				seen[p.Type]++
			}
		}
		t.Logf("Events captured: %d, types: %v", len(events), seen)

		required := []string{"agent_start", "turn_start", "message_start", "message_update", "message_end", "turn_end", "agent_end"}
		for _, r := range required {
			if seen[r] == 0 {
				t.Errorf("missing required event: %s", r)
			}
		}
		if !agentEnd {
			t.Error("agent did not reach agent_end")
		}
		if seqIdx < len(seq) {
			t.Errorf("event sequence incomplete: got %d/%d (next expected: %s)", seqIdx, len(seq), seq[seqIdx])
		}
	})

	t.Run("metrics_cost_emission", func(t *testing.T) {
		resp, ca, ch := connectSSE("/api/v1/agents/" + id + "/metrics/stream?replay=5")
		defer ca()
		defer resp.Body.Close()
		if resp.StatusCode != 200 { t.Fatalf("status %d", resp.StatusCode) }

		go c.prompt(id, "Reply exactly: METRICS_COST_TEST")

		var events []struct{ event, data string }
		to := time.After(30 * time.Second)
		gotCost := false

	findCost:
		for {
			select {
			case e, ok := <-ch:
				if !ok { break findCost }
				events = append(events, e)
				if e.event == "metrics" && e.data != "" {
					var p struct {
						Type        string  `json:"type"`
						InputTokens int64   `json:"input_tokens"`
						OutputTokens int64  `json:"output_tokens"`
						CostUSD     float64 `json:"cost_usd"`
					}
					if err := jsonParse(e.data, &p); err == nil && p.Type == "cost" {
						gotCost = true
						t.Logf("Cost event: type=%s input=%d output=%d cost=$%.6f", p.Type, p.InputTokens, p.OutputTokens, p.CostUSD)
						break findCost
					}
				}
			case <-to:
				break findCost
			}
		}
		ca()
		t.Logf("Metrics events: %d, got_cost=%v", len(events), gotCost)
		if !gotCost {
			t.Error("no MetricCost event received after prompt")
		}
	})

	t.Run("message_update_delta_format", func(t *testing.T) {
		resp, ca, ch := connectSSE("/api/v1/agents/" + id + "/events/stream")
		defer ca()
		defer resp.Body.Close()

		go c.prompt(id, "Reply with exactly: DELTA_CHECK")

		to := time.After(30 * time.Second)
		var textDeltas int

	collectDeltas:
		for {
			select {
			case e, ok := <-ch:
				if !ok { break collectDeltas }
				if e.event == "message" && e.data != "" {
					var p struct {
						Type     string `json:"type"`
						MsgEvent struct {
							Type     string          `json:"type"`
							DeltaRaw json.RawMessage `json:"delta,omitempty"`
							Text     string          `json:"text,omitempty"`
						} `json:"assistantMessageEvent"`
					}
					if err := jsonParse(e.data, &p); err != nil {
						continue
					}
					if p.Type == "message_update" && p.MsgEvent.Type != "" {
						deltaStr := string(p.MsgEvent.DeltaRaw)
						hasContent := p.MsgEvent.Text != "" || strings.Contains(deltaStr, `"text":`) || (len(deltaStr) > 2 && deltaStr[0] != '{' && deltaStr[1] != '"')
						t.Logf("  msg_update type=%s delta=%s text=%q", p.MsgEvent.Type, deltaStr, p.MsgEvent.Text)
						if hasContent {
							textDeltas++
						}
					}
				}
				if strings.Contains(e.data, `"agent_end"`) {
					time.Sleep(500 * time.Millisecond)
					break collectDeltas
				}
			case <-to:
				break collectDeltas
			}
		}
		ca()
		t.Logf("Text deltas captured: %d", textDeltas)
		if textDeltas == 0 {
			t.Error("no text delta content in message_update events")
		}
	})

	t.Run("multi_turn_events", func(t *testing.T) {
		resp, ca, ch := connectSSE("/api/v1/agents/" + id + "/events/stream")
		defer ca()
		defer resp.Body.Close()
		// Send first prompt after SSE connected
		time.Sleep(200 * time.Millisecond)
		c.prompt(id, "Reply exactly: TURN_ONE")

		to := time.After(120 * time.Second)
		var turnStarts, turnEnds int
		var sentSecond bool

	collectTurns:
		for {
			select {
			case e, ok := <-ch:
				if !ok { break collectTurns }
				if e.event == "message" && e.data != "" {
					var p struct{ Type string `json:"type"` }
					jsonParse(e.data, &p)
					if p.Type == "turn_start" {
						turnStarts++
						t.Logf("  turn_start #%d", turnStarts)
					}
					if p.Type == "turn_end" {
						turnEnds++
						t.Logf("  turn_end #%d", turnEnds)
						// After first turn ends, send second prompt
						if turnEnds == 1 && !sentSecond {
							sentSecond = true
							go func() {
								time.Sleep(500 * time.Millisecond)
								c.prompt(id, "Reply exactly: TURN_TWO")
							}()
						}
					}
				}
				// We want at least 2 turn_starts and 1 turn_end for the second turn
				if turnStarts >= 2 && turnEnds >= 1 {
					time.Sleep(1 * time.Second)
					break collectTurns
				}
			case <-to:
				break collectTurns
			}
		}
		ca()
		t.Logf("Turns: start=%d end=%d", turnStarts, turnEnds)
		if turnStarts < 2 {
			t.Errorf("expected ≥2 turn_start events, got %d", turnStarts)
		}
	})
}

func jsonParse(data string, into interface{}) error {
	return json.Unmarshal([]byte(data), into)
}

func readOrEmpty(r io.Reader) string {
	data, _ := io.ReadAll(r)
	return string(data)
}

func NewScanner(r io.Reader) *Scanner {
	return &Scanner{scanner: bufio.NewScanner(r)}
}

type Scanner struct {
	scanner *bufio.Scanner
}
func (s *Scanner) Scan() bool  { return s.scanner.Scan() }
func (s *Scanner) Text() string { return s.scanner.Text() }

// ── Test: Concurrent ─────────────────────────

func TestE2E_Concurrent(t *testing.T) {
	c := cl(t)
	var ids []string
	var mu sync.Mutex
	var wg sync.WaitGroup
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			var id string
			c.create(&id)
			c.start(id)
			var dr struct{ State string }
			c.json("GET", "/api/v1/agents/"+id, nil, &dr)
			mu.Lock()
			ids = append(ids, id)
			mu.Unlock()
		}()
	}
	wg.Wait()
	t.Logf("Created %d agents", len(ids))
	for _, id := range ids {
		wg.Add(1)
		go func(a string) { defer wg.Done(); c.prompt(a, "Reply exactly: OK") }(id)
	}
	wg.Wait()
	for _, id := range ids {
		wg.Add(1)
		go func(a string) { defer wg.Done(); c.shutdown(a) }(id)
	}
	wg.Wait()
}

// ── Test: Bridge ─────────────────────────────

func TestE2E_Bridge(t *testing.T) {
	c := cl(t)
	var sup, wrk string
	c.create(&sup)
	c.create(&wrk)
	c.start(sup)
	c.start(wrk)
	var br struct {
		SupervisorID string `json:"supervisor_id"`
		WorkerID     string `json:"worker_id"`
	}
	c.json("POST", "/api/v1/bridge", map[string]interface{}{"supervisor_id": sup, "worker_id": wrk}, &br)
	if br.SupervisorID != sup || br.WorkerID != wrk {
		t.Errorf("bridge: %+v", br)
	}
	c.json("POST", "/api/v1/bridge/worker-prompt", map[string]string{"message": "What is the meaning of life?"}, nil)
	var q []map[string]interface{}
	c.json("GET", "/api/v1/bridge/questions", nil, &q)
	var lg []map[string]interface{}
	c.json("GET", "/api/v1/bridge/log", nil, &lg)
	t.Logf("Bridge: questions=%d log=%d", len(q), len(lg))
	c.shutdown(wrk)
	c.shutdown(sup)
}

// ── Test: Report ─────────────────────────────

func TestE2E_Report(t *testing.T) {
	c := cl(t)
	var id string
	c.create(&id)
	c.start(id)
	c.prompt(id, "Reply exactly: FIRST")
	c.prompt(id, "Reply exactly: SECOND")
	var rp struct {
		AgentID string `json:"agent_id"`
		State   string `json:"final_state"`
		Usage   struct {
			InputTokens  int64   `json:"input_tokens"`
			OutputTokens int64   `json:"output_tokens"`
			CostUSD      float64 `json:"cost_usd"`
			TurnCount    int64   `json:"turn_count"`
		} `json:"token_usage"`
	}
	c.json("GET", "/api/v1/agents/"+id+"/report", nil, &rp)
	t.Logf("Report: ag=%s state=%s tokens=%d/%d cost=$%.6f turns=%d", rp.AgentID, rp.State, rp.Usage.InputTokens, rp.Usage.OutputTokens, rp.Usage.CostUSD, rp.Usage.TurnCount)
	if rp.AgentID != id { t.Errorf("agent_id mismatch") }
	var ev struct{ Count int }
	c.json("GET", "/api/v1/agents/"+id+"/events", nil, &ev)
	if ev.Count == 0 { t.Error("events=0") }
	c.shutdown(id)
}

// ── Test: Rapid API calls ────────────────────

func TestE2E_Rapid(t *testing.T) {
	c := cl(t)
	var id string
	c.create(&id)
	c.start(id)
	var ok atomic.Int64
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			r := c.do("GET", "/api/v1/agents/"+id, nil)
			r.Body.Close()
			if r.StatusCode == 200 { ok.Add(1) }
		}()
	}
	wg.Wait()
	t.Logf("Rapid: %d/50", ok.Load())
	if ok.Load() < 40 { t.Errorf("only %d", ok.Load()) }
	c.shutdown(id)
}

// ── Test: UI endpoints ───────────────────────

func TestE2E_UI(t *testing.T) {
	c := cl(t)
	check := func(p string, min int, subs []string) {
		t.Helper()
		r := c.do("GET", p, nil)
		defer r.Body.Close()
		if r.StatusCode != 200 { t.Errorf("%s: %d", p, r.StatusCode) }
		b, _ := io.ReadAll(r.Body)
		if len(b) < min { t.Errorf("%s: %d bytes", p, len(b)) }
		s := string(b)
		for _, sub := range subs {
			if !strings.Contains(s, sub) { t.Errorf("%s: missing %q", p, sub) }
		}
	}
	check("/ui", 100, []string{"Helios Agent Runtime", "app.js"})
	check("/ui/", 100, []string{"Helios Agent Runtime"})
	check("/ui/agents/abc", 100, []string{"Helios Agent Runtime"})
	check("/ui/bridge", 100, []string{"Helios Agent Runtime"})
	check("/ui/static/styles.css", 1000, []string{"--bg-primary", ".sidebar", ".message"})
	check("/ui/static/app.js", 1000, []string{"App =", "function init", "function renderAgentDetail", "connectMetricsSSE("})
}

// ── Test: Config template + health ───────────

func TestE2E_ConfigHealth(t *testing.T) {
	c := cl(t)
	var p map[string]interface{}
	c.json("GET", "/api/v1/config-template", nil, &p)
	if _, ok := p["omp_path"]; !ok { t.Error("missing omp_path") }
	if _, ok := p["model"]; !ok { t.Error("missing model") }
	var h struct{ Status, Version string }
	c.json("GET", "/api/v1/health", nil, &h)
	if h.Status != "ok" { t.Errorf("status: %s", h.Status) }
	t.Logf("Version: %s", h.Version)
}