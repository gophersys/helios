# contracts/ — WS1 contract negotiation drafts

> Status: Drafts for negotiation · 2026-06-12 · These are **not frozen contracts.** They are the
> 09 §4 step-1/2 artifacts for the six universal patterns: per pattern, a producer-side draft and
> a consumer-side draft were authored independently and reconciled into one document, with
> unresolved tensions recorded as open questions. Freezing happens at the contract-PR gate
> (09 §4 step 3) after Mateo's review; the frozen contract then lands in `libs/go/<pattern>/`
> and this draft moves to the attic.

| Draft | Kind | Summary |
|---|---|---|
| [configuration.md](configuration.md) | pattern (10 §4) | Immutable, fully-resolved input IR; parsed once at the edge |
| [dependencies.md](dependencies.md) | pattern (10 §4) | The injected record of ports; the hexagon |
| [errors.md](errors.md) | pattern (10 §4) | Typed, wrappable, redaction-safe error model with stable `Kind` |
| [observability.md](observability.md) | pattern (10 §4) | Structured Event stream, OTel-aligned, secret-safe |
| [secrets.md](secrets.md) | pattern (10 §4) | Reference→value resolution; un-printable `Secret` type |
| [testing.md](testing.md) | pattern (10 §4) | Canonical fakes + adapter≡fake conformance suites |
| [agentsession.md](agentsession.md) | connector (F4, 05 §2) | The agent-session port: one normalized, resumable Event stream + tool grants + permission round-trip + credential seam over any harness (C22, ADR-0008) |

Every draft obeys: HNS-1 naming (10 §5) · the `New(configuration, dependencies)` spine (10 §4) ·
interfaces ≤5 methods, accept-interfaces-return-concrete (10 §9) · `context.Context` first ·
Go 1.26 floor (ADR-0003) · module path `github.com/gophersys/libs/go/<pattern>` (ADR-0009 B) ·
public fakes in `<pattern>test`. `agentsession` is an **F4 connector contract** (05 §2), not a
10 §4 library pattern — it obeys the same construction rules but its adapter seam, capability
manifest, and conformance suite are the connector-family obligations of 05 §1/§3/§6.
