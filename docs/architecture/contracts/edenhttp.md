# Contract — edenhttp

> Status: Frozen (ADR-0022 #3) · 2026-06-14 · The Milestone-B B5 reusable HTTP spine — the 6-stage
> handler pipeline, the uniform response envelope, the typed errors→status map, the SSE
> writer/stream, the dev-JWT identity + `namespace:action` grant grammar, and the `natssse`
> JetStream→SSE bridge that is the stateless half of the agentgateway. Frozen with the library
> built: the exported surface is mechanically recorded at `libs/go/edenhttp/.apibaseline` (the
> freeze made mechanical, ADR-0020) and the ADR-0020 8-dimension test taxonomy is green, including a
> REAL embedded nats-server + a REAL nats container proving the SSE bridge replays a JetStream
> stream by Seq and resumes gap-free by `Last-Event-ID`. This is a **kit-shaped** library (a set of
> composable HTTP pieces a consumer wires behind net/http) with ONE substrate adapter sub-package
> (`natssse`, the only place `nats.go` is imported). A breaking change to the surface requires a
> contract revision (ADR-0016 §1) + re-recording the `.apibaseline` — the cardinal sin otherwise
> (10 §9).
>
> Epistemic legend: ✅ ratified · 🔶 derived-but-settled · ⚠️ load-bearing assumption · 🧩 open fork.

## 1. Scope

✅ `edenhttp` is the **reusable HTTP spine** (ADR-0022 #3): the small kit of composable pieces an
Eden HTTP service builds its surface from. It is NOT a server and owns NO routes — net/http is the
consumer's; this kit returns the `http.Handler` / `http.HandlerFunc` the consumer mounts. It owns
four concepts, each with one home (10 §9):

- the **6-stage handler pipeline** (parse → validate → authorize → execute → respond → action),
  adopted from the IOTEA prior art and adapted to Eden + the frozen errors taxonomy;
- the **uniform response envelope** `{data, errors, kind}` — every Eden HTTP body is one shape;
- the **SSE writer/stream** — `id:`/`event:`/`data:` framing, explicit flush, heartbeat/keepalive,
  and `Last-Event-ID`/`from-seq` cursor parsing (the half IOTEA never had; Eden-new);
- **identity + authz** — a dev-JWT (HMAC-SHA256) verifier and the `namespace:action` grant grammar
  (IOTEA RBAC). The lib's auth CONCEPT is "identity" (HNS-1 rule 11 — never a concept named `auth`);
  idiomatic `jwt`/`token`/`Claims` type names are fine.

✅ The `natssse` sub-package is the **stateless JetStream→SSE bridge** (the B5 gateway's production
events path): an ephemeral JetStream consumer on `agent.<id>.events` from a caller-supplied start
sequence, each `agentruntime.EventEnvelope` framed onto an `SSEStream` (SSE `id` == event `Seq`),
heartbeats on a quiet stream, and a reaped consumer on disconnect/terminal. STATELESS by
construction: JetStream durable replay (the `agentruntime` MsgId==Seq invariant) is the source of
truth, so ANY gateway replica serves ANY session.

It does **not** own (it CONSUMES these frozen ports, never redefines them):

- the NATS bus protocol / the three-subject grammar / the `EventEnvelope` codec — **agentruntime**
  (ADR-0022 §4). `natssse` consumes `agent.<id>.events` and transports the `EventEnvelope`
  verbatim; it never re-spells the subject grammar or the message types.
- the agentsession **Event taxonomy** — **agentsession** (ADR-0008). The SSE `event:` token is the
  `EventKind.String()`; the taxonomy is transported, never redefined.
- the error model (`Kind`, wrap, `AsType`) — **errors**. `StatusForKind` maps the frozen `Kind`
  onto an HTTP status; it never invents a parallel classification.
- credential storage/minting — **secrets** + Vault. The JWT secret is a value the composition root
  resolves (from `EDEN_GATEWAY_JWT_SECRET`) and hands to `NewHMACVerifier`; `edenhttp` reads no env
  and stores no credential beyond the in-memory verifier secret, which is never logged or surfaced.

## 2. Construction (the spine)

```go
func New(configuration Config, dependencies Deps) (*Spine, error)
```

✅ `New` is **PURE** (10 §9): no I/O, no clock read, no env read, no goroutine. It validates the
injected ports (a non-nil `Verifier`, a non-nil `Clock`) and returns the concrete `*Spine` the
consumer draws its identity `Middleware` and SSE heartbeat cadence from. A missing dependency is a
wrapped `ConfigError` (`errors.KindInvalid`) so the composition root fails fast and loud. (`Config`/
`Deps` are the idiomatic Go exported type names HNS-1 rule 11 sanctions.)

`Config` is the immutable, fully-resolved spine input: the `HeartbeatInterval` (SSE keepalive
cadence; 0 → `DefaultHeartbeatInterval`). It holds **no secret**.

`Deps` is the injected hexagon (a nil required port is a `New`-time `ConfigError`):

| Port | Type | Role |
|---|---|---|
| `Verifier` | `edenhttp.TokenVerifier` (consumer-defined) | authenticates each bearer token → an `Identity`; `HMACVerifier` is the in-lib dev-JWT impl, a production IdP verifier binds the same port |
| `Clock` | `edenhttp.Clock` | the spine's ONLY time source (token-expiry reference + heartbeat scheduling) so `New` is pure and tests deterministic |
| `Logger` | `edenhttp.Logger` (consumer-defined, optional) | the redaction-safe structured-log seam; nil == no-op |

## 3. The ports (consumer-defined, ≤5 methods — 10 §9)

```go
type Clock interface{ Now() time.Time }                                   // 1 method

type TokenVerifier interface {                                            // 1 method
	Verify(token string, now time.Time) (Identity, error)             // raw bearer → Identity | KindUnauthenticated
}

type Logger interface {                                                   // 2 methods
	Info(message string, fields ...any)
	Error(message string, fields ...any)
}
```

✅ `TokenVerifier` is the SHAPE OF THE NEED, not a mirror of a JWT library: the middleware drives
one method. `HMACVerifier` realizes it for the dev-JWT path (HS256, alg pinned, constant-time
signature compare, exp/nbf window); a production deployment binds its own verifier behind the same
port without touching the middleware. `Verify` reads no env and no clock of its own — the spine
passes the `Clock` instant as `now`, so a verify is deterministic and fakeable.

## 4. The pipeline + the wire types

### 4.1 The 6-stage pipeline

```go
type Handler[I any, O any] struct {
	Parse         func(*http.Request) (I, error)                            // 1. default: bounded JSON body decode
	Validate      func(I) error                                            // 2. default: accept
	Required      Grant                                                     // 3. authorize: zero Grant → no grant required
	Execute       func(ctx, Identity, I) (O, error)                        // 4. REQUIRED — the business step
	SuccessStatus int                                                      // 5. respond: 0 → 200
	Action        func(ctx, Identity, I, O) error                          // 6. after-respond side effect (logged, never surfaced)
	Logger        Logger
}
func (Handler[I, O]) ServeHTTP(http.ResponseWriter, *http.Request)
```

✅ `ServeHTTP` runs the stages in order, short-circuiting to the uniform error `Envelope` on the
first stage that returns a typed error (its `Kind` → status via `StatusForKind`). The verified
`Identity` is read from the request context (`IdentityFrom`); a handler reached without the
`Middleware` is `KindUnauthenticated` (it must be mounted behind it). The body is bounded
(`DecodeJSONBody`: a 1 MiB `io.LimitReader` + `DisallowUnknownFields`).

### 4.2 The uniform envelope + the errors→status map

```go
type Envelope struct { Data any `json:"data"`; Errors []string `json:"errors"`; Kind string `json:"kind,omitempty"` }
func NewDataEnvelope(data any) Envelope
func NewErrorEnvelope(kind errors.Kind, messages ...string) Envelope
func WriteData(w http.ResponseWriter, status int, data any)
func WriteError(w http.ResponseWriter, err error) int   // classify Kind → status → uniform Envelope; returns the status
func WriteJSON(w http.ResponseWriter, status int, body any)
func StatusForKind(kind errors.Kind) int                // the ONE home for the Kind→status map
```

✅ Every Eden HTTP body is `{data, errors, kind}`. `WriteError` writes the stable `Kind` token + an
operator-safe message ONLY — never the cause chain, never a credential; a 5xx returns a fixed
generic message (the internal cause stays server-side). `StatusForKind`: invalid→400, not-found→404,
conflict→409, exhausted→429, unauthenticated→401, permission→403, unavailable→503, deadline→504,
canceled→499, unknown/internal→500.

### 4.3 The SSE writer/stream

```go
const CursorAll uint64 = 0
func ResolveCursor(r *http.Request) (uint64, error)    // Last-Event-ID | ?from-seq= | CursorAll; KindInvalid on a bad value
type SSEFrame struct { ID uint64; Event string; Data []byte }
func NewSSEStream(w http.ResponseWriter) (*SSEStream, error)   // sets text/event-stream headers, commits 200, requires http.Flusher
func (*SSEStream) Send(frame SSEFrame) error           // event:/id:/data: + flush
func (*SSEStream) Heartbeat() error                    // ": keepalive" comment + flush
func (*SSEStream) Comment(kind errors.Kind)            // trailing fault comment after the 200 is committed
```

✅ `ResolveCursor` returns the LAST SEEN sequence; the bridge replays from `seq+1` so a reconnect is
gap-free and dup-free. The SSE `id:` is the resume cursor the browser echoes as `Last-Event-ID`. The
`SSEStream` is a single-writer value (the SSE one-ordered-byte-stream contract); there is no `Close`
(the `http.Server` owns the connection teardown).

### 4.4 Identity + the grant grammar

```go
type Grant struct { Namespace, Action string }
func NewGrant(namespace, action string) Grant
func ParseGrant(raw string) (Grant, error)             // "namespace:action" | "*"; KindInvalid on malformed
func (Grant) String() string
func (Grant) Covers(required Grant) bool               // held grant authorizes a request (held wildcards widen)

type Identity struct { Subject string; Grants []Grant }
func (Identity) Authorize(required Grant) error        // nil | KindPermission
func (Identity) HasGrant(required Grant) bool
func IdentityFrom(ctx context.Context) (Identity, bool)

type HMACVerifier struct{ ... }
func NewHMACVerifier(secret string) (*HMACVerifier, error)        // empty secret → KindInvalid
func (*HMACVerifier) Verify(token string, now time.Time) (Identity, error)
func (*HMACVerifier) Sign(subject string, grants []Grant, expiresAt time.Time) (string, error)

func (*Spine) Middleware(next http.Handler) http.Handler         // verify bearer → stash Identity, or 401
func (*Spine) MiddlewareFunc(next http.HandlerFunc) http.Handler
func (*Spine) Clock() Clock
func (*Spine) HeartbeatInterval() time.Duration
```

✅ The `namespace:action` grant grammar is the IOTEA RBAC vocabulary (ADR-0022 #3): the HELD grant's
wildcards widen the match (`*` covers everything, `sessions:*` covers any action on `sessions`,
`sessions:control` covers only that pair); a request never widens itself. `Middleware` authenticates
EVERY request FIRST (the gateway is behind auth even locally — ADR-0022 #3) and stashes the
`Identity` on the context for a pipeline's authorize stage; an absent/malformed/under-signed token
is the uniform 401 and `next` is NOT called.

### 4.5 The natssse bridge (`edenhttp/natssse`)

```go
func New(configuration Config, dependencies Deps) (*Bridge, error)   // PURE over a dialed nats.JetStreamContext + a Clock
func (*Bridge) Stream(ctx, agentID agentruntime.AgentID, lastSeq uint64, sse *edenhttp.SSEStream) error
```

✅ `Stream` opens an ephemeral JetStream consumer on `agent.<agentID>.events` starting AFTER
`lastSeq` (`CursorAll` → DeliverAll, else `StartSequence(lastSeq+1)`), pumps each `EventEnvelope` as
one SSE frame (`id` == `Seq`) to the terminal event, a client disconnect (ctx canceled), or a fault.
It reaps the consumer + subscription on EVERY exit path (the deferred Unsubscribe) so no NATS
subscription or goroutine outlives the call (goleak-clean).

## 5. Invariants (load-bearing, gate-proven)

- ✅ **Behind auth even locally** — `Middleware` rejects an absent/malformed/unsigned/expired token
  with a 401 and never calls `next`; the alg is pinned to HS256 (no alg-confusion downgrade); the
  signature is a constant-time compare. Proven non-vacuous by a weaken-to-confirm (drop the auth
  gate → an unsigned request is admitted; restore → 401).
- ✅ **Gap-free Seq-resume** — `ResolveCursor` + `natssse.Stream` replay from `lastSeq+1`, so a
  reconnect from `Last-Event-ID N` delivers exactly the events after `N`, in `Seq` order, no dup of
  `N`. Proven against a REAL embedded nats-server + a REAL nats container (the integration lane);
  weaken-to-confirm by breaking the `+1` (a dup of `N` appears).
- ✅ **Uniform envelope, no leak** — every body is `{data, errors, kind}`; a 5xx never carries the
  internal cause; no credential reaches a body, header, SSE payload, log, or error (the SeededCanary
  property + the errors redaction contract).
- ✅ **Reaped bridge** — the JetStream consumer + the SSE goroutine are reaped on disconnect/terminal
  (goleak-clean; the ADR-0020 leak + lifecycle lanes).
- ✅ **Real substrate, never mocked** — the bridge is proven on a REAL embedded `nats-server/v2`
  (fast lanes) AND a REAL `nats` container (the integration lane); never a hand-rolled NATS fake.

## 6. Forks

- 🔶 **Stdlib-only HMAC dev-JWT** (no `golang-jwt`). The verifier is HS256 over `crypto/hmac` +
  `crypto/sha256` + `encoding/base64`/`json` — a leaf-lib import boundary (stdlib + sibling libs
  only, ADR-0018 depguard) AND a minimal supply-chain surface. It is a DEV token (ADR-0022 #3
  "behind auth even locally"), not a production IdP token; a real IdP binds the `TokenVerifier`
  port. (Settled: the dev path needs only symmetric verify; the port keeps production open.)
- 🔶 **`natssse` as a substrate-adapter sub-package** (the only `nats.go` importer in edenhttp),
  leaf=false, proven by the integration lane not mutation — exactly the `agentruntime/natsbus`
  posture. The pure spine (pipeline/envelope/SSE-framing/grants/dev-JWT) stays covered by the
  property/conformance/lifecycle/load/unit lanes. (Settled; mirrors the established adapter pattern.)
- 🔶 **Ephemeral push consumer per request** (not a durable). A stateless gateway replica serves any
  session by JetStream replay; an ephemeral consumer from `StartSequence` is the simplest correct
  realization (no durable name to garbage-collect across replicas). Revisit only if a measured
  consumer-churn cost appears. (Settled.)
