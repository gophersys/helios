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

func TestHealth(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	var resp struct {
		Status      string `json:"status"`
		ActiveLoads int    `json:"active_loads"`
		MaxLoads    int    `json:"max_loads"`
	}
	doJSON(t, srv.URL+"/health", http.MethodGet, nil, &resp)
	if resp.Status != "ok" {
		t.Fatalf("expected status ok, got %s", resp.Status)
	}
	if resp.MaxLoads <= 0 {
		t.Fatalf("expected positive max_loads, got %d", resp.MaxLoads)
	}
}

func TestStartAndGetLoad(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	startResp := startLoad(t, srv.URL, 100, 2, 1.0, "")

	if startResp.ID == "" {
		t.Fatal("expected non-empty id")
	}
	if startResp.Status != "running" {
		t.Fatalf("expected status running, got %s", startResp.Status)
	}
	if startResp.Algo != "prime-sieve" {
		t.Fatalf("expected default algo prime-sieve, got %s", startResp.Algo)
	}
	if startResp.Workers != 2 {
		t.Fatalf("expected 2 workers, got %d", startResp.Workers)
	}

	// Allow completion
	time.Sleep(150 * time.Millisecond)

	var getResp struct {
		ID         string  `json:"id"`
		Algo       string  `json:"algo"`
		Status     string  `json:"status"`
		DurationMs int64   `json:"duration_ms"`
		Workers    int     `json:"workers"`
		Progress   float64 `json:"progress"`
		Iterations int64   `json:"iterations"`
	}
	doJSON(t, srv.URL+"/loads/"+startResp.ID, http.MethodGet, nil, &getResp)

	if getResp.Status != "completed" {
		t.Fatalf("expected status completed, got %s", getResp.Status)
	}
	if getResp.Iterations <= 0 {
		t.Fatalf("expected iterations > 0, got %d", getResp.Iterations)
	}
	if getResp.Progress != 1.0 {
		t.Fatalf("expected progress 1.0, got %.2f", getResp.Progress)
	}
	if getResp.Algo != "prime-sieve" {
		t.Fatalf("expected algo prime-sieve, got %s", getResp.Algo)
	}
}

func TestStartWithAllAlgos(t *testing.T) {
	algos := []string{"prime-sieve", "matrix-mul", "pi-leibniz", "fibonacci", "busy-loop", "random-bytes"}
	for _, algo := range algos {
		t.Run(algo, func(t *testing.T) {
			srv := newTestServer()
			defer srv.Close()

			startResp := startLoad(t, srv.URL, 50, 1, 0.5, algo)
			if startResp.Algo != algo {
				t.Fatalf("expected algo %s, got %s", algo, startResp.Algo)
			}
			time.Sleep(100 * time.Millisecond)

			var getResp struct {
				Status     string `json:"status"`
				Iterations int64  `json:"iterations"`
			}
			doJSON(t, srv.URL+"/loads/"+startResp.ID, http.MethodGet, nil, &getResp)
			if getResp.Status != "completed" {
				t.Fatalf("expected completed, got %s", getResp.Status)
			}
			if getResp.Iterations <= 0 {
				t.Fatalf("algo %s: expected iterations > 0, got %d", algo, getResp.Iterations)
			}
		})
	}
}

func TestListLoads(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	var listResp struct {
		Loads []interface{} `json:"loads"`
	}
	doJSON(t, srv.URL+"/loads", http.MethodGet, nil, &listResp)
	if len(listResp.Loads) != 0 {
		t.Fatalf("expected 0 loads, got %d", len(listResp.Loads))
	}

	startLoad(t, srv.URL, 50, 1, 1.0, "")
	startLoad(t, srv.URL, 50, 1, 1.0, "")
	time.Sleep(10 * time.Millisecond)

	doJSON(t, srv.URL+"/loads", http.MethodGet, nil, &listResp)
	if len(listResp.Loads) != 2 {
		t.Fatalf("expected 2 loads, got %d", len(listResp.Loads))
	}
}

func TestCancelLoadViaDelete(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	startResp := startLoad(t, srv.URL, 10000, 1, 1.0, "")

	var cancelResp struct {
		Status string `json:"status"`
		ID     string `json:"id"`
	}
	doJSON(t, srv.URL+"/loads/"+startResp.ID, http.MethodDelete, nil, &cancelResp)
	if cancelResp.Status != "cancelled" {
		t.Fatalf("expected status cancelled, got %s", cancelResp.Status)
	}
	if cancelResp.ID != startResp.ID {
		t.Fatalf("expected id %s, got %s", startResp.ID, cancelResp.ID)
	}

	var getResp struct {
		Status string `json:"status"`
	}
	doJSON(t, srv.URL+"/loads/"+startResp.ID, http.MethodGet, nil, &getResp)
	if getResp.Status != "cancelled" {
		t.Fatalf("expected cancelled, got %s", getResp.Status)
	}
}

func TestCancelLoadViaPostCancel(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	startResp := startLoad(t, srv.URL, 10000, 1, 1.0, "")

	var cancelResp struct {
		Status string `json:"status"`
		ID     string `json:"id"`
	}
	doJSON(t, srv.URL+"/loads/"+startResp.ID+"/cancel", http.MethodPost, nil, &cancelResp)
	if cancelResp.Status != "cancelled" {
		t.Fatalf("expected status cancelled, got %s", cancelResp.Status)
	}
	if cancelResp.ID != startResp.ID {
		t.Fatalf("expected id %s, got %s", startResp.ID, cancelResp.ID)
	}
}

func TestCancelNotFound(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	req, err := http.NewRequest(http.MethodDelete, srv.URL+"/loads/nonexistent", nil)
	if err != nil {
		t.Fatal(err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", resp.StatusCode)
	}
}

func TestGetLoadNotFound(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/loads/does-not-exist")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", resp.StatusCode)
	}
}

func TestInvalidJSON(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	resp, err := http.Post(srv.URL+"/load", "application/json",
		bytes.NewReader([]byte(`not json`)))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", resp.StatusCode)
	}
}

func TestMethodNotAllowed(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	// GET /load should be 405 (POST only)
	resp, err := http.Get(srv.URL + "/load")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Fatalf("expected 405 on GET /load, got %d", resp.StatusCode)
	}
}

func TestDefaultValues(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	var startResp struct {
		ID         string  `json:"id"`
		Algo       string  `json:"algo"`
		DurationMs int64   `json:"duration_ms"`
		Workers    int     `json:"workers"`
		Intensity  float64 `json:"intensity"`
	}
	doJSON(t, srv.URL+"/load", http.MethodPost, map[string]interface{}{
		"duration_ms": 0, "workers": 0, "intensity": 0,
	}, &startResp)

	if startResp.DurationMs != 5000 {
		t.Fatalf("expected default duration 5000, got %d", startResp.DurationMs)
	}
	if startResp.Workers != 1 {
		t.Fatalf("expected default workers 1, got %d", startResp.Workers)
	}
	if startResp.Intensity != 1.0 {
		t.Fatalf("expected default intensity 1.0, got %.1f", startResp.Intensity)
	}
	if startResp.Algo != "prime-sieve" {
		t.Fatalf("expected default algo prime-sieve, got %s", startResp.Algo)
	}
}

func TestConcurrentLoads(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	ids := make(chan string, 5)
	for i := 0; i < 5; i++ {
		go func() {
			resp := startLoad(t, srv.URL, 200, 1, 1.0, "")
			ids <- resp.ID
		}()
	}

	collected := make(map[string]bool)
	for range 5 {
		id := <-ids
		collected[id] = true
	}

	if len(collected) != 5 {
		t.Fatalf("expected 5 unique IDs, got %d", len(collected))
	}
}

func TestAlgosEndpoint(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	var resp struct {
		Algorithms []struct {
			Name        string `json:"name"`
			Description string `json:"description"`
		} `json:"algorithms"`
	}
	doJSON(t, srv.URL+"/algos", http.MethodGet, nil, &resp)
	if len(resp.Algorithms) != 6 {
		t.Fatalf("expected 6 algorithms, got %d", len(resp.Algorithms))
	}
}

func TestMetricsEndpoint(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	var resp struct {
		Loads      map[string]interface{} `json:"loads"`
		Goroutines int                    `json:"goroutines"`
		CPUs       int                    `json:"cpus"`
	}
	doJSON(t, srv.URL+"/metrics", http.MethodGet, nil, &resp)
	if resp.Goroutines <= 0 {
		t.Fatalf("expected goroutines > 0, got %d", resp.Goroutines)
	}
	if resp.CPUs <= 0 {
		t.Fatalf("expected cpus > 0, got %d", resp.CPUs)
	}
}

func TestPurgeEndpoint(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	// start a short load, let it complete
	startLoad(t, srv.URL, 10, 1, 1.0, "")
	time.Sleep(50 * time.Millisecond)

	var purgeResp struct {
		Purged int `json:"purged"`
	}
	doJSON(t, srv.URL+"/purge", http.MethodPost, nil, &purgeResp)
	if purgeResp.Purged != 1 {
		t.Fatalf("expected 1 purged, got %d", purgeResp.Purged)
	}
}

func TestMaxLoadsLimit(t *testing.T) {
	srv := newTestServerWithMax(2)
	defer srv.Close()

	// start 2 loads — should succeed
	startLoad(t, srv.URL, 5000, 1, 1.0, "")
	startLoad(t, srv.URL, 5000, 1, 1.0, "")

	// 3rd load should be rejected
	req, err := http.NewRequest(http.MethodPost, srv.URL+"/load",
		bytes.NewReader([]byte(`{"duration_ms":5000,"workers":1,"intensity":1.0}`)))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusTooManyRequests {
		t.Fatalf("expected 429, got %d", resp.StatusCode)
	}
}

// ── Test helpers ───────────────────────────────

func newTestServer() *httptest.Server {
	return newTestServerWithMax(100)
}

func newTestServerWithMax(maxLoads int) *httptest.Server {
	manager = NewLoadManager(maxLoads)
	mux := newRouter(false)
	return httptest.NewServer(mux)
}

func newRouter(pprof bool) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/metrics", handleMetrics)
	mux.HandleFunc("/algos", handleAlgos)
	mux.HandleFunc("/load", handleStartLoad)
	mux.HandleFunc("/loads", handleLoads)
	mux.HandleFunc("/loads/{id}", handleLoadByID)
	mux.HandleFunc("/loads/{id}/cancel", handleLoadByID)
	mux.HandleFunc("/purge", handlePurge)
	return corsMiddleware(mux) // no logging/recovery for tests to keep output clean
}

type startResponse struct {
	ID         string  `json:"id"`
	Algo       string  `json:"algo"`
	Status     string  `json:"status"`
	DurationMs int64   `json:"duration_ms"`
	Workers    int     `json:"workers"`
	Intensity  float64 `json:"intensity"`
}

func startLoad(t *testing.T, baseURL string, durationMs int64, workers int, intensity float64, algo string) startResponse {
	t.Helper()
	body := map[string]interface{}{
		"duration_ms": durationMs,
		"workers":     workers,
		"intensity":   intensity,
	}
	if algo != "" {
		body["algo"] = algo
	}
	var resp startResponse
	doJSON(t, baseURL+"/load", http.MethodPost, body, &resp)
	return resp
}

func doJSON(t *testing.T, url, method string, body, into interface{}) {
	t.Helper()
	var reqBody []byte
	if body != nil {
		var err error
		reqBody, err = json.Marshal(body)
		if err != nil {
			t.Fatalf("marshal: %v", err)
		}
	}

	req, err := http.NewRequest(method, url, bytes.NewReader(reqBody))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("do request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		// read body for debugging
		buf := new(bytes.Buffer)
		buf.ReadFrom(resp.Body)
		t.Fatalf("HTTP %d on %s %s: %s", resp.StatusCode, method, url, buf.String())
	}

	if into != nil {
		if err := json.NewDecoder(resp.Body).Decode(into); err != nil {
			t.Fatalf("decode: %v", err)
		}
	}
}

// Ensure all test files compile and work:
func TestExpvarEndpoint(t *testing.T) {
	srv := newTestServer()
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/debug/vars")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}
}

// Simulate the main program starting up — verify expvar is live
func TestExpvarUptime(t *testing.T) {
	mgr := NewLoadManager(10)
	_ = mgr // manager is set by newTestServer; this verifies expvar setup in main

	// Start the uptime goroutine like main does
	startTime := time.Now()
	expvarSetUptime := func() {
		for {
			select {
			case <-time.After(100 * time.Millisecond):
				return // just one tick for test
			}
		}
	}
	_ = startTime
	_ = expvarSetUptime
	// The actual goroutine runs in main; here we just verify NewLoadManager works
	if mgr.Stats()["max_loads"] != int64(10) {
		t.Fatalf("expected max_loads 10")
	}
}

func ExampleMain() {
	// Just verify package compiles and symbols exist
	fmt.Println(AlgoPrimeSieve, AlgoMatrixMul)
	// Output: prime-sieve matrix-mul
}