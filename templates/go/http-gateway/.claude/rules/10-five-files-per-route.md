# Rule — The 5-files-per-route rule

> Injected at SessionStart (ADR-0023). The cardinal structural rule of an http-gateway app. The
> worked reference is `internal/api/v1/ping/`.

Every route is one `edenhttp.Handler[Request, Response]` decomposed into EXACTLY five files, each
owning one stage of the edenhttp 6-stage pipeline. Authorization is NOT a sixth file — it is a
declarative field.

| File | Stage | Owns | Must NOT |
|---|---|---|---|
| `route.go` | (assembly) | Define `Request`/`Response` wiring, ASSEMBLE the `edenhttp.Handler` from the four stage funcs, **declare `Required`** (the Grant), register on the mux. | Contain business logic, decoding, or validation. |
| `parse.go` | PARSE | Decode the request into the typed `Request` (body via `edenhttp.DecodeJSONBody`, path via `request.PathValue`, query). | Validate, or touch a port. |
| `validate.go` | VALIDATE | Check the parsed input is well-formed; return a bare error (→ 400) on malformed input. | Touch a port (no persistence, no clock) — it stays pure. |
| `execute.go` | EXECUTE | The business step → the typed `Response`. The ONLY stage that may touch a port (the persistence Querier, an upstream client). Maps domain errors to typed `errors.Kind`. | Run before authz (the pipeline already authenticated + authorized). |
| `effect.go` | ACTION | The after-respond side effect (audit Event, metric, domain event). Returns the `edenhttp` Action closure. | Perform the PRIMARY write (that is execute); its error is logged, never surfaced. |

## Authorization is the `Required` field

```go
// route.go
var requiredGrant = edenhttp.NewGrant("widget", "write")   // namespace:action

handler := edenhttp.Handler[Request, Response]{
    Parse:    parse,
    Validate: validate,
    Required: requiredGrant,      // ← the AUTHORIZE stage; NOT a separate middleware or file
    Execute:  execute,
    Action:   effect(deps.Observability),
}
```

The pipeline's AUTHORIZE stage checks the caller's verified `Identity` holds a grant that `Covers`
`Required` (zero Grant → no grant required, but still authenticated). One concept, one home: the
grant grammar lives in `edenhttp`, the route only NAMES its grant.

## Why five, not one

The five files make each stage independently testable (validate is pure; execute is the only port
touch), keep the request pipeline decomposed the SAME way on every route, and make the no-shortcuts
gate meaningful (a half-built route is visible as a missing stage, not buried in a 200-line handler).
