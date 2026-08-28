package healthcheck

import (
	"context"
	"encoding/json"
	"net/http"
	"time"
)

// probeTimeout bounds a single readiness probe so a wedged dependency cannot hang the kubelet's
// readiness check (the check itself must answer promptly even when a dependency is slow/down).
const probeTimeout = 2 * time.Second

// Probe is the readiness port: ONE dependency the gateway must reach to serve traffic (the Postgres
// pool, a secrets backend, an upstream). It is consumer-defined HERE — the shape of the need, not a
// mirror of any implementation (10 §9): the composition root adapts its concrete pool/client onto
// it. A Probe reports a typed error when the dependency is unreachable; Ready renders that into a
// 503 naming the failing dependency. ≤5 methods (interface-design rule).
type Probe interface {
	// Name is the dependency's stable, operator-facing label ("postgres", "vault") — the token that
	// appears in the 503 body when this probe fails. It is never a secret.
	Name() string
	// Check reports nil iff the dependency is reachable RIGHT NOW. The returned error is operator-safe
	// (it names the dependency, never a credential); Ready bounds the call with a short deadline.
	Check(ctx context.Context) error
}

// NamedProbe adapts a (name, check-func) pair into a Probe, so the composition root expresses a
// dependency reachability check as a closure (the same shape as http.HandlerFunc adapts a func into
// a Handler) without each dependency declaring its own named type. The name is the operator-facing
// label that appears in the 503 body; the func reports nil iff the dependency is reachable.
type NamedProbe struct {
	// Label is the dependency's stable, operator-facing name (e.g. "postgres"). Never a secret.
	Label string
	// CheckFunc reports nil iff the dependency is reachable under the deadline Ready imposes.
	CheckFunc func(ctx context.Context) error
}

// Name returns the dependency label.
func (p NamedProbe) Name() string { return p.Label }

// Check runs the adapted reachability func.
func (p NamedProbe) Check(ctx context.Context) error { return p.CheckFunc(ctx) }

// compile-time assertion: NamedProbe satisfies the Probe port.
var _ Probe = NamedProbe{}

// readyResponse is the readiness body. On success it is {"status":"ready"}; on failure it names the
// dependencies that are down so an operator reading the probe sees WHICH dependency wedged the pod.
type readyResponse struct {
	Status  string   `json:"status"`
	Unready []string `json:"unready,omitempty"`
}

// Ready returns the readiness probe handler over the supplied dependency probes. Readiness asks "can
// this process serve traffic RIGHT NOW" — it is the signal a kubernetes Service uses to add/remove
// the pod from the load-balancer rotation, so a not-ready pod stops receiving traffic WITHOUT being
// killed. It probes every dependency under a short deadline and returns 200 {"status":"ready"} when
// all are reachable, else 503 naming the failing ones. With NO probes (the probe-only/no-DB boot the
// composition root uses before persistence is wired) it answers 200 — there is nothing to be unready
// for, which is the correct readiness of a dependency-free surface.
func Ready(probes ...Probe) http.Handler {
	return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		ctx, cancel := context.WithTimeout(request.Context(), probeTimeout)
		defer cancel()

		var unready []string
		for _, probe := range probes {
			if err := probe.Check(ctx); err != nil {
				unready = append(unready, probe.Name())
			}
		}

		writer.Header().Set("Content-Type", "application/json")
		body := readyResponse{Status: "ready"}
		status := http.StatusOK
		if len(unready) > 0 {
			body = readyResponse{Status: "unready", Unready: unready}
			status = http.StatusServiceUnavailable
		}
		writer.WriteHeader(status)
		_ = json.NewEncoder(writer).Encode(body) //nolint:errcheck // a probe write failure is the kubelet's to observe.
	})
}
