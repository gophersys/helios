package middleware

import (
	"encoding/json"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
)

// RateLimitConfig is the immutable rate-limit policy (the configuration pattern). A zero or negative
// Limit disables limiting (RateLimit returns a pass-through), so a generated app opts in by setting a
// budget rather than the middleware imposing one by surprise.
type RateLimitConfig struct {
	// Limit is the maximum number of requests permitted per client within Window. ≤0 → unlimited.
	Limit int
	// Window is the rolling interval Limit is measured over. ≤0 → one minute.
	Window time.Duration
}

// defaultWindow is the rolling interval when RateLimitConfig.Window is unset.
const defaultWindow = time.Minute

// rateLimitBody is the 429 payload, a uniform edenhttp error Envelope so a rate-limited caller reads
// the SAME error shape as any other gateway failure (one wire contract). KindExhausted → 429.
var rateLimitBody = func() []byte {
	body, _ := json.Marshal(edenhttp.NewErrorEnvelope(errors.KindExhausted, "rate limit exceeded")) //nolint:errcheck // a fixed, marshalable value.
	return body
}()

// RateLimit returns a middleware that enforces a per-client sliding-window request budget using only
// net/http + the standard library (no external limiter dependency). It buckets by client IP and
// admits a request iff fewer than Limit requests from that client fall within the trailing Window;
// otherwise it answers 429 with the uniform error Envelope and does NOT call next. A non-positive
// Limit returns a pass-through, so the policy is opt-in.
func RateLimit(configuration RateLimitConfig) func(next http.Handler) http.Handler {
	if configuration.Limit <= 0 {
		return func(next http.Handler) http.Handler { return next }
	}
	window := configuration.Window
	if window <= 0 {
		window = defaultWindow
	}
	limiter := newSlidingWindow(configuration.Limit, window)
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
			if !limiter.admit(clientKey(request), time.Now()) {
				writer.Header().Set("Content-Type", "application/json")
				writer.WriteHeader(http.StatusTooManyRequests)
				_, _ = writer.Write(rateLimitBody) //nolint:errcheck // a rejected-client write failure is the client's to observe.
				return
			}
			next.ServeHTTP(writer, request)
		})
	}
}

// slidingWindow is a per-client sliding-window counter: for each client key it keeps the timestamps
// of the requests still inside the trailing window and admits while their count is under the limit.
// It is concurrency-safe (one mutex guards the map + the per-client slices) and self-pruning (each
// admit drops timestamps that have aged out, so a quiet client's slice shrinks to empty).
type slidingWindow struct {
	limit  int
	window time.Duration

	mutex sync.Mutex
	hits  map[string][]time.Time
}

// newSlidingWindow constructs a sliding-window limiter for limit requests per window.
func newSlidingWindow(limit int, window time.Duration) *slidingWindow {
	return &slidingWindow{limit: limit, window: window, hits: make(map[string][]time.Time)}
}

// admit records a request from key at now and reports whether it is within budget. It prunes the
// client's timestamps older than the trailing window first, so the decision is over a true sliding
// window (not a fixed bucket that resets on a boundary). A rejected request is NOT recorded, so a
// client hammering the limit does not push its own window forward indefinitely.
func (w *slidingWindow) admit(key string, now time.Time) bool {
	cutoff := now.Add(-w.window)

	w.mutex.Lock()
	defer w.mutex.Unlock()

	recent := w.hits[key][:0]
	for _, stamp := range w.hits[key] {
		if stamp.After(cutoff) {
			recent = append(recent, stamp)
		}
	}
	if len(recent) >= w.limit {
		w.hits[key] = recent
		return false
	}
	w.hits[key] = append(recent, now)
	return true
}

// clientKey identifies the rate-limit bucket for a request: the client IP (the connection's remote
// address, host part only, so multiple ports from one host share a budget). A parse failure falls
// back to the raw RemoteAddr — a stable key is enough for bucketing.
func clientKey(request *http.Request) string {
	host, _, err := net.SplitHostPort(request.RemoteAddr)
	if err != nil {
		return request.RemoteAddr
	}
	return host
}
