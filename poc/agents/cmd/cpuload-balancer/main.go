package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"expvar"
	"flag"
	"fmt"
	"io"
	"log"
	"math"
	"math/big"
	"net/http"
	"net/http/httputil"
	"net/url"
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
//  Strategy
// ──────────────────────────────────────────────

type Strategy string

const (
	StrategyLeastCPU   Strategy = "least-cpu"
	StrategyRoundRobin Strategy = "round-robin"
	StrategyRandom     Strategy = "random"
	StrategyLeastConn  Strategy = "least-conn"
	StrategyWeightedRR Strategy = "weighted-round-robin"
)

func allStrategies() []Strategy {
	return []Strategy{StrategyLeastCPU, StrategyRoundRobin, StrategyRandom, StrategyLeastConn, StrategyWeightedRR}
}

func isValidStrategy(s string) bool {
	for _, st := range allStrategies() {
		if string(st) == s {
			return true
		}
	}
	return false
}

// ──────────────────────────────────────────────
//  Backend
// ──────────────────────────────────────────────

type BackendStatus string

const (
	StatusHealthy   BackendStatus = "healthy"
	StatusUnhealthy BackendStatus = "unhealthy"
	StatusChecking  BackendStatus = "checking"
)

type CPUMetrics struct {
	Load       float64 `json:"load"`        // 0..1 fraction of capacity used
	Goroutines int     `json:"goroutines"`
	CPUs       int     `json:"cpus"`
}

type Backend struct {
	ID              string        `json:"id"`
	URL             string        `json:"url"`
	Weight          int           `json:"weight"`
	Status          BackendStatus `json:"status"`
	CPUMetrics      CPUMetrics    `json:"cpu_metrics"`
	ActiveConns     int64         `json:"active_conns"`
	ConsecutiveFails int          `json:"consecutive_fails"`
	FailThreshold   int           `json:"fail_threshold"`
	CooldownPeriod  time.Duration `json:"cooldown_period"`
	LastChecked     time.Time     `json:"last_checked"`
	LastFailure     time.Time     `json:"last_failure"`
	CooldownUntil   time.Time     `json:"cooldown_until"`
	RequestsTotal   int64         `json:"requests_total"`
	RequestsFailed  int64         `json:"requests_failed"`
	LatencySum      time.Duration `json:"-"` // not exported
	LatencyAvg      time.Duration `json:"latency_avg"`
	CreatedAt       time.Time     `json:"created_at"`

	parsedURL *url.URL // cached parse
	mu        sync.RWMutex
}

// snapshot returns a thread-safe copy for JSON serialization.
func (b *Backend) snapshot() Backend {
	b.mu.RLock()
	defer b.mu.RUnlock()
	s := Backend{
		ID:              b.ID,
		URL:             b.URL,
		Weight:          b.Weight,
		Status:          b.Status,
		CPUMetrics:      b.CPUMetrics,
		ActiveConns:     b.ActiveConns,
		ConsecutiveFails: b.ConsecutiveFails,
		FailThreshold:   b.FailThreshold,
		CooldownPeriod:  b.CooldownPeriod,
		LastChecked:     b.LastChecked,
		LastFailure:     b.LastFailure,
		CooldownUntil:   b.CooldownUntil,
		RequestsTotal:   b.RequestsTotal,
		RequestsFailed:  b.RequestsFailed,
		LatencySum:      b.LatencySum,
		LatencyAvg:      b.LatencyAvg,
		CreatedAt:       b.CreatedAt,
	}
	if b.LatencySum > 0 && b.RequestsTotal > 0 {
		s.LatencyAvg = time.Duration(int64(b.LatencySum) / b.RequestsTotal)
	}
	return s
}

func computeUtilization(m CPUMetrics) float64 {
	if m.CPUs <= 0 {
		return 0
	}
	return math.Min(m.Load/float64(m.CPUs), 1.0)
}

// ──────────────────────────────────────────────
//  Backend registry
// ──────────────────────────────────────────────

type BackendRegistry struct {
	mu       sync.RWMutex
	backends map[string]*Backend
	ids      []string // insertion order for round-robin
}

func NewBackendRegistry() *BackendRegistry {
	return &BackendRegistry{
		backends: make(map[string]*Backend),
	}
}

func (r *BackendRegistry) Add(urlStr string, weight int, failThreshold int, cooldown time.Duration) (*Backend, error) {
	parsed, err := url.Parse(urlStr)
	if err != nil {
		return nil, fmt.Errorf("invalid URL: %w", err)
	}
	if parsed.Scheme == "" {
		return nil, fmt.Errorf("URL must have a scheme")
	}

	id := generateID()
	b := &Backend{
		ID:             id,
		URL:            urlStr,
		Weight:         weight,
		Status:         StatusHealthy,
		FailThreshold:  failThreshold,
		CooldownPeriod: cooldown,
		parsedURL:      parsed,
		CreatedAt:      time.Now(),
	}

	r.mu.Lock()
	r.backends[id] = b
	r.ids = append(r.ids, id)
	r.mu.Unlock()
	return b, nil
}

func (r *BackendRegistry) Get(id string) *Backend {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.backends[id]
}

func (r *BackendRegistry) Remove(id string) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, ok := r.backends[id]; !ok {
		return false
	}
	delete(r.backends, id)
	for i, v := range r.ids {
		if v == id {
			r.ids = append(r.ids[:i], r.ids[i+1:]...)
			break
		}
	}
	return true
}

func (r *BackendRegistry) List() []Backend {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := make([]Backend, 0, len(r.backends))
	for _, id := range r.ids {
		if b, ok := r.backends[id]; ok {
			out = append(out, b.snapshot())
		}
	}
	return out
}

func (r *BackendRegistry) HealthyBackends() []*Backend {
	r.mu.RLock()
	defer r.mu.RUnlock()
	var out []*Backend
	for _, b := range r.backends {
		b.mu.RLock()
		status := b.Status
		cooldown := b.CooldownUntil
		b.mu.RUnlock()
		if status == StatusHealthy || (status == StatusUnhealthy && time.Now().After(cooldown)) {
			out = append(out, b)
		}
	}
	return out
}

func (r *BackendRegistry) Len() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.backends)
}

// ──────────────────────────────────────────────
//  Health checker
// ──────────────────────────────────────────────

type HealthChecker struct {
	registry *BackendRegistry
	interval time.Duration
	timeout  time.Duration
	client   *http.Client
	stopCh   chan struct{}
}

func NewHealthChecker(registry *BackendRegistry, interval, timeout time.Duration) *HealthChecker {
	return &HealthChecker{
		registry: registry,
		interval: interval,
		timeout:  timeout,
		client:   &http.Client{Timeout: timeout},
		stopCh:   make(chan struct{}),
	}
}

func (hc *HealthChecker) Start() {
	go func() {
		ticker := time.NewTicker(hc.interval)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				hc.checkAll()
			case <-hc.stopCh:
				return
			}
		}
	}()
}

func (hc *HealthChecker) Stop() {
	close(hc.stopCh)
}

func (hc *HealthChecker) checkAll() {
	backends := hc.registry.List()
	for _, b := range backends {
		be := hc.registry.Get(b.ID)
		if be == nil {
			continue
		}
		hc.CheckBackend(be)
	}
}

func (hc *HealthChecker) CheckBackend(b *Backend) {
	b.mu.Lock()
	b.Status = StatusChecking
	b.mu.Unlock()

	healthURL := b.URL + "/health"
	start := time.Now()
	resp, err := hc.client.Get(healthURL)
	elapsed := time.Since(start)

	b.mu.Lock()
	defer b.mu.Unlock()

	b.LastChecked = time.Now()

	if err != nil || resp == nil || resp.StatusCode != http.StatusOK {
		if resp != nil && resp.Body != nil {
			resp.Body.Close()
		}
		b.ConsecutiveFails++
		b.LastFailure = time.Now()
		b.RequestsFailed++

		if b.ConsecutiveFails >= b.FailThreshold {
			b.Status = StatusUnhealthy
			b.CooldownUntil = time.Now().Add(b.CooldownPeriod)
			log.Printf("Backend %s (%s) marked unhealthy after %d consecutive failures",
				b.ID, b.URL, b.ConsecutiveFails)
		} else {
			log.Printf("Backend %s (%s) health check failed (%d/%d)",
				b.ID, b.URL, b.ConsecutiveFails, b.FailThreshold)
		}
		return
	}
	resp.Body.Close()

	// Reset on success
	b.ConsecutiveFails = 0
	b.Status = StatusHealthy
	b.CooldownUntil = time.Time{}
	b.LatencySum += elapsed
	b.LatencyAvg = time.Duration(int64(b.LatencySum) / b.RequestsTotal)
}

// ──────────────────────────────────────────────
//  Metrics collector
// ──────────────────────────────────────────────

type MetricsCollector struct {
	registry *BackendRegistry
	interval time.Duration
	timeout  time.Duration
	client   *http.Client
	stopCh   chan struct{}
}

func NewMetricsCollector(registry *BackendRegistry, interval, timeout time.Duration) *MetricsCollector {
	return &MetricsCollector{
		registry: registry,
		interval: interval,
		timeout:  timeout,
		client:   &http.Client{Timeout: timeout},
		stopCh:   make(chan struct{}),
	}
}

func (mc *MetricsCollector) Start() {
	go func() {
		ticker := time.NewTicker(mc.interval)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				mc.collectAll()
			case <-mc.stopCh:
				return
			}
		}

	}()
}

func (mc *MetricsCollector) Stop() {
	close(mc.stopCh)
}

func (mc *MetricsCollector) collectAll() {
	backends := mc.registry.List()
	for _, b := range backends {
		be := mc.registry.Get(b.ID)
		if be == nil {
			continue
		}
		mc.collectOne(be)
	}
}

type metricsResponse struct {
	ActiveLoads float64 `json:"active_loads"`
	MaxLoads    float64 `json:"max_loads"`
} // also has goroutines, cpus

type metricsPayload struct {
	Loads      map[string]interface{} `json:"loads"`
	Goroutines float64                `json:"goroutines"`
	CPUs       float64                `json:"cpus"`
}

func (mc *MetricsCollector) collectOne(b *Backend) {
	metricsURL := b.URL + "/metrics"
	resp, err := mc.client.Get(metricsURL)
	if err != nil {
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return
	}

	var payload metricsPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		return
	}

	b.mu.Lock()
	defer b.mu.Unlock()

	loads, ok := payload.Loads["active_loads"].(float64)
	if !ok {
		loads = 0
	}
	maxLoads, ok2 := payload.Loads["max_loads"].(float64)
	if !ok2 || maxLoads <= 0 {
		maxLoads = 1
	}

	loadFraction := loads / maxLoads

	b.CPUMetrics = CPUMetrics{
		Load:       loadFraction,
		Goroutines: int(payload.Goroutines),
		CPUs:       int(payload.CPUs),
	}
}

// ──────────────────────────────────────────────
//  Load balancer
// ──────────────────────────────────────────────

type LoadBalancer struct {
	registry         *BackendRegistry
	healthChecker    *HealthChecker
	metricsCollector *MetricsCollector

	strategyMu   sync.RWMutex
	strategy     Strategy
	rrIndex      atomic.Uint64

	requestsTotal   atomic.Int64
	requestsFailed  atomic.Int64
	strategyCounts  sync.Map // string → int64
}

func NewLoadBalancer(healthInterval, healthTimeout, metricsInterval, metricsTimeout time.Duration) *LoadBalancer {
	registry := NewBackendRegistry()
	lb := &LoadBalancer{
		registry:         registry,
		healthChecker:    NewHealthChecker(registry, healthInterval, healthTimeout),
		metricsCollector: NewMetricsCollector(registry, metricsInterval, metricsTimeout),
		strategy:         StrategyLeastCPU,
	}
	return lb
}

func (lb *LoadBalancer) Start() {
	lb.healthChecker.Start()
	lb.metricsCollector.Start()
}

func (lb *LoadBalancer) Stop() {
	lb.healthChecker.Stop()
	lb.metricsCollector.Stop()
}

func (lb *LoadBalancer) SetStrategy(s Strategy) {
	lb.strategyMu.Lock()
	defer lb.strategyMu.Unlock()
	lb.strategy = s
}

func (lb *LoadBalancer) GetStrategy() Strategy {
	lb.strategyMu.RLock()
	defer lb.strategyMu.RUnlock()
	return lb.strategy
}

func (lb *LoadBalancer) Next() *Backend {
	strategy := lb.GetStrategy()
	lb.incrementStrategyCount(string(strategy))

	switch strategy {
	case StrategyRoundRobin:
		return lb.nextRoundRobin()
	case StrategyRandom:
		return lb.nextRandom()
	case StrategyLeastConn:
		return lb.nextLeastConn()
	case StrategyWeightedRR:
		return lb.nextWeightedRR()
	default: // least-cpu
		return lb.nextLeastCPU()
	}
}

func (lb *LoadBalancer) nextLeastCPU() *Backend {
	backends := lb.registry.HealthyBackends()
	if len(backends) == 0 {
		return nil
	}

	// Pick backend with lowest CPU utilization
	best := backends[0]
	bestScore := computeScore(best, cpuless)
	for _, b := range backends[1:] {
		score := computeScore(b, cpuless)
		if score < bestScore {
			best = b
			bestScore = score
		}
	}
	return best
}

type scoreMode int

const (
	cpuless   scoreMode = iota // lower is better
	connless                   // lower is better
)

func computeScore(b *Backend, mode scoreMode) float64 {
	b.mu.RLock()
	defer b.mu.RUnlock()

	switch mode {
	case connless:
		return float64(b.ActiveConns)
	default:
		// CPU utilization score: weighted combination of load + goroutines + active connections
		util := computeUtilization(b.CPUMetrics)
		connFactor := float64(b.ActiveConns) / 10.0 // normalize to ~same scale
		return util + connFactor
	}
}

func (lb *LoadBalancer) nextRoundRobin() *Backend {
	backends := lb.registry.HealthyBackends()
	if len(backends) == 0 {
		return nil
	}
	idx := lb.rrIndex.Add(1) % uint64(len(backends))
	return backends[idx]
}

func (lb *LoadBalancer) nextRandom() *Backend {
	backends := lb.registry.HealthyBackends()
	if len(backends) == 0 {
		return nil
	}
	return backends[cryptoIntN(len(backends))]
}

func (lb *LoadBalancer) nextLeastConn() *Backend {
	backends := lb.registry.HealthyBackends()
	if len(backends) == 0 {
		return nil
	}
	best := backends[0]
	bestScore := computeScore(best, connless)
	for _, b := range backends[1:] {
		score := computeScore(b, connless)
		if score < bestScore {
			best = b
			bestScore = score
		}
	}
	return best
}

func (lb *LoadBalancer) nextWeightedRR() *Backend {
	backends := lb.registry.HealthyBackends()
	if len(backends) == 0 {
		return nil
	}

	// Build weighted list from snapshots
	type wb struct {
		b      *Backend
		weight int
	}
	var weighted []wb
	totalWeight := 0
	for _, b := range backends {
		b.mu.RLock()
		w := b.Weight
		b.mu.RUnlock()
		if w <= 0 {
			w = 1
		}
		weighted = append(weighted, wb{b, w})
		totalWeight += w
	}
	if totalWeight <= 0 {
		return backends[0]
	}

	// Deterministic selection based on rrIndex
	n := lb.rrIndex.Add(1) % uint64(totalWeight)
	remain := int64(n)
	for _, w := range weighted {
		remain -= int64(w.weight)
		if remain < 0 {
			return w.b
		}
	}
	return backends[len(backends)-1]
}

func (lb *LoadBalancer) incrementStrategyCount(s string) {
	v, _ := lb.strategyCounts.LoadOrStore(s, new(atomic.Int64))
	v.(*atomic.Int64).Add(1)
}

// Proxy handles incoming requests by selecting a backend and reverse-proxying.
func (lb *LoadBalancer) Proxy() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		backend := lb.Next()
		if backend == nil {
			lb.requestsFailed.Add(1)
			http.Error(w, `{"error":"no healthy backends available"}`, http.StatusServiceUnavailable)
			return
		}

		backend.mu.Lock()
		backend.ActiveConns++
		backend.RequestsTotal++
		urlCopy := *backend.parsedURL
		backend.mu.Unlock()

		lb.requestsTotal.Add(1)

		proxy := httputil.NewSingleHostReverseProxy(&urlCopy)
		proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
			backend.mu.Lock()
			backend.ActiveConns--
			backend.RequestsFailed++
			lb.requestsFailed.Add(1)
			backend.mu.Unlock()

			log.Printf("Proxy error for backend %s (%s): %v", backend.ID, backend.URL, err)
			http.Error(w, `{"error":"upstream error"}`, http.StatusBadGateway)
		}

		// Custom director to set backend headers
		origDirector := proxy.Director
		proxy.Director = func(req *http.Request) {
			origDirector(req)
			req.Header.Set("X-Backend-Id", backend.ID)
			req.Header.Set("X-Backend-Url", backend.URL)
			if clientIP := req.Header.Get("X-Forwarded-For"); clientIP == "" {
				req.Header.Set("X-Forwarded-For", r.RemoteAddr)
			}
		}

		start := time.Now()
		proxy.ServeHTTP(w, r)
		elapsed := time.Since(start)

		backend.mu.Lock()
		backend.ActiveConns--
		backend.LatencySum += elapsed
		backend.mu.Unlock()
	}
}

// ──────────────────────────────────────────────
//  Config
// ──────────────────────────────────────────────

type config struct {
	Port              int
	StrategyRaw       string
	HealthInterval    time.Duration
	HealthTimeout     time.Duration
	MetricsInterval   time.Duration
	MetricsTimeout    time.Duration
	FailThreshold     int
	CooldownPeriod    time.Duration
	DefaultWeight     int
	Pprof             bool
}

func loadConfig(args []string) config {
	cfg := config{
		Port:            9090,
		StrategyRaw:     "least-cpu",
		HealthInterval:  10 * time.Second,
		HealthTimeout:   5 * time.Second,
		MetricsInterval: 5 * time.Second,
		MetricsTimeout:  3 * time.Second,
		FailThreshold:   3,
		CooldownPeriod:  30 * time.Second,
		DefaultWeight:   1,
		Pprof:           false,
	}

	fs := flag.NewFlagSet("cpuload-balancer", flag.ContinueOnError)
	fs.IntVar(&cfg.Port, "port", cfg.Port, "HTTP listen port (also PORT env)")
	fs.StringVar(&cfg.StrategyRaw, "strategy", cfg.StrategyRaw, "balancing strategy: least-cpu, round-robin, random, least-conn, weighted-round-robin")
	fs.DurationVar(&cfg.HealthInterval, "health-interval", cfg.HealthInterval, "health check interval")
	fs.DurationVar(&cfg.HealthTimeout, "health-timeout", cfg.HealthTimeout, "health check timeout")
	fs.DurationVar(&cfg.MetricsInterval, "metrics-interval", cfg.MetricsInterval, "metrics collection interval")
	fs.DurationVar(&cfg.MetricsTimeout, "metrics-timeout", cfg.MetricsTimeout, "metrics collection timeout")
	fs.IntVar(&cfg.FailThreshold, "fail-threshold", cfg.FailThreshold, "consecutive failures before marking backend unhealthy")
	fs.DurationVar(&cfg.CooldownPeriod, "cooldown", cfg.CooldownPeriod, "cooldown period before retrying unhealthy backends")
	fs.IntVar(&cfg.DefaultWeight, "default-weight", cfg.DefaultWeight, "default weight for backends")
	fs.BoolVar(&cfg.Pprof, "pprof", cfg.Pprof, "enable pprof endpoints")
	if args != nil {
		fs.Parse(args) //nolint:errcheck
	}

	if p := os.Getenv("PORT"); p != "" {
		if v, err := strconv.Atoi(p); err == nil {
			cfg.Port = v
		}
	}
	if s := os.Getenv("STRATEGY"); s != "" {
		cfg.StrategyRaw = s
	}
	if d := os.Getenv("HEALTH_INTERVAL"); d != "" {
		if v, err := time.ParseDuration(d); err == nil {
			cfg.HealthInterval = v
		}
	}
	if d := os.Getenv("HEALTH_TIMEOUT"); d != "" {
		if v, err := time.ParseDuration(d); err == nil {
			cfg.HealthTimeout = v
		}
	}
	if d := os.Getenv("METRICS_INTERVAL"); d != "" {
		if v, err := time.ParseDuration(d); err == nil {
			cfg.MetricsInterval = v
		}
	}
	if d := os.Getenv("METRICS_TIMEOUT"); d != "" {
		if v, err := time.ParseDuration(d); err == nil {
			cfg.MetricsTimeout = v
		}
	}
	if d := os.Getenv("COOLDOWN"); d != "" {
		if v, err := time.ParseDuration(d); err == nil {
			cfg.CooldownPeriod = v
		}
	}
	if v := os.Getenv("FAIL_THRESHOLD"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.FailThreshold = n
		}
	}
	if v := os.Getenv("DEFAULT_WEIGHT"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.DefaultWeight = n
		}
	}
	if v := os.Getenv("PPROF"); v == "1" || strings.ToLower(v) == "true" {
		cfg.Pprof = true
	}

	// Validate strategy
	if !isValidStrategy(cfg.StrategyRaw) {
		log.Printf("Unknown strategy %q, defaulting to least-cpu", cfg.StrategyRaw)
		cfg.StrategyRaw = "least-cpu"
	}

	// Clamp values
	if cfg.HealthInterval < time.Second {
		cfg.HealthInterval = time.Second
	}
	if cfg.MetricsInterval < time.Second {
		cfg.MetricsInterval = time.Second
	}
	if cfg.FailThreshold <= 0 {
		cfg.FailThreshold = 1
	}
	if cfg.CooldownPeriod < 0 {
		cfg.CooldownPeriod = 0
	}
	if cfg.DefaultWeight <= 0 {
		cfg.DefaultWeight = 1
	}

	return cfg
}

// ──────────────────────────────────────────────
//  Middleware
// ──────────────────────────────────────────────

type responseWriter struct {
	http.ResponseWriter
	status  int
	written int64
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

func generateID() string {
	b := make([]byte, 8)
	rand.Read(b) //nolint:errcheck
	return hex.EncodeToString(b)
}

func requestID() string {
	b := make([]byte, 6)
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
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Request-Id, X-Backend-Id")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// cryptoIntN returns a uniform random int in [0, n) using crypto/rand.
func cryptoIntN(n int) int {
	if n <= 0 {
		return 0
	}
	bigN := big.NewInt(int64(n))
	v, err := rand.Int(rand.Reader, bigN)
	if err != nil {
		return 0
	}
	return int(v.Int64())
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// ──────────────────────────────────────────────
//  HTTP handlers
// ──────────────────────────────────────────────

var lb *LoadBalancer
var cfg config

// GET /health
func handleHealth(w http.ResponseWriter, r *http.Request) {
	backends := lb.registry.List()
	healthy := 0
	unhealthy := 0
	total := 0
	for _, b := range backends {
		total++
		if b.Status == StatusHealthy {
			healthy++
		} else {
			unhealthy++
		}
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"status":          "ok",
		"timestamp":       time.Now().UTC().Format(time.RFC3339),
		"strategy":        string(lb.GetStrategy()),
		"backends_total":  total,
		"backends_healthy": healthy,
		"backends_unhealthy": unhealthy,
		"uptime_seconds":  expvar.Get("uptime"),
	})
}

// GET /metrics
func handleMetrics(w http.ResponseWriter, r *http.Request) {
	backends := lb.registry.List()
	backendMetrics := make([]map[string]interface{}, 0, len(backends))
	for _, b := range backends {
		backendMetrics = append(backendMetrics, map[string]interface{}{
			"id":         b.ID,
			"url":        b.URL,
			"status":     string(b.Status),
			"cpu_load":   b.CPUMetrics.Load,
			"goroutines": b.CPUMetrics.Goroutines,
			"cpus":       b.CPUMetrics.CPUs,
			"active_conns": b.ActiveConns,
			"requests_total": b.RequestsTotal,
			"requests_failed": b.RequestsFailed,
			"latency_avg_ns": b.LatencyAvg.Nanoseconds(),
		})
	}

	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"backends":         backendMetrics,
		"requests_total":   lb.requestsTotal.Load(),
		"requests_failed":  lb.requestsFailed.Load(),
		"goroutines":       runtime.NumGoroutine(),
		"cpus":             runtime.NumCPU(),
		"strategy":         string(lb.GetStrategy()),
		"memory_alloc_mb":  float64(m.Alloc) / (1024 * 1024),
		"memory_total_mb":  float64(m.TotalAlloc) / (1024 * 1024),
		"memory_sys_mb":    float64(m.Sys) / (1024 * 1024),
		"gc_cycles":        m.NumGC,
		"gc_pause_ns":      m.PauseTotalNs,
		"uptime_seconds":   expvar.Get("uptime"),
	})
}

// POST /backends — register a backend
// GET /backends — list backends
func handleBackends(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		backends := lb.registry.List()
		writeJSON(w, http.StatusOK, map[string]interface{}{"backends": backends})

	case http.MethodPost:
		var req struct {
			URL           string   `json:"url"`
			Weight        *int     `json:"weight"`
			FailThreshold *int     `json:"fail_threshold"`
			CooldownMs    *int64   `json:"cooldown_ms"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON: " + err.Error()})
			return
		}
		if req.URL == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "url required"})
			return
		}

		weight := cfg.DefaultWeight
		if req.Weight != nil {
			weight = *req.Weight
		}
		failThreshold := cfg.FailThreshold
		if req.FailThreshold != nil {
			failThreshold = *req.FailThreshold
		}
		cooldown := cfg.CooldownPeriod
		if req.CooldownMs != nil {
			cooldown = time.Duration(*req.CooldownMs) * time.Millisecond
		}

		backend, err := lb.registry.Add(req.URL, weight, failThreshold, cooldown)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusCreated, backend.snapshot())

	default:
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "GET or POST required"})
	}
}

// GET /backends/{id}
// DELETE /backends/{id}
func handleBackendByID(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	if id == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "id required"})
		return
	}

	switch r.Method {
	case http.MethodGet:
		b := lb.registry.Get(id)
		if b == nil {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "backend not found"})
			return
		}
		writeJSON(w, http.StatusOK, b.snapshot())

	case http.MethodDelete:
		if !lb.registry.Remove(id) {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "backend not found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "removed", "id": id})

	default:
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "GET or DELETE required"})
	}
}

// POST /backends/{id}/check — force health check
func handleBackendCheck(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "POST required"})
		return
	}
	id := r.PathValue("id")
	if id == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "id required"})
		return
	}
	b := lb.registry.Get(id)
	if b == nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "backend not found"})
		return
	}
	lb.healthChecker.CheckBackend(b)
	writeJSON(w, http.StatusOK, b.snapshot())
}

// GET /strategy — get current strategy
// PUT /strategy — set strategy
func handleStrategy(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		writeJSON(w, http.StatusOK, map[string]interface{}{
			"strategy": string(lb.GetStrategy()),
		})

	case http.MethodPut:
		var req struct {
			Strategy string `json:"strategy"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON: " + err.Error()})
			return
		}
		if !isValidStrategy(req.Strategy) {
			writeJSON(w, http.StatusBadRequest, map[string]interface{}{
				"error":    fmt.Sprintf("invalid strategy %q", req.Strategy),
				"allowed":  allStrategies(),
			})
			return
		}
		lb.SetStrategy(Strategy(req.Strategy))
		writeJSON(w, http.StatusOK, map[string]interface{}{
			"strategy": req.Strategy,
		})

	default:
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "GET or PUT required"})
	}
}

// GET /strategies — list available strategies
func handleStrategies(w http.ResponseWriter, r *http.Request) {
	strategies := allStrategies()
	descriptions := map[Strategy]string{
		StrategyLeastCPU:   "Route to backend with lowest CPU utilization",
		StrategyRoundRobin: "Distribute evenly in rotation",
		StrategyRandom:     "Pick a backend at random",
		StrategyLeastConn:  "Route to backend with fewest active connections",
		StrategyWeightedRR: "Weighted round-robin based on backend weights",
	}
	out := make([]map[string]interface{}, len(strategies))
	for i, s := range strategies {
		out[i] = map[string]interface{}{
			"name":        string(s),
			"description": descriptions[s],
		}
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{"strategies": out})
}

// GET /stats — balancer statistics
func handleStats(w http.ResponseWriter, r *http.Request) {
	backends := lb.registry.List()
	byBackend := make([]map[string]interface{}, 0, len(backends))
	totalConns := int64(0)
	for _, b := range backends {
		totalConns += b.ActiveConns
		byBackend = append(byBackend, map[string]interface{}{
			"id":              b.ID,
			"url":             b.URL,
			"status":          string(b.Status),
			"active_conns":    b.ActiveConns,
			"requests_total":  b.RequestsTotal,
			"requests_failed": b.RequestsFailed,
			"cpu_utilization": computeUtilization(b.CPUMetrics),
		})
	}

	// Dump strategy counts
	strategyCounts := make(map[string]int64)
	lb.strategyCounts.Range(func(key, value interface{}) bool {
		strategyCounts[key.(string)] = value.(*atomic.Int64).Load()
		return true
	})

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"backends":        byBackend,
		"strategy":        string(lb.GetStrategy()),
		"strategy_counts": strategyCounts,
		"requests_total":  lb.requestsTotal.Load(),
		"requests_failed": lb.requestsFailed.Load(),
		"total_conns":     totalConns,
	})
}

// ──────────────────────────────────────────────
//  Main
// ──────────────────────────────────────────────

func main() {
	cfg = loadConfig(os.Args[1:])

	lb = NewLoadBalancer(cfg.HealthInterval, cfg.HealthTimeout, cfg.MetricsInterval, cfg.MetricsTimeout)
	lb.SetStrategy(Strategy(cfg.StrategyRaw))
	lb.Start()

	// expvar — server uptime
	startTime := time.Now()
	uptimeVar := expvar.NewString("uptime")
	uptimeVar.Set("0")
	go func() {
		for {
			time.Sleep(1 * time.Second)
			uptimeVar.Set(strconv.FormatInt(int64(time.Since(startTime).Seconds()), 10))
		}
	}()

	mux := http.NewServeMux()

	// Core API
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/metrics", handleMetrics)
	mux.HandleFunc("/backends", handleBackends)
	mux.HandleFunc("/backends/{id}", handleBackendByID)
	mux.HandleFunc("/backends/{id}/check", handleBackendCheck)
	mux.HandleFunc("/strategy", handleStrategy)
	mux.HandleFunc("/strategies", handleStrategies)
	mux.HandleFunc("/stats", handleStats)

	// Proxy endpoint — catch-all to forward to backends
	mux.HandleFunc("/proxy/", lb.Proxy())
	mux.HandleFunc("/proxy", lb.Proxy())

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
		mux.HandleFunc("/debug/pprof/", http.DefaultServeMux.ServeHTTP)
		mux.HandleFunc("/debug/pprof/cmdline", http.DefaultServeMux.ServeHTTP)
		mux.HandleFunc("/debug/pprof/profile", http.DefaultServeMux.ServeHTTP)
		mux.HandleFunc("/debug/pprof/symbol", http.DefaultServeMux.ServeHTTP)
		mux.HandleFunc("/debug/pprof/trace", http.DefaultServeMux.ServeHTTP)
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
	}

	// Graceful shutdown
	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP)
		<-sig
		log.Println("Shutting down...")
		lb.Stop()
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		srv.Shutdown(ctx)
	}()

	log.Printf("CPU load balancer listening on :%d (strategy: %s, health: %s, metrics: %s)",
		cfg.Port, cfg.StrategyRaw, cfg.HealthInterval, cfg.MetricsInterval)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
	log.Println("Server stopped")
}