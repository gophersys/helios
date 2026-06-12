# `agentcfg` — Go library architecture

A portable, harness-agnostic agent-configuration system. Compile-time emits native configs for each coding harness; runtime acts as a routing engine that any Go program can embed.

This document is the design. It's opinionated. Where it's not opinionated, it says so and explains why.

---

## 1. Design philosophy

Five rules. They drive every later decision.

1. **The IR is the product.** Everything funnels through one immutable intermediate representation. Compile and route are independent consumers of the same IR. No second source of truth.
2. **Small interfaces, deep packages.** Interface types are 2–5 methods. Implementations live in subpackages and are imported only when used. The top-level package re-exports the few types every consumer touches.
3. **Plug everything that varies.** Providers, harnesses, key resolvers, LLM clients, file emission — each behind an interface, each with a default impl, each registerable from outside the library.
4. **Errors carry structure.** Validation produces typed diagnostics, not strings. Runtime errors wrap with `%w` and expose sentinel values. No `fmt.Errorf("bad: %v", x)` at boundaries.
5. **Side effects are explicit.** Loading config, resolving keys, emitting files, calling LLMs — all take `context.Context`, all accept `io.FS` / `http.Client` / `slog.Logger` injection points, all are testable without disk or network.

The library's job ends at "given a request, here is the model and the auth headers." It does *not* operate harness CLIs, *does not* reimplement LiteLLM, *does not* try to be an agent framework. It is the layer below all of those.

---

## 2. The architecture in one diagram

```
                   ┌──────────────┐
   agents.yaml ──► │   schema     │  raw structs (mutable, parse-time)
                   └──────┬───────┘
                          │ Resolve(ctx, opts)
                          ▼
                   ┌──────────────┐
                   │      ir      │  immutable IR
                   └──┬────────┬──┘
                      │        │
            ┌─────────┘        └─────────┐
            ▼                            ▼
    ┌──────────────┐             ┌──────────────┐
    │   harness    │             │   routing    │
    │  (compile)   │             │  (runtime)   │
    └──────┬───────┘             └──────┬───────┘
           │                            │
           ▼                            ▼
       FileSet                    ResolvedModel
           │                            │
           ▼                            ▼
     write to disk              client.Call(ctx, m, req)
```

Two phases:
- **Parse + Resolve** is offline. Happens once per config-load. Produces `*ir.Resolved`.
- **Compile** is offline; **Route + Call** is online. Both read `*ir.Resolved`. The IR is safe for concurrent reads forever.

---

## 3. Package layout

```
github.com/<owner>/agentcfg/

  agentcfg.go              package agentcfg — top-level public surface
                           re-exports: Load, Resolve, Router, Client,
                           plus key types (Config, Resolved, ResolvedModel)

  schema/                  Raw types parsed from YAML.
    config.go              Config, ProviderSpec, ModelAlias, RoutingPolicy,
                           Mode, Subagent, MCPServerSpec, Rules
    parse.go               Strict YAML decode, line-number-preserving errors
    validate.go            Structural validation (refs resolve, no cycles)

  ir/                      Resolved, immutable intermediate representation.
    resolved.go            Resolved, ResolvedModel, ResolvedMode,
                           ResolvedSubagent (concrete refs, no aliases)
    accessors.go           Resolved.Provider, Resolved.Model, Resolved.Mode...

  provider/                Provider interface + factory registry.
    provider.go            interface Provider, Kind constants, Register
    auth.go                interface Auth, BearerAuth, APIKeyAuth, SigV4Auth
    anthropic/             impl
    openai/                impl
    openaicompat/          impl (catch-all for LiteLLM, vLLM, etc.)
    bedrock/               impl
    vertex/                impl
    gemini/                impl
    ollama/                impl

  key/                     Key/secret resolution.
    key.go                 interface Resolver, type Ref
    env/                   os.Getenv-backed
    onepassword/           `op run` / `op read` shell-out
    litellm/               distribute virtual keys
    chain/                 try multiple resolvers in order

  routing/                 Runtime routing policy and engine.
    routing.go             RoutingPolicy (from schema), Request, Kind
    router.go              Router struct with atomic.Pointer[ir.Resolved]

  harness/                 Harness interface + per-harness adapters.
    harness.go             interface Harness, FileSet, File, Register
    claudecode/            claude-code + .mcp.json + .claude/agents/*.md +
                           claude-code-router config emission
    aider/                 ~/.aider.conf.yml + .env + model.settings.yml
    cline/                 .clinerules/ + cline_mcp_settings.json
    roo/                   .roomodes + .roo/rules-{mode}/
    kilo/                  kilo.jsonc + .kilo/agents/*.md
    opencode/              opencode.json + agents/*.md
    crush/                 crush.json
    continueide/           ~/.continue/config.yaml ("continue" is reserved)
    goose/                 ~/.config/goose/config.yaml + recipes/*.yaml
    codex/                 ~/.codex/config.toml + profiles

  mcp/                     MCP server descriptors shared by harnesses.
    mcp.go                 Server, Transport (stdio|http|sse)

  client/                  LLM call abstraction.
    client.go              interface Client, Request, Response, Stream
    http/                  default http.Client-backed impl
    fake/                  in-memory for tests

  diag/                    Diagnostics.
    diag.go                Diagnostic, Severity, Source location
    formatter.go           human and structured (JSON) output

  cap/                     Capability matrix shared by harnesses.
    cap.go                 Capabilities struct, FeatureSet bitfield

  emit/                    File emission helpers.
    fileset.go             FileSet, File (path + content + mode + sensitive)
    write.go               atomic write, chmod, directory creation
    diff.go                diff against existing files (for CLI)

  cmd/agentcfg/            CLI binary — separate module ideally.
    main.go                agentcfg compile|validate|lint|render|route

  internal/
    yamlx/                 strict yaml.v3 wrapper, position-preserving
    template/              text/template helpers with strict mode
    testfs/                io.FS for golden-file tests

  examples/
    minimal/               smallest-possible agents.yaml + Go embed
    embed/                 embed in a larger Go service
    custom-harness/        registering a third-party harness

  testdata/
    yaml/                  inputs
    golden/                expected outputs per harness
```

**Why this shape:**
- The top-level package is small and stable. Most consumers `import "github.com/x/agentcfg"` and never touch subpackages.
- Provider impls are separate packages so importing a single library doesn't pull AWS SDK + GCP SDK + every vendor's transport. Pay only for what you use.
- Harness impls are separate packages for the same reason — a service that only targets Claude Code shouldn't compile Goose recipe templates.
- `internal/` is unstable, no semver commitment.
- `cmd/agentcfg/` is a separate binary; ideally its own go module to avoid forcing CLI deps on library consumers.

---

## 4. Top-level public surface

The 90% case lives in one package. This is what most users see.

```go
// Package agentcfg loads, validates, compiles, and routes agent configurations.
package agentcfg

import (
    "context"
    "io"

    "github.com/owner/agentcfg/client"
    "github.com/owner/agentcfg/diag"
    "github.com/owner/agentcfg/harness"
    "github.com/owner/agentcfg/ir"
    "github.com/owner/agentcfg/key"
    "github.com/owner/agentcfg/routing"
    "github.com/owner/agentcfg/schema"
)

// Re-exports — the types consumers compose with daily.
type (
    Config         = schema.Config
    Resolved       = ir.Resolved
    ResolvedModel  = ir.ResolvedModel
    Router         = routing.Router
    Client         = client.Client
    Diagnostic     = diag.Diagnostic
    Severity       = diag.Severity
    File           = harness.File
    FileSet        = harness.FileSet
    Harness        = harness.Harness
)

// LoadOption configures Load.
type LoadOption func(*loadOpts)

// Load reads and parses agents.yaml. It does NOT resolve references or
// fetch secrets — call Resolve for that.
func Load(path string, opts ...LoadOption) (*Config, error)

// LoadFS reads from an io.FS — used for embedded configs and tests.
func LoadFS(fsys fs.FS, path string, opts ...LoadOption) (*Config, error)

// ResolveOption configures Resolve.
type ResolveOption func(*resolveOpts)

// WithKeyResolver overrides the default env-based key resolver.
func WithKeyResolver(r key.Resolver) ResolveOption

// WithHTTPClient injects an http.Client (e.g. for tests or auth wrappers).
func WithHTTPClient(c *http.Client) ResolveOption

// WithProviderRegistry overrides the global provider factory registry.
func WithProviderRegistry(r *provider.Registry) ResolveOption

// Resolve dereferences aliases, builds Provider instances, validates
// cross-references, and returns an immutable IR safe for concurrent use.
func (c *Config) Resolve(ctx context.Context, opts ...ResolveOption) (*Resolved, []Diagnostic, error)

// Compile produces the native config files for a single named harness.
// To compile for many harnesses, call once per name (safe to parallelize).
func Compile(ctx context.Context, r *Resolved, harnessName string) (FileSet, []Diagnostic, error)

// CompileAll runs Compile for every registered harness, in parallel.
func CompileAll(ctx context.Context, r *Resolved) (map[string]FileSet, []Diagnostic, error)

// NewRouter constructs a runtime router from a resolved IR.
// Router supports hot-reload via Router.Reload(newResolved).
func NewRouter(r *Resolved) *Router

// NewClient constructs the default LLM client. Pass nil for default options.
func NewClient(opts ...client.Option) Client
```

End-to-end usage:

```go
cfg, err := agentcfg.Load("agents.yaml")
if err != nil { return err }

resolved, diags, err := cfg.Resolve(ctx,
    agentcfg.WithKeyResolver(env.New()),
)
if err != nil { return err }
for _, d := range diags { log.Print(d) }

// Compile-time path:
files, _, err := agentcfg.Compile(ctx, resolved, "claude-code")
files.WriteAll(ctx, "/Users/me")

// Runtime path:
router := agentcfg.NewRouter(resolved)
clt := agentcfg.NewClient()

m, err := router.Route(ctx, routing.Request{
    Kind: routing.KindThink, TokenCount: 12_000,
})
resp, err := clt.Call(ctx, m, &client.Request{Messages: msgs, Tools: tools})
```

That's the 90% case. Two function calls and a struct.

---

## 5. The IR — `ir.Resolved`

The IR is the load-bearing pivot. Design priorities, in order:

1. **Immutable after construction.** No setters, no public fields, all access via methods. Concurrent readers are guaranteed safe forever. The `Router` swaps the entire IR atomically on reload; nothing inside is ever mutated in place.
2. **Aliases dereferenced.** `mode.architect.model = "thinker"` in the YAML becomes `mode.architect.Model = ResolvedModel{Provider: anthropicProvider, ID: "claude-opus-4-7"}` in the IR. Routing and compilation never need the alias table.
3. **Auth bound at resolve time, not call time.** Secrets are fetched once, attached to each `Provider`. The runtime path doesn't touch `KeyResolver`. (Trade-off: rotating a secret requires re-resolve. That's the right trade — rotation is rare; calls are hot.)
4. **Back-reference to source `*Config` is kept** for tools that need the original YAML (CLI render, diff against existing).

```go
// Package ir holds the resolved intermediate representation.
package ir

type Resolved struct {
    // unexported; access via methods
    providers  map[string]provider.Provider
    models     map[string]ResolvedModel
    modes      map[string]ResolvedMode
    subagents  map[string]ResolvedSubagent
    routing    ResolvedRouting
    mcpServers map[string]mcp.Server
    rules      Rules
    source     *schema.Config
}

func (r *Resolved) Source() *schema.Config { return r.source }

func (r *Resolved) Provider(id string) (provider.Provider, bool)
func (r *Resolved) Providers() iter.Seq2[string, provider.Provider]

func (r *Resolved) Model(alias string) (ResolvedModel, bool)
func (r *Resolved) Models() iter.Seq2[string, ResolvedModel]

func (r *Resolved) Mode(name string) (ResolvedMode, bool)
func (r *Resolved) Subagent(name string) (ResolvedSubagent, bool)

func (r *Resolved) Routing() ResolvedRouting
func (r *Resolved) MCPServer(id string) (mcp.Server, bool)

type ResolvedModel struct {
    Alias        string
    Provider     provider.Provider
    ID           string                  // concrete model ID at the provider
    Capabilities []string                // tool_use, cache, longctx_2m, etc.
}

type ResolvedMode struct {
    Name         string
    Model        ResolvedModel
    Description  string
    Tools        []string                // grants: read, edit, command, web, mcp:<server>
    RulesDir     string                  // relative path
    EditPathGlob []string
}

type ResolvedSubagent struct {
    Name         string
    Model        ResolvedModel
    Description  string
    Tools        []string
    MCPServers   []string                // by id; servers themselves live in Resolved
    PromptFile   string
    Isolation    bool                    // isolated context from parent
    Permissions  Permissions
}

type ResolvedRouting struct {
    Default              string          // alias name
    Background           string
    Think                string
    LongContext          string
    LongContextThreshold int
    WebSearch            string
}
```

Important: `ResolvedModel` carries `Provider` by interface, not by ID. The caller never re-looks-up — they have everything needed for the call.

---

## 6. Provider abstraction

A Provider is "I can speak to model X over wire Y, with auth Z." That's it.

```go
package provider

type Provider interface {
    // ID returns the user-defined ID from the YAML.
    ID() string

    // Kind tells consumers which API shape this provider speaks.
    Kind() Kind

    // BaseURL is the root endpoint, no trailing slash.
    BaseURL() string

    // Auth returns the auth strategy bound at resolve time.
    Auth() Auth
}

type Kind string

const (
    KindAnthropic     Kind = "anthropic"
    KindOpenAI        Kind = "openai"
    KindOpenAICompat  Kind = "openai-compat"
    KindBedrock       Kind = "bedrock"
    KindVertex        Kind = "vertex"
    KindGemini        Kind = "gemini"
    KindOllama        Kind = "ollama"
)

// Auth applies authentication to an outbound HTTP request.
type Auth interface {
    Apply(ctx context.Context, req *http.Request) error
}

// Factory constructs a Provider from a schema spec.
type Factory func(schema.ProviderSpec, key.Resolver) (Provider, error)

// Registry holds Factory functions by Kind. The zero value is unusable;
// use DefaultRegistry or NewRegistry.
type Registry struct { ... }

func (r *Registry) Register(k Kind, f Factory)
func (r *Registry) Build(spec schema.ProviderSpec, kr key.Resolver) (Provider, error)

var DefaultRegistry = NewRegistry()
```

Each impl is its own subpackage. Anthropic:

```go
package anthropic

import "github.com/owner/agentcfg/provider"

func init() {
    provider.DefaultRegistry.Register(provider.KindAnthropic, New)
}

func New(spec schema.ProviderSpec, kr key.Resolver) (provider.Provider, error) {
    apiKey, err := kr.Resolve(context.Background(), key.Ref{EnvVar: spec.APIKeyEnv})
    if err != nil { return nil, fmt.Errorf("anthropic: resolve key: %w", err) }
    return &anthropicProvider{
        id:      spec.ID,
        baseURL: cmp.Or(spec.BaseURL, "https://api.anthropic.com"),
        auth:    apiKeyAuth{header: "x-api-key", value: apiKey},
    }, nil
}

type anthropicProvider struct {
    id      string
    baseURL string
    auth    provider.Auth
}

func (p *anthropicProvider) ID() string             { return p.id }
func (p *anthropicProvider) Kind() provider.Kind    { return provider.KindAnthropic }
func (p *anthropicProvider) BaseURL() string        { return p.baseURL }
func (p *anthropicProvider) Auth() provider.Auth    { return p.auth }
```

**Why this is right:** the `Provider` interface is tiny. Different APIs (chat-completions vs messages vs gemini's `generateContent`) live in `client/`, where they belong. `Provider` just answers "where do I post?" and "what header do I add?" — not "how do I format the body?"

---

## 7. Harness abstraction

A Harness is "I know how to translate a `Resolved` into native files for one tool."

```go
package harness

type Harness interface {
    // Name is the stable ID — "claude-code", "aider", "kilo", etc.
    Name() string

    // Capabilities reports what the harness supports.
    Capabilities() cap.Capabilities

    // Compile produces the file set for this harness.
    // Diagnostics describe schema features the harness can't express
    // (e.g. Crush can't express subagents) — these are warnings, not errors.
    Compile(ctx context.Context, r *ir.Resolved) (FileSet, []diag.Diagnostic, error)
}

// File is one output file.
type File struct {
    Path      string      // absolute or project-relative; harness decides
    Content   []byte
    Mode      os.FileMode // 0644 default, 0600 for sensitive
    Sensitive bool        // implies 0600 and skip diff display
}

// FileSet bundles output for one Compile call.
type FileSet struct {
    Harness string
    Files   []File
}

// WriteAll writes every file under root, creating directories.
// Existing files are overwritten atomically. Symlinks are rejected.
func (fs FileSet) WriteAll(ctx context.Context, root string) error

// Diff returns a unified diff against existing files at root.
func (fs FileSet) Diff(root string) ([]Diff, error)

// Registry holds harness implementations by name.
type Registry struct { ... }
func (r *Registry) Register(h Harness)
func (r *Registry) Get(name string) (Harness, bool)
func (r *Registry) All() iter.Seq2[string, Harness]

var DefaultRegistry = NewRegistry()
```

A harness impl uses `text/template` or struct marshaling internally — it's an implementation detail, not part of the interface.

Claude Code's harness is the most complex because it emits three artifacts (`settings.json`, per-subagent markdown files, optional CCR config):

```go
package claudecode

import "github.com/owner/agentcfg/harness"

func init() {
    harness.DefaultRegistry.Register(New())
}

type Harness struct {
    // options: emit-ccr-config, project-root, etc.
}

func New(opts ...Option) *Harness { ... }

func (h *Harness) Name() string { return "claude-code" }

func (h *Harness) Capabilities() cap.Capabilities {
    return cap.Capabilities{
        Routing:           cap.RoutingFull,        // via CCR
        Modes:             cap.ModesViaSubagents,
        Subagents:         cap.SubagentsBuggy,     // bug #44385
        PerSubagentMCP:    cap.MCPAdditiveOnly,    // #24054
        EnvInterpolation:  true,
    }
}

func (h *Harness) Compile(ctx context.Context, r *ir.Resolved) (harness.FileSet, []diag.Diagnostic, error) {
    var fs harness.FileSet
    fs.Harness = h.Name()

    settings, err := h.renderSettings(r)
    if err != nil { return fs, nil, fmt.Errorf("settings.json: %w", err) }
    fs.Files = append(fs.Files, harness.File{
        Path: ".claude/settings.json", Content: settings, Mode: 0o644,
    })

    for name, sa := range r.subagentsSeq() {
        md, err := h.renderSubagent(r, name, sa)
        if err != nil { return fs, nil, fmt.Errorf("subagent %s: %w", name, err) }
        fs.Files = append(fs.Files, harness.File{
            Path:    fmt.Sprintf(".claude/agents/%s.md", name),
            Content: md, Mode: 0o644,
        })
    }

    if h.emitCCR {
        ccr, err := h.renderCCRConfig(r)
        if err != nil { return fs, nil, fmt.Errorf("ccr config: %w", err) }
        fs.Files = append(fs.Files, harness.File{
            Path: "~/.claude-code-router/config.json", Content: ccr, Mode: 0o600,
            Sensitive: true,
        })
    }

    diags := h.lint(r)  // emit warnings for features we couldn't express
    return fs, diags, nil
}
```

**Why this is right:** Harness implementations are completely independent. Adding a new harness — say `cursor` — is one new package, one `init()` registration. No core code change.

---

## 8. Capabilities — surface what's missing

```go
package cap

type Capabilities struct {
    Routing          RoutingSupport
    Modes            ModesSupport
    Subagents        SubagentsSupport
    PerSubagentMCP   MCPScoping
    PerModeMCP       MCPScoping
    EnvInterpolation bool
    Hooks            bool
    PromptCaching    bool
}

type RoutingSupport int
const (
    RoutingNone RoutingSupport = iota
    RoutingPlannerExecutor           // architect + editor (Aider)
    RoutingLargeSmall                 // two slots (Crush)
    RoutingFull                       // content+threshold (CCR)
)

type ModesSupport int
const (
    ModesNone ModesSupport = iota
    ModesBuiltinOnly
    ModesCustom
    ModesCustomWithPerModeModel       // Roo, Kilo
)

type SubagentsSupport int
const (
    SubagentsNone SubagentsSupport = iota
    SubagentsParentModelOnly          // Claude Code current bug; Goose subagents
    SubagentsOwnModel                 // Kilo, Goose sub-recipes, OpenCode user-defined
)

type MCPScoping int
const (
    MCPNoScoping MCPScoping = iota
    MCPServerLevel                    // Roo groups [mcp]
    MCPToolLevel                      // Kilo {server}_{tool}
    MCPAdditiveOnly                   // Claude Code — can add, can't subtract
)
```

`Resolved` carries the configured features. `Harness.Compile` emits diagnostics for any unsupported combination — e.g., Crush gets a `Severity::Warning` for every subagent in the config because Crush can't express them. The user sees what they're losing.

---

## 9. Routing engine

```go
package routing

type Router struct {
    cur atomic.Pointer[ir.Resolved]
    log *slog.Logger
}

func New(r *ir.Resolved, opts ...Option) *Router

// Reload swaps the IR atomically. In-flight Routes continue with the
// old IR; new Routes use the new one.
func (r *Router) Reload(next *ir.Resolved)

type Request struct {
    Kind       Kind
    TokenCount int
    Mode       string
    Subagent   string
    Tags       []string
}

type Kind string
const (
    KindDefault     Kind = "default"
    KindBackground  Kind = "background"
    KindThink       Kind = "think"
    KindLongContext Kind = "longContext"
    KindWebSearch   Kind = "webSearch"
)

func (r *Router) Route(ctx context.Context, req Request) (ir.ResolvedModel, error)
```

Routing rules, in priority order — codified once, lives in `routing.go`:

```go
func (r *Router) Route(ctx context.Context, req Request) (ir.ResolvedModel, error) {
    res := r.cur.Load()
    if res == nil {
        return ir.ResolvedModel{}, ErrNoIR
    }

    // 1. Subagent override wins outright.
    if req.Subagent != "" {
        sa, ok := res.Subagent(req.Subagent)
        if !ok { return ir.ResolvedModel{}, fmt.Errorf("%w: %q", ErrUnknownSubagent, req.Subagent) }
        return sa.Model, nil
    }

    // 2. Mode override beats routing rules.
    if req.Mode != "" {
        m, ok := res.Mode(req.Mode)
        if !ok { return ir.ResolvedModel{}, fmt.Errorf("%w: %q", ErrUnknownMode, req.Mode) }
        return m.Model, nil
    }

    // 3. Token-count promotion to longContext.
    rp := res.Routing()
    if rp.LongContextThreshold > 0 && req.TokenCount >= rp.LongContextThreshold {
        if alias := rp.LongContext; alias != "" {
            if m, ok := res.Model(alias); ok { return m, nil }
        }
    }

    // 4. Kind-based.
    switch req.Kind {
    case KindBackground:  return resolveAlias(res, rp.Background, rp.Default)
    case KindThink:       return resolveAlias(res, rp.Think, rp.Default)
    case KindLongContext: return resolveAlias(res, rp.LongContext, rp.Default)
    case KindWebSearch:   return resolveAlias(res, rp.WebSearch, rp.Default)
    }
    return resolveAlias(res, rp.Default)
}
```

**Hot reload:** the router never holds locks during routing; it loads an atomic pointer once per call. Reload is one atomic store. Eventually-consistent across in-flight calls is exactly what you want.

---

## 10. Client — the LLM call layer

```go
package client

type Client interface {
    Call(ctx context.Context, m ir.ResolvedModel, req *Request) (*Response, error)
    Stream(ctx context.Context, m ir.ResolvedModel, req *Request) (Stream, error)
}

type Request struct {
    Messages   []Message
    Tools      []Tool
    System     string
    MaxTokens  int
    Stop       []string
    // Provider-specific knobs are namespaced and ignored by providers that don't know them.
    ProviderExt map[string]any
}

type Response struct {
    Content     []ContentPart       // text | tool_use | thinking
    StopReason  StopReason
    Usage       Usage
    RawProvider json.RawMessage     // for debugging
}

type Stream interface {
    Next(ctx context.Context) (Event, bool, error)
    Close() error
}
```

The default impl chooses the wire format from `m.Provider.Kind()` — Anthropic Messages, OpenAI Chat Completions, Gemini `generateContent`, etc. Each is a sealed translation that runs in the package; the public API is unified.

**Important non-goal:** this is not a streaming-tool-call-prompt-cache normalization layer. If you need that, route Claude Code through itself for cache, or stand up LiteLLM as an `openai-compat` provider and let *it* handle normalization. `client` is the bare wire.

---

## 11. Key resolution

```go
package key

type Resolver interface {
    Resolve(ctx context.Context, ref Ref) (string, error)
}

type Ref struct {
    EnvVar string  // primary path — most things are env vars
    OP     string  // op://Vault/Item/credential
    Vault  string  // HashiCorp Vault path
    // Future: Doppler, Infisical, AWS Secrets Manager, etc.
}

// Chain tries resolvers in order, returns the first that succeeds.
type Chain []Resolver

func (c Chain) Resolve(ctx context.Context, ref Ref) (string, error)
```

Implementations:

- `env.New()` — `os.Getenv` plus optional `.env` file
- `onepassword.New(opts...)` — shells out to `op read` and caches
- `litellm.New(masterKey, base)` — generates and rotates virtual keys
- `vault.New(client, path)` — HashiCorp Vault

The default `Chain` is `env` only. Users opt into anything that touches network.

```go
resolver := chain.New(
    onepassword.New(),    // try 1Password first
    env.New(),            // fall back to env vars
)
resolved, _, err := cfg.Resolve(ctx, agentcfg.WithKeyResolver(resolver))
```

---

## 12. Schema — parse strictly, error precisely

```go
package schema

type Config struct {
    Version    int                          `yaml:"version"`
    Metadata   Metadata                     `yaml:"metadata"`
    Providers  map[string]ProviderSpec      `yaml:"providers"`
    Models     map[string]ModelAlias        `yaml:"models"`
    Routing    RoutingPolicy                `yaml:"routing"`
    Modes      map[string]Mode              `yaml:"modes"`
    Subagents  map[string]Subagent          `yaml:"subagents"`
    MCPServers map[string]MCPServerSpec     `yaml:"mcp_servers"`
    Rules      Rules                        `yaml:"rules"`
}

type ProviderSpec struct {
    ID         string  `yaml:"-"`            // populated from map key
    Type       string  `yaml:"type"`
    BaseURL    string  `yaml:"base_url"`
    APIKeyEnv  string  `yaml:"api_key_env"`
}

type ModelAlias struct {
    Alias        string   `yaml:"-"`
    Provider     string   `yaml:"provider"`
    ID           string   `yaml:"id"`
    Capabilities []string `yaml:"capabilities"`
}

// ... etc.
```

Parsing rules:
- Use `gopkg.in/yaml.v3` in strict mode (`KnownFields(true)`) — typos become errors with line numbers, not silent drops. **Verified caveat (2026-06-01):** `KnownFields` does reject unknown fields, but yaml.v3's `TypeError` only exposes `Errors []string` with line numbers embedded in the *message text*, not as structured fields. To deliver the structured `Location{Line, Column}` that §13 promises, decode into a `yaml.Node` first (it carries `.Line`/`.Column`) and validate against the node tree — `KnownFields` alone is not enough. This belongs in `internal/yamlx`.
- `Validate()` is a separate phase. Returns `[]diag.Diagnostic`, not error, because partial configs should still surface multiple problems at once.

```go
func Parse(r io.Reader) (*Config, error)
func (c *Config) Validate() []diag.Diagnostic
```

Validate runs:
1. All `model.provider` refs resolve in `providers`.
2. All routing aliases resolve in `models`.
3. All subagent `model` refs resolve in `models`.
4. All `mcp_servers` referenced from subagents/modes exist.
5. No cycles in subagent → tools → mcp_server → tool references.
6. `LongContextThreshold` ≥ 0 if `LongContext` is set.

---

## 13. Diagnostics

```go
package diag

type Diagnostic struct {
    Severity   Severity
    Code       string     // stable identifier, e.g. "AC1042"
    Field      string     // dotted path, e.g. "modes.architect.model"
    Message    string
    Location   Location   // line, column from YAML decoder
    Workaround string     // optional — for known harness limitations
}

type Severity int

const (
    SeverityInfo Severity = iota
    SeverityWarning
    SeverityError
)

type Location struct {
    File   string
    Line   int
    Column int
}
```

Two output formatters:

```go
func Format(diags []Diagnostic) string             // human-readable
func FormatJSON(diags []Diagnostic) ([]byte, error) // for CI / tooling
```

Codes follow a stable namespace: `AC1xxx` schema, `AC2xxx` resolve, `AC3xxx` harness, `AC4xxx` routing.

---

## 14. Compile-time walkthrough

```go
package main

import (
    "context"
    "log/slog"
    "os"

    "github.com/owner/agentcfg"
    _ "github.com/owner/agentcfg/harness/aider"
    _ "github.com/owner/agentcfg/harness/claudecode"
    _ "github.com/owner/agentcfg/harness/kilo"
    _ "github.com/owner/agentcfg/harness/opencode"
    _ "github.com/owner/agentcfg/provider/anthropic"
    _ "github.com/owner/agentcfg/provider/openaicompat"
    "github.com/owner/agentcfg/key/env"
)

func main() {
    ctx := context.Background()

    cfg, err := agentcfg.Load("agents.yaml")
    must(err)

    resolved, diags, err := cfg.Resolve(ctx, agentcfg.WithKeyResolver(env.New()))
    must(err)
    reportDiags(diags)

    targets := []string{"claude-code", "aider", "kilo", "opencode"}
    for _, t := range targets {
        files, diags, err := agentcfg.Compile(ctx, resolved, t)
        must(err)
        reportDiags(diags)

        out := filepath.Join("./out", t)
        must(files.WriteAll(ctx, out))
        slog.Info("compiled", "harness", t, "files", len(files.Files), "out", out)
    }
}
```

Blank imports register provider and harness factories with the default registries. Removing one blank import drops that harness from the binary — pay only for what you use.

---

## 15. Runtime walkthrough

```go
package agentapp

import (
    "context"

    "github.com/owner/agentcfg"
    "github.com/owner/agentcfg/client"
    "github.com/owner/agentcfg/ir"
    "github.com/owner/agentcfg/routing"
)

type AgentLoop struct {
    router *agentcfg.Router
    client agentcfg.Client
}

func New(resolved *ir.Resolved) *AgentLoop {
    return &AgentLoop{
        router: agentcfg.NewRouter(resolved),
        client: agentcfg.NewClient(),
    }
}

// HotReload swaps the IR atomically; in-flight calls finish on the old one.
func (a *AgentLoop) HotReload(r *ir.Resolved) { a.router.Reload(r) }

func (a *AgentLoop) Step(ctx context.Context, turn Turn) (*client.Response, error) {
    req := routing.Request{
        Kind:       turn.Kind,        // KindDefault, KindThink, KindBackground...
        TokenCount: turn.EstimatedTokens,
        Mode:       turn.Mode,
        Subagent:   turn.Subagent,
    }
    m, err := a.router.Route(ctx, req)
    if err != nil { return nil, err }

    return a.client.Call(ctx, m, &client.Request{
        Messages: turn.Messages,
        Tools:    turn.Tools,
        System:   turn.System,
    })
}
```

Embedding this in a larger system is two structs and a method. Replace `agentcfg.Client` with a fake for tests; replace `Router` with a fixed-model `nullRouter` for unit work.

---

## 16. Concurrency contract

- `*schema.Config` — mutable until `Validate` returns; treat as read-only afterward.
- `*ir.Resolved` — fully immutable after `Resolve` returns. Concurrent reads are safe forever.
- `*routing.Router` — concurrent-safe. Loads IR via atomic pointer per call. Reload is atomic.
- `*harness.Registry` and `*provider.Registry` — safe to register during init, do not mutate after `Resolve` runs.
- `Harness.Compile` — must be pure. Library calls it concurrently via `CompileAll`.
- `Provider` impls — must be safe for concurrent reads of `BaseURL`, `Kind`, `Auth`.
- `Auth.Apply` — must be safe for concurrent calls; impls may cache (e.g., SigV4 derives keys lazily) but must guard with their own mu.
- `key.Resolver` — must be safe for concurrent calls. Impls should cache (env is free; 1Password is not).
- `Client.Call` and `Client.Stream` — concurrent-safe. Default impl uses one `*http.Client` (which is itself concurrent-safe).

**Hot reload pattern (canonical):**

```go
// Worker that reloads on SIGHUP
sig := make(chan os.Signal, 1)
signal.Notify(sig, syscall.SIGHUP)
for range sig {
    cfg, err := agentcfg.Load("agents.yaml")
    if err != nil { slog.Error("reload: parse", "err", err); continue }
    next, _, err := cfg.Resolve(ctx, opts...)
    if err != nil { slog.Error("reload: resolve", "err", err); continue }
    router.Reload(next)
    slog.Info("reloaded")
}
```

---

## 17. Testing strategy

Three layers:

1. **Unit tests per package.** Schema parse round-trips; routing rules table-driven; provider builders use a `fakeKeyResolver`.
2. **Golden-file harness tests.** Each harness package has `testdata/yaml/*.yaml` inputs and `testdata/golden/<harness>/...` outputs. Compile, diff, fail with `-update` flag to refresh.
3. **Cross-harness integration test.** One canonical `examples/minimal/agents.yaml` compiles cleanly for every registered harness. Catches accidental schema additions that break adapters.

Test infrastructure lives in `internal/testfs` (io.FS over an in-memory tree) and `client/fake` (deterministic LLM responses).

```go
func TestKiloCompile(t *testing.T) {
    cases := loadGoldenCases(t, "testdata/yaml")
    for _, tc := range cases {
        t.Run(tc.Name, func(t *testing.T) {
            cfg := mustParse(t, tc.Input)
            r, _, err := cfg.Resolve(t.Context(), agentcfg.WithKeyResolver(fakeKeys{}))
            require.NoError(t, err)
            files, _, err := agentcfg.Compile(t.Context(), r, "kilo")
            require.NoError(t, err)
            assertGoldenFileSet(t, files, "testdata/golden/kilo/"+tc.Name)
        })
    }
}
```

---

## 18. Versioning and stability

- Module path: `github.com/<owner>/agentcfg/v1`.
- The top-level `agentcfg` package is **API-stable** within v1. Adding parameters to existing functions = new major. Adding new functions = minor.
- Subpackages: stable interfaces, **may add new methods to interfaces via optional interface upgrade pattern**:
  ```go
  type Harness interface { ... }
  // Optional: implement if you need per-file post-processing
  type FilePostProcessor interface {
      Harness
      PostProcess(File) (File, error)
  }
  ```
  Consumers type-assert: `if pp, ok := h.(FilePostProcessor); ok { ... }`.
- `internal/` is unstable. No promises.
- Schema is versioned independently (`version: 1` in YAML). Bumping the schema is a major bump unless backwards-compatible.

---

## 19. What's *not* in this library

Deliberate non-goals. The library is small because these are someone else's problem:

- **No harness CLI invocation.** We configure harnesses. The user runs them. (Calling `claude-code` from Go is shelling out, has nothing to do with config.)
- **No tool-call normalization across providers.** Anthropic XML vs OpenAI JSON vs Gemini protobuf-shaped — `client/` does the raw wire; full normalization is what LiteLLM exists for.
- **No prompt cache management.** Provider-specific; we forward `cache_control` on the Anthropic path and leave the rest alone.
- **No streaming-event normalization.** SSE/JSONL/grpc differ per provider; we expose a typed `Event` per call but don't pretend they're identical.
- **No tracing/observability framework.** We emit `slog` events at standard points. Plug in `slog`-compatible handlers (Tempo, Honeycomb, Datadog) yourself.
- **No agent framework.** No tool-loop, no scratchpad, no skills. This is the layer below your agent loop.

If you need any of those, layer them on top. They don't belong in the config layer.

---

## 20. Open questions / decisions to make

The design is opinionated where evidence is clear and explicit where it isn't:

1. **CLI shape.** Should `cmd/agentcfg` be a separate Go module to avoid forcing CLI deps (cobra, pflag) onto library consumers? My vote: yes. Two `go.mod`s in one repo, library is the root.
2. **YAML library.** `gopkg.in/yaml.v3` is the default; `go.yaml.in/yaml/v4` (the YAML-org-maintained fork; v1–v3 are frozen/security-only) **is confirmed to exist but is at release-candidate stage as of 2026-06-01** — adopt when it ships stable. Strict mode mandatory either way.
3. **Generic provider config.** Today `ProviderSpec` is one struct for all kinds. Some kinds (Bedrock, Vertex) want extra fields (region, project). Either (a) add optional fields and document which kinds use which, or (b) use `extra: map[string]any` for kind-specific extension. My vote: (a) for the top half-dozen well-known fields, (b) for everything else.
4. **Plugin model for harnesses.** Compile-time blank-import vs runtime go-plugin vs separate process via gRPC. My vote: compile-time blank-import only. `go-plugin` is brittle; gRPC is way out of scope for v1.
5. **Per-call key rotation.** Today auth is bound at resolve time. Some setups want per-call refresh (short-lived STS tokens). Option: `Auth` impls can implement a `Refresh(ctx)` method, called opportunistically by `client`. Add in v1.1 if needed.
6. **MCP server proxy.** Should the library know how to *start* MCP servers (run `npx -y @modelcontextprotocol/server-github`)? My vote: no. The library declares what should run; running it is the harness's job or the embedding system's.
7. **Content-based routing.** v1 is request-type + token-count. Content routing (regex / classifier match the prompt) is real but specialized. Decide: ship in v1.1 with a `Predicate` interface, or never. My vote: v1.1 — keep v1 simple.

---

## 21. Naming and module bootstrap

```
# go.mod
module github.com/<owner>/agentcfg

go 1.24                       # 1.24 floor (verified 2026-06-01): t.Context() in tests (§17)
                              # is 1.24+. iter (1.23), cmp.Or (1.22), atomic.Pointer (1.19) are
                              # all covered. The doc previously said 1.23 — that does not compile.

require (
    gopkg.in/yaml.v3 v3.0.1
)
```

Suggested names — pick one:
- `agentcfg` (descriptive, no marketing)
- `helios/agentcfg` (if it lives inside your Helios system as a submodule)
- `forge` (short, evocative; risk of collision)
- `loom` (weaving harnesses + models)

My pick: `agentcfg`. It says what it does. Three syllables. Easy to grep.

---

## 22. What ships in v0.1

Smallest viable cut to validate the design before committing to the full matrix:

- `schema` + `ir` + `agentcfg` top-level — load/resolve works
- `provider/anthropic` + `provider/openai` + `provider/openaicompat` — covers ~80% of providers
- `key/env` + `key/chain` — only environment-based secrets
- `harness/claudecode` + `harness/aider` + `harness/kilo` — three harnesses, each representative of a category (Claude Code = routing-heavy, Aider = planner/executor, Kilo = mode+subagent)
- `routing.Router` with token-count + kind dispatch
- `client/http` for Anthropic + OpenAI wire formats
- `diag` for validation output
- Golden-file tests for the three harnesses
- One `examples/embed` showing the full loop

v0.2 adds the remaining harnesses + Bedrock/Vertex providers. v0.3 adds 1Password resolver + LiteLLM virtual key support. v1.0 freezes the public API.

---

## 23. The one-line summary

A `Resolved` IR sits between a strict schema and a small set of plug-in interfaces. Compile-time harnesses translate it to native files; a runtime router picks models from it per-request; everything else is `context.Context`, `io.FS`, `http.Client`, and `slog`.

---

## 24. Verification status (2026-06-01)

Parallel-agent verification of the Go and ecosystem claims. The design is technically sound and idiomatic; the corrections below are applied inline above.

**Confirmed.** `iter.Seq2` (Go 1.23) · `atomic.Pointer[T]` (1.19) and the lock-free hot-swap reasoning · `cmp.Or` (1.22) · yaml.v3 `KnownFields(true)` strict mode · registry + blank-import `init()` self-registration (stdlib precedent: `database/sql` drivers, `image/png|jpeg|gif`) · optional-interface-upgrade via type assertion (precedent: `io.Copy`→`WriterTo`, `http.Flusher/Hijacker`) · immutable-IR concurrency (sound, given construction-only population and no post-`Resolve` map writes) · LiteLLM exposing `/v1/messages` (Anthropic unified + pass-through) · claude-code-router's `Providers`+`Router` (default/background/think/longContext/longContextThreshold/webSearch) shape.

**Corrected (applied above).**
- **Go floor `1.23` → `1.24`.** `t.Context()` in §17 tests is 1.24+; 1.23 would not compile.
- **`atomic.Pointer[*ir.Resolved]` → `atomic.Pointer[ir.Resolved]`** in the §3 package layout (a double-pointer typo; §9's struct was already correct).
- **Structured `Location{Line,Column}` is not free from `KnownFields`** — decode to `yaml.Node` (§12 caveat).
- **`go.yaml.in/yaml/v4` confirmed to exist** (RC stage), §20 hedge updated.

**Highest-risk open decision (unchanged, flagged).** The two-`go.mod` split (root library + `cmd/agentcfg` submodule, §20.1). Supported, but the decision most likely to cause ongoing tooling friction (nested-module tags, `replace` juggling, CI complexity). Note: library *importers* only pull `cobra`/`pflag` into their module graph if an *imported* package depends on them — so simply keeping CLI deps inside `cmd/` may suffice without a second module. Re-examine before committing.

**Not load-bearing for this library.** None of the model-landscape benchmark numbers affect this design — the library is model-agnostic; per-model data (price, context window, dialect, tool-call-parser, caching) is editable config, not code.
