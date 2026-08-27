package agentruntime

import (
	"net/http"
	"strconv"
)

// ProbeHandler returns the kubelet/docker liveness+health HTTP surface (ADR-0022: the PID-1 sidecar
// serves /live + /health/{id}). It is read-only over the active-agent registry and safe to serve
// concurrently with Run on its own listener. Two routes:
//
//   - GET /live          — process-level liveness: 200 once the sidecar is up (always, while serving),
//     so the kubelet livenessProbe restarts a wedged container. (The HARD lifecycle is the
//     docker/k8s API; this probe is the in-pod liveness signal it reads.)
//   - GET /health/{id}   — per-agent readiness: 200 while the agent is registered + active, 503 once
//     it has drained/exited, so a readinessProbe stops routing to a draining pod.
//
// Returns a *http.ServeMux (concrete, accept-nothing/return-concrete) the app mounts on its listener.
func (r *Runtime) ProbeHandler() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /live", r.handleLive)
	mux.HandleFunc("GET /health/{id}", r.handleHealth)
	return mux
}

// handleLive answers the process-liveness probe: 200 while the sidecar serves. A request reaching the
// handler proves the listener + run loop's HTTP goroutine are alive, which is the liveness signal. The
// body reports the count of active agents so an operator/curl sees the pod's occupancy at a glance.
func (r *Runtime) handleLive(writer http.ResponseWriter, _ *http.Request) {
	writer.Header().Set("Content-Type", "text/plain; charset=utf-8")
	writer.WriteHeader(http.StatusOK)
	_, _ = writer.Write([]byte("live agents=" + strconv.Itoa(r.registry.count()) + "\n")) //nolint:errcheck // a probe-response write failure is a dead client socket; nothing to recover.
}

// handleHealth answers the per-agent readiness probe: 200 while the named agent is active in the
// registry, 503 once it has drained/exited (so a readinessProbe drains traffic from a stopping pod).
// An unknown id reads inactive → 503 (a probe for a never-started agent is not ready).
func (r *Runtime) handleHealth(writer http.ResponseWriter, request *http.Request) {
	id := AgentID(request.PathValue("id"))
	writer.Header().Set("Content-Type", "text/plain; charset=utf-8")
	if r.registry.isActive(id) {
		writer.WriteHeader(http.StatusOK)
		_, _ = writer.Write([]byte("ready\n")) //nolint:errcheck // probe-response write failure == dead client socket.
		return
	}
	writer.WriteHeader(http.StatusServiceUnavailable)
	_, _ = writer.Write([]byte("not-ready\n")) //nolint:errcheck // probe-response write failure == dead client socket.
}
