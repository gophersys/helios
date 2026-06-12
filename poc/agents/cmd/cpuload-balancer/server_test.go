package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// ── Test suite ─────────────────────────────────

func newTestBalancerServer() *httptest.Server {
	cfg = loadConfig(nil)
	cfg.HealthInterval = time.Hour // disable periodic checks in tests
	cfg.MetricsInterval = time.Hour

	lb = NewLoadBalancer(cfg.HealthInterval, cfg.HealthTimeout, cfg.MetricsInterval, cfg.MetricsTimeout)
	lb.SetStrategy(StrategyLeastCPU)

	mux := http.NewServeMux()
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/metrics", handleMetrics)
	mux.HandleFunc("/backends", handleBackends)
	mux.HandleFunc("/backends/{id}", handleBackendByID)
	mux.HandleFunc("/backends/{id}/check", handleBackendCheck)
	mux.HandleFunc("/strategy", handleStrategy)
	mux.HandleFunc("/strategies", handleStrategies)
	mux.HandleFunc("/stats", handleStats)
	mux.HandleFunc("/proxy/", lb.Proxy())
	mux.HandleFunc("/proxy", lb.Proxy())

	handler := corsMiddleware(recoveryMiddleware(loggingMiddleware(mux)))
	return httptest.NewServer(handler)
}

func resetBalancer() {
	lb.registry = NewBackendRegistry()
	lb.strategy = StrategyLeastCPU
	lb.rrIndex.Store(0)
	lb.requestsTotal.Store(0)
	lb.requestsFailed.Store(0)
}

// ──────────────────────────────────────────────
//  Helpers
// ──────────────────────────────────────────────

type backendResponse struct {
	ID              string  `json:"id"`
	URL             string  `json:"url"`
	Weight          int     `json:"weight"`
	Status          string  `json:"status"`
	RequestsTotal   int64   `json:"requests_total"`
	RequestsFailed  int64   `json:"requests_failed"`
	ConsecutiveFails int    `json:"consecutive_fails"`
	ActiveConns     int64   `json:"active_conns"`
	FailThreshold   int     `json:"fail_threshold"`
}

type strategyResponse struct {
	Strategy string `json:"strategy"`
}

type errorResponse struct {
	Error string `json:"error"`
}

func doJSON(t *testing.T, url, method string, body interface{}, into interface{}) {
	t.Helper()
	var reqBody []byte
	if body != nil {
		var err error
		reqBody, err = json.Marshal(body)
		if err != nil {
			t.Fatalf("marshal body: %v", err)
		}
	}
	req, err := http.NewRequest(method, url, bytes.NewReader(reqBody))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("do request: %v", err)
	}
	defer resp.Body.Close()

	if into != nil && resp.StatusCode < 300 {
		if err := json.NewDecoder(resp.Body).Decode(into); err != nil {
			t.Fatalf("decode response: %v", err)
		}
	}
	if into != nil && resp.StatusCode >= 400 {
		if err := json.NewDecoder(resp.Body).Decode(into); err != nil {
			// partial decode ok for error bodies
		}
	}
}

func registerBackend(t *testing.T, baseURL, backendURL string, opts map[string]interface{}) *backendResponse {
	t.Helper()
	body := map[string]interface{}{"url": backendURL}
	for k, v := range opts {
		body[k] = v
	}
	var resp backendResponse
	doJSON(t, baseURL+"/backends", "POST", body, &resp)
	return &resp
}

// ──────────────────────────────────────────────
//  Tests
// ──────────────────────────────────────────────

func TestHealth(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	var resp map[string]interface{}
	doJSON(t, srv.URL+"/health", "GET", nil, &resp)

	if resp == nil || resp["status"] != "ok" {
		t.Fatalf("expected status ok, got %v", resp)
	}
	if _, ok := resp["strategy"]; !ok {
		t.Errorf("expected strategy in health response")
	}
	if _, ok := resp["backends_total"]; !ok {
		t.Errorf("expected backends_total in health response")
	}
}

func TestRegisterBackend(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	backendURL := "http://127.0.0.1:8080"
	b := registerBackend(t, srv.URL, backendURL, nil)

	if b.URL != backendURL {
		t.Errorf("expected url %s, got %s", backendURL, b.URL)
	}
	if b.Status != "healthy" {
		t.Errorf("expected status healthy, got %s", b.Status)
	}
	if b.Weight != cfg.DefaultWeight {
		t.Errorf("expected weight %d, got %d", cfg.DefaultWeight, b.Weight)
	}
	if b.ID == "" {
		t.Errorf("expected non-empty id")
	}
}

func TestRegisterBackendCustomWeight(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	b := registerBackend(t, srv.URL, "http://127.0.0.1:8080", map[string]interface{}{
		"weight": 5,
	})
	if b.Weight != 5 {
		t.Errorf("expected weight 5, got %d", b.Weight)
	}
}

func TestRegisterBackendInvalidURL(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	var resp errorResponse
	doJSON(t, srv.URL+"/backends", "POST", map[string]interface{}{
		"url": "not-a-valid-url",
	}, &resp)

	if resp.Error == "" {
		t.Error("expected error for invalid URL")
	}
}

func TestRegisterBackendMissingURL(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	var resp errorResponse
	doJSON(t, srv.URL+"/backends", "POST", map[string]interface{}{}, &resp)
	if resp.Error == "" {
		t.Error("expected error for missing url")
	}
}

func TestListBackends(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	// Register two backends
	registerBackend(t, srv.URL, "http://127.0.0.1:8080", nil)
	registerBackend(t, srv.URL, "http://127.0.0.1:8081", nil)

	var resp struct {
		Backends []backendResponse `json:"backends"`
	}
	doJSON(t, srv.URL+"/backends", "GET", nil, &resp)

	if len(resp.Backends) != 2 {
		t.Fatalf("expected 2 backends, got %d", len(resp.Backends))
	}
}

func TestGetBackendByID(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	b := registerBackend(t, srv.URL, "http://127.0.0.1:8080", nil)

	var resp backendResponse
	doJSON(t, srv.URL+"/backends/"+b.ID, "GET", nil, &resp)

	if resp.ID != b.ID {
		t.Errorf("expected id %s, got %s", b.ID, resp.ID)
	}
	if resp.URL != b.URL {
		t.Errorf("expected url %s, got %s", b.URL, resp.URL)
	}
}

func TestGetBackendNotFound(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	var resp errorResponse
	doJSON(t, srv.URL+"/backends/nonexistent", "GET", nil, &resp)
	if resp.Error == "" {
		t.Error("expected error for nonexistent backend")
	}
}

func TestDeleteBackend(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	b := registerBackend(t, srv.URL, "http://127.0.0.1:8080", nil)

	var resp map[string]interface{}
	doJSON(t, srv.URL+"/backends/"+b.ID, "DELETE", nil, &resp)

	if resp["status"] != "removed" {
		t.Errorf("expected status removed, got %v", resp["status"])
	}

	// Verify it's gone
	var list struct {
		Backends []backendResponse `json:"backends"`
	}
	doJSON(t, srv.URL+"/backends", "GET", nil, &list)
	if len(list.Backends) != 0 {
		t.Errorf("expected 0 backends after delete, got %d", len(list.Backends))
	}
}

func TestDeleteBackendNotFound(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	var resp errorResponse
	doJSON(t, srv.URL+"/backends/nonexistent", "DELETE", nil, &resp)
	if resp.Error == "" {
		t.Error("expected error for nonexistent backend delete")
	}
}

func TestBackendCheckNotFound(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	var resp errorResponse
	doJSON(t, srv.URL+"/backends/nonexistent/check", "POST", nil, &resp)
	if resp.Error == "" {
		t.Error("expected error for checking nonexistent backend")
	}
}

func TestStrategyGetSet(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	// Initial strategy should be least-cpu
	var getResp strategyResponse
	doJSON(t, srv.URL+"/strategy", "GET", nil, &getResp)
	if getResp.Strategy != "least-cpu" {
		t.Errorf("expected least-cpu, got %s", getResp.Strategy)
	}

	// Set to round-robin
	var setResp strategyResponse
	doJSON(t, srv.URL+"/strategy", "PUT", map[string]string{"strategy": "round-robin"}, &setResp)
	if setResp.Strategy != "round-robin" {
		t.Errorf("expected round-robin, got %s", setResp.Strategy)
	}

	// Verify persistence
	doJSON(t, srv.URL+"/strategy", "GET", nil, &getResp)
	if getResp.Strategy != "round-robin" {
		t.Errorf("expected round-robin after set, got %s", getResp.Strategy)
	}
}

func TestStrategyInvalid(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	var resp struct {
		Error   string          `json:"error"`
		Allowed []Strategy      `json:"allowed"`
	}
	doJSON(t, srv.URL+"/strategy", "PUT", map[string]string{"strategy": "invalid-strat"}, &resp)

	if resp.Error == "" {
		t.Error("expected error for invalid strategy")
	}
}

func TestStrategiesEndpoint(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	var resp struct {
		Strategies []struct {
			Name        string `json:"name"`
			Description string `json:"description"`
		} `json:"strategies"`
	}
	doJSON(t, srv.URL+"/strategies", "GET", nil, &resp)

	if len(resp.Strategies) == 0 {
		t.Fatal("expected at least one strategy")
	}

	expected := []string{"least-cpu", "round-robin", "random", "least-conn", "weighted-round-robin"}
	found := make(map[string]bool)
	for _, s := range resp.Strategies {
		found[s.Name] = true
	}
	for _, name := range expected {
		if !found[name] {
			t.Errorf("missing strategy %s", name)
		}
	}
}

func TestStatsEndpoint(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	registerBackend(t, srv.URL, "http://127.0.0.1:8080", nil)

	var resp map[string]interface{}
	doJSON(t, srv.URL+"/stats", "GET", nil, &resp)

	if resp["strategy"] != "least-cpu" {
		t.Errorf("expected strategy least-cpu, got %v", resp["strategy"])
	}
	if _, ok := resp["backends"]; !ok {
		t.Errorf("expected backends in stats")
	}
	if _, ok := resp["requests_total"]; !ok {
		t.Errorf("expected requests_total in stats")
	}
	if _, ok := resp["strategy_counts"]; !ok {
		t.Errorf("expected strategy_counts in stats")
	}
}

func TestMetricsEndpoint(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	registerBackend(t, srv.URL, "http://127.0.0.1:8080", nil)

	var resp map[string]interface{}
	doJSON(t, srv.URL+"/metrics", "GET", nil, &resp)

	if _, ok := resp["backends"]; !ok {
		t.Errorf("expected backends in metrics")
	}
	if _, ok := resp["requests_total"]; !ok {
		t.Errorf("expected requests_total in metrics")
	}
	if _, ok := resp["goroutines"]; !ok {
		t.Errorf("expected goroutines in metrics")
	}
	if _, ok := resp["strategy"]; !ok {
		t.Errorf("expected strategy in metrics")
	}
}

func TestMethodsNotAllowed(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	// PUT on health
	var resp errorResponse
	doJSON(t, srv.URL+"/health", "PUT", nil, &resp)
	// health handler doesn't enforce method, should still work (returns ok)

	// DELETE on backends collection
	doJSON(t, srv.URL+"/backends", "DELETE", nil, &resp)
	if resp.Error == "" {
		t.Error("expected error for DELETE on backends collection")
	}

	// POST on backend by ID (no route by default)
	doJSON(t, srv.URL+"/backends/someid", "POST", nil, &resp)
	if resp.Error == "" {
		t.Error("expected error for POST on backend by ID")
	}
}

func TestEmptyBackendsProxy(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	req, _ := http.NewRequest("GET", srv.URL+"/proxy/test", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("proxy request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusServiceUnavailable {
		t.Errorf("expected 503 with no backends, got %d", resp.StatusCode)
	}
}

func TestBackendRegistrationOrder(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	urls := []string{
		"http://10.0.0.1:8080",
		"http://10.0.0.2:8080",
		"http://10.0.0.3:8080",
	}
	for _, u := range urls {
		registerBackend(t, srv.URL, u, nil)
	}

	// backends should be returned in insertion order
	var resp struct {
		Backends []backendResponse `json:"backends"`
	}
	doJSON(t, srv.URL+"/backends", "GET", nil, &resp)

	if len(resp.Backends) != len(urls) {
		t.Fatalf("expected %d backends, got %d", len(urls), len(resp.Backends))
	}
	for i, b := range resp.Backends {
		if b.URL != urls[i] {
			t.Errorf("index %d: expected url %s, got %s", i, urls[i], b.URL)
		}
	}
}

func TestRoundRobinDistribution(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	// Add three backends (all healthy since no live health check running)
	// The health check in tests is disabled, so they stay healthy
	backends := make([]string, 3)
	for i := 0; i < 3; i++ {
		u := fmt.Sprintf("http://127.0.0.%d:8080", i+1)
		b := registerBackend(t, srv.URL, u, nil)
		backends[i] = b.ID
	}

	lb.SetStrategy(StrategyRoundRobin)

	// Pick 6 times — each backend should be picked twice
	counts := make(map[string]int)
	for i := 0; i < 6; i++ {
		b := lb.Next()
		if b == nil {
			t.Fatal("expected backend, got nil")
		}
		counts[b.ID]++
	}

	for _, id := range backends {
		if counts[id] != 2 {
			t.Errorf("backend %s picked %d times, expected 2", id, counts[id])
		}
	}
}

func TestStrategyPersistence(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	// Set a strategy through the API
	doJSON(t, srv.URL+"/strategy", "PUT", map[string]string{"strategy": "weighted-round-robin"}, nil)

	// Verify via Next()
	registerBackend(t, srv.URL, "http://127.0.0.1:8080", nil)
	b := lb.Next()
	if b == nil {
		t.Fatal("expected backend")
	}
}

func TestCORSHeaders(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	req, _ := http.NewRequest("OPTIONS", srv.URL+"/health", nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("options request: %v", err)
	}
	defer resp.Body.Close()

	if resp.Header.Get("Access-Control-Allow-Origin") != "*" {
		t.Errorf("expected CORS origin *")
	}
	if resp.StatusCode != http.StatusNoContent {
		t.Errorf("expected 204 for OPTIONS, got %d", resp.StatusCode)
	}
}

func TestProxyHeaderInjection(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	// Create a test backend server that records headers
	backendSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"x_backend_id":    r.Header.Get("X-Backend-Id"),
			"x_backend_url":   r.Header.Get("X-Backend-Url"),
			"x_forwarded_for": r.Header.Get("X-Forwarded-For"),
		})
	}))
	defer backendSrv.Close()

	registerBackend(t, srv.URL, backendSrv.URL, nil)

	req, _ := http.NewRequest("GET", srv.URL+"/proxy/test", nil)
	req.RemoteAddr = "10.0.0.1:54321"
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("proxy request: %v", err)
	}
	defer resp.Body.Close()

	var body map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}

	if body["x_backend_id"] == "" {
		t.Error("expected X-Backend-Id header")
	}
	if body["x_forwarded_for"] == "" {
		t.Error("expected X-Forwarded-For header")
	}
}

func TestConcurrentBackendOperations(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	done := make(chan bool, 20)
	for i := 0; i < 20; i++ {
		go func(i int) {
			url := fmt.Sprintf("http://10.0.0.%d:8080", i+1)
			registerBackend(t, srv.URL, url, nil)
			done <- true
		}(i)
	}
	for i := 0; i < 20; i++ {
		<-done
	}

	var resp struct {
		Backends []backendResponse `json:"backends"`
	}
	doJSON(t, srv.URL+"/backends", "GET", nil, &resp)
	if len(resp.Backends) != 20 {
		t.Errorf("expected 20 backends after concurrent adds, got %d", len(resp.Backends))
	}
}

func TestRoundRobinNoBackends(t *testing.T) {
	resetBalancer()
	lb.SetStrategy(StrategyRoundRobin)
	b := lb.Next()
	if b != nil {
		t.Error("expected nil with no backends")
	}
}

func TestLeastCPUNoBackends(t *testing.T) {
	resetBalancer()
	b := lb.Next()
	if b != nil {
		t.Error("expected nil with no backends")
	}
}

func TestRandomNoBackends(t *testing.T) {
	resetBalancer()
	lb.SetStrategy(StrategyRandom)
	b := lb.Next()
	if b != nil {
		t.Error("expected nil with no backends")
	}
}

func TestLeastConnNoBackends(t *testing.T) {
	resetBalancer()
	lb.SetStrategy(StrategyLeastConn)
	b := lb.Next()
	if b != nil {
		t.Error("expected nil with no backends")
	}
}

func TestWeightedRRNoBackends(t *testing.T) {
	resetBalancer()
	lb.SetStrategy(StrategyWeightedRR)
	b := lb.Next()
	if b != nil {
		t.Error("expected nil with no backends")
	}
}

func TestBackendForceCheck(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	// Register a real backend that will respond healthily
	backendSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}))
	defer backendSrv.Close()

	b := registerBackend(t, srv.URL, backendSrv.URL, nil)

	// Force health check
	var resp backendResponse
	doJSON(t, srv.URL+"/backends/"+b.ID+"/check", "POST", nil, &resp)

	if resp.Status != "healthy" {
		t.Errorf("expected status healthy after check, got %s", resp.Status)
	}
}

func TestMaxLoadsBackendCompat(t *testing.T) {
	// Verify that the balancer can talk to a cpuload server's metrics endpoint
	// by parsing the right fields. This is an integration-oriented unit test.
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"loads": map[string]interface{}{
				"active_loads": float64(2),
				"max_loads":    float64(10),
			},
			"goroutines": float64(5),
			"cpus":       float64(4),
		})
	}))
	defer server.Close()

	mc := NewMetricsCollector(NewBackendRegistry(), time.Hour, time.Second)
	backend, _ := mc.registry.Add(server.URL, 1, 3, 30*time.Second)
	mc.collectOne(backend)

	backend.mu.RLock()
	metrics := backend.CPUMetrics
	backend.mu.RUnlock()

	if metrics.Load != 0.2 {
		t.Errorf("expected load 0.2, got %f", metrics.Load)
	}
	if metrics.Goroutines != 5 {
		t.Errorf("expected goroutines 5, got %d", metrics.Goroutines)
	}
	if metrics.CPUs != 4 {
		t.Errorf("expected CPUs 4, got %d", metrics.CPUs)
	}
}

func TestAllStrategiesAcceptViaAPI(t *testing.T) {
	srv := newTestBalancerServer()
	defer srv.Close()
	resetBalancer()

	for _, s := range allStrategies() {
		var resp strategyResponse
		doJSON(t, srv.URL+"/strategy", "PUT", map[string]string{"strategy": string(s)}, &resp)
		if resp.Strategy != string(s) {
			t.Errorf("expected strategy %s, got %s", s, resp.Strategy)
		}
	}
}

func TestCryptoIntN(t *testing.T) {
	// Basic sanity
	for n := 1; n <= 100; n++ {
		v := cryptoIntN(n)
		if v < 0 || v >= n {
			t.Errorf("cryptoIntN(%d) = %d, out of range", n, v)
		}
	}
	if v := cryptoIntN(0); v != 0 {
		t.Errorf("cryptoIntN(0) = %d, expected 0", v)
	}
	if v := cryptoIntN(-1); v != 0 {
		t.Errorf("cryptoIntN(-1) = %d, expected 0", v)
	}
}

// Ensure benchmarks compile: verify Next() with strategy
func BenchmarkNext(b *testing.B) {
	resetBalancer()
	for i := 0; i < 10; i++ {
		lb.registry.Add(fmt.Sprintf("http://127.0.0.%d:8080", i+1), 1, 3, 30*time.Second)
	}
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		lb.Next()
	}
}

func TestComputeScoreConcurrentSafety(t *testing.T) {
	resetBalancer()
	backend, _ := lb.registry.Add("http://127.0.0.1:8080", 1, 3, 30*time.Second)
	done := make(chan bool, 10)
	for i := 0; i < 10; i++ {
		go func() {
			_ = computeScore(backend, cpuless)
			done <- true
		}()
	}
	for i := 0; i < 10; i++ {
		<-done
	}
}

func TestComputeUtilization(t *testing.T) {
	tests := []struct {
		load float64
		cpus int
		want float64
	}{
		{0, 4, 0},
		{2, 4, 0.5},
		{4, 4, 1},
		{8, 4, 1},  // capped
		{5, 0, 0},  // no cpus
	}
	for _, tc := range tests {
		m := CPUMetrics{Load: tc.load, CPUs: tc.cpus}
		got := computeUtilization(m)
		if got != tc.want {
			t.Errorf("computeUtilization({%f, %d}) = %f, want %f", tc.load, tc.cpus, got, tc.want)
		}
	}
}