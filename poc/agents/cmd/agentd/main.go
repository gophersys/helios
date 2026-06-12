package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"strings"
	"syscall"
	"time"

	"github.com/helios/poc/agents/pkg/agent"
	"github.com/helios/poc/agents/ui"
)

var (
	agents   = make(map[string]*agent.Agent)
	bridge   *agent.SupervisorWorkerBridge
	agentsMu sync.RWMutex
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/agents", handleCreateAgent)
	mux.HandleFunc("GET /api/v1/agents", handleListAgents)
	mux.HandleFunc("GET /api/v1/agents/{id}", handleGetAgent)
	mux.HandleFunc("POST /api/v1/agents/{id}/start", handleStartAgent)
	mux.HandleFunc("POST /api/v1/agents/{id}/prompt", handlePromptAgent)
	mux.HandleFunc("POST /api/v1/agents/{id}/abort", handleAbortAgent)
	mux.HandleFunc("POST /api/v1/agents/{id}/shutdown", handleShutdownAgent)
	mux.HandleFunc("GET /api/v1/agents/{id}/metrics", handleGetAgentMetrics)
	mux.HandleFunc("GET /api/v1/agents/{id}/events", handleGetAgentEvents)
	mux.HandleFunc("GET /api/v1/agents/{id}/report", handleAgentReport)
	mux.HandleFunc("GET /api/v1/agents/{id}/token-usage", handleTokenUsage)
	mux.HandleFunc("GET /api/v1/agents/{id}/metrics/stream", handleMetricsSSE)
	mux.HandleFunc("GET /api/v1/agents/{id}/events/stream", handleEventsSSE)
	mux.HandleFunc("GET /api/v1/metrics/stream", handleGlobalMetricsSSE)
	mux.HandleFunc("POST /api/v1/bridge", handleCreateBridge)
	mux.HandleFunc("GET /api/v1/bridge", handleGetBridge)
	mux.HandleFunc("POST /api/v1/bridge/worker-prompt", handleBridgeWorkerPrompt)
	mux.HandleFunc("GET /api/v1/bridge/questions", handleBridgeQuestions)
	mux.HandleFunc("GET /api/v1/bridge/log", handleBridgeLog)
	mux.HandleFunc("GET /api/v1/health", handleHealth)
	mux.HandleFunc("GET /api/v1/config-template", handleConfigTemplate)
	mux.HandleFunc("GET /api/v1/subs/stats", handleSubscriberStats)
	// UI routes — handler creation is infallible with embed.FS, so ignore error
	uiHandler, _ := ui.Handler()
	mux.Handle("GET /ui", uiHandler)
	mux.Handle("GET /ui/", uiHandler)
	mux.Handle("GET /ui/static/", uiHandler)
	mux.Handle("GET /ui/agents/{id}", uiHandler)
	mux.Handle("GET /ui/bridge", uiHandler)

	handler := corsMiddleware(loggingMiddleware(mux))

	server := &http.Server{
		Addr:         ":" + port,
		Handler:      handler,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 0,
		IdleTimeout:  120 * time.Second,
	}

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		log.Printf("Agent runtime HTTP server starting on :%s", port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	<-quit
	log.Println("Shutting down...")

	agentsMu.Lock()
	for id, a := range agents {
		log.Printf("Shutting down agent: %s", id)
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		a.Shutdown(ctx)
		cancel()
	}
	agentsMu.Unlock()

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced shutdown: %v", err)
	}
	log.Println("Server stopped")
}

// ──────────────────────────────────────────────
//  Agent CRUD handlers
// ──────────────────────────────────────────────

func handleCreateAgent(w http.ResponseWriter, r *http.Request) {
	var cfg agent.AgentConfig
	if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"invalid config: %s"}`, err), http.StatusBadRequest)
		return
	}
	if cfg.OMPPath == "" {
		cfg.OMPPath = "omp"
	}
	if cfg.Model == "" {
		cfg.Model = "openrouter/deepseek/deepseek-v4-flash"
	}
	id := fmt.Sprintf("agent_%d", time.Now().UnixNano())
	a := agent.NewAgent(id, cfg)
	agentsMu.Lock()
	agents[id] = a
	agentsMu.Unlock()
	writeJSON(w, http.StatusCreated, map[string]interface{}{
		"id": id, "config": cfg, "state": a.State(),
	})
}

func handleListAgents(w http.ResponseWriter, r *http.Request) {
	agentsMu.RLock()
	defer agentsMu.RUnlock()
	list := make([]map[string]interface{}, 0, len(agents))
	for id, a := range agents {
		list = append(list, map[string]interface{}{
			"id": id, "state": a.State(), "uptime": a.Uptime().String(),
			"tokens_in": a.TokenUsage().InputTokens, "tokens_out": a.TokenUsage().OutputTokens,
			"cost_usd": a.TokenUsage().CostUSD,
		})
	}
	writeJSON(w, http.StatusOK, list)
}

func handleGetAgent(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	agentsMu.RLock()
	a, ok := agents[id]
	agentsMu.RUnlock()
	if !ok {
		http.Error(w, `{"error":"agent not found"}`, http.StatusNotFound)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"id": id, "state": a.State(), "uptime": a.Uptime().String(),
		"config": a.Config,
		"tokens_in": a.TokenUsage().InputTokens, "tokens_out": a.TokenUsage().OutputTokens,
		"cost_usd": a.TokenUsage().CostUSD,
	})
}

func handleStartAgent(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	agentsMu.RLock()
	a, ok := agents[id]
	agentsMu.RUnlock()
	if !ok {
		http.Error(w, `{"error":"agent not found"}`, http.StatusNotFound)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	if err := a.Start(ctx); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"start failed: %s"}`, err), http.StatusInternalServerError)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{"id": id, "state": a.State()})
}

func handlePromptAgent(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	agentsMu.RLock()
	a, ok := agents[id]
	agentsMu.RUnlock()
	if !ok {
		http.Error(w, `{"error":"agent not found"}`, http.StatusNotFound)
		return
	}
	var body struct {
		Message string `json:"message"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"invalid body: %s"}`, err), http.StatusBadRequest)
		return
	}
	if a.State() != agent.StateReady && a.State() != agent.StateRunning {
		http.Error(w, fmt.Sprintf(`{"error":"agent not ready (state: %s)"}`, a.State()), http.StatusConflict)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Minute)
	defer cancel()
	if err := a.Prompt(ctx, body.Message); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"prompt failed: %s"}`, err), http.StatusInternalServerError)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"id": id, "state": a.State(), "token_usage": a.TokenUsage(),
	})
}

func handleAbortAgent(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	agentsMu.RLock()
	a, ok := agents[id]
	agentsMu.RUnlock()
	if !ok {
		http.Error(w, `{"error":"agent not found"}`, http.StatusNotFound)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	if err := a.Abort(ctx); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"abort failed: %s"}`, err), http.StatusInternalServerError)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{"id": id, "state": a.State()})
}

func handleShutdownAgent(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	agentsMu.RLock()
	a, ok := agents[id]
	agentsMu.RUnlock()
	if !ok {
		http.Error(w, `{"error":"agent not found"}`, http.StatusNotFound)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()
	if err := a.Shutdown(ctx); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"shutdown failed: %s"}`, err), http.StatusInternalServerError)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{"id": id, "state": a.State()})
}

func handleGetAgentMetrics(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	agentsMu.RLock()
	a, ok := agents[id]
	agentsMu.RUnlock()
	if !ok {
		http.Error(w, `{"error":"agent not found"}`, http.StatusNotFound)
		return
	}
	if r.URL.Query().Get("format") == "json" {
		data, err := a.Metrics().ExportJSON()
		if err != nil {
			http.Error(w, fmt.Sprintf(`{"error":"export failed: %s"}`, err), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write(data)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"count": a.Metrics().Len(), "total_emitted": a.Metrics().TotalEmitted(),
	})
}

func handleMetricsSSE(w http.ResponseWriter, r *http.Request) {
	defer func() {
		if rec := recover(); rec != nil {
			http.Error(w, fmt.Sprintf(`{"error":"panic: %v"}`, rec), http.StatusInternalServerError)
		}
	}()
	id := r.PathValue("id")
	agentsMu.RLock()
	a, ok := agents[id]
	agentsMu.RUnlock()
	if !ok {
		http.Error(w, `{"error":"not found"}`, http.StatusNotFound)
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, `{"error":"streaming not supported"}`, http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(http.StatusOK)
	flusher.Flush()

	replayCount := 10
	if rc := r.URL.Query().Get("replay"); rc != "" {
		if n, err := parseUint(rc); err == nil {
			replayCount = n
		}
	}

	_, ch, unsub := a.Metrics().SubscribeSSE(256, replayCount)
	defer unsub()
	writeMetricsSSE(ch, w, r.Context().Done())
}

func handleEventsSSE(w http.ResponseWriter, r *http.Request) {
	defer func() {
		if rec := recover(); rec != nil {
			http.Error(w, fmt.Sprintf(`{"error":"panic: %v"}`, rec), http.StatusInternalServerError)
		}
	}()

	id := r.PathValue("id")
	agentsMu.RLock()
	a, ok := agents[id]
	agentsMu.RUnlock()
	if !ok {
		http.Error(w, `{"error":"not found"}`, http.StatusNotFound)
		return
	}

	rpc := a.GetRPCClient()
	if rpc == nil {
		http.Error(w, `{"error":"agent not started"}`, http.StatusConflict)
		return
	}

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, `{"error":"streaming not supported"}`, http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(http.StatusOK)
	flusher.Flush()

	rpcStream := rpc.Subscribe()
	defer rpc.Unsubscribe(rpcStream)
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case frame, ok := <-rpcStream:
			if !ok {
				return
			}
			data, err := json.Marshal(frame)
			if err != nil {
				continue
			}
			sse := agent.SSEEvent{Event: "message", Data: string(data)}
			sse.WriteTo(w)
			flusher.Flush()

		case <-ticker.C:
			fmt.Fprintf(w, "event: keepalive\ndata: {}\n\n")
			flusher.Flush()

		case <-r.Context().Done():
			return
		}
	}
}

func handleGetAgentEvents(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	agentsMu.RLock()
	a, ok := agents[id]
	agentsMu.RUnlock()
	if !ok {
		http.Error(w, `{"error":"agent not found"}`, http.StatusNotFound)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"count": len(a.Events()), "events": a.Events(),
	})
}

func handleAgentReport(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	agentsMu.RLock()
	a, ok := agents[id]
	agentsMu.RUnlock()
	if !ok {
		http.Error(w, `{"error":"agent not found"}`, http.StatusNotFound)
		return
	}
	writeJSON(w, http.StatusOK, a.GenerateReport())
}
func handleTokenUsage(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	agentsMu.RLock()
	a, ok := agents[id]
	agentsMu.RUnlock()
	if !ok {
		http.Error(w, `{"error":"agent not found"}`, http.StatusNotFound)
		return
	}
	writeJSON(w, http.StatusOK, a.TokenUsage())
}


func handleGlobalMetricsSSE(w http.ResponseWriter, r *http.Request) {
	if _, ok := w.(http.Flusher); !ok {
		http.Error(w, `{"error":"streaming not supported"}`, http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(http.StatusOK)

	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()

	lastSnapshots := make(map[string]int64)
	for {
		select {
		case <-ticker.C:
			agentsMu.RLock()
			for id, a := range agents {
				total := a.Metrics().TotalEmitted()
				prev := lastSnapshots[id]
				if total > prev {
					events := a.Metrics().SnapshotEvents()
					for _, ev := range events[prev:] {
						data, err := json.Marshal(ev)
						if err != nil {
							continue
						}
						sse := agent.SSEEvent{Event: "metrics", Data: string(data)}
						sse.WriteTo(w)
					}
					lastSnapshots[id] = total
				}
			}
			agentsMu.RUnlock()
			w.(http.Flusher).Flush()

		case <-r.Context().Done():
			return
		}
	}
}

func writeMetricsSSE(ch <-chan agent.MetricsEvent, w io.Writer, done <-chan struct{}) {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case ev, ok := <-ch:
			if !ok {
				return
			}
			data, err := json.Marshal(ev)
			if err != nil {
				continue
			}
			sse := agent.SSEEvent{Event: "metrics", Data: string(data), ID: ev.ID}
			sse.WriteTo(w)
			if flusher, ok := w.(http.Flusher); ok {
				flusher.Flush()
			}

		case <-ticker.C:
			sse := agent.SSEEvent{Event: "keepalive", Data: `{"type":"keepalive"}`}
			sse.WriteTo(w)
			if flusher, ok := w.(http.Flusher); ok {
				flusher.Flush()
			}

		case <-done:
			return
		}
	}
}

func parseUint(s string) (int, error) {
	var n int
	for _, c := range s {
		if c < '0' || c > '9' {
			return 0, fmt.Errorf("not a number")
		}
		n = n*10 + int(c-'0')
	}
	return n, nil
}

// ──────────────────────────────────────────────
//  Bridge handlers
// ──────────────────────────────────────────────

func handleCreateBridge(w http.ResponseWriter, r *http.Request) {
	var body struct {
		SupervisorID string `json:"supervisor_id"`
		WorkerID     string `json:"worker_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"invalid body: %s"}`, err), http.StatusBadRequest)
		return
	}
	agentsMu.RLock()
	supervisor, ok1 := agents[body.SupervisorID]
	worker, ok2 := agents[body.WorkerID]
	agentsMu.RUnlock()
	if !ok1 {
		http.Error(w, fmt.Sprintf(`{"error":"supervisor %s not found"}`, body.SupervisorID), http.StatusNotFound)
		return
	}
	if !ok2 {
		http.Error(w, fmt.Sprintf(`{"error":"worker %s not found"}`, body.WorkerID), http.StatusNotFound)
		return
	}

	bridge = agent.NewSupervisorWorkerBridge(supervisor, worker)
	go func() {
		toolMgr := agent.NewHostToolManager(worker)
		toolMgr.RegisterTool(agent.NewConsultSupervisorTool(), func(ctx context.Context, args json.RawMessage) (interface{}, error) {
			return map[string]interface{}{
				"content": []map[string]interface{}{{"type": "text", "text": "Bridge is active"}},
			}, nil
		})
		c, cancel := context.WithTimeout(r.Context(), 10*time.Second)
		defer cancel()
		toolMgr.SyncTools(c)
	}()
	writeJSON(w, http.StatusCreated, map[string]interface{}{
		"supervisor_id": body.SupervisorID, "worker_id": body.WorkerID,
	})
}

func handleGetBridge(w http.ResponseWriter, r *http.Request) {
	if bridge == nil {
		http.Error(w, `{"error":"no bridge configured"}`, http.StatusNotFound)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"supervisor_id": bridge.Supervisor().ID, "worker_id": bridge.Worker().ID,
		"questions": len(bridge.GetQuestions()),
	})
}

func handleBridgeWorkerPrompt(w http.ResponseWriter, r *http.Request) {
	if bridge == nil {
		http.Error(w, `{"error":"no bridge configured"}`, http.StatusNotFound)
		return
	}
	var body struct{ Message string `json:"message"` }
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"invalid body: %s"}`, err), http.StatusBadRequest)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Minute)
	defer cancel()
	if err := bridge.AskWorker(ctx, body.Message); err != nil {
		http.Error(w, fmt.Sprintf(`{"error":"worker prompt failed: %s"}`, err), http.StatusInternalServerError)
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{"message": body.Message, "state": bridge.Worker().State()})
}

func handleBridgeQuestions(w http.ResponseWriter, r *http.Request) {
	if bridge == nil {
		http.Error(w, `{"error":"no bridge configured"}`, http.StatusNotFound)
		return
	}
	writeJSON(w, http.StatusOK, bridge.GetQuestions())
}

func handleBridgeLog(w http.ResponseWriter, r *http.Request) {
	if bridge == nil {
		http.Error(w, `{"error":"no bridge configured"}`, http.StatusNotFound)
		return
	}
	writeJSON(w, http.StatusOK, bridge.GetLog())
}

// ──────────────────────────────────────────────
//  System handlers
// ──────────────────────────────────────────────

func handleHealth(w http.ResponseWriter, r *http.Request) {
	agentsMu.RLock()
	c := len(agents)
	agentsMu.RUnlock()
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"status": "ok", "timestamp": time.Now().UTC().Format(time.RFC3339),
		"version": "0.2.0", "agents": c,
	})
}

func handleConfigTemplate(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(agent.GenerateConfigTemplate()))
}

func handleSubscriberStats(w http.ResponseWriter, r *http.Request) {
	agentsMu.RLock()
	stats := make(map[string]interface{})
	for id, a := range agents {
		stats[id] = a.Metrics().SubscriberStats()
	}
	agentsMu.RUnlock()
	writeJSON(w, http.StatusOK, stats)
}

// ──────────────────────────────────────────────
//  Middleware & helpers
// ──────────────────────────────────────────────

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		wrapped := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}
		next.ServeHTTP(wrapped, r)
		log.Printf("%s %s %d %s", r.Method, r.URL.Path, wrapped.statusCode, time.Since(start))
	})
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		// In development, allow any local origin
		if origin == "" || strings.Contains(origin, "localhost") || strings.Contains(origin, "127.0.0.1") {
			w.Header().Set("Access-Control-Allow-Origin", origin)
		} else {
			w.Header().Set("Access-Control-Allow-Origin", "http://localhost:8080")
		}
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Last-Event-ID")
		w.Header().Set("Access-Control-Expose-Headers", "Content-Type")
		w.Header().Set("Access-Control-Allow-Credentials", "false")
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}
		next.ServeHTTP(w, r)
	})
}

type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

func (rw *responseWriter) Flush() {
	if f, ok := rw.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}
