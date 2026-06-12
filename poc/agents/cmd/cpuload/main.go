package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"expvar"
	"flag"
	"fmt"
	"log"
	"math"
	"math/big"
	"net/http"
	"net/http/pprof"
	"os"
	"os/signal"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

// ──────────────────────────────────────────────
//  Algorithm registry
// ──────────────────────────────────────────────

// LoadAlgo identifies the CPU burn algorithm.
type LoadAlgo string

const (
	AlgoPrimeSieve  LoadAlgo = "prime-sieve"
	AlgoMatrixMul   LoadAlgo = "matrix-mul"
	AlgoPiLeibniz   LoadAlgo = "pi-leibniz"
	AlgoFibonacci   LoadAlgo = "fibonacci"
	AlgoBusyLoop    LoadAlgo = "busy-loop"
	AlgoRandomBytes LoadAlgo = "random-bytes"
)

func allAlgos() []LoadAlgo {
	return []LoadAlgo{AlgoPrimeSieve, AlgoMatrixMul, AlgoPiLeibniz, AlgoFibonacci, AlgoBusyLoop, AlgoRandomBytes}
}

func isValidAlgo(s string) bool {
	for _, a := range allAlgos() {
		if string(a) == s {
			return true
		}
	}
	return false
}

// ──────────────────────────────────────────────
//  Load task
// ──────────────────────────────────────────────

type LoadTask struct {
	ID         string    `json:"id"`
	Algo       LoadAlgo  `json:"algo"`
	DurationMs int64     `json:"duration_ms"`
	Workers    int       `json:"workers"`
	Intensity  float64   `json:"intensity"` // multiplier for inner work per tick
	Status     string    `json:"status"`    // "running","completed","cancelled"
	Progress   float64   `json:"progress"`  // 0.0–1.0, updated live
	StartedAt  time.Time `json:"started_at"`
	EndedAt    *time.Time `json:"ended_at,omitempty"`
	Iterations int64     `json:"iterations"`

	cancel context.CancelFunc
	done   chan struct{}
	iter   atomic.Int64
	stop   atomic.Bool
}

func newLoadTask(id string, algo LoadAlgo, workers int, durationMs int64, intensity float64) *LoadTask {
	ctx, cancel := context.WithCancel(context.Background())
	t := &LoadTask{
		ID:         id,
		Algo:       algo,
		DurationMs: durationMs,
		Workers:    workers,
		Intensity:  intensity,
		Status:     "running",
		StartedAt:  time.Now().UTC(),
		cancel:     cancel,
		done:       make(chan struct{}),
	}
	go t.run(ctx)
	return t
}

func (t *LoadTask) run(ctx context.Context) {
	defer close(t.done)

	var wg sync.WaitGroup
	start := time.Now()
	deadline := start.Add(time.Duration(t.DurationMs) * time.Millisecond)

	for i := 0; i < t.Workers; i++ {
		wg.Add(1)
		go t.worker(ctx, &wg, deadline)
	}

	// progress updater
	ticker := time.NewTicker(250 * time.Millisecond)
	defer ticker.Stop()
loop:
	for {
		select {
		case <-ctx.Done():
			break loop
		case <-ticker.C:
			elapsed := time.Since(start)
			t.Progress = math.Min(1.0, float64(elapsed)/float64(time.Duration(t.DurationMs)*time.Millisecond))
			if elapsed >= time.Duration(t.DurationMs)*time.Millisecond {
				break loop
			}
		}
	}
	wg.Wait()

	now := time.Now().UTC()
	t.EndedAt = &now
	t.Progress = 1.0
	t.Iterations = t.iter.Load()

	if t.stop.Load() {
		t.Status = "cancelled"
	} else {
		t.Status = "completed"
	}
}

func (t *LoadTask) worker(ctx context.Context, wg *sync.WaitGroup, deadline time.Time) {
	defer wg.Done()

	// Precompute per-tick work based on intensity
	intensity := math.Max(t.Intensity, 0.001)

	for {
		if time.Now().After(deadline) || t.stop.Load() {
			return
		}
		select {
		case <-ctx.Done():
			return
		default:
		}

		burnCPU(t.Algo, intensity)
		t.iter.Add(1)
	}
}

// ──────────────────────────────────────────────
//  CPU burn algorithms
// ──────────────────────────────────────────────

func burnCPU(algo LoadAlgo, intensity float64) {
	switch algo {
	case AlgoPrimeSieve:
		sievePrimes(int(10000 + 5000*intensity))
	case AlgoMatrixMul:
		matrixMul(int(60 + 20*intensity))
	case AlgoPiLeibniz:
		piLeibniz(int(50000 + 50000*intensity))
	case AlgoFibonacci:
		fibonacci(35 + int(5*intensity))
	case AlgoBusyLoop:
		busyLoop(int(50000 + 50000*intensity))
	case AlgoRandomBytes:
		randomBytes(int(5000 + 5000*intensity))
	}
}

func sievePrimes(n int) {
	if n < 2 {
		return
	}
	composite := make([]bool, n+1)
	limit := int(math.Sqrt(float64(n)))
	for i := 2; i <= limit; i++ {
		if !composite[i] {
			for j := i * i; j <= n; j += i {
				composite[j] = true
			}
		}
	}
}
func matrixMul(n int) {
	a := make([][]float64, n)
	b := make([][]float64, n)
	for i := range a {
		a[i] = make([]float64, n)
		b[i] = make([]float64, n)
		for j := range a[i] {
			a[i][j] = float64(i*10 + j)
			b[i][j] = float64(j*10 + i)
		}
	}
	c := make([][]float64, n)
	for i := range c {
		c[i] = make([]float64, n)
		for k := 0; k < n; k++ {
			aik := a[i][k]
			for j := 0; j < n; j++ {
				c[i][j] += aik * b[k][j]
			}
		}
	}
	runtime.KeepAlive(c)
}
func piLeibniz(terms int) {
	pi := 0.0
	sign := 1.0
	for k := 0; k < terms; k++ {
		pi += sign / float64(2*k+1)
		sign = -sign
	}
	runtime.KeepAlive(pi)
}
func fibonacci(n int) int {
	if n <= 1 {
		return n
	}
	return fibonacci(n-1) + fibonacci(n-2)
}
func busyLoop(inner int) {
	sum := 0.0
	for i := 0; i < inner; i++ {
		sum += math.Sqrt(float64(i*i + i + 1))
	}
	runtime.KeepAlive(sum)
}
func randomBytes(n int) {
	buf := make([]byte, n)
	for i := 0; i < n; i++ {
		// intentional CPU burn: simulate expensive random generation
		v, _ := rand.Int(rand.Reader, big.NewInt(256))
		buf[i] = byte(v.Int64())
	}
	runtime.KeepAlive(buf)
}

// ──────────────────────────────────────────────
//  Load manager
// ──────────────────────────────────────────────

type LoadManager struct {
	mu           sync.RWMutex
	tasks        map[string]*LoadTask
	next         atomic.Int64
	maxLoads     int64
	activeCount  atomic.Int64
	totalStarted atomic.Int64
	totalCompleted atomic.Int64
}

func NewLoadManager(maxLoads int) *LoadManager {
	return &LoadManager{
		tasks:    make(map[string]*LoadTask),
		maxLoads: int64(maxLoads),
	}
}

func (lm *LoadManager) Start(algo LoadAlgo, workers int, durationMs int64, intensity float64) (*LoadTask, error) {
	// capacity check
	if lm.activeCount.Load() >= lm.maxLoads {
		return nil, fmt.Errorf("max concurrent loads (%d) reached", lm.maxLoads)
	}

	// generate unique ID
	id, _ := hex.DecodeString(fmt.Sprintf("%016x%08x",
		uint64(time.Now().UnixNano()),
		uint64(lm.next.Add(1)),
	))
	idStr := hex.EncodeToString(id)

	t := newLoadTask(idStr, algo, workers, durationMs, intensity)

	lm.mu.Lock()
	lm.tasks[idStr] = t
	lm.mu.Unlock()

	lm.activeCount.Add(1)
	lm.totalStarted.Add(1)

	// async cleanup on completion
	go func() {
		<-t.done
		lm.activeCount.Add(-1)
		lm.totalCompleted.Add(1)
	}()

	return t, nil
}

func (lm *LoadManager) Cancel(id string) bool {
	lm.mu.RLock()
	t, ok := lm.tasks[id]
	lm.mu.RUnlock()
	if !ok {
		return false
	}
	t.stop.Store(true)
	t.cancel()
	return true
}

func (lm *LoadManager) List() []LoadTask {
	lm.mu.RLock()
	defer lm.mu.RUnlock()
	out := make([]LoadTask, 0, len(lm.tasks))
	for _, t := range lm.tasks {
		out = append(out, snapshotTask(t))
	}
	return out
}

func (lm *LoadManager) Get(id string) *LoadTask {
	lm.mu.RLock()
	defer lm.mu.RUnlock()
	return lm.tasks[id]
}

func (lm *LoadManager) Purge() int {
	lm.mu.Lock()
	defer lm.mu.Unlock()
	var n int
	for id, t := range lm.tasks {
		if t.Status != "running" {
			delete(lm.tasks, id)
			n++
		}
	}
	return n
}

func (lm *LoadManager) Stats() map[string]interface{} {
	lm.mu.RLock()
	runningCount := 0
	for _, t := range lm.tasks {
		if t.Status == "running" {
			runningCount++
		}
	}
	lm.mu.RUnlock()

	return map[string]interface{}{
		"active_loads":    lm.activeCount.Load(),
		"running_tasks":   runningCount,
		"total_started":   lm.totalStarted.Load(),
		"total_completed": lm.totalCompleted.Load(),
		"max_loads":       lm.maxLoads,
	}
}

func snapshotTask(t *LoadTask) LoadTask {
	return LoadTask{
		ID:         t.ID,
		Algo:       t.Algo,
		DurationMs: t.DurationMs,
		Workers:    t.Workers,
		Intensity:  t.Intensity,
		Status:     t.Status,
		Progress:   t.Progress,
		StartedAt:  t.StartedAt,
		EndedAt:    t.EndedAt,
		Iterations: t.iter.Load(),
	}
}

// ──────────────────────────────────────────────
//  Config
// ──────────────────────────────────────────────

type config struct {
	Port     int
	MaxLoads int
	Pprof    bool
}

func loadConfig() config {
	cfg := config{
		Port:     8080,
		MaxLoads: 100,
		Pprof:    false,
	}

	flag.IntVar(&cfg.Port, "port", cfg.Port, "HTTP listen port (also PORT env)")
	flag.IntVar(&cfg.MaxLoads, "max-loads", cfg.MaxLoads, "max concurrent load tasks")
	flag.BoolVar(&cfg.Pprof, "pprof", cfg.Pprof, "enable pprof endpoints")
	flag.Parse()

	if p := os.Getenv("PORT"); p != "" {
		if v, err := strconv.Atoi(p); err == nil {
			cfg.Port = v
		}
	}
	if m := os.Getenv("MAX_LOADS"); m != "" {
		if v, err := strconv.Atoi(m); err == nil {
			cfg.MaxLoads = v
		}
	}
	if v := os.Getenv("PPROF"); v == "1" || strings.ToLower(v) == "true" {
		cfg.Pprof = true
	}

	if cfg.Port <= 0 || cfg.Port > 65535 {
		cfg.Port = 8080
	}
	if cfg.MaxLoads <= 0 {
		cfg.MaxLoads = 1
	}

	return cfg
}

// ──────────────────────────────────────────────
//  Middleware
// ──────────────────────────────────────────────

type responseWriter struct {
	http.ResponseWriter
	status   int
	written  int64
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.status = code
	rw.ResponseWriter.WriteHeader(code)
}

func (rw *responseWriter) Write(b []byte) (int, error) {
	n, err := rw.ResponseWriter.Write(b)
	rw.written += int64(n)
	return n, err
}

func requestID() string {
	b := make([]byte, 8)
	rand.Read(b) //nolint:errcheck
	return hex.EncodeToString(b)
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rid := r.Header.Get("X-Request-Id")
		if rid == "" {
			rid = requestID()
		}
		rw := &responseWriter{ResponseWriter: w, status: http.StatusOK}
		r.Header.Set("X-Request-Id", rid)
		w.Header().Set("X-Request-Id", rid)

		start := time.Now()
		next.ServeHTTP(rw, r)

		dur := time.Since(start)
		log.Printf("%s %s %s %d %d %s",
			r.Method, r.URL.Path, r.RemoteAddr, rw.status, rw.written, dur.Round(time.Microsecond))
	})
}

func recoveryMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				// 64KB stack trace
				buf := make([]byte, 65536)
				n := runtime.Stack(buf, false)
				log.Printf("PANIC: %v\n%s", rec, buf[:n])
				writeJSON(w, http.StatusInternalServerError, map[string]string{
					"error": "internal server error",
				})
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Request-Id")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// ──────────────────────────────────────────────
//  HTTP handlers
// ──────────────────────────────────────────────

var manager *LoadManager

// POST /load — start a load task
func handleStartLoad(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "POST required"})
		return
	}
	var req struct {
		Algo       string  `json:"algo"`
		DurationMs int64   `json:"duration_ms"`
		Workers    int     `json:"workers"`
		Intensity  float64 `json:"intensity"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON: " + err.Error()})
		return
	}

	algo := LoadAlgo(req.Algo)
	if algo == "" || !isValidAlgo(string(algo)) {
		algo = AlgoPrimeSieve
	}
	if req.DurationMs <= 0 {
		req.DurationMs = 5000
	}
	if req.Workers <= 0 {
		req.Workers = 1
	}
	if req.Intensity <= 0 {
		req.Intensity = 1.0
	}

	t, err := manager.Start(algo, req.Workers, req.DurationMs, req.Intensity)
	if err != nil {
		writeJSON(w, http.StatusTooManyRequests, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusAccepted, map[string]interface{}{
		"id":          t.ID,
		"algo":        t.Algo,
		"status":      t.Status,
		"duration_ms": req.DurationMs,
		"workers":     req.Workers,
		"intensity":   req.Intensity,
	})
}

// GET /loads — list all tasks
// POST /loads/{id}/cancel — cancel by id
func handleLoads(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		tasks := manager.List()
		writeJSON(w, http.StatusOK, map[string]interface{}{"loads": tasks})
	case http.MethodPost:
		// cancel via POST /loads/{id}/cancel
		path := strings.TrimPrefix(r.URL.Path, "/loads")
		path = strings.TrimSuffix(path, "/cancel") // leaves "/{id}"
		id := strings.TrimPrefix(path, "/")
		if id == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "id required"})
			return
		}
		if !manager.Cancel(id) {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "load not found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "cancelled", "id": id})
	default:
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "GET or POST required"})
	}
}

// GET /loads/{id} — get single task
// DELETE /loads/{id} — cancel task
// POST /loads/{id}/cancel — cancel (compat)
func handleLoadByID(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if id == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "id required"})
		return
	}

	switch r.Method {
	case http.MethodGet:
		t := manager.Get(id)
		if t == nil {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "load not found"})
			return
		}
		writeJSON(w, http.StatusOK, snapshotTask(t))

	case http.MethodDelete:
		if !manager.Cancel(id) {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "load not found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "cancelled", "id": id})

	case http.MethodPost:
		// /loads/{id}/cancel subpath routing
		if strings.HasSuffix(r.URL.Path, "/cancel") {
			if !manager.Cancel(id) {
				writeJSON(w, http.StatusNotFound, map[string]string{"error": "load not found"})
				return
			}
			writeJSON(w, http.StatusOK, map[string]string{"status": "cancelled", "id": id})
			return
		}
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "use DELETE or POST /loads/{id}/cancel"})

	default:
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "GET or DELETE required"})
	}
}

// GET /health
func handleHealth(w http.ResponseWriter, r *http.Request) {
	stats := manager.Stats()
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"status":       "ok",
		"timestamp":    time.Now().UTC().Format(time.RFC3339),
		"active_loads": stats["active_loads"],
		"max_loads":    stats["max_loads"],
	})
}

// GET /metrics
func handleMetrics(w http.ResponseWriter, r *http.Request) {
	stats := manager.Stats()
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"loads":            stats,
		"goroutines":       runtime.NumGoroutine(),
		"cpus":             runtime.NumCPU(),
		"memory_alloc_mb":  float64(m.Alloc) / (1024 * 1024),
		"memory_total_mb":  float64(m.TotalAlloc) / (1024 * 1024),
		"memory_sys_mb":    float64(m.Sys) / (1024 * 1024),
		"gc_cycles":        m.NumGC,
		"gc_pause_ns":      m.PauseTotalNs,
		"uptime_seconds":   expvar.Get("uptime"),
	})
}

// GET /algos — list available algorithms
func handleAlgos(w http.ResponseWriter, r *http.Request) {
	algos := allAlgos()
	descriptions := map[LoadAlgo]string{
		AlgoPrimeSieve:  "Sieve of Eratosthenes — composite marking",
		AlgoMatrixMul:   "N×N matrix multiplication (ikj loop order)",
		AlgoPiLeibniz:   "Pi approximation via Leibniz series",
		AlgoFibonacci:   "Naive recursive Fibonacci (n=35–40)",
		AlgoBusyLoop:    "sqrt + float arithmetic busy loop",
		AlgoRandomBytes: "Cryptographic random byte generation",
	}
	out := make([]map[string]interface{}, len(algos))
	for i, a := range algos {
		out[i] = map[string]interface{}{
			"name":        string(a),
			"description": descriptions[a],
		}
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{"algorithms": out})
}

// POST /purge — remove completed/cancelled tasks
func handlePurge(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "POST required"})
		return
	}
	n := manager.Purge()
	writeJSON(w, http.StatusOK, map[string]interface{}{"purged": n})
}

// ──────────────────────────────────────────────
//  Helpers
// ──────────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// ──────────────────────────────────────────────
//  Main
// ──────────────────────────────────────────────

func main() {
	cfg := loadConfig()
	manager = NewLoadManager(cfg.MaxLoads)

	// expvar — server uptime
	startTime := time.Now()
	uptimeVar := expvar.NewString("uptime")
	uptimeVar.Set("0")
	go func() {
		for {
			time.Sleep(1 * time.Second)
			uptimeVar.Set(
				strconv.FormatInt(int64(time.Since(startTime).Seconds()), 10))
		}
	}()

	mux := http.NewServeMux()

	// Core API
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/metrics", handleMetrics)
	mux.HandleFunc("/algos", handleAlgos)
	mux.HandleFunc("/load", handleStartLoad)
	mux.HandleFunc("/loads", handleLoads)
	mux.HandleFunc("/loads/{id}", handleLoadByID)
	mux.HandleFunc("/loads/{id}/cancel", handleLoadByID) // convenience
	mux.HandleFunc("/purge", handlePurge)

	// Debug expvar
	mux.HandleFunc("/debug/vars", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		fmt.Fprintf(w, "{\n")
		first := true
		expvar.Do(func(kv expvar.KeyValue) {
			if !first {
				fmt.Fprintf(w, ",\n")
			}
			first = false
			fmt.Fprintf(w, "%q: %s", kv.Key, kv.Value)
		})
		fmt.Fprintf(w, "\n}\n")
	})

	// Pprof — gated by config
	if cfg.Pprof {
		mux.HandleFunc("/debug/pprof/", pprof.Index)
		mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
		mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
		mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
		mux.HandleFunc("/debug/pprof/trace", pprof.Trace)
		log.Println("pprof endpoints enabled at /debug/pprof/*")
	}

	// Wrap with middleware (outer → inner: cors → recovery → logging → handler)
	handler := loggingMiddleware(recoveryMiddleware(corsMiddleware(mux)))

	srv := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Port),
		Handler:      handler,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  120 * time.Second,
		// MaxHeaderBytes: 1 << 16, // 64KB
	}

	// Graceful shutdown
	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP)
		<-sig
		log.Println("Shutting down...")
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		srv.Shutdown(ctx)
	}()

	log.Printf("CPU load simulator listening on :%d (max loads: %d)", cfg.Port, cfg.MaxLoads)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
	log.Println("Server stopped")
}