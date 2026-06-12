// Renders the Eden ATLAS — the unified consumption entry point — into a single
// self-contained HTML file. This is the v0 conformance instance of doc 12 §7
// (12-presentation-layer.md): it implements the altitude model (§2), the breadcrumb,
// and the design-lens photosphere diagram (§3) over Eden's own architecture corpus.
//
// Usage:   node docs/tools/render-atlas.mjs
//          (requires `marked` and `mermaid` — `yarn install` provides marked; in this
//           environment set NODE_PATH=/tmp/eden-render/node_modules, which carries both)
// Output:  docs/eden-atlas.html  (gitignored; never edit by hand — regenerate this way)
//
// Style: reuses render-html.mjs's visual language (sidebar / chips / sans-serif / dark
// mode). Mermaid is inlined as a self-contained client-side bundle (the inline-mermaid
// technique) so the file opens offline with no network dependency; marked renders the
// prose snippets. The architecture markdown stays the source of truth — this is a
// derived reading surface.

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

let marked;
try {
  ({ marked } = require('marked'));
} catch {
  console.error('marked not found — run `yarn install` (it is a devDependency), or set NODE_PATH=/tmp/eden-render/node_modules.');
  process.exit(1);
}
marked.use({ gfm: true });

// ── paths ────────────────────────────────────────────────────────────────────
const HERE = dirname(fileURLToPath(import.meta.url));   // docs/tools
const DOCS = resolve(HERE, '..');                       // docs
const OUT = `${DOCS}/eden-atlas.html`;
const GENERATED = '2026-06-12';                          // snapshot date for the OD index

// Locate the inlinable mermaid browser bundle (so the page is self-contained, offline).
const MERMAID_CANDIDATES = [
  resolve(DOCS, '..', 'node_modules', 'mermaid', 'dist', 'mermaid.min.js'),
  '/tmp/eden-render/node_modules/mermaid/dist/mermaid.min.js',
  ...(process.env.NODE_PATH || '').split(':').filter(Boolean)
    .map((p) => resolve(p, 'mermaid', 'dist', 'mermaid.min.js')),
];
const mermaidBundlePath = MERMAID_CANDIDATES.find((p) => p && existsSync(p));
if (!mermaidBundlePath) {
  console.error('mermaid.min.js not found — install mermaid (yarn install) or set NODE_PATH=/tmp/eden-render/node_modules.');
  process.exit(1);
}
const mermaidBundle = readFileSync(mermaidBundlePath, 'utf8');

// ── small helpers ──────────────────────────────────────────────────────────────
const esc = (s) => String(s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

// Render inline markdown (bold/code/links) without wrapping <p> tags.
const inline = (md) => marked.parseInline(String(md));

// Turn an epistemic-tagged token into a badge. Recognises ✅🔶⚠️🧩.
const FLAG_CLASS = { '✅': 'ok', '🔶': 'hyp', '⚠️': 'warn', '🧩': 'design' };
const badgeFor = (text) => {
  const t = String(text).trim();
  const lead = [...t][0];
  if (FLAG_CLASS[lead]) {
    const rest = t.slice(lead.length).trim();
    return `<span class="badge ${FLAG_CLASS[lead]}">${esc(lead)}</span>${rest ? ' ' + inline(rest) : ''}`;
  }
  return inline(t);
};

// ── section 5 data: open-questions snapshot (canonical homes own these) ─────────
const OPEN_QUESTIONS = [{"id":"OD-1","question":"Which Svelte behavior layer (Bits UI headless vs Melt UI builders vs hand-rolled on runes) should the re-founded photosphere adopt?","category":"ui","blocks":"WS4 photosphere re-founding spike; design-brief's visual language (design_system_reference stays null until ruled)","needed_by":"WS4 spike","lean":"Bits UI (headless, Svelte 5-native), pending a data pass of ADR-0004 rigor (a11y matrix, maintenance, LLM legibility)"},{"id":"OD-2","question":"Should the Svelte app use SvelteKit (routing/SSR) or a Vite SPA, given Tauri wraps the same bundle either way?","category":"architecture","blocks":"M3 frontend skeleton","needed_by":"M3 frontend skeleton","lean":"SvelteKit (routing/SSR story, ecosystem default) over SPA (simpler Tauri parity)"},{"id":"OD-3","question":"Which client state/query layers replace the former React zustand/jotai/xstate/TanStack-Query choices post-React?","category":"architecture","blocks":"M3","needed_by":"M3","lean":"Svelte 5 runes + TanStack Svelte Query; XState's Svelte adapter only if backend-lifecycle machine-mirroring survives review"},{"id":"OD-4","question":"Should the CI executor v1 be an own runner on docker/kubernetes from day 1, or wrap an existing runner behind the executor port first?","category":"architecture","blocks":"L2 (kernel ladder)","needed_by":"L2","lean":"Own runner (contract purity, content-aware caching) vs wrap (speed) — recommendation own runner"},{"id":"OD-6","question":"What is the Stripe adapter scope and metering granularity for hosted-tier billing?","category":"product","blocks":"hosted-tier milestone billing; F3 contract carries it","needed_by":"hosted milestone","lean":"Defer until hosted milestone; F3 contract designed to carry it"},{"id":"OD-7","question":"How are the inherited agentconfiguration open items (CLI module split, yaml v3 vs v4, harness plugin model, per-call key rotation, content-based routing) ruled?","category":"architecture","blocks":"WS2 agentconfiguration work","needed_by":"WS2","lean":"Per upstream agentcfg-architecture §open-questions; rule during WS2"},{"id":"OD-9","question":"What is the transcript retention & privacy policy (per-project retention, redaction verification)?","category":"product","blocks":"any non-Mateo user existing","needed_by":"L4","lean":"None recorded — needs ruling before any non-Mateo user exists"},{"id":"OD-10","question":"What is the visual-editor scope for the v1 dashboard — read-only pipeline/artifact viewer first, or editable canvas?","category":"ui","blocks":"L2/L4 dashboard; the editor's architectural contract (edits re-enter via phase artifacts, never canvas mutation)","needed_by":"L2/L4","lean":"Viewer-first recommended; editing re-enters via phase artifacts, not canvas mutation (this constraint holds regardless of scope ruling)"},{"id":"OD-11","question":"What concrete components compose the S6 observability stack (trace/metric/log storage, dashboarding)?","category":"architecture","blocks":"S6 must be minimally live by L1 exit (06 §2)","needed_by":"L0/L1","lean":"Candidates to evaluate: Grafana LGTM stack, ClickHouse-backed, openobserve"},{"id":"OD-12","question":"When should the first managed-cloud adapter (EKS/GKE/AKS/DO) plus its billing-polling and cloud-drift surface be scheduled, since the ladder completes on local substrates leaving cloud unexercised?","category":"architecture","blocks":"post-L4 planning; exercising cloud adapters/billing/drift","needed_by":"post-L4 planning","lean":"Schedule one managed-kubernetes adapter + its billing/drift surface immediately post-L4 (recommended), or accept all four as unscheduled backlog with explicit sign-off"},{"id":"OD-13","question":"What is the fleet deployment architecture (C17): per-customer isolated environments, gated rollouts of one change across N deployments, fleet-wide observability — D4 modeling + orchestrator design?","category":"architecture","blocks":"the production milestone","needed_by":"post-spine (before production milestone)","lean":"Needs architecture work before the production milestone; rides ADR-0012's compute posture"},{"id":"11 §10 Q1","question":"Should requirements.statement enforce EARS template grammar, or recommend-only in v1?","category":"contract","blocks":"requirements document schema strictness; intake-agent authoring loop","needed_by":"revisit with intake-agent eval data","lean":"🔶 recommend-only v1; revisit with intake-agent eval data"},{"id":"11 §10 Q2","question":"How are document-schema $id URIs hosted — keep logical eden://document/v1/<name>, or publish resolvable URLs once the gateway exists?","category":"contract","blocks":"schema $id resolvability; becomes an OD entry when hosted tier is scoped","needed_by":"when hosted tier is scoped","lean":"Logical URI now; promote to an OD entry when hosted tier is scoped"},{"id":"11 §10 Q3","question":"Do pipeline records (04 §4) migrate into the document envelope, or keep their own schemas?","category":"contract","blocks":"engine build (record schema design)","needed_by":"engine build","lean":"Own schemas, same id/link grammar — revisit at engine build"},{"id":"contracts/configuration §7 Q1","question":"Decode target: a typed `v any` pointer, or an opaque `Document` read by `Path`?","category":"contract","blocks":"configuration contract freeze (09 §4 step 3)","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer — opaque `Document`/`Value` read surface (honors immutability, accumulate-all diagnostics, matches kernel call sites)"},{"id":"contracts/configuration §7 Q2","question":"Error channel: is `error` non-nil iff a SeverityError finding (ParseError carries findings), or `error` for I/O only?","category":"contract","blocks":"configuration contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer — `error` is I/O-only; ParseError repurposed to wrap the Source I/O cause, findings live in Diagnostics"},{"id":"contracts/configuration §7 Q3","question":"Byte input: pass `Source` structs to `Parse`, or inject a `Source` port in Deps and call `Parse(ctx, name)`?","category":"contract","blocks":"configuration contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer — injected one-method port read only inside `Parse` (keeps `New` pure, composition root sole reader)"},{"id":"contracts/configuration §7 Q4","question":"Is Merge/overlay folding present at all, or implicit inside one `Parse` call?","category":"contract","blocks":"configuration contract freeze; stage-overlay composition","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer — explicit position-preserving `Merge(base, overlay)` so diagnostics blame the right file"},{"id":"contracts/configuration §7 Q5","question":"Is the diagnostics accumulator a `Diagnostics` value type, or a bare `[]Diagnostic`?","category":"contract","blocks":"configuration contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer — a `Diagnostics` value type with Append/HasError/All (validators need a write sink)"},{"id":"contracts/configuration §7 Q6","question":"Severity levels: Info/Warning/Error (three), or Warning/Error (two)?","category":"contract","blocks":"configuration contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer (simpler) — two levels; SeverityInfo rejected for v1 (additive later if needed)"},{"id":"contracts/configuration §7 Q7","question":"Value surface: concrete `Resolved`/`Value` structs with `Slice()`, or a `Value` interface with Field/Len/At?","category":"contract","blocks":"configuration contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer — `Value` interface capped at 5 methods, Diagnostic-returning conversions, element access via path.Index(i)"},{"id":"contracts/configuration §7 Q8","question":"Should Config carry MaxSourceBytes / AllowUnknownKeys knobs, or just a Strict bool?","category":"contract","blocks":"configuration contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Producer retained — MaxSourceBytes cap + AllowUnknownKeys (opt-out named so the zero Config stays strict)"},{"id":"contracts/configuration §7 Q9","question":"Does configuration resolve SecretReference, or treat it as an opaque leaf?","category":"contract","blocks":"configuration↔secrets cross-contract seam; both contracts' freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Agreed — SecretReference is an opaque loggable leaf; the secrets port resolves it at point-of-use"},{"id":"contracts/dependencies §7 Q1","question":"Per-library Deps: embed `dependencies.Set`, or narrow to only the ports the component uses?","category":"contract","blocks":"dependencies contract freeze (09 §4 step 3)","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Narrow (accept minimum interface); Set stays composition-root currency; embed permitted only where the whole Set is used"},{"id":"contracts/dependencies §7 Q2","question":"Does dependencies own a `Sink` port, and if so typed how?","category":"contract","blocks":"dependencies contract freeze; observability seam","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Own `Sink` with `any` (no observability import; graph stays leaf); Secrets/Telemetry/Platform owned elsewhere"},{"id":"contracts/dependencies §7 Q3","question":"Does the dependencies package have its own `New` spine, or only Resolve/Validate?","category":"contract","blocks":"dependencies contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 No own `New` — dependencies is the argument to every spine; surface is Resolve (default) + Validate"},{"id":"contracts/dependencies §7 Q4","question":"Real-port construction: per-port Real* providers, a one-call Real(), or Resolve()?","category":"contract","blocks":"dependencies contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Keep both per-port Real* and Resolve(Set); drop Real() as a duplicate of Resolve"},{"id":"contracts/dependencies §7 Q5","question":"Clock surface: `Now()` only, or `Now()` + `After(ctx, d)`?","category":"contract","blocks":"dependencies contract freeze; deterministic timeouts in engine/testharness","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 `Now()` + `After(ctx, d)` (After is load-bearing for FakeClock.Advance-drivable timeouts)"},{"id":"contracts/dependencies §7 Q6","question":"Missing-port error shape: typed `*MissingPortError`, or sentinel `ErrMissingPort`?","category":"contract","blocks":"dependencies contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Typed exported `*MissingPortError{Port}` (errors.AsType-inspectable, names the missing port)"},{"id":"contracts/errors §7 Q1","question":"Should errors expose an abstract StatusCode codomain + StatusCodeOf so the mapping lives below transport?","category":"contract","blocks":"errors contract freeze (09 §4 step 3)","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Rejected in-errors StatusCode — the Kind→code table lives only at the transport boundary; totality met by exhaustive switch over closed Kind"},{"id":"contracts/errors §7 Q2","question":"Wrap argument order and Kind-inheritance: `Wrap(cause, kind, format, args...)` vs `Wrap(kind, message, cause)`?","category":"contract","blocks":"errors contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer signature `Wrap(kind, message, cause)` + Kind inheritance; constant-style message keeps interpolation (leak vector) out by default"},{"id":"contracts/errors §7 Q3","question":"Field model: typed `Field` + free function `With(err, ...Field)`, or `*Error.WithField(k, v)` method?","category":"contract","blocks":"errors contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Producer's `WithField` method shape + consumer's fail-safe semantics (safe-scalar enforcement, '[unredactable]' marker, never panic/leak); Field struct rejected"},{"id":"contracts/errors §7 Q4","question":"Keep or drop a fine-grained `Code`/`WithCode` token below Kind?","category":"contract","blocks":"errors contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Kept WithCode/Code (additive, optional; not what the transport boundary switches on)"},{"id":"contracts/errors §7 Q5","question":"Include `FromContext` (ctx → Kind) mapping canceled/deadline?","category":"contract","blocks":"errors contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Kept FromContext (pure, eliminates hand-rolled ctx-error mapping; returns nil when ctx live)"},{"id":"contracts/errors §7 Q6","question":"Re-export `Join` for swarm/fan-out aggregation?","category":"contract","blocks":"errors contract freeze; swarm/FileLease aggregation","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Kept Join re-export (AsType/Is/Join all re-exported so consumers never reach for stdlib errors)"},{"id":"contracts/errors §7 Q7","question":"Kind enumerator set: producer's 11 (split Unauthenticated + Permission) vs consumer's 10 (folded Unauthorized)?","category":"contract","blocks":"errors contract freeze; transport boundary information fidelity","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Producer's split (KindUnauthenticated + KindPermission) per AIP-193/google.rpc.Code; taxonomy is append-only safe-to-freeze superset"},{"id":"contracts/observability §7 Q1","question":"Span/scope shape: `With(fields)` field inheritance, or `Scope(ctx,name,fields)` timed span — or both?","category":"contract","blocks":"observability contract freeze (09 §4 step 3); engine runPhase scoping","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Kept BOTH at the 5-method ceiling (With = cheap static inheritance; Scope = timed correlated span engine.runPhase needs)"},{"id":"contracts/observability §7 Q2","question":"Field value type: sealed `Value` union (no Secret), or `Valuer{TelemetryValue() any}` carrying a redacted Secret?","category":"contract","blocks":"observability contract freeze; secret-safe telemetry seam","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer's `Valuer` (admits only the redacted projection; secrets.Secret satisfies it via '***REDACTED***'); primitive constructors retained"},{"id":"contracts/observability §7 Q3","question":"Lower adapter seam: per-Event `Sink{Write(Event)}`, or batch `Exporter{Export([]Record)}`?","category":"contract","blocks":"observability contract freeze; OTLP/slog adapter shape","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer's batch `Exporter` + `Record` (library owns batching/resource-stamping once; adapter only translates)"},{"id":"contracts/observability §7 Q4","question":"Time source: adapter stamps now (library reads no clock), or inject a `Clock` in Deps?","category":"contract","blocks":"observability contract freeze; deterministic Scope duration","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Inject Clock (Scope duration) AND keep producer's zero-Time → adapter-stamps fallback for ad-hoc Emit"},{"id":"contracts/observability §7 Q5","question":"Is a `Plane` enum required on every Event for P9's three-plane partition?","category":"contract","blocks":"observability contract freeze; P9 three-plane backend partition","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Adopted Plane (consumer); added PlaneUnset zero so an unstamped Event inherits Config.DefaultPlane visibly"},{"id":"contracts/observability §7 Q6","question":"Keep a closed `Kind` Event-classification enum, or let classification ride the stable dotted `Name`?","category":"contract","blocks":"observability contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Rejected Kind (avoid a second taxonomy parallel to Name); branch on stable documented Name constants; additive const later if needed"},{"id":"contracts/observability §7 Q7","question":"New's validation error type: bare `error`, or a typed `*ConfigError`?","category":"contract","blocks":"observability contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer's typed `*ConfigError` (carries Field + Message, wraps cause with %w; matches errors.md discipline)"},{"id":"contracts/observability §7 Q8","question":"Ledger field set: cost-shaped (CostMicros, CacheReadIn) vs run-shaped (RunID, PhaseID, Harness, Retries, WallTime)?","category":"contract","blocks":"observability contract freeze; FinOps (S9) + run/budget machinery","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Merged superset (both FinOps and run/correlation fields); CacheReadIn renamed CacheHits keeping cache-hit-input-tokens semantics"},{"id":"contracts/secrets §7 Q1","question":"Reference shape: validated URI with scheme routing, or a bare stable name?","category":"contract","blocks":"secrets contract freeze (09 §4 step 3)","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Kept both — Reference is the validated value type with Scheme(); schemeless routes via Config.DefaultScheme so Ref(name) ergonomics survive"},{"id":"contracts/secrets §7 Q2","question":"Error model: a `Kind int` enum on a wrapped error, or typed error structs?","category":"contract","blocks":"secrets contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Typed structs (InvalidReferenceError/NotFoundError/DeniedError/UnavailableError/ZeroizedError) via errors.AsType[T]; KindUnspecified dropped"},{"id":"contracts/secrets §7 Q3","question":"Should Secret expose `Close() io.Closer`, or `Zeroize()` only?","category":"contract","blocks":"secrets contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Rejected Close() — `defer sec.Zeroize()` is the single semantic wipe operation; no io.Closer affordance"},{"id":"contracts/secrets §7 Q4","question":"New return type: concrete `*Mediator`, or the `Provider` interface?","category":"contract","blocks":"secrets contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Concrete `*Mediator` (return-concrete ground rule); callers store as Provider"},{"id":"contracts/secrets §7 Q5","question":"Add typed convenience over Use (UseString/UseValue/Use1)?","category":"contract","blocks":"secrets contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Adopted as `Use1[V]` (leak-safe closure for the one-derived-value case; not an accessor)"},{"id":"contracts/secrets §7 Q6","question":"Routing: a package `Mediator` keyed by scheme, or per-stage adapter selection at the composition root?","category":"contract","blocks":"secrets contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Both compose — Mediator routes by scheme; root does per-stage switch via Deps.Resolvers; single-adapter apps can bind directly"},{"id":"contracts/secrets §7 Q7","question":"Test minting hook: exported NewForTest, //go:linkname, or a shared internal package?","category":"contract","blocks":"secrets contract freeze; secretstest","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Shared internal minting package; secretstest.MintSecret the only public test-only surface; no linkname/no exported NewForTest"},{"id":"contracts/secrets §7 Q8","question":"Redaction sentinel value: '***REDACTED***' or 'secrets.Secret(REDACTED)'?","category":"contract","blocks":"secrets contract freeze; cross-contract consistency with observability","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 'secrets.Secret(REDACTED)' exported as secrets.Redacted (names the type at the leak site; greppable)"},{"id":"contracts/testing §7 Q1","question":"Assertion sink: bind to a testing.TB-shaped `T` interface, or an assertion-free 3-method `Report`?","category":"contract","blocks":"testing contract freeze (09 §4 step 3); static-binary Evidence minting","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer's `Report` (core must not import stdlib testing so suites run in shipped binaries to mint Evidence); Skipf added, Cleanup moved to Harness"},{"id":"contracts/testing §7 Q2","question":"Subject-construction seam: `Factory(ctx, T)` returning its own teardown, or `Factory(ctx, Harness)` returning (S, error)?","category":"contract","blocks":"testing contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer's `Harness` (vends deterministic sources + capability gate); factory returns (S, error); teardown via Harness.Cleanup (LIFO)"},{"id":"contracts/testing §7 Q3","question":"Suite as a struct with `Cases map`, or an interface returning `iter.Seq`?","category":"contract","blocks":"testing contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Hybrid — Suite[S] stays a struct but Cases is iter.Seq[Case] (stable order, streams large suites); Case[S] is a struct"},{"id":"contracts/testing §7 Q4","question":"Clock shape: Now/Since/After/Sleep vs Now/Since/NewTimer?","category":"contract","blocks":"testing contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Merged to 4 methods — Now, Since, NewTimer (stoppable, prevents fake-timer leaks), Sleep(ctx,d) (cancellable blocking seam)"},{"id":"contracts/testing §7 Q5","question":"RandomSource: `Read` only, or `Read` + `Uint64`?","category":"contract","blocks":"testing contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Producer — Read only (io.Reader-compatible so crypto/rand interchanges); Uint64/UUID/jitter are testingtest helpers"},{"id":"contracts/testing §7 Q6","question":"Fake-determinism stability: is identical Config ⇒ identical timeline/bytes a frozen, breaking-change-gated invariant?","category":"contract","blocks":"testing contract freeze; golden-test reproducibility","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Accepted as a frozen invariant — the FakeClock/FakeRandomSource byte/timeline algorithm is contract; changes are breaking, behind a new constructor only"},{"id":"contracts/testing §7 Q7","question":"Deps content: empty `struct{}`, or `Deps{Epoch time.Time}`?","category":"contract","blocks":"testing contract freeze; cross-process fake reproducibility","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer — injected Epoch (data, not a clock read; New stays pure) for explicit cross-process reproducibility"},{"id":"contracts/testing §7 Q8","question":"Where does the testing.T capability live — `Wrap(t)` returning suite T, or `Report(t)`/`Harness(t)` adapters?","category":"contract","blocks":"testing contract freeze; testingtest surface","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer's adapter set renamed to avoid shadowing types: NewReport, NewHarness, AssertResult"},{"id":"contracts/testing §7 Q9","question":"RunSuite as a free function, or a Suite.Run method?","category":"contract","blocks":"testing contract freeze","needed_by":"WS1 contract-PR freeze gate","lean":"🧩 Consumer's free function RunSuite[S] (Go methods can't add type params; threading Runner + returning Result is cleaner)"},{"id":"research/04 §open Q1","question":"Geometric zoom vs semantic grouping for altitude on the photosphere canvas?","category":"ui","blocks":"photosphere navigation model (U1/U3); diagram-as-observability surface","needed_by":"photosphere/dashboard design (promote into a spec before build)","lean":"🔶 Semantic grouping + drill-down + perspectives; reserve zoom for within-altitude"},{"id":"research/04 §open Q2","question":"Is 'design view' vs 'observability view' one perspective-toggle (Ilograph) or two workspaces (Blender)?","category":"ui","blocks":"C10 surface architecture (view flip vs posture switch)","needed_by":"photosphere/dashboard design","lean":"🔶 Perspective toggle on one canvas; workspace only if panels diverge hard"},{"id":"research/04 §open Q3","question":"How is semantic drift surfaced without false-positive fatigue?","category":"ui","blocks":"U4 drift feature; the differentiated semantic-drift bet","needed_by":"drift feature build (post cheap link-existence ship)","lean":"🔶 Ship link-existence Accuracy Score first; gate semantic drift behind confidence + remediation-PR"},{"id":"research/04 §open Q4","question":"Mandatory tutorial for the founder but skippable for experts — one flow or two?","category":"ui","blocks":"onboarding/tutorial design (U5)","needed_by":"onboarding design","lean":"🔶 One Walkthrough, tiered/skippable steps with when-conditions"},{"id":"research/04 §open Q5","question":"Web-first or desktop-first for the founder's first PoC?","category":"ui","blocks":"entry-surface decision for the founder persona","needed_by":"first PoC entry design","lean":"✅ Web is the zero-friction entry; desktop is the power-user upgrade"},{"id":"research/04 §open Q6","question":"How much of doc 11's Markdoc-class validation runs client-side vs in the cluster (C4)?","category":"ui","blocks":"doc-11 rendering/validation split; depends on where ground truth lives","needed_by":"doc-11 UI build","lean":"🔶 Validate in-cluster (where ground truth is); client renders + hover-syncs"},{"id":"research/04 §open Q7","question":"Does the breadcrumb extend into code/symbol (VS Code), or stop at component?","category":"ui","blocks":"multi-altitude navigation design (whether code/run are true altitudes)","needed_by":"navigation design","lean":"🔶 Extend to file→symbol when a browser/VS Code editor is the active surface"},{"id":"research/04 §open Q8","question":"Are pie/radial accelerators (Blender Q) worth the learning cost on a software ops tool?","category":"ui","blocks":"accelerator/shortcut design","needed_by":"accelerator design (measure demand first)","lean":"🔶 Defer; ship palette + small canonical shortcut set first, measure demand"},{"id":"research/04 §open Q9","question":"Is Linux/WebKitGTK a supported desktop target or web-only?","category":"ui","blocks":"desktop-shell test matrix; the main 'same bundle' rendering leak","needed_by":"desktop-shell scoping","lean":"🔶 Support but treat as first-class visual-regression target; degrade to web if it lags"},{"id":"research/04 §open Q10","question":"What is Eden's '~6 load-bearing verbs' canonical set?","category":"ui","blocks":"command-palette + shortcut vocabulary (U2)","needed_by":"palette/shortcut design","lean":"🔶 Likely create-project, run-gate, open-transcript, jump-altitude, regenerate-doc, redeploy"},{"id":"codingharness README Q-sandbox","question":"What true filesystem + network sandbox boundary confines an agent's writes (workspace pod, seccomp/landlock, or --add-dir scoping), and when, if ever, is bypassPermissions acceptable?","category":"architecture","blocks":"the real F4 agent adapter (libs/go/codingharness) contract; host safety","needed_by":"F4 codingharness contract draft (WS2)","lean":"None recorded — spike used acceptEdits + --allowedTools, but nothing confined writes beyond cwd"},{"id":"codingharness README Q-toolgrant","question":"Who owns the deterministic mapping from a phase's declared capabilities to concrete --allowedTools/--disallowedTools patterns, and how is a denied tool surfaced (it lands in permission_denials, not an error)?","category":"contract","blocks":"F4 contract's tools grant compilation","needed_by":"F4 codingharness contract draft","lean":"None recorded"},{"id":"codingharness README Q-resume","question":"How does the real loop steer across turns (--resume/--continue, --input-format stream-json), and is session state persisted (--no-session-persistence vs resumable) and where?","category":"architecture","blocks":"multi-turn agent steering in the real adapter","needed_by":"F4 codingharness contract draft","lean":"None recorded — spike is single-shot"},{"id":"codingharness README Q-structured-out","question":"Does the kernel rely on --json-schema + --output-format json to force the final result into a schema (e.g. a SourceChange artifact), or parse free-form result text?","category":"architecture","blocks":"how SourceChange artifacts are extracted from a session","needed_by":"F4 codingharness contract draft","lean":"None recorded — schema-forcing is cleaner but constrains the prompt"},{"id":"codingharness README Q-budgets","question":"How does --max-budget-usd map onto TokenBudget (02 §2): abort behavior, partial-ledger on a budget kill, and reconciliation with run-level budget escalation (promote-to-stronger-model)?","category":"architecture","blocks":"F4 cost-ceiling enforcement; budget escalation policy","needed_by":"F4 codingharness contract draft","lean":"None recorded — spike wired the flag but did not exercise it"},{"id":"codingharness README Q-multimodel","question":"Must the ledger carry per-model token/cost lines (not just aggregate) for the routing-economics comparison ADR-0008 promises 'measured, not argued'?","category":"architecture","blocks":"F4 ledger schema; ADR-0008 routing-economics evidence","needed_by":"F4 codingharness contract draft","lean":"Yes implied — modelUsage proves a single session spans models; ledger must carry per-model lines"},{"id":"codingharness README Q-cache-cost","question":"How does the ledger/cost-ceiling price all four token axes (input/output/cache-read/cache-creation) per the provider's cache pricing so budgets aren't wildly wrong?","category":"architecture","blocks":"F4 cost model correctness","needed_by":"F4 codingharness contract draft","lean":"None recorded — cache read/write dominate token volume; a model ignoring them is wrong"},{"id":"codingharness README Q-cleanroom","question":"How does the real harness run hermetically (--bare/--safe-mode, explicit --system-prompt, pinned --model) so runs are reproducible and the agent only sees the Spec's context (evidence information-barrier, 02 §2)?","category":"architecture","blocks":"F4 reproducibility; evidence information-barrier","needed_by":"F4 codingharness contract draft","lean":"None recorded — CLI auto-loaded ambient CLAUDE.md/skills, inflating cost"},{"id":"codingharness README Q-failure-tax","question":"How does the adapter map result.subtype failure classes (error_max_turns, error_during_execution, …) onto the errors pattern's typed Kinds so gates and retries can branch?","category":"contract","blocks":"F4 failure handling; gate/retry branching","needed_by":"F4 codingharness contract draft","lean":"None recorded — spike collapses these to a boolean"},{"id":"codingharness README Q-schema-drift","question":"What pins the CLI version and a conformance suite over the event stream (05 §6), given the event schema is a moving target (rate_limit_event is evidence)?","category":"architecture","blocks":"F4 decoder robustness; conformance suite (05 §6)","needed_by":"F4 codingharness contract draft","lean":"None recorded — baseline is a forward-compatible loose decoder + pinned-and-tested CLI version"},{"id":"codingharness README Q-auth","question":"How does the real adapter inject short-lived scoped tokens via the secrets port (05 §4) so credentials never reach agent context or the transcript?","category":"architecture","blocks":"F4 credential security","needed_by":"F4 codingharness contract draft","lean":"None recorded — spike inherited ambient env auth, which the real adapter must change"},{"id":"codingharness README Q-redaction","question":"What redaction-on-capture and observability plane-(b) storage path applies before transcripts (which may capture secrets in tool results) are persisted?","category":"architecture","blocks":"F4 transcript persistence; plane-(b) storage","needed_by":"F4 codingharness contract draft","lean":"None recorded — transcripts are first-class objects but may capture secrets"},{"id":"design-brief 🔶 visual-language","question":"What palette, type scale, and surface treatment does Eden's visual language commit to (deliberately left OPEN pending research note 04, with design_system_reference null)?","category":"product","blocks":"the F6 design-system artifact the brief will inform; photosphere re-founding (ties to OD-1)","needed_by":"after research note 04 lands and OD-1 is ruled","lean":"🔶 Deliberately open in v1 — the brief fixes the experience (Ableton density, dual-altitude, first-class docs/diagrams), not the look; design_system_reference stays null until OD-1 rules and the F6 artifact exists"},{"id":"04 §6 routing-economics","question":"Does the spec-driven economics bet hold — strong model authors specs / cheap model fills templates (think→strongest, default/background→cheap), and do archetype×stage cost estimates converge?","category":"kernel","blocks":"the cost/routing economics that justify the agentconfiguration routing split; wizard cost-range estimates","needed_by":"validated by kernel self-construction instrumentation (09 §7 cost model calibrated on the kernel's own build)","lean":"🔶 Unproven but instrumented to be tested — metered from run 1; the kernel's own construction calibrates the cost model"}];

// ── section 6 data: the why-map (artifact | why | depended_on_by | flag) ────────
const WHY_MAP = [{"artifact":"docs/architecture/README.md","why":"The canonical index of the architecture set: owns reading order (00-11), the epistemic legend (✅🔶⚠️🧩), the external-corpus source registry, the cohesion contract (one concept one home), and Eden invariants E1-E7. Self-classed as canonical-spec (docs/README §1).","depended_on_by":"CLAUDE.md (read-before-acting), every architecture doc (cites legend/registry/cohesion table), every contributor.","flag":"OK."},{"artifact":"docs/architecture/00-charter.md","why":"Canonical home for what Eden is, theses T1-T8, scope, non-goals — the WHY the whole platform exists, grounded in Bender's 15 failure modes and the 'discipline layer' thesis (corpus doc 00).","depended_on_by":"01 principles (P-rows cite theses), 03 (Bender modes), every downstream doc; the root README is a précis of it.","flag":"OK."},{"artifact":"docs/architecture/01-principles.md","why":"Canonical home for P1-P13, each with statement/implication/enforcement-mechanism/provenance — turns theses into enforceable commitments naming the lint/gate that checks them.","depended_on_by":"Invariants E1-E7 (each E-row = a P-row), contracts/, 03-11 cite principles by id.","flag":"OK."},{"artifact":"docs/architecture/02-domain-model.md","why":"Canonical home for entity definitions and schema ownership (Project, Cell, Spec, Evidence, Gate, Connector, Drift, Swarm, FileLease...) — the shared vocabulary so other docs cite-never-redefine; conceptual source for libs/protocols wire types.","depended_on_by":"03 (subsystems own entities), 04 (phase artifacts), 05 (connector anatomy), 11 (document tiers map to entities).","flag":"OK."},{"artifact":"docs/architecture/03-system-decomposition.md","why":"Canonical home for subsystems S1-S10, dependency rules, repo/deployment mapping, and the compact in-repo list of Bender's 15 failure modes — answers 'what are the parts and what may import what'.","depended_on_by":"05 (families map to S3), 06 (ladder builds S-slices), 08/09 (S-team ownership); the Bender list is cited set-wide.","flag":"OK."},{"artifact":"docs/architecture/04-process-model.md","why":"Canonical home for the Eden SDLC: the 10-phase spine instantiated per cell, phase-artifact schemas, gate policy (auto/approve/edit), swarm semantics, token budgets — the operational core of thesis T2 ('the SDLC is the product').","depended_on_by":"06 ladder, 08 testing, 09 workstreams, 11 (records emitted per phase), schemas/ (E2 hard schemas promised here).","flag":"OK."},{"artifact":"docs/architecture/05-connector-model.md","why":"Canonical home for connector anatomy (7 parts), families F1-F6, capability manifests, conformance, drift detection — P1/E1 made mechanical (everything external behind a contract).","depended_on_by":"03 (S3 framework), 07 (credential profiles), ADR-0008/0012/0013 (F4/F1/F2 rulings), poc/agents (F4 donor).","flag":"OK."},{"artifact":"docs/architecture/06-dogfooding-bootstrap.md","why":"Canonical home for the L0-L4 bootstrap ladder and migration/update model — operationalizes T5/P11/E5 ('Eden builds Eden'); decision basis ADR-0007. The sequencing proof that gates the whole build.","depended_on_by":"09 build plan (WS map onto rungs), ADR-0007, the L1 50-task inventory that poc/knowledge rules informed.","flag":"OK."},{"artifact":"docs/architecture/07-security-model.md","why":"Canonical home for the threat model, credential vaulting (never-in-agent-context), agent sandboxing, clean-room verification, supply chain, tenancy, audit — defends the 'crown jewels' (user cloud credentials) and the reward-hacking surface.","depended_on_by":"contracts/secrets.md (un-printable Secret type), 08 (clean-room evidence P3), 02 (Credential entity).","flag":"OK."},{"artifact":"docs/architecture/08-testing-strategy.md","why":"Canonical home for the three test layers, conformance suites, evidence-quality instruments (mutation/spec-determinacy), and agent evals — addresses Bender mode 5 (quadratic test-compute) as a planned subsystem, not a convention.","depended_on_by":"05 (conformance suites), poc/knowledge (cited as the live eval harness for §4), 10 (testing pattern).","flag":"OK."},{"artifact":"docs/architecture/09-build-execution-plan.md","why":"Canonical home for workstreams WS1-WS5, the interface-negotiation protocol, worktree/merge discipline, milestones — how Eden is actually built with Claude while rehearsing the practices L1+ will automate. Named in CLAUDE.md as the current-workstreams reference.","depended_on_by":"contracts/ (the §4 step-1/2 artifacts), poc/codingharness (the §7 spike), WS-tagged work across the repo.","flag":"OK."},{"artifact":"docs/architecture/10-library-system.md","why":"Canonical home for the pattern catalogue, HNS-1 full-naming law, environment≠platform axes (P6), folder architecture, dev→release→adopt lifecycle, and the library manifest — migrated/absorbed from the root /LIBRARY-SYSTEM.md + /LIBRARIES.md (ADR-0010), keeping §1-§9 numbers so '10 §N' citations resolve.","depended_on_by":"contracts/ (all six patterns), ADR-0009 (rulings A-F), P5/P6/P12, libs/ submodule structure.","flag":"OK. Absorption of the two root docs is complete (originals in attic); the start-of-session git status showing them as untracked is stale (commit d9a4fc4 resolved it)."},{"artifact":"docs/architecture/11-project-document-system.md","why":"Canonical home for document tiers (P→A→I), identifier/link grammar, the envelope, dual-surface canonical form, traceability rules T1-T7 — invariant E2 made concrete (the hard schemas 04 §4 promised); decision basis ADR-0011.","depended_on_by":"schemas/document/v1/ (the schemas), tools/documentvalidator (enforces T1-T7), documents/ (eden as project #1), 04 (phase records).","flag":"OK."},{"artifact":"docs/architecture/open-decisions.md","why":"The living register of unruled forks (OD-1…OD-13) with options+recommendation+needed-by, plus a Resolved table mapping rulings to ADRs — the single home for the only blocking human-interaction pattern (P13). Keeps decisions out of prose.","depended_on_by":"Every 🧩 tag awaiting a ruling; ADRs cite the OD they resolve (e.g. 0013 resolves OD-5, 0012 rides OD-13).","flag":"OK. One latent inconsistency: OD-5 is shown only in the Resolved table as RD-12/ADR-0013 but the Open table jumps OD-4→OD-13→OD-6 (OD-5 correctly absent). Cosmetic."},{"artifact":"docs/architecture/adr/0001-record-architecture-decisions.md","why":"Establishes the ADR mechanism itself — durable, append-only decision records so conversational/agent rulings don't evaporate from context windows; gives the 04 §5 approve-gate a concrete artifact.","depended_on_by":"Every subsequent ADR; the open-decisions Resolved column; CLAUDE.md hard rule 'do not re-litigate'.","flag":"OK."},{"artifact":"docs/architecture/adr/0002-rename-helios-to-eden.md","why":"Records the full Helios→Eden rename (invariant E7) — the single source for the rename's blast radius (org stays gophersys, repos/npm-scope/Go-module-roots change) and the 'historical artifacts keep their names' carve-out.","depended_on_by":"E7, every doc's Eden naming, poc/ and attic/ retention rules, ADR-0009 B (module roots).","flag":"OK. Note the rename is documented but not fully executed: poc/agents and poc/knowledge still carry github.com/helios/... module paths — intentional per the historical-artifacts carve-out, not a violation."},{"artifact":"docs/architecture/adr/0003-go-1.26-floor.md","why":"Sets Go 1.26 as the floor (supersedes corpus 1.24) and 'everything that can be Go is Go' — evidence cited from poc/knowledge's 100%-baseline-violation result on four post-cutoff rules.","depended_on_by":"All Go modules, contracts/ (errors.AsType etc.), 09 posture, poc/knowledge (the evidence).","flag":"OK."},{"artifact":"docs/architecture/adr/0004-svelte-replatform.md","why":"Rules Eden's UI is Svelte 5, a deliberate value-ruling superseding the corpus's settled React 19/React-Aria/vanilla-extract decisions — recorded with full blast radius rather than absorbed silently.","depended_on_by":"ADR-0005 (photosphere), open-decisions OD-1/2/3 (Svelte behavior/framework/state), 10 §12 (former client-lib plan now attic).","flag":"OK."},{"artifact":"docs/architecture/adr/0005-photosphere-refound-svelte.md","why":"Rules photosphere stays a standalone independently-versioned asset, re-founded on Svelte, retaining the DTCG theming engine — follows from ADR-0004 without folding the design system into the monorepo.","depended_on_by":"03 (S7), 05 (F6 design-system connector), 11 (design-brief links to it), WS4.","flag":"OK. Forward-references a separate gophersys/photosphere repo + its own ADR chain — that repo is not present in this monorepo (by design; it is external)."},{"artifact":"docs/architecture/adr/0006-local-first-hosting.md","why":"Originally ruled local-first (eden up) hosting posture so tenancy/billing aren't front-loaded before self-proof.","depended_on_by":"06 ladder, 02 (Environment/Platform entities).","flag":"Largely superseded: explicitly amended by ADR-0012 (hosted-default). Still load-bearing for the 'projects-live-with-the-user' property via BYO mode, so kept rather than atticked — correct, but a reader must follow the amendment chain."},{"artifact":"docs/architecture/adr/0007-kernel-first-bootstrap.md","why":"Rules the kernel-first ladder L0-L4 (hand-build minimal kernel, every rung builds the next) over parallel-track or platform-first-dogfood-later — the decision basis for doc 06.","depended_on_by":"06 (the ladder spec), 09 (L0 detailed), the whole build sequencing.","flag":"OK."},{"artifact":"docs/architecture/adr/0008-claude-code-first-agent-connector.md","why":"Rules Claude Code as the first F4 agent adapter (the harness Eden is built with), with pi/omp+DeepSeek committed second to prove the abstraction + supply the cheap arm — evidence from poc/knowledge's 72-run matrix and docs/research/01-02.","depended_on_by":"05 (F4 family), 06 L0 (codingharness), poc/codingharness (the de-risking spike), docs/research/00-02.","flag":"OK."},{"artifact":"docs/architecture/adr/0009-library-system-rulings.md","why":"Rules the six library-system open decisions A-F (dependencies slug, eden/libs module roots, root gitignored go.work, U1 as gated donor, bare-host, docs-first) that 10 §11 left open — Mateo delegated to architectural merit.","depended_on_by":"10 §11, contracts/ (module paths, New(configuration,dependencies) spine), poc/ donor-material rule (D), root go.work policy.","flag":"OK."},{"artifact":"docs/architecture/adr/0010-documentation-scheme.md","why":"Rules the four-class doc scheme (canonical/research/README/attic), kebab-case naming, the attic preservation policy, and the in-repo migration pass that absorbed the root SCREAMING-case planning docs into doc 10 and disabled Nx Cloud.","depended_on_by":"docs/README.md (the scheme's canonical home), attic/, CLAUDE.md (commit/doc rules, Nx-Cloud-off), every new document's placement.","flag":"OK."},{"artifact":"docs/architecture/adr/0011-document-schema-language.md","why":"Rules JSON Schema 2020-12 as the document-schema language, dual-surface canonical form (md+frontmatter / yaml → one JSON projection), and schemas/document/v1/ placement — makes E2 concrete for project documents.","depended_on_by":"schemas/document/v1/, tools/documentvalidator, 11, documents/.","flag":"OK."},{"artifact":"docs/architecture/adr/0012-compute-posture.md","why":"Amends ADR-0006 to hosted-default: clients are control surfaces, compute runs on a cluster the user points at, local k3d/kind is just another cluster, BYO encouraged — driven by founder intake C3-C7/C19 (the persona won't operate infra).","depended_on_by":"open-decisions OD-13 (fleet), 06, documents/ product tier (rides the intake), 05 F1/F3.","flag":"OK. Strong example of intake→ADR traceability."},{"artifact":"docs/architecture/adr/0013-scm-integration-modes.md","why":"Resolves OD-5: two per-project SCM modes (eden-authority default, byo-authority advanced) with per-project enforcement {enforced|advisory} and permanently-visible guarantees — driven by intake C8/C18 (advanced users keep repos on their own platforms).","depended_on_by":"05 F2, open-decisions Resolved (RD-12), documents/ product tier.","flag":"OK."},{"artifact":"docs/architecture/adr/template.md","why":"The boilerplate every ADR follows (Status/Date/Deciders/Context/Decision/Consequences) — referenced by ADR-0001 as the required format.","depended_on_by":"ADR-0001, every ADR author.","flag":"OK."},{"artifact":"docs/architecture/contracts/ (README + 6 drafts: configuration, dependencies, errors, observability, secrets, testing)","why":"The 09 §4 step-1/2 interface-negotiation artifacts for the six universal Go pattern libraries — independently-authored producer+consumer drafts reconciled into one document each, with open tensions recorded, before WS1 freezes them.","depended_on_by":"WS1/WS2 (the libs/go/<pattern> contracts they become), 10 §4 (pattern catalogue), 07 (secrets), P-row enforcement mechanisms.","flag":"OK but explicitly transient: on freeze each draft is supposed to move to attic and the real contract lands in libs/go/<pattern>. Until WS1 runs they sit in limbo — justified, not orphaned, but watch for staleness vs the eventual frozen contracts."},{"artifact":"docs/research/00-deepseek-models.md","why":"Point-in-time research note (2026-06-05) on DeepSeek V4 Pro vs Flash benchmarks/pricing/routing — promoted into routing economics (04 §6) and ADR-0008's second-adapter rationale.","depended_on_by":"04 §6, ADR-0008; class rule = cited never edited.","flag":"OK. Pre-rename wording retained by ADR-0002 policy (corrected on touch)."},{"artifact":"docs/research/01-pi-harness.md","why":"Research note on pi/oh-my-pi's extension system, RPC mode, DeepSeek integration, RLM subagents — promoted into the F4 connector design (05 §2) and ADR-0008.","depended_on_by":"05 §2, ADR-0008, poc/knowledge (omp harness).","flag":"OK."},{"artifact":"docs/research/02-agent-instrumentation.md","why":"Research note on the Go architecture for spawning/controlling coding agents in sandboxes — promoted into the F4 contract + agentconfiguration layering (05 §2, 10 §12); the design poc/agents prototypes.","depended_on_by":"05 §2, 10 §12, poc/agents (the implementation of these patterns).","flag":"OK."},{"artifact":"docs/research/03-knowledge-libraries.md","why":"Research note on the curated-knowledge-vs-priors thesis, rule schema, anti-slop mechanics, and PoC design — promoted into P7, 08 §4, and the knowledge pipeline; the design poc/knowledge implements.","depended_on_by":"P7, 08 §4, poc/knowledge (the harness + rule schema).","flag":"OK."},{"artifact":"docs/research/04-platform-ui-paradigms.md","why":"Research note (2026-06-12) on deep-tool depth/learnability, doc-as-data, diagrams-as-runtime (intake C10), onboarding, desktop/web parity, multi-altitude nav.","depended_on_by":"Nothing yet — 'Promoted into: pending' in the research README.","flag":"Not-yet-promoted: the only research note with no canonical-spec destination. Legitimate (it is recent and UI specs are still open via OD-1/2/3/10), but it is the one research artifact currently un-cited by the canon — track so it doesn't become orphaned. NOTE: doc 12 (presentation-layer) now promotes it."},{"artifact":"docs/research/README.md","why":"Operational README + index for the research-note class: maps each note to its promotion target and states the cite-never-edit / pre-rename-wording rules.","depended_on_by":"Anyone navigating research; the promotion-tracking discipline.","flag":"OK."},{"artifact":"docs/README.md","why":"Canonical home of the documentation scheme (ADR-0010): the four document classes, naming rules, generated-artifact policy, the docs/ map, and the attic log. Named in CLAUDE.md as read-before-acting.","depended_on_by":"docs/architecture/README.md, every doc's class/placement, the attic log.","flag":"OK."},{"artifact":"docs/attic/2026-06-03-helios-library-system.md + 2026-06-03-helios-library-manifest.md","why":"Verbatim preservation of the absorbed root /LIBRARY-SYSTEM.md and /LIBRARIES.md (synthesized from a 14-agent research swarm) — kept because pre-commit history cannot protect untracked work; absorption targets logged in docs/README §3.","depended_on_by":"Nothing cites them as authority (forbidden by the attic rule); they exist purely as recovery/provenance for doc 10.","flag":"OK — correctly inert by design. Not orphaned (provenance role), not citable."},{"artifact":"docs/tools/render-html.mjs","why":"Regenerates the single-file HTML reading copy of docs/architecture/ (marked-based) — the only sanctioned way to produce eden-architecture.html, which is never hand-edited.","depended_on_by":"docs/architecture/eden-architecture.html, CLAUDE.md generated-artifact rule.","flag":"OK."},{"artifact":"docs/tools/render-documents.mjs","why":"Regenerates a project's documents.html reading copy by shelling out to documentvalidator project|links|validate (never re-implementing the projection) — keeps the validator the single source of truth.","depended_on_by":"documents/documents.html, schemas/.../linkbox/documents.html, documents/README usage line.","flag":"OK. Good cohesion (delegates to the validator rather than duplicating projection logic)."},{"artifact":"docs/architecture/eden-architecture.html","why":"Generated single-file reading copy of the architecture set, for offline/at-a-glance review.","depended_on_by":"Human readers only; regenerated from the 00-11 sources via render-html.mjs.","flag":"OK. Correctly untracked and gitignored (.gitignore line 50), matching the 'gitignored, never-committed, regenerable reading copy' policy in CLAUDE.md and docs/README §1 — verified absent from git (ls-files/HEAD/log). documents.html files follow the same correct policy."},{"artifact":"schemas/document/v1/ (envelope + 10 type schemas + examples/linkbox)","why":"The hard JSON-Schema-2020-12 schemas enforcing E2 for project documents (ADR-0011); each type allOf-extends the envelope; $id is the eden://document/v1/<name> logical URI. Canonical spec = doc 11.","depended_on_by":"tools/documentvalidator (validates against them), documents/ (eden's own docs), render-documents.mjs, doc 11.","flag":"OK."},{"artifact":"schemas/document/v1/examples/linkbox/ (full P→A→I chain + adr + spec + documents.html)","why":"A complete worked-example project ('linkbox') exercising every document type and cross-tier link — serves as the validator's positive-path test fixture and the doc-11 reference instance.","depended_on_by":"tools/documentvalidator golden tests (testdata/golden/linkbox/*.json), schemas README.","flag":"OK. Note the linkbox chain is more complete than Eden's own documents/ chain (see documents/ flag)."},{"artifact":"schemas/README.md","why":"Operational README orienting schemas/: layout, $id convention, semver/migration policy, and the validation entrypoint — cites doc 11 + ADR-0011 as canon.","depended_on_by":"Schema authors, validator users.","flag":"OK."},{"artifact":"tools/documentvalidator/ (Go CLI: cmd + internal/corpus + internal/projection + testdata)","why":"The deterministic enforcement entrypoint of doc 11 §8 — validates a document corpus against the schemas (shape) and traceability rules T1-T7, emits the JSON projection, checks links — explicitly no model in the path (P8). Module github.com/gophersys/eden/tools/documentvalidator.","depended_on_by":"render-documents.mjs (shells out to it), documents/ enforcement, CI gate for the document system, schemas README.","flag":"OK. The one piece of real, tested, Eden-named Go code on the main path (golden + scenario tests present). The doc comment says 'T1-T5' while doc 11 and the README say 'T1-T7' — minor drift to reconcile."},{"artifact":"documents/ (eden's own product tier: product-charter, requirements, user-workflows, design-brief + README)","why":"Eden as project #1 of its own document system (E5): schema-validated P-tier documents whose meta.source points at the founder intake — the hand-built dogfood proving doc 11 on Eden itself.","depended_on_by":"documentvalidator (validation target), ADR-0012/0013 (which mine the same intake), doc 11 §1.","flag":"PARTIAL DOGFOOD: only the P-tier (+ design-brief) exists; the A-tier (domain-model, system-design, service-contracts) and I-tier (implementation-plan, specification) that doc 11 §2 defines and that schemas exist for are absent for Eden. The architecture lives as prose in docs/architecture/ instead of as schema-valid documents/ artifacts — a known gap (full self-hosting of the doc system is an L2 item), not an error, but worth naming."},{"artifact":"documents/intake/2026-06-12-founder-intake-01.md","why":"Verbatim, never-edited founder-intake source (typos preserved) — the provenance the product-tier meta.source spans (C1, C2, ...) point at; the raw input the intake-agent discipline (doc 11 §1) is modeled on.","depended_on_by":"All four documents/ product files, ADR-0012 (C3-C7,C19) and ADR-0013 (C8,C18) cite its C-spans.","flag":"OK. Strong provenance hygiene; still says 'helios' in the verbatim text, correctly untouched per ADR-0002."},{"artifact":"poc/agents/ (Go: agentd daemon + cpuload demo, pkg/agent transport/bridge/tools/token-tracker, embedded UI)","why":"Proves the management (dial-out-only) transport pattern and agent spawn/control/tool-dispatch/token-tracking design from docs/research/02 — donor for apps/agent and the F4 connector layer (ADR-0008).","depended_on_by":"05 §2 / F4 design, 09 WS3 (salvages its dial-out patterns), 06 L1 task inventory.","flag":"OK as donor material (ADR-0009 D: reference, don't modify in place; not on main). Module still github.com/helios/... by the historical-artifacts carve-out."},{"artifact":"poc/knowledge/ (Go eval harness: 10 oracle-backed rules, 6 temptation tasks, 4 arms, 72-run matrix on omp+DeepSeek V4 Flash, results/)","why":"Empirically validates the knowledge≠enforcement thesis (P7) and the post-cutoff-seam result (four Go 1.26 rules at ~100% baseline violation) cited by ADR-0003 and 08 §4; its rule schema + _verify/ clean-room layout feed the kernel's test-harness design.","depended_on_by":"P7, 08 §4, ADR-0003 (the 1.26 evidence), ADR-0008 (the 72-run matrix), docs/research/03, MEMORY.md note.","flag":"OK and load-bearing — the single strongest ✅-verified artifact in the repo (multiple ADRs cite its results). results/ kept as provenance; bin/ regenerable+gitignored."},{"artifact":"poc/codingharness/ (Go spike driving one headless Claude Code session, capturing transcript + token/cost ledger; sample-run/)","why":"De-risks the kernel's F4 Claude Code adapter (ADR-0008) before libs/go/codingharness is contract-drafted — the 09 §7 item-4 spike; exits non-zero on session failure so an orchestrator can branch on exit code alone.","depended_on_by":"06 L0 (codingharness), 09 §7, ADR-0008.","flag":"OK as donor material. Module is github.com/gophersys/eden/poc/codingharness (Eden-named, unlike the older two pocs — it postdates the rename)."},{"artifact":"poc/README.md","why":"Operational README declaring poc/ as donor material (ADR-0009 D): referenceable/salvageable but enters main only through gates, not renamed (ADR-0002), not modified in place; tabulates what each poc proved and feeds.","depended_on_by":"Anyone reading poc/; the donor-material discipline.","flag":"OK."},{"artifact":".ci/ (ctl.sh + providers/github/on-push|on-pr + project.json + README)","why":"Baseline CI layer inherited from gophersys/template: nx run-many/affected verbs with affected-check as the canonical PR gate; providers/ is the source of truth for CI-system shims. CLAUDE.md names 'bash .ci/ctl.sh affected-check' as the PR gate.","depended_on_by":"CLAUDE.md PR-gate rule, every project.json target, GitHub Actions.","flag":"OK but inherited template scaffolding, not Eden-authored — its README still references 'brain ecosystem' and a brain/.claude/rules path. No-ops until yarn install (per CLAUDE.md). Justified as the workspace gate; the brain-ecosystem references are seed residue."},{"artifact":"libs/ submodule (gophersys/libs: typescript/python/rust/zephyr/protocols, all .gitkeep placeholders)","why":"The shared-library submodule that ADR-0009 B makes a separate module root (github.com/gophersys/libs) precisely to force published-version consumption; the eventual home of the six frozen Go pattern contracts and libs/protocols (buf).","depended_on_by":"10 (library system), contracts/ (their freeze target), 03 S8, root gitignored go.work (ADR-0009 C).","flag":"MOSTLY EMPTY + DIRTY: every language subtree is a bare .gitkeep — no go/ subtree yet exists for the Go patterns the contracts target, and the README's partitions (python/rust/zephyr) are template-generic, not Eden's Go+Svelte reality. Submodule shows uncommitted changes ('M libs' / commit 'reduce language partitions to bare folders'). Justified as the scaffold awaiting WS1, but currently a placeholder whose README describes the brain ecosystem, not Eden."},{"artifact":"infrastructure/ submodule (gophersys/infrastructure: cloud/oracle+aws, kubernetes/, apps/codectl+fintel, docker/)","why":"Shared infrastructure submodule for the multi-cloud K3s cluster; in Eden terms the substrate an F1 adapter would target (ADR-0012's hosted cluster).","depended_on_by":"Conceptually ADR-0012 (compute posture) / 05 F1; nothing in the Eden docs cites it by path.","flag":"LARGELY UNJUSTIFIED FOR EDEN: its apps (codectl, fintel) and CLAUDE.md describe a different product ecosystem (the 'brain'/gophersys fleet), not Eden. It is template/seed inheritance carried in as a submodule; no Eden artifact depends on its specific contents. Either it becomes Eden's real F1 target (and gets Eden-relevant content) or it is seed baggage. Currently the latter."},{"artifact":".devcontainer/ submodule (gophersys/.devcontainer: base + flutter + zephyr images, .ci/, .claude/rules)","why":"Shared IDP container images giving identical local-dev and CI runtime across the gophersys ecosystem; Eden references the base image via the standard .devcontainer convention.","depended_on_by":".ci/ (runs nx affected inside these images), local dev, the CLAUDE.md submodule note.","flag":"PARTIALLY UNJUSTIFIED + DIRTY: the base image is legitimately used, but the flutter and zephyr images serve Flutter/Android and Zephyr-RTOS targets that Eden (Go + Svelte, ADR-0003/0004) has no use for — pure ecosystem-template inheritance. The submodule is dirty (m: base/ctl.sh, base/devcontainer.json uncommitted). Pin was just bumped (commit d9a4fc4) but flutter/zephyr remain Eden-irrelevant baggage."},{"artifact":"apps/.gitkeep + libs/<lang>/.gitkeep placeholders","why":"Reserve the apps/ tree (future apps/frontend, apps/desktop, apps/agent per 03 repo mapping) and the libs language subtrees so the Nx workspace + go.work paths resolve before real code lands.","depended_on_by":"ADR-0009 C (go.work spans apps/* + libs/go/*), 03 §3 repo mapping.","flag":"OK as intentional placeholders, but apps/ has only .gitkeep — none of the planned apps/frontend|desktop|agent exist yet (expected pre-L2). libs/go/ doesn't even exist as a directory yet (the contracts' freeze target)."},{"artifact":"Root workspace config (nx.json, package.json @eden/source, tsconfig.base.json, .prettier*, .editorconfig, .gitattributes, .gitmodules, README.md)","why":"The Nx + yarn-4 workspace plumbing seeded from gophersys/template and renamed to @eden/source; nx.json carries neverConnectToCloud:true per ADR-0010; .gitmodules wires the three submodules; root README is Eden's elevator pitch + rename note.","depended_on_by":"The whole build/lint/format toolchain, CLAUDE.md workspace facts, every project.json.","flag":"OK. nx.json correctly has neverConnectToCloud:true (matches ADR-0010 / CLAUDE.md). Root README honestly flags the gophersys/eden repo rename as still pending."},{"artifact":".claude/scheduled_tasks.lock","why":"Runtime lock file written by the Claude Code harness (session id, pid, acquired-at) to coordinate scheduled tasks.","depended_on_by":"The Claude Code harness only.","flag":"ORPHAN/INCIDENTAL: a tool-generated runtime artifact, not an Eden design artifact. It exists because a session produced it; arguably should be gitignored rather than tracked. No Eden doc references it."}];

// ── section 4 data: ADR timeline ────────────────────────────────────────────────
const ADR_TIMELINE = [
  { id: '0001', title: 'Record architecture decisions', status: 'Accepted', one: 'Establishes the ADR mechanism itself — durable, append-only decision records so agent/conversational rulings survive context-window loss.' },
  { id: '0002', title: 'Rename Helios → Eden', status: 'Accepted', one: 'Full rename (invariant E7); org stays gophersys; historical artifacts (poc/, attic/) keep their helios module paths by carve-out.' },
  { id: '0003', title: 'Go 1.26 floor', status: 'Accepted', one: 'Go 1.26 floor (supersedes corpus 1.24); everything that can be Go is Go — evidenced by poc/knowledge\'s post-cutoff result.' },
  { id: '0004', title: 'Svelte re-platform', status: 'Accepted', one: 'UI is Svelte 5, a deliberate value-ruling superseding the corpus\'s settled React 19 / React-Aria / vanilla-extract decisions.' },
  { id: '0005', title: 'Photosphere re-founded on Svelte', status: 'Accepted', one: 'Photosphere stays a standalone independently-versioned asset, re-founded on Svelte, retaining the DTCG theming engine. Follows ADR-0004.' },
  { id: '0006', title: 'Local-first hosting', status: 'Amended by ADR-0012', one: 'Originally ruled local-first (eden up) so tenancy/billing aren\'t front-loaded. Now amended to hosted-default; kept for the BYO "projects-live-with-the-user" property.' },
  { id: '0007', title: 'Kernel-first bootstrap', status: 'Accepted', one: 'The kernel-first ladder L0–L4 (hand-build a minimal kernel; every rung builds the next) over parallel-track or platform-first. Basis for doc 06.' },
  { id: '0008', title: 'Claude Code first agent connector', status: 'Accepted', one: 'Claude Code is the first F4 agent adapter; pi/omp+DeepSeek committed second to prove the abstraction + supply the cheap arm. Evidence: 72-run matrix.' },
  { id: '0009', title: 'Library-system rulings A–F', status: 'Accepted', one: 'Rules the six library-system open decisions (dependencies slug, eden/libs module roots, gitignored go.work, U1 gated donor, bare-host, docs-first).' },
  { id: '0010', title: 'Documentation scheme', status: 'Accepted', one: 'The four-class doc scheme (canonical / research / README / attic), kebab-case naming, attic preservation, the in-repo absorption pass, Nx-Cloud-off.' },
  { id: '0011', title: 'Document schema language', status: 'Accepted', one: 'JSON Schema 2020-12 as the document-schema language; dual-surface canonical form (md+frontmatter / yaml → one JSON projection). Makes E2 concrete.' },
  { id: '0012', title: 'Compute posture (hosted-default)', status: 'Accepted · amends ADR-0006', one: 'Amends ADR-0006 to hosted-default: clients are control surfaces; compute runs on a cluster the user points at; BYO encouraged. Driven by founder intake C3–C7/C19.' },
  { id: '0013', title: 'SCM integration modes', status: 'Accepted · resolves OD-5', one: 'Two per-project SCM modes (eden-authority default, byo-authority advanced) with per-project enforcement {enforced|advisory}. Driven by intake C8/C18.' },
  { id: '0014', title: 'Upstream consolidation + human front door', status: 'Accepted · resolves OD-8', one: 'External corpus copied verbatim into docs/upstream/ as a fifth document class; all citations repointed in-repo; root README becomes the plain-language entry layer.' },
];

// ── mermaid: section 2 system map (S1–S10 + connector families + kernel) ────────
// Edges derived from 03 §2 dependency rules. The kernel is S4 (process engine);
// the connector families F1–F6 live under S3 (connector framework).
const SYSTEM_MAP = `flowchart TB
  classDef plane fill:#eef2f7,stroke:#c3ccd8,color:#1d2129;
  classDef kernel fill:#e7efff,stroke:#7aa2ff,color:#1d2129,stroke-width:2px;
  classDef lib fill:#eef7ef,stroke:#9fcf9f,color:#1d2129;
  classDef obs fill:#fff3e6,stroke:#e8b87a,color:#1d2129;
  classDef sec fill:#fdeef0,stroke:#e09aa6,color:#1d2129;
  classDef conn fill:#f3eefb,stroke:#c3a9e8,color:#1d2129;

  S1["S1 · Control plane<br/><small>tenancy · Connect gateway · knows all</small>"]:::plane
  S4["S4 · Process engine<br/><b>the kernel</b> · 10-phase spine"]:::kernel
  S5["S5 · CI/CD engine<br/><small>executors docker→kubernetes</small>"]:::plane
  S2["S2 · Workspace service<br/><small>git · pods · remote dev</small>"]:::plane
  S3["S3 · Connector framework<br/><small>ports/adapters · conformance</small>"]:::plane
  S6["S6 · Observability<br/><small>one OTel stack · 3 planes</small>"]:::obs
  S7["S7 · Design system<br/><small>photosphere (external asset)</small>"]:::plane
  S8["S8 · Library system<br/><small>patterns · HNS-1 · knowledge libs</small>"]:::lib
  S9["S9 · FinOps<br/><small>metering · budgets · estimates</small>"]:::plane
  S10["S10 · Security<br/><small>vault · sandbox · clean-room (cross-cutting)</small>"]:::sec

  subgraph FAM["S3 · Connector families F1–F6"]
    direction LR
    F1["F1 · infrastructure"]:::conn
    F2["F2 · scm"]:::conn
    F3["F3 · billing/usage"]:::conn
    F4["F4 · agent harness"]:::conn
    F5["F5 · observability sinks"]:::conn
    F6["F6 · design system"]:::conn
  end

  S1 -->|composes all| S4
  S1 -->|composes all| S5
  S1 -->|composes all| S2
  S1 -->|composes all| S3
  S1 -->|composes all| S9

  S4 -->|workspaces / pods| S2
  S4 -->|agent + infra ports| S3
  S4 -->|templates / specs| S8

  S5 -->|executor substrates| S2
  S5 -->|executor substrates| S3
  S5 -->|gates / linters| S8

  S2 -->|infrastructure family only| S3
  S3 --- FAM

  S9 -->|usage| S3
  S9 -->|token ledger| S4

  S4 -.emits.-> S6
  S5 -.emits.-> S6
  S2 -.emits.-> S6
  S3 -.emits.-> S6
  S1 -.emits.-> S6

  S8 -.consumed by all.- S4
  S7 -.published asset.- S1

  S10 -. vault/sandbox services .- S4
  S10 -. vault/sandbox services .- S2`;

// ── mermaid: doc 12 §3 design-lens photosphere (the A2 system diagram) ──────────
// The conformance instance of doc 12: the design lens over Eden's own corpus.
// Marked as a hand-authored v0 block per the §3 bootstrap exception.
const PHOTOSPHERE = `flowchart LR
  classDef cmp fill:#e7efff,stroke:#7aa2ff,color:#1d2129;
  classDef ctr fill:#f3eefb,stroke:#c3a9e8,color:#1d2129;
  classDef ext fill:#eef7ef,stroke:#9fcf9f,color:#1d2129;

  KERNEL["CMP · process-engine<br/><small>kernel · 10-phase spine</small>"]:::cmp
  CICD["CMP · ci-cd-engine"]:::cmp
  CONN["CMP · connector-framework"]:::cmp
  DOCSYS["CMP · document-system<br/><small>validator · schemas · projection</small>"]:::cmp
  LIBSYS["CMP · library-system<br/><small>patterns · knowledge libs</small>"]:::cmp
  OBS["CMP · observability<br/><small>3-plane OTel</small>"]:::cmp

  CTRC["CTR · configuration / dependencies / errors<br/>observability / secrets / testing"]:::ctr
  HARNESS["CTR · F4 codingharness<br/><small>Claude Code adapter</small>"]:::ctr
  PHOTO["external · photosphere<br/><small>design system (S7)</small>"]:::ext

  KERNEL -->|depends_on| CONN
  KERNEL -->|depends_on| LIBSYS
  KERNEL -->|implements| CTRC
  KERNEL -->|drives| DOCSYS
  CICD -->|depends_on| CONN
  CONN -->|realizes| HARNESS
  DOCSYS -->|validates against| LIBSYS
  KERNEL -.emits.-> OBS
  CICD -.emits.-> OBS
  LIBSYS -.theming.- PHOTO`;

// ── hero nav cards (section 1) ──────────────────────────────────────────────────
// Links are relative to docs/ (the atlas lives at docs/eden-atlas.html).
const HERO = [
  { group: 'Canon', cards: [
    { title: 'Eden Architecture', href: 'architecture/eden-architecture.html', meta: 'README + 00–12 + ADR + open-decisions', why: 'The whole canonical doc set as one navigable reading surface — the A1 document altitude for Eden-the-project.' },
  ]},
  { group: 'Project Eden (dogfood #1)', cards: [
    { title: 'Project Documents', href: '../documents/documents.html', meta: 'product-charter · requirements · user-workflows · design-brief', why: 'Eden as project #1 of its own document system (E5), rendered from the validator\'s projection — the §5 reading paths in practice.' },
  ]},
  { group: 'Contracts — the six universal Go patterns', cards: [
    { title: 'contracts/ README', href: 'architecture/contracts/README.md', meta: 'interface-negotiation index', why: 'The 09 §4 step-1/2 producer+consumer reconciliation index; each draft freezes into libs/go/<pattern>.' },
    { title: 'configuration', href: 'architecture/contracts/configuration.md', meta: 'parse · merge · diagnostics', why: 'Typed configuration read surface; immutable Document, accumulate-all diagnostics.' },
    { title: 'dependencies', href: 'architecture/contracts/dependencies.md', meta: 'the Set · ports · Resolve', why: 'The composition-root currency every New spine takes; Clock/Secrets/Sink ports.' },
    { title: 'errors', href: 'architecture/contracts/errors.md', meta: 'Kind taxonomy · Wrap · redaction', why: 'Closed Kind taxonomy below the transport boundary; safe-by-default field redaction.' },
    { title: 'observability', href: 'architecture/contracts/observability.md', meta: 'Emit · Scope · 3-plane · ledger', why: 'The 5-method telemetry surface; Plane partition; the FinOps+run ledger superset.' },
    { title: 'secrets', href: 'architecture/contracts/secrets.md', meta: 'Reference · Secret · Zeroize', why: 'Un-printable Secret with defer-Zeroize wipe; scheme-routed Mediator; never in agent context.' },
    { title: 'testing', href: 'architecture/contracts/testing.md', meta: 'Suite · Harness · FakeClock', why: 'Deterministic fakes (frozen byte/timeline invariant); core avoids stdlib testing so suites mint Evidence in shipped binaries.' },
  ]},
  { group: 'Research notes', cards: [
    { title: '00 · DeepSeek models', href: 'research/00-deepseek-models.md', meta: '2026-06-05', why: 'V4 Pro vs Flash benchmarks/pricing/routing — promoted into 04 §6 routing economics + ADR-0008.' },
    { title: '01 · pi harness', href: 'research/01-pi-harness.md', meta: 'omp extension system', why: 'pi/oh-my-pi extension/RPC/DeepSeek/RLM — promoted into the F4 design (05 §2) + ADR-0008.' },
    { title: '02 · agent instrumentation', href: 'research/02-agent-instrumentation.md', meta: 'spawn/control in sandboxes', why: 'The Go architecture for controlling coding agents — promoted into the F4 contract; poc/agents prototypes it.' },
    { title: '03 · knowledge libraries', href: 'research/03-knowledge-libraries.md', meta: 'curated knowledge ≠ priors', why: 'The knowledge≠enforcement thesis + rule schema — promoted into P7, 08 §4; poc/knowledge implements it.' },
    { title: '04 · platform UI paradigms', href: 'research/04-platform-ui-paradigms.md', meta: '2026-06-12 · U1–U10', why: 'Deep-tool depth/learnability, docs-as-data, diagrams-as-runtime, multi-altitude nav — now promoted into doc 12 (this atlas\'s spec).' },
  ]},
  { group: 'Upstream corpus (verbatim · ADR-0014)', cards: [
    { title: 'Upstream corpus', href: 'upstream/agentic-engineering/README.md', meta: 'agentic-engineering/ · build-system/', why: 'The two verbatim point-in-time imports the canon cites — Bender substrate (agentic-engineering, 00–04) and the build-system thread (12 invariants, spec-driven). Helios-era naming preserved; never edited in place. See also the build-system index: upstream/build-system/README.md.' },
  ]},
  { group: 'Schemas & tools', cards: [
    { title: 'Schemas', href: '../schemas/README.md', meta: 'document/v1 · JSON Schema 2020-12', why: 'The hard schemas enforcing E2 for project documents (ADR-0011); each type allOf-extends the envelope.' },
    { title: 'Document validator', href: '../tools/documentvalidator/', meta: 'Go CLI · T1–T7 · no model in path', why: 'The deterministic doc-11 §8 enforcement entrypoint — validates shape + traceability, emits the projection.' },
  ]},
];

// ── reading paths (section 3) ────────────────────────────────────────────────────
const READING_PATHS = [
  {
    title: 'Understand Eden from zero',
    blurb: 'The intended top-to-bottom orientation through the canon — charter to presentation.',
    steps: [
      { label: 'README · doc map & legend', href: 'architecture/eden-architecture.html#d-readme' },
      { label: '00 · Charter (the WHY, T1–T8)', href: 'architecture/eden-architecture.html#d-00-charter' },
      { label: '01 · Principles (P1–P13)', href: 'architecture/eden-architecture.html#d-01-principles' },
      { label: '06 · Dogfooding & bootstrap (L0–L4)', href: 'architecture/eden-architecture.html#d-06-dogfooding-bootstrap' },
      { label: '09 · Build execution plan (WS1–WS5)', href: 'architecture/eden-architecture.html#d-09-build-execution-plan' },
      { label: '11 · Project document system', href: 'architecture/eden-architecture.html#d-11-project-document-system' },
      { label: '12 · Presentation layer (this atlas\'s spec)', href: 'architecture/12-presentation-layer.md' },
    ],
  },
  {
    title: "Mateo's review queue",
    blurb: 'The human-at-the-gate path: the dogfood product tier, the contract §7 questions awaiting a ruling, then the open questions.',
    steps: [
      { label: 'Project documents (the dogfood tier)', href: '../documents/documents.html' },
      { label: 'contracts/ README (negotiation index)', href: 'architecture/contracts/README.md' },
      { label: 'configuration §7 (9 open questions)', href: 'architecture/contracts/configuration.md#7-open-questions' },
      { label: 'dependencies §7 (6 open questions)', href: 'architecture/contracts/dependencies.md#7-open-questions' },
      { label: 'errors §7 · observability §7 · secrets §7 · testing §7', href: 'architecture/contracts/errors.md#7-open-questions' },
      { label: 'Open questions index (below)', href: '#open-questions' },
    ],
  },
  {
    title: 'Library work',
    blurb: 'The path for building the pattern libraries: the library system spec, the contracts they freeze into, then the freeze gate.',
    steps: [
      { label: '10 §1 · The pattern catalogue', href: 'architecture/eden-architecture.html#d-10-library-system' },
      { label: '10 §2–§5 · folder architecture · HNS-1 naming · environment≠platform', href: 'architecture/eden-architecture.html#d-10-library-system' },
      { label: 'contracts/ (the six freeze targets)', href: 'architecture/contracts/README.md' },
      { label: '09 §4 · the interface-negotiation protocol', href: 'architecture/eden-architecture.html#d-09-build-execution-plan' },
      { label: '09 §8 · milestones (the WS1 contract-freeze gate)', href: 'architecture/eden-architecture.html#d-09-build-execution-plan' },
    ],
  },
];

// ── altitude model (doc 12 §2 A0–A4 — the conformance ladder) ───────────────────
const ALTITUDES = [
  { id: 'A0', name: 'Organization / portfolio', entity: 'Organization, Project*', renders: 'the project grid; fleet roll-up (C17/OD-13); org-wide gate & spend roll-ups', persona: 'founder' },
  { id: 'A1', name: 'Project context', entity: 'Project, Monorepo, Environment × Platform', renders: 'the project home: maturity ladder, document set, system diagram, dashboards, gate queue', persona: 'both' },
  { id: 'A2', name: 'System', entity: 'system-design components (CMP-*)', renders: 'the photosphere diagram at depth-1 — components & connectors as a relation graph', persona: 'both' },
  { id: 'A3', name: 'Component internals / contracts', entity: 'a CMP-* and its CTR-*, depends_on edges', renders: 'component responsibility, its contracts, its documents, its drift status', persona: 'engineer' },
  { id: 'A4', name: 'Runs / transcripts / evidence', entity: 'Run, Transcript, Evidence, Observation', renders: 'the build/runtime detail: a transcript, an evidence envelope, an incident, a deployment record', persona: 'engineer' },
];

// ── build the HTML body pieces ──────────────────────────────────────────────────

// breadcrumb (doc 12 §2 — "where am I" is permanent; A0→A2 for the atlas's altitude)
const breadcrumbHtml = `
<div class="breadcrumb" aria-label="altitude breadcrumb">
  <span class="crumb global">Eden</span>
  <span class="sep">›</span>
  <span class="crumb global">A0 · Portfolio</span>
  <span class="sep">›</span>
  <span class="crumb ctx">A1 · Project: eden</span>
  <span class="sep">›</span>
  <span class="crumb ctx here">A2 · System map</span>
</div>`;

const heroHtml = HERO.map((g) => `
  <div class="hero-group">
    <div class="hero-group-title">${esc(g.group)}</div>
    <div class="cards">
      ${g.cards.map((c) => `
        <a class="card" href="${esc(c.href)}">
          <div class="card-title">${esc(c.title)}</div>
          <div class="card-meta">${esc(c.meta)}</div>
          <div class="card-why">${inline(c.why)}</div>
        </a>`).join('')}
    </div>
  </div>`).join('');

const altitudeHtml = `
<div class="tw"><table class="altitude">
  <thead><tr><th>Altitude</th><th>Name</th><th>Eden entity (02)</th><th>What renders</th><th>Persona</th></tr></thead>
  <tbody>
    ${ALTITUDES.map((a) => `<tr>
      <td><span class="alt-chip">${esc(a.id)}</span></td>
      <td>${esc(a.name)}</td>
      <td><code>${esc(a.entity)}</code></td>
      <td>${esc(a.renders)}</td>
      <td><span class="persona ${a.persona}">${esc(a.persona)}</span></td>
    </tr>`).join('')}
  </tbody>
</table></div>`;

const readingPathsHtml = READING_PATHS.map((p, i) => `
  <div class="path">
    <div class="path-head"><span class="path-num">${i + 1}</span><span class="path-title">${esc(p.title)}</span></div>
    <p class="path-blurb">${esc(p.blurb)}</p>
    <ol class="path-steps">
      ${p.steps.map((s) => `<li><a href="${esc(s.href)}">${esc(s.label)}</a></li>`).join('')}
    </ol>
  </div>`).join('');

const STATUS_CLASS = (s) => /amended|supersed/i.test(s) ? 'amended'
  : /resolves|amends/i.test(s) ? 'note' : 'accepted';

const timelineHtml = `
<ol class="timeline">
  ${ADR_TIMELINE.map((a) => `
    <li class="tl-item">
      <a class="tl-chip" href="architecture/eden-architecture.html#d-adr-${a.id}">ADR-${a.id}</a>
      <div class="tl-body">
        <div class="tl-title">${esc(a.title)} <span class="tl-status ${STATUS_CLASS(a.status)}">${esc(a.status)}</span></div>
        <div class="tl-one">${inline(a.one)}</div>
      </div>
    </li>`).join('')}
</ol>`;

// open-questions index, grouped by category
const CATEGORY_ORDER = ['contract', 'architecture', 'ui', 'product', 'process', 'kernel'];
const CATEGORY_LABEL = {
  contract: 'Contract freeze (WS1)', architecture: 'Architecture', ui: 'UI / presentation',
  product: 'Product', process: 'Process', kernel: 'Kernel economics',
};
const byCategory = new Map();
for (const q of OPEN_QUESTIONS) {
  if (!byCategory.has(q.category)) byCategory.set(q.category, []);
  byCategory.get(q.category).push(q);
}
const orderedCats = [
  ...CATEGORY_ORDER.filter((c) => byCategory.has(c)),
  ...[...byCategory.keys()].filter((c) => !CATEGORY_ORDER.includes(c)),
];
const openQuestionsHtml = orderedCats.map((cat) => {
  const items = byCategory.get(cat);
  return `
  <details class="oq-cat" open>
    <summary><span class="oq-cat-name">${esc(CATEGORY_LABEL[cat] || cat)}</span><span class="oq-count">${items.length}</span></summary>
    <div class="tw"><table class="oq">
      <thead><tr><th>ID</th><th>Question</th><th>Blocks / needed by</th><th>Lean</th></tr></thead>
      <tbody>
        ${items.map((q) => `<tr>
          <td class="oq-id"><code>${esc(q.id)}</code></td>
          <td>${inline(q.question)}</td>
          <td class="oq-meta">${inline(q.blocks)}<br><span class="oq-needed">needed by: ${inline(q.needed_by)}</span></td>
          <td class="oq-lean">${badgeFor(q.lean)}</td>
        </tr>`).join('')}
      </tbody>
    </table></div>
  </details>`;
}).join('');

// why-map: render the flag as a badge keyed off its leading word
const flagBadge = (flag) => {
  const t = String(flag).trim();
  if (/^OK\b/i.test(t)) return `<span class="badge ok">OK</span>${inline(t.replace(/^OK[.\s]*/i, ' ').trim() ? ' ' + inline(t.replace(/^OK[.:]?\s*/i, '')) : '')}`;
  if (/^INCONSISTENCY/i.test(t)) return `<span class="badge warn">INCONSISTENCY</span> ${inline(t.replace(/^INCONSISTENCY[:.\s]*/i, ''))}`;
  if (/^PARTIAL/i.test(t)) return `<span class="badge hyp">PARTIAL</span> ${inline(t.replace(/^PARTIAL[\sA-Z]*?[:.\s]/i, ''))}`;
  if (/^MOSTLY EMPTY/i.test(t)) return `<span class="badge warn">EMPTY + DIRTY</span> ${inline(t.replace(/^MOSTLY EMPTY \+ DIRTY[:.\s]*/i, ''))}`;
  if (/^LARGELY UNJUSTIFIED/i.test(t)) return `<span class="badge warn">UNJUSTIFIED</span> ${inline(t.replace(/^LARGELY UNJUSTIFIED[^:]*:\s*/i, ''))}`;
  if (/^PARTIALLY UNJUSTIFIED/i.test(t)) return `<span class="badge warn">UNJUSTIFIED + DIRTY</span> ${inline(t.replace(/^PARTIALLY UNJUSTIFIED \+ DIRTY[:.\s]*/i, ''))}`;
  if (/^ORPHAN/i.test(t)) return `<span class="badge warn">ORPHAN</span> ${inline(t.replace(/^ORPHAN\/INCIDENTAL[:.\s]*/i, ''))}`;
  if (/^Not-yet-promoted/i.test(t)) return `<span class="badge hyp">NOT-YET-PROMOTED</span> ${inline(t.replace(/^Not-yet-promoted[:.\s]*/i, ''))}`;
  if (/^Largely superseded/i.test(t)) return `<span class="badge hyp">SUPERSEDED</span> ${inline(t.replace(/^Largely superseded[:.\s]*/i, ''))}`;
  return inline(t);
};

const whyMapHtml = `
<div class="tw"><table class="whymap">
  <thead><tr><th>Artifact</th><th>Why it exists</th><th>Depended on by</th><th>Status</th></tr></thead>
  <tbody>
    ${WHY_MAP.map((w) => `<tr>
      <td class="wm-art"><code>${esc(w.artifact)}</code></td>
      <td class="wm-why">${inline(w.why)}</td>
      <td class="wm-dep">${inline(w.depended_on_by)}</td>
      <td class="wm-flag">${flagBadge(w.flag)}</td>
    </tr>`).join('')}
  </tbody>
</table></div>`;

// ── nav (sticky sidebar) ────────────────────────────────────────────────────────
const NAV = [
  { id: 'hero', chip: '1', label: 'Corpus map' },
  { id: 'altitude', chip: 'IA', label: 'Altitude model (A0–A4)' },
  { id: 'system-map', chip: '2', label: 'System map (S1–S10)' },
  { id: 'photosphere', chip: '§3', label: 'Photosphere (design lens)' },
  { id: 'reading-paths', chip: '3', label: 'Reading paths' },
  { id: 'timeline', chip: '4', label: 'Decisions timeline' },
  { id: 'open-questions', chip: '5', label: 'Open questions' },
  { id: 'why-map', chip: '6', label: 'Why-map' },
];
const navHtml = NAV.map((n) =>
  `<li><a href="#${n.id}"><span class="nchip">${esc(n.chip)}</span>${esc(n.label)}</a></li>`).join('');

// ── styles (reuses render-html.mjs's palette + variables) ───────────────────────
const css = `
:root{
  --bg:#ffffff; --fg:#1d2129; --muted:#5b6472; --line:#e3e6ea; --accent:#2563eb;
  --chipbg:#eef2f7; --codebg:#f5f6f8; --quote:#f7f8fa; --navbg:#fafbfc; --th:#f0f2f5;
  --card:#ffffff; --cardhover:#f6f9ff;
  --ok-bg:#e6f4ea; --ok-fg:#1f7a3d; --hyp-bg:#fff4e0; --hyp-fg:#9a6300;
  --warn-bg:#fdeaea; --warn-fg:#b3261e; --design-bg:#f0eafb; --design-fg:#6c3fb0;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#15171b; --fg:#e6e8ec; --muted:#9aa3b0; --line:#2a2e35; --accent:#7aa2ff;
    --chipbg:#23272e; --codebg:#1e2126; --quote:#1b1e23; --navbg:#191c20; --th:#20242a;
    --card:#1b1e23; --cardhover:#1f2530;
    --ok-bg:#173524; --ok-fg:#76d39a; --hyp-bg:#3a2c12; --hyp-fg:#e8c07a;
    --warn-bg:#3a1d1d; --warn-fg:#f0a3a0; --design-bg:#2c2440; --design-fg:#c7a9f0;
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--bg); color:var(--fg);
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif;
  font-size:16px; line-height:1.65; display:flex;
}
nav{
  width:280px; min-width:280px; height:100vh; position:sticky; top:0; overflow-y:auto;
  background:var(--navbg); border-right:1px solid var(--line); padding:1.2rem .9rem 3rem;
}
nav .title{font-weight:700; font-size:1.05rem; margin:0 0 .15rem .35rem}
nav .sub{font-size:.74rem; color:var(--muted); margin:0 0 1rem .35rem}
nav ol{list-style:none; margin:0; padding:0}
nav li{margin:.12rem 0}
nav a{display:block; color:var(--fg); text-decoration:none; padding:.34rem .45rem; border-radius:6px; font-size:.9rem}
nav a:hover{background:var(--chipbg)}
nav .nchip{
  display:inline-block; min-width:2.1rem; text-align:center; margin-right:.55rem;
  background:var(--chipbg); color:var(--muted); border-radius:5px;
  font-size:.66rem; font-weight:700; padding:.1rem .3rem; vertical-align:1px;
}
nav .legend{margin:1.4rem .35rem 0; font-size:.72rem; color:var(--muted); line-height:1.9}
nav .legend .badge{margin-right:.3rem}
main{flex:1; min-width:0; padding:2rem 3rem 6rem; max-width:1180px}
.banner{font-size:.82rem; color:var(--muted); border:1px solid var(--line); border-radius:8px; padding:.7rem 1rem; margin-bottom:1.2rem; background:var(--navbg)}
.banner code{font-size:.92em}
h1{font-size:1.85rem; line-height:1.2; margin:.2rem 0 .3rem; letter-spacing:-.02em}
.lede{color:var(--muted); font-size:1rem; margin:0 0 1.2rem; max-width:70ch}
section{border-top:3px solid var(--line); margin-top:2.8rem; padding-top:1.5rem; scroll-margin-top:1rem}
section:first-of-type{border-top:none; margin-top:.6rem; padding-top:0}
.sec-chip{
  display:inline-block; background:var(--chipbg); color:var(--muted); font-weight:700;
  font-size:.68rem; letter-spacing:.06em; border-radius:6px; padding:.16rem .5rem; margin-bottom:.5rem;
}
h2{font-size:1.4rem; margin:.1rem 0 .4rem; letter-spacing:-.015em}
.sec-blurb{color:var(--muted); font-size:.92rem; margin:.1rem 0 1.2rem; max-width:80ch}
a{color:var(--accent)}
code{font-family:"SF Mono",ui-monospace,Menlo,Consolas,monospace; font-size:.84em; background:var(--codebg); border-radius:4px; padding:.1em .35em}

/* breadcrumb (doc 12 §2) */
.breadcrumb{font-size:.82rem; margin:0 0 1.2rem; display:flex; flex-wrap:wrap; align-items:center; gap:.1rem}
.crumb{padding:.16rem .5rem; border-radius:6px; font-weight:600}
.crumb.global{background:var(--chipbg); color:var(--muted)}
.crumb.ctx{background:var(--ok-bg); color:var(--ok-fg)}
.crumb.here{outline:2px solid var(--accent); outline-offset:0}
.breadcrumb .sep{color:var(--muted); padding:0 .25rem}

/* badges */
.badge{display:inline-block; font-size:.66rem; font-weight:700; letter-spacing:.02em; padding:.1rem .42rem; border-radius:5px; vertical-align:1px; white-space:nowrap}
.badge.ok{background:var(--ok-bg); color:var(--ok-fg)}
.badge.hyp{background:var(--hyp-bg); color:var(--hyp-fg)}
.badge.warn{background:var(--warn-bg); color:var(--warn-fg)}
.badge.design{background:var(--design-bg); color:var(--design-fg)}

/* hero cards */
.hero-group{margin:0 0 1.4rem}
.hero-group-title{font-size:.74rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin:0 0 .6rem}
.cards{display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:.8rem}
.card{
  display:block; text-decoration:none; color:var(--fg); background:var(--card);
  border:1px solid var(--line); border-radius:10px; padding:.85rem 1rem; transition:background .12s,border-color .12s;
}
.card:hover{background:var(--cardhover); border-color:var(--accent)}
.card-title{font-weight:650; font-size:.98rem; margin-bottom:.1rem}
.card-meta{font-size:.74rem; color:var(--accent); margin-bottom:.45rem; font-family:"SF Mono",ui-monospace,Menlo,monospace}
.card-why{font-size:.84rem; color:var(--muted); line-height:1.5}

/* tables */
.tw{overflow-x:auto; margin:1rem 0; border:1px solid var(--line); border-radius:8px}
table{border-collapse:collapse; width:100%; font-size:.85rem; line-height:1.5}
th,td{padding:.5rem .7rem; text-align:left; vertical-align:top; border-bottom:1px solid var(--line)}
th{background:var(--th); font-size:.76rem; letter-spacing:.02em; position:sticky; top:0}
tr:last-child td{border-bottom:none}
table.altitude code{white-space:nowrap}
.alt-chip{display:inline-block; background:var(--design-bg); color:var(--design-fg); font-weight:700; font-size:.78rem; border-radius:6px; padding:.16rem .5rem}
.persona{display:inline-block; font-size:.7rem; font-weight:600; border-radius:5px; padding:.1rem .42rem; background:var(--chipbg); color:var(--muted)}
.persona.founder{background:var(--hyp-bg); color:var(--hyp-fg)}
.persona.engineer{background:var(--ok-bg); color:var(--ok-fg)}

/* mermaid */
.diagram{border:1px solid var(--line); border-radius:10px; padding:1.2rem; background:var(--navbg); overflow-x:auto; text-align:center}
.diagram svg{max-width:100%; height:auto}
.v0-note{font-size:.78rem; color:var(--muted); margin:.6rem 0 0; padding:.5rem .8rem; border-left:3px solid var(--accent); background:var(--quote); border-radius:0 6px 6px 0}

/* reading paths */
.paths{display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:1rem}
.path{border:1px solid var(--line); border-radius:10px; padding:1rem 1.1rem; background:var(--card)}
.path-head{display:flex; align-items:center; gap:.6rem; margin-bottom:.3rem}
.path-num{display:inline-flex; align-items:center; justify-content:center; width:1.5rem; height:1.5rem; border-radius:50%; background:var(--accent); color:#fff; font-weight:700; font-size:.8rem}
.path-title{font-weight:650; font-size:1rem}
.path-blurb{font-size:.82rem; color:var(--muted); margin:.2rem 0 .7rem}
.path-steps{margin:0; padding-left:1.3rem; font-size:.86rem}
.path-steps li{margin:.32rem 0}

/* timeline */
.timeline{list-style:none; margin:0; padding:0}
.tl-item{display:flex; gap:.9rem; padding:.7rem 0; border-bottom:1px solid var(--line)}
.tl-item:last-child{border-bottom:none}
.tl-chip{flex:0 0 auto; align-self:flex-start; text-decoration:none; font-weight:700; font-size:.74rem; padding:.22rem .5rem; border-radius:6px; background:var(--chipbg); color:var(--accent); white-space:nowrap}
.tl-title{font-weight:600; font-size:.95rem; margin-bottom:.15rem}
.tl-status{display:inline-block; font-size:.66rem; font-weight:700; padding:.08rem .4rem; border-radius:5px; vertical-align:1px; margin-left:.3rem}
.tl-status.accepted{background:var(--ok-bg); color:var(--ok-fg)}
.tl-status.amended{background:var(--hyp-bg); color:var(--hyp-fg)}
.tl-status.note{background:var(--design-bg); color:var(--design-fg)}
.tl-one{font-size:.86rem; color:var(--muted); line-height:1.5}

/* open questions */
.oq-cat{margin:0 0 .8rem; border:1px solid var(--line); border-radius:8px; overflow:hidden}
.oq-cat summary{cursor:pointer; padding:.6rem .9rem; font-weight:650; font-size:.92rem; background:var(--navbg); display:flex; align-items:center; gap:.5rem; user-select:none}
.oq-cat summary::-webkit-details-marker{display:none}
.oq-cat summary::before{content:"▸"; color:var(--muted); transition:transform .15s}
.oq-cat[open] summary::before{transform:rotate(90deg)}
.oq-count{margin-left:auto; font-size:.72rem; font-weight:700; color:var(--muted); background:var(--chipbg); border-radius:10px; padding:.06rem .5rem}
.oq-cat .tw{margin:0; border:none; border-top:1px solid var(--line); border-radius:0}
.oq-id code{white-space:nowrap; font-size:.78em}
.oq-meta{font-size:.78rem; color:var(--muted); max-width:24ch}
.oq-needed{color:var(--accent); font-size:.92em}
.oq-lean{max-width:34ch}

/* why-map */
.whymap{font-size:.82rem}
.wm-art code{font-size:.74em; white-space:normal; word-break:break-word}
.wm-art{max-width:18ch}
.wm-why{max-width:42ch; color:var(--fg)}
.wm-dep{max-width:26ch; color:var(--muted); font-size:.96em}
.wm-flag{max-width:30ch; font-size:.96em}

@media (max-width: 980px){
  body{flex-direction:column}
  nav{position:static; width:auto; height:auto; min-width:0; border-right:none; border-bottom:1px solid var(--line)}
  main{padding:1.4rem 1.2rem 4rem}
}
@media print{ nav{display:none} main{max-width:none; padding:0} }
`;

// ── assemble the page ───────────────────────────────────────────────────────────
const page = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eden Atlas — unified consumption entry point</title>
<style>${css}</style>
</head>
<body>
<nav>
  <p class="title">Eden Atlas</p>
  <p class="sub">v0 · generated ${GENERATED} · doc 12 §7 conformance instance</p>
  <ol>${navHtml}</ol>
  <div class="legend">
    <span class="badge ok">✅</span> verified<br>
    <span class="badge hyp">🔶</span> hypothesis<br>
    <span class="badge warn">⚠️</span> corrected<br>
    <span class="badge design">🧩</span> design choice
  </div>
</nav>
<main>
${breadcrumbHtml}
<h1>Eden Atlas</h1>
<p class="lede">The unified entry point into Eden's corpus — the v0 conformance instance of <a href="architecture/12-presentation-layer.md">doc 12 §7</a>. It implements the altitude model (§2), the breadcrumb, and the design-lens photosphere (§3) over Eden's own architecture, and indexes every corpus a reader can descend into. Consumption is navigation, not reading order.</p>
<div class="banner">Generated by <code>docs/tools/render-atlas.mjs</code> from the corpus — never hand-edited (CLAUDE.md hard rule). The architecture markdown stays the source of truth; this is a derived reading surface. Build/runtime diagram lenses are stubbed at v0 (Eden-the-project has no live telemetry plane yet).</div>

<section id="hero">
  <div class="sec-chip">1 · HERO NAV</div>
  <h2>The corpus map</h2>
  <p class="sec-blurb">Every corpus a reader can descend into, with a one-line reason each exists. Canon and the project's own product tier lead; the six pattern contracts, the research notes, and the schemas/tools follow.</p>
  ${heroHtml}
</section>

<section id="altitude">
  <div class="sec-chip">IA · ALTITUDE MODEL</div>
  <h2>A0–A4 — the navigation ladder (doc 12 §2)</h2>
  <p class="sec-blurb">The C4-inspired altitude ladder mapped onto Eden's own entities. Navigation is altitude moves: descending = clicking a node to its detail; ascending = the breadcrumb above. This atlas sits at A1→A2 for Eden-the-project. The ladder is a relation graph, not a tree.</p>
  ${altitudeHtml}
</section>

<section id="system-map">
  <div class="sec-chip">2 · SYSTEM MAP</div>
  <h2>Subsystems S1–S10, the kernel, and the connector families</h2>
  <p class="sec-blurb">An overview of the ten subsystems (03 §1) with edges derived from the 03 §2 dependency rules. The kernel is S4 (process engine); the connector families F1–F6 live under S3. Solid edges are imports; dotted edges are emits-to / consumed-by / cross-cutting.</p>
  <div class="diagram"><pre class="mermaid">${esc(SYSTEM_MAP)}</pre></div>
</section>

<section id="photosphere">
  <div class="sec-chip">§3 · DESIGN LENS</div>
  <h2>The photosphere diagram — Eden's components at depth-1</h2>
  <p class="sec-blurb">The A2 system diagram in the <strong>design lens</strong> (doc 12 §3): intended components (CMP), their contracts (CTR), and dependency/realization edges over Eden's own architecture. The build and runtime lenses are stubbed at v0.</p>
  <div class="diagram"><pre class="mermaid">${esc(PHOTOSPHERE)}</pre></div>
  <p class="v0-note"><!-- to-be-generated: projection of system-design CMP-* --> <span class="badge design">🧩</span> v0 bootstrap exception (doc 12 §3): this is a hand-authored mermaid block, not yet a projection of an owned system-design artifact. Diagram-from-projection is a standing renderer obligation; this block is a TODO against it.</p>
</section>

<section id="reading-paths">
  <div class="sec-chip">3 · READING PATHS</div>
  <h2>Three guided paths</h2>
  <p class="sec-blurb">Ordered entry sequences by intent. The canon links open the single-file architecture reading copy at the right anchor; contract and project links open their own files.</p>
  <div class="paths">${readingPathsHtml}</div>
</section>

<section id="timeline">
  <div class="sec-chip">4 · DECISIONS TIMELINE</div>
  <h2>ADR-0001 … 0014</h2>
  <p class="sec-blurb">The append-only decision record, one line each with status. Follow the amendment chain: ADR-0006 (local-first) is amended by ADR-0012 (hosted-default); ADR-0013 resolves OD-5. Each chip opens the full ADR.</p>
  ${timelineHtml}
</section>

<section id="open-questions">
  <div class="sec-chip">5 · OPEN QUESTIONS</div>
  <h2>Index — snapshot ${GENERATED}</h2>
  <p class="sec-blurb">A <strong>derived view</strong>: the canonical homes own these questions (open-decisions.md, each doc's §-open, each contract's §7). This is a generated snapshot as of ${GENERATED}, grouped by category — when an answer is needed, consult the canonical home, not this table. ${OPEN_QUESTIONS.length} questions across ${orderedCats.length} categories.</p>
  ${openQuestionsHtml}
</section>

<section id="why-map">
  <div class="sec-chip">6 · WHY-MAP</div>
  <h2>Every artifact: why it exists, what depends on it, and its status</h2>
  <p class="sec-blurb">The dependency-and-justification map across the whole repo. Status badges flag the few artifacts that are inconsistent, partial, or seed baggage; everything else is OK.</p>
  ${whyMapHtml}
</section>

</main>
<script>${mermaidBundle}</script>
<script>
  (function () {
    var dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    mermaid.initialize({
      startOnLoad: true,
      theme: dark ? 'dark' : 'neutral',
      securityLevel: 'loose',
      flowchart: { htmlLabels: true, curve: 'basis' },
      themeVariables: { fontFamily: '-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Inter,sans-serif' }
    });
  })();
</script>
</body>
</html>`;

writeFileSync(OUT, page);
console.log(`wrote ${OUT} (${(page.length / 1024).toFixed(0)} KB) — ${OPEN_QUESTIONS.length} open questions, ${WHY_MAP.length} why-map rows, ${ADR_TIMELINE.length} ADRs`);
