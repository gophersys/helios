# contracts/ — WS1 contract negotiation drafts

> Status: Drafts for negotiation · 2026-06-12 · These are **not frozen contracts.** They are the
> 09 §4 step-1/2 artifacts for the six universal patterns: per pattern, a producer-side draft and
> a consumer-side draft were authored independently and reconciled into one document, with
> unresolved tensions recorded as open questions. Freezing happens at the contract-PR gate
> (09 §4 step 3) after Mateo's review; the frozen contract then lands in `libs/go/<pattern>/`
> and this draft moves to the attic.

| Draft | Pattern (10 §4) |
|---|---|
| [configuration.md](configuration.md) | Immutable, fully-resolved input IR; parsed once at the edge |
| [dependencies.md](dependencies.md) | The injected record of ports; the hexagon |
| [errors.md](errors.md) | Typed, wrappable, redaction-safe error model with stable `Kind` |
| [observability.md](observability.md) | Structured Event stream, OTel-aligned, secret-safe |
| [secrets.md](secrets.md) | Reference→value resolution; un-printable `Secret` type |
| [testing.md](testing.md) | Canonical fakes + adapter≡fake conformance suites |

Every draft obeys: HNS-1 naming (10 §5) · the `New(configuration, dependencies)` spine (10 §4) ·
interfaces ≤5 methods, accept-interfaces-return-concrete (10 §9) · `context.Context` first ·
Go 1.26 floor (ADR-0003) · module path `github.com/gophersys/libs/go/<pattern>` (ADR-0009 B) ·
public fakes in `<pattern>test`.
