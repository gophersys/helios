package stateless_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/natssse"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/agentgateway/internal/stateless"
)

// stubJetStream is a non-nil nats.JetStreamContext for the New validation + control-pipeline unit
// tests: New only checks the handle for nil (it is pure), and the unit suite never hits the events
// route, so an embedded nil interface satisfies the type without implementing any method. A test that
// actually streams uses a REAL JetStream (the integration arm), never this.
type stubJetStream struct{ nats.JetStreamContext }

//nolint:gosec // a fixed TEST HMAC secret, not a real credential.
const unitSecret = "stateless-unit-signing-key"

// unitClock is a fixed clock for the unit suite.
type unitClock struct{}

func (unitClock) Now() time.Time { return time.Date(2026, time.June, 14, 12, 0, 0, 0, time.UTC) }

// fakeControl records the published control messages so the control-pipeline unit tests assert the
// verb/text/By without a real bus.
type fakeControl struct {
	mu       sync.Mutex
	messages []agentruntime.ControlMessage
	fail     error
}

func (f *fakeControl) PublishControl(_ context.Context, message agentruntime.ControlMessage) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.fail != nil {
		return f.fail
	}
	f.messages = append(f.messages, message)
	return nil
}

func (f *fakeControl) last() (agentruntime.ControlMessage, bool) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if len(f.messages) == 0 {
		return agentruntime.ControlMessage{}, false
	}
	return f.messages[len(f.messages)-1], true
}

// newUnitGateway builds a stateless.Gateway with a real edenhttp spine + a fake control publisher and
// a (non-streaming) bridge. The bridge is constructed over a nil-checked fake that New only validates
// for nil — the unit suite never hits the events route (that is the integration arm's REAL-NATS job).
func newUnitGateway(t *testing.T, control stateless.ControlPublisher) (*stateless.Gateway, *edenhttp.HMACVerifier) {
	t.Helper()
	verifier, err := edenhttp.NewHMACVerifier(unitSecret)
	if err != nil {
		t.Fatalf("verifier: %v", err)
	}
	spine, err := edenhttp.New(edenhttp.Config{}, edenhttp.Deps{Verifier: verifier, Clock: unitClock{}})
	if err != nil {
		t.Fatalf("spine: %v", err)
	}
	// A bridge over a non-nil (but unused) JetStream stand-in: the unit suite never calls the events
	// route, so the bridge is only validated for nil at New.
	bridge, err := natssse.New(natssse.Config{}, natssse.Deps{JetStream: stubJetStream{}, Clock: unitClock{}})
	if err != nil {
		t.Fatalf("bridge: %v", err)
	}
	gateway, err := stateless.New(
		stateless.Config{},
		stateless.Deps{Spine: spine, Bridge: bridge, Control: control},
	)
	if err != nil {
		t.Fatalf("gateway: %v", err)
	}
	return gateway, verifier
}

func mintUnit(t *testing.T, verifier *edenhttp.HMACVerifier, grantStrings ...string) string {
	t.Helper()
	grants := make([]edenhttp.Grant, 0, len(grantStrings))
	for _, raw := range grantStrings {
		grant, err := edenhttp.ParseGrant(raw)
		if err != nil {
			t.Fatalf("parse grant: %v", err)
		}
		grants = append(grants, grant)
	}
	token, err := verifier.Sign("user-unit", grants, unitClock{}.Now().Add(time.Hour))
	if err != nil {
		t.Fatalf("sign: %v", err)
	}
	return token
}

// ── New validation ────────────────────────────────────────────────────────────.

func TestNew_RequiresSpine(t *testing.T) {
	t.Parallel()
	_, err := stateless.New(stateless.Config{}, stateless.Deps{Bridge: &natssse.Bridge{}, Control: &fakeControl{}})
	requireKind(t, err, errors.KindInvalid)
}

func TestNew_RequiresBridge(t *testing.T) {
	t.Parallel()
	verifier, _ := edenhttp.NewHMACVerifier(unitSecret)                                                //nolint:errcheck // fixed non-empty secret.
	spine, _ := edenhttp.New(edenhttp.Config{}, edenhttp.Deps{Verifier: verifier, Clock: unitClock{}}) //nolint:errcheck // valid deps.
	_, err := stateless.New(stateless.Config{}, stateless.Deps{Spine: spine, Control: &fakeControl{}})
	requireKind(t, err, errors.KindInvalid)
}

func TestNew_RequiresControl(t *testing.T) {
	t.Parallel()
	verifier, _ := edenhttp.NewHMACVerifier(unitSecret)                                                      //nolint:errcheck // fixed non-empty secret.
	spine, _ := edenhttp.New(edenhttp.Config{}, edenhttp.Deps{Verifier: verifier, Clock: unitClock{}})       //nolint:errcheck // valid deps.
	bridge, _ := natssse.New(natssse.Config{}, natssse.Deps{JetStream: stubJetStream{}, Clock: unitClock{}}) //nolint:errcheck // valid deps.
	_, err := stateless.New(stateless.Config{}, stateless.Deps{Spine: spine, Bridge: bridge})
	requireKind(t, err, errors.KindInvalid)
}

// ── control pipeline + auth (no real bus) ─────────────────────────────────────.

func TestControl_PublishesVerbAndAuditBy(t *testing.T) {
	t.Parallel()
	control := &fakeControl{}
	gateway, verifier := newUnitGateway(t, control)

	recorder := post(t, gateway, "/sessions/agent-7/control", `{"verb":"steer","text":"hint"}`, mintUnit(t, verifier, "sessions:control"))
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200; body=%s", recorder.Code, recorder.Body.String())
	}
	message, ok := control.last()
	if !ok {
		t.Fatal("no control message published")
	}
	if message.AgentID != "agent-7" || message.Verb != agentruntime.VerbSteer || message.Text != "hint" {
		t.Errorf("message = %+v, want {agent-7 steer hint}", message)
	}
	if message.By != "user-unit" {
		t.Errorf("audit By = %q, want user-unit (the authenticated subject)", message.By)
	}
}

func TestControl_UnknownVerbIs400(t *testing.T) {
	t.Parallel()
	gateway, verifier := newUnitGateway(t, &fakeControl{})
	recorder := post(t, gateway, "/sessions/agent-7/control", `{"verb":"explode"}`, mintUnit(t, verifier, "sessions:control"))
	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", recorder.Code)
	}
}

func TestControl_UnderGrantedIs403(t *testing.T) {
	t.Parallel()
	control := &fakeControl{}
	gateway, verifier := newUnitGateway(t, control)
	recorder := post(t, gateway, "/sessions/agent-7/control", `{"verb":"abort"}`, mintUnit(t, verifier, "sessions:read"))
	if recorder.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want 403", recorder.Code)
	}
	if _, ok := control.last(); ok {
		t.Error("an under-granted control was published (authorize did not deny it)")
	}
}

func TestControl_UnauthenticatedIs401(t *testing.T) {
	t.Parallel()
	gateway, _ := newUnitGateway(t, &fakeControl{})
	recorder := post(t, gateway, "/sessions/agent-7/control", `{"verb":"abort"}`, "")
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", recorder.Code)
	}
}

func TestVerbRoute_AbortNoBody(t *testing.T) {
	t.Parallel()
	control := &fakeControl{}
	gateway, verifier := newUnitGateway(t, control)
	recorder := post(t, gateway, "/sessions/agent-7/abort", "", mintUnit(t, verifier, "sessions:*"))
	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200; body=%s", recorder.Code, recorder.Body.String())
	}
	message, ok := control.last()
	if !ok || message.Verb != agentruntime.VerbAbort {
		t.Errorf("abort verb route did not publish an abort: %+v ok=%v", message, ok)
	}
}

func TestControl_PublishFaultMapsToStatus(t *testing.T) {
	t.Parallel()
	control := &fakeControl{fail: errors.New(errors.KindUnavailable, "bus down")}
	gateway, verifier := newUnitGateway(t, control)
	recorder := post(t, gateway, "/sessions/agent-7/control", `{"verb":"prompt","text":"x"}`, mintUnit(t, verifier, "sessions:control"))
	if recorder.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want 503 (the publish fault Kind)", recorder.Code)
	}
}

func TestHealth_NoAuth(t *testing.T) {
	t.Parallel()
	gateway, _ := newUnitGateway(t, &fakeControl{})
	request := httptest.NewRequest(http.MethodGet, "/healthz", http.NoBody)
	recorder := httptest.NewRecorder()
	gateway.Handler().ServeHTTP(recorder, request)
	if recorder.Code != http.StatusOK {
		t.Fatalf("healthz status = %d, want 200", recorder.Code)
	}
	var envelope edenhttp.Envelope
	if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
		t.Fatalf("decode: %v", err)
	}
}

// ── helpers ───────────────────────────────────────────────────────────────────.

func post(t *testing.T, gateway *stateless.Gateway, path, body, token string) *httptest.ResponseRecorder {
	t.Helper()
	reader := strings.NewReader(body)
	request := httptest.NewRequest(http.MethodPost, path, reader)
	if token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}
	if body != "" {
		request.Header.Set("Content-Type", "application/json")
	}
	recorder := httptest.NewRecorder()
	gateway.Handler().ServeHTTP(recorder, request)
	return recorder
}

func requireKind(t *testing.T, err error, want errors.Kind) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected an error of kind %s, got nil", want)
	}
	if got := errors.KindOf(err); got != want {
		t.Fatalf("error kind = %s, want %s", got, want)
	}
}
