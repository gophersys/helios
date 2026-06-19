// Package healthcheck holds the gateway's kubelet probes: liveness (the process is up) and readiness
// (the process can serve traffic). They are PUBLIC routes — the kubelet probes pre-identity, so they
// are mounted OUTSIDE the edenhttp authentication Middleware. They return a tiny, uniform JSON body
// so a `curl /healthz/live` is human-legible and the compose/kubernetes probe parses a stable shape.
package healthcheck

import (
	"net/http"
)

// liveBody is the static liveness payload. Liveness asks only "is the process running and the event
// loop responsive" — it does NOT check dependencies (that is readiness), so a transient dependency
// outage never causes the kubelet to KILL a healthy process.
const liveBody = `{"status":"alive"}`

// Live returns the liveness probe handler. It always answers 200 while the process can accept a
// connection and run a handler — the kubelet restarts the pod only if this stops responding.
func Live() http.Handler {
	return http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) {
		writer.Header().Set("Content-Type", "application/json")
		writer.WriteHeader(http.StatusOK)
		_, _ = writer.Write([]byte(liveBody)) //nolint:errcheck // a probe write failure is the kubelet's to observe.
	})
}
