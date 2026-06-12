# AI Agent Instrumentation — Go Integration Architecture

> Research date: June 5, 2026

## Goal

Build Go libraries under `~/helios/go/ai/agents/` to programmatically spin up and control coding agents (pi, Claude Code, Codex) inside sandbox environments as part of a software factory. The agents work from a known SDK of core libraries and principles, with a pre-programmed SDLC pipeline.

## Architecture Overview

```
helios/go/ai/agents/
├── config/           # Agent configuration as code
│   ├── agent.go      # AgentConfig: model, tools, skills, prompts, cwd, sandbox
│   ├── skill.go      # Skill definition + discovery
│   ├── rules.go      # AGENTS.md / CLAUDE.md conventions
│   └── pipeline.go   # SDLC pipeline stages (plan, impl, review, verify)
├── credentials/      # API key management
│   ├── creds.go      # CredentialStore: env vars, vault, auth.json
│   └── provider.go   # Provider-specific auth (Anthropic, OpenAI, DeepSeek)
├── pi/               # Pi-specific integration
│   ├── client.go     # Pi RPC client (stdin/stdout JSONL)
│   ├── types.go      # RPC message types (events, commands, responses)
│   └── session.go    # Session lifecycle (create, prompt, fork, compact)
├── claude/           # Claude Code integration
│   └── client.go
├── codex/            # Codex CLI integration
│   └── client.go
├── sandbox/          # Sandbox isolation
│   ├── docker.go     # Docker-based sandbox
│   ├── e2b.go        # E2B cloud sandbox
│   └── local.go      # Local process sandbox
├── transport/        # Communication protocols
│   ├── rpc.go        # pi RPC (stdin/stdout JSONL)
│   ├── http.go       # HTTP/SSE (for Sandbox Agent SDK)
│   └── stdio.go      # Generic stdio JSON-RPC
├── sdlc/             # Software factory pipeline
│   ├── pipeline.go   # Pipeline runner
│   ├── planner.go    # Planning agent
│   ├── implementer.go # Implementation agents (parallel)
│   ├── reviewer.go   # Review agent
│   └── verifier.go   # Verification agent
└── orchestrator/     # Multi-agent orchestration
    ├── factory.go    # Agent factory: spawn configured agents
    └── router.go     # Model router: Flash for routine, Pro for complex
```

## Integration Approaches

### Approach 1: pi RPC Mode (Direct Subprocess — Best for pi)

pi supports `--mode rpc` — JSONL over stdin/stdout. Language-agnostic. Go can spawn `pi --mode rpc` as a subprocess and communicate via stdin/stdout pipes.

**Protocol:** Newline-delimited JSON records. Commands in, responses + events out.

```go
// pi/client.go — simplified
type PiClient struct {
    cmd    *exec.Cmd
    stdin  io.WriteCloser
    stdout *bufio.Scanner
    // channel-based event streaming
    events chan PiEvent
}

func NewPiClient(config PiConfig) (*PiClient, error) {
    cmd := exec.Command("pi",
        "--mode", "rpc",
        "--model", config.Model,
        "--no-session", // or provide session path
    )
    cmd.Dir = config.WorkingDir

    stdin, _ := cmd.StdinPipe()
    stdout, _ := cmd.StdoutPipe()
    cmd.Start()

    return &PiClient{
        cmd:    cmd,
        stdin:  stdin,
        stdout: bufio.NewScanner(stdout),
        events: make(chan PiEvent, 100),
    }, nil
}

func (c *PiClient) Prompt(msg string, images []Image) error {
    cmd := map[string]any{
        "type":    "prompt",
        "message": msg,
    }
    if len(images) > 0 {
        cmd["images"] = images
    }
    return c.sendCommand(cmd)
}

func (c *PiClient) Steer(msg string) error {
    return c.sendCommand(map[string]any{
        "type":              "steer",
        "message":           msg,
        "streamingBehavior": "steer",
    })
}

func (c *PiClient) GetState() (AgentState, error) {
    // sends {"type": "get_state"}, reads response
}

func (c *PiClient) SetModel(provider, modelID string) error {
    return c.sendCommand(map[string]any{
        "type":    "set_model",
        "provider": provider,
        "modelId":  modelID,
    })
}

func (c *PiClient) Abort() error {
    return c.sendCommand(map[string]any{"type": "abort"})
}

func (c *PiClient) NewSession() error {
    return c.sendCommand(map[string]any{"type": "new_session"})
}

// Event loop — runs in goroutine
func (c *PiClient) readEvents() {
    for c.stdout.Scan() {
        line := c.stdout.Bytes()
        // Parse JSON, determine if response or event
        // Events: message_update, tool_execution_start/update/end,
        //         agent_start/end, turn_start/end, compaction events
        // Dispatch to channels or callbacks
    }
}
```

**RPC Event Types:**
- `message_start`, `message_update`, `message_end` — streaming text + thinking deltas
- `tool_execution_start`, `tool_execution_update`, `tool_execution_end` — tool lifecycle
- `agent_start`, `agent_end` — agent processing lifecycle
- `turn_start`, `turn_end` — single LLM response + tool calls
- `compaction_start`, `compaction_end` — automatic context compaction
- `queue_update` — steering/follow-up queue status

**RPC Commands:**
- `prompt`, `steer`, `follow_up` — message queuing
- `abort` — cancel current operation
- `new_session` — start fresh session
- `get_state`, `get_messages` — inspect current state
- `set_model`, `cycle_model`, `get_available_models` — model management
- `set_thinking_level`, `cycle_thinking_level` — reasoning control
- `set_steering_mode`, `set_follow_up_mode` — queue behavior
- `compact`, `abort_compaction` — manual compaction
- `quit` — graceful shutdown

### Approach 2: Sandbox Agent SDK (Universal — All Agents)

[Rivet's Sandbox Agent SDK](https://github.com/rivet-dev/sandbox-agent) is a Rust binary that runs inside a sandbox and exposes a universal HTTP/SSE API. One API controls Claude Code, Codex, OpenCode, Pi, Amp, and Cursor.

```go
// transport/http.go — Go client for Sandbox Agent
type SandboxClient struct {
    baseURL string
    token   string
    client  *http.Client
}

func (c *SandboxClient) CreateSession(name string, agent AgentType, mode string) (*Session, error) {
    // POST /sessions with { agent: "pi"|"codex"|"claude-code", agentMode: "default" }
}

func (c *SandboxClient) PostMessage(sessionID string, msg string) error {
    // POST /sessions/{id}/messages
}

func (c *SandboxClient) StreamEvents(sessionID string) (<-chan Event, error) {
    // SSE stream: GET /sessions/{id}/events
    // Parses universal event schema normalized across agents
}
```

**Advantage:** Write integration once, swap agent with a config change. Works with any sandbox (Docker, E2B, Daytona, Vercel).

### Approach 3: Codex CLI Wrapping (Go Community SDKs)

Three Go community SDKs already exist for Codex CLI:
- [godeps/codex-sdk-go](https://pkg.go.dev/github.com/godeps/codex-sdk-go) — CLI stdin/stdout JSONL
- [pmenglund/codex-sdk-go](https://pkg.go.dev/github.com/pmenglund/codex-sdk-go) — App-server JSON-RPC over Unix socket
- [ethpandaops/codex-agent-sdk-go](https://github.com/ethpandaops/codex-agent-sdk-go) — Auto-selecting transport

Pattern is identical to pi RPC: spawn binary, pipe JSON-RPC.

## Recommended Approach for Helios

**Layer 1: Universal Transport (`transport/`)**

Abstract communication with any agent into a common interface:

```go
type AgentTransport interface {
    Prompt(ctx context.Context, msg Message) error
    Steer(ctx context.Context, msg string) error
    StreamEvents(ctx context.Context) (<-chan AgentEvent, error)
    GetState(ctx context.Context) (AgentState, error)
    SetModel(ctx context.Context, provider, modelID string) error
    SetThinkingLevel(ctx context.Context, level string) error
    Abort(ctx context.Context) error
    NewSession(ctx context.Context) error
    Close() error
}

type AgentEvent struct {
    Type    string          // message_update, tool_execution_start, etc.
    Data    json.RawMessage // Agent-specific payload
    Agent   string          // "pi", "codex", "claude"
    Session string
}
```

Implementations:
- `transport/rpc.go` → pi RPC mode (stdin/stdout JSONL)
- `transport/http.go` → Sandbox Agent SDK (HTTP/SSE)
- `transport/codex.go` → Codex CLI SDK (godeps/codex-sdk-go)

**Layer 2: Agent Config (`config/`)**

Configuration as code — an `AgentConfig` struct that defines everything needed to spawn an agent:

```go
type AgentConfig struct {
    // Identity
    Name    string   // "planner", "implementer-1", "reviewer"
    Role    AgentRole // Planner, Explorer, Implementer, Reviewer, Verifier

    // Model
    Provider    string // "deepseek", "anthropic", "openai"
    ModelID     string // "deepseek-v4-pro", "claude-opus-4-8"
    ThinkingLevel string // "off", "medium", "high", "xhigh"

    // Environment
    WorkingDir  string   // repo checkout path
    Sandbox     SandboxConfig

    // Capabilities
    Tools       []string // ["read", "bash", "edit", "write", "grep", "web_search"]
    Skills      []Skill  // Skills to load
    Extensions  []string // Paths to extension .ts files

    // Context
    Rules       []Rule   // AGENTS.md / CLAUDE.md conventions
    SystemPrompt string  // Custom system prompt override
    AppendPrompt string  // Additional instructions

    // Session
    SessionFile string   // Path to session.jsonl for persistence
    Ephemeral   bool     // In-memory only

    // Pipeline
    Stage       SDLCStage
    Contracts   []Contract // Typed interfaces between stages
}

type AgentRole string
const (
    RolePlanner     AgentRole = "planner"
    RoleExplorer    AgentRole = "explorer"
    RoleImplementer AgentRole = "implementer"
    RoleReviewer    AgentRole = "reviewer"
    RoleVerifier    AgentRole = "verifier"
    RoleGeneral     AgentRole = "general"
)

type Rule struct {
    Path    string // AGENTS.md file path
    Content string // Or inline
}
```

**Layer 3: Agent Factory (`orchestrator/factory.go`)**

Spawn configured agents from config:

```go
type AgentFactory struct {
    credentials *credentials.Store
    sandbox     sandbox.Provider
    transport   transport.Type // "rpc", "http-sandbox-agent", "codex-sdk"
}

func (f *AgentFactory) Spawn(ctx context.Context, cfg AgentConfig) (*Agent, error) {
    // 1. Resolve credentials
    apiKey, _ := f.credentials.Get(cfg.Provider, cfg.ModelID)

    // 2. Provision sandbox (Docker container, E2B, or local)
    env, _ := f.sandbox.Provision(ctx, cfg.Sandbox)

    // 3. Write config files into sandbox
    //    - .pi/settings.json
    //    - .pi/extensions/ (or ~/.pi/agent/extensions/)
    //    - AGENTS.md (rules)
    //    - .pi/skills/ or .agents/skills/
    //    - models.json (provider config)
    env.WriteFile(".pi/AGENTS.md", cfg.buildAgentsMD())
    env.WriteFile(".pi/settings.json", cfg.buildSettings())
    env.WriteFile("models.json", cfg.buildModelsJSON(apiKey))

    // 4. Install pi if needed
    env.Exec("npm", "install", "-g", "--ignore-scripts", "@earendil-works/pi-coding-agent")

    // 5. Spawn pi in RPC mode
    transport, _ := transport.NewRPC(transport.RPCConfig{
        Binary:  "pi",
        Args:    cfg.buildPiArgs(),
        WorkDir: env.WorkDir,
    })

    return &Agent{
        Config:    cfg,
        Transport: transport,
        Env:       env,
    }, nil
}
```

**Layer 4: SDLC Pipeline (`sdlc/pipeline.go`)**

The software factory conveyor belt:

```go
type Pipeline struct {
    factory  *AgentFactory
    stages   []SDLCStage
    sdk      *SDKContext // Known core libraries, principles, conventions
}

type SDKContext struct {
    Libraries   []Library   // Core libs the agents know about
    Principles  []string    // Design principles
    Conventions []Convention // Coding conventions
    Templates   []Template   // File/project templates
    Tests       []TestPattern // Common test patterns
}

func (p *Pipeline) Run(ctx context.Context, task Task) (*PipelineResult, error) {
    // Stage 1: Plan
    planner := p.factory.Spawn(ctx, AgentConfig{
        Name: "planner",
        Role: RolePlanner,
        ModelID: "deepseek-v4-pro", // Pro for reasoning
        Tools: []string{"read", "grep", "find", "ls"},
        Rules: p.sdk.PlanningRules(),
    })
    plan, _ := planner.Prompt(ctx, task.ToPlanningPrompt(p.sdk))

    // Stage 2: Explore (parallel)
    explorers := p.spawnParallel(ctx, plan.ExplorationTasks, AgentConfig{
        Role: RoleExplorer,
        ModelID: "deepseek-v4-flash", // Flash for codebase mapping
        Tools: []string{"grep", "find", "ls", "read"},
    })

    // Stage 3: Implement (parallel, with file leases)
    implConfig := AgentConfig{
        Role: RoleImplementer,
        ModelID: "deepseek-v4-flash", // Flash for implementation
        Tools: []string{"read", "write", "edit", "bash"},
    }
    results := p.spawnWithLeases(ctx, plan.ImplementationTasks, implConfig)

    // Stage 4: Review (parallel per diff)
    reviewConfig := AgentConfig{
        Role: RoleReviewer,
        ModelID: "deepseek-v4-flash", // Flash for review
        Tools: []string{"read", "bash"}, // read-only
    }
    reviews := p.spawnParallel(ctx, results.AsReviewTasks(), reviewConfig)

    // Stage 5: Verify
    verifier := p.factory.Spawn(ctx, AgentConfig{
        Role: RoleVerifier,
        ModelID: "deepseek-v4-flash",
        Tools: []string{"bash"},
    })
    verifier.Prompt(ctx, "Run the full test suite and report results")

    return &PipelineResult{Plan: plan, Reviews: reviews}, nil
}
```

## Skills & Rules System

### Skills

Skills follow the [Agent Skills standard](https://agentskills.io/specification). A skill is a directory with `SKILL.md`:

```
skills/
├── helios-sdk/
│   ├── SKILL.md          # When and how to use the Helios SDK
│   ├── references/
│   │   └── api.md        # Full API reference (loaded on-demand)
│   └── scripts/
│       └── scaffold.sh   # Project scaffolding
├── helios-testing/
│   ├── SKILL.md
│   └── references/
│       └── patterns.md
└── helios-deployment/
    ├── SKILL.md
    └── scripts/
        └── deploy.sh
```

In Go, skills are defined as code:

```go
type Skill struct {
    Name        string
    Description string
    Path        string   // Directory containing SKILL.md
    BaseDir     string
    AllowedTools []string // Optional tool allowlist
}

// Generate from Go structs, write to sandbox before agent launch
func (s *Skill) WriteTo(dir string) error {
    // Write SKILL.md with proper frontmatter
    // Copy scripts/, references/, assets/
}
```

### Rules (AGENTS.md)

AGENTS.md files are the "constitution" for agents. They cascade from global → project → stage-specific:

```
Global:    ~/.pi/agent/AGENTS.md       (all projects)
Project:   <repo>/AGENTS.md            (project conventions)
Stage:     <sandbox>/AGENTS.md         (stage-specific, generated per agent)
```

In Go:

```go
func (cfg AgentConfig) buildAgentsMD() string {
    var sections []string

    // SDK conventions
    sections = append(sections, cfg.SDK.Conventions.ToMarkdown()...)

    // Coding rules
    sections = append(sections, "## Coding Rules", cfg.RulesContent)

    // Stage-specific instructions
    switch cfg.Role {
    case RolePlanner:
        sections = append(sections, "## Planning Instructions",
            "- Decompose the task into independent work packages",
            "- Output contracts as typed Go interfaces",
            "- Do NOT write any implementation code",
        )
    case RoleImplementer:
        sections = append(sections, "## Implementation Instructions",
            "- Write code against the provided spec contract",
            "- Follow the SDK conventions exactly",
            "- Run tests after each change",
        )
    case RoleReviewer:
        sections = append(sections, "## Review Instructions",
            "- Grade against conventions, not personal preference",
            "- Flag anti-patterns with specific references to convention docs",
            "- Do NOT edit code",
        )
    }

    return strings.Join(sections, "\n\n")
}
```

## Credential Management (`credentials/`)

```go
type CredentialStore struct {
    // Priority: runtime override > auth.json > env vars > fallback
}

type ProviderCreds struct {
    APIKey      string
    APIBase     string
    Provider    string // "deepseek", "anthropic", "openai"
}

func (s *CredentialStore) Get(provider, modelID string) (*ProviderCreds, error) {
    // 1. Check runtime overrides (set via code, not persisted)
    // 2. Check ~/.pi/agent/auth.json
    // 3. Check env vars (ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY)
    // 4. Check custom models.json fallback resolvers
}

func (s *CredentialStore) SetRuntime(provider, apiKey string) {
    // Override for this process, not persisted to disk
}
```

## Sandbox Patterns (`sandbox/`)

Three tiers of isolation:

| Tier | Implementation | Use Case |
|------|---------------|----------|
| Local process | `os/exec` with cwd isolation | Development, testing |
| Docker | Container per agent, volume mounts | CI, staging |
| Cloud sandbox | E2B, Daytona, Vercel Sandboxes | Production, untrusted code |

```go
type SandboxProvider interface {
    Provision(ctx context.Context, config SandboxConfig) (*SandboxEnv, error)
    Destroy(ctx context.Context, env *SandboxEnv) error
}

type SandboxEnv struct {
    WorkDir string   // Path inside sandbox
    TempDir string
    // For Docker: container ID
    // For E2B: sandbox ID + URL
}

// Docker implementation
func (d *DockerSandbox) Provision(ctx context.Context, cfg SandboxConfig) (*SandboxEnv, error) {
    // Create container with:
    // - Mount repo at /workspace
    // - Install pi + dependencies
    // - Write config files
    // - Set API keys as env vars
}

// The Gondolin pattern (from pi docs): keep pi + auth on host,
// route tools into a Linux micro-VM for isolation.
```

## Model Router (`orchestrator/router.go`)

Routes tasks to the right model based on complexity:

```go
type ModelRouter struct {
    models map[TaskClass]ModelSpec
}

type TaskClass string
const (
    ClassSimplePlan     TaskClass = "simple-plan"     // Flash
    ClassComplexPlan    TaskClass = "complex-plan"    // Pro
    ClassCodeGen        TaskClass = "code-gen"        // Flash
    ClassComplexRefactor TaskClass = "complex-refactor" // Pro
    ClassReview         TaskClass = "review"          // Flash
    ClassVerify         TaskClass = "verify"          // Flash
    ClassAgenticLoop    TaskClass = "agentic-loop"    // Pro
    ClassFactualQA      TaskClass = "factual-qa"      // Pro
)

func (r *ModelRouter) Route(task Task) ModelSpec {
    // ~85% Flash, ~15% Pro by token volume
    if task.EstimatedComplexity > Threshold || task.RequiresFactualAccuracy {
        return r.models[ClassComplexPlan] // deepseek-v4-pro
    }
    return r.models[ClassCodeGen] // deepseek-v4-flash
}
```

## Event Streaming & Observability

All agent events flow through a centralized event bus:

```go
type EventBus struct {
    subscribers map[string][]chan AgentEvent
}

// Events emitted:
// - agent.spawn.{agentName}         — Agent created
// - agent.prompt.{agentName}        — Prompt sent
// - agent.stream.{agentName}.delta  — Streaming text/tool output
// - agent.tool.{agentName}.{tool}   — Tool execution
// - agent.end.{agentName}           — Agent finished
// - pipeline.stage.{stage}.start    — SDLC stage begins
// - pipeline.stage.{stage}.end      — SDLC stage ends
// - pipeline.error                  — Error in pipeline

func (p *Pipeline) Run(ctx context.Context, task Task) (*PipelineResult, error) {
    p.events.Emit("pipeline.stage.plan.start", task)

    // ... run stages ...

    p.events.Emit("pipeline.stage.verify.end", result)
    return result, nil
}
```

## What to Build First

**Phase 1: Core Transport**
- `pi/client.go` — pi RPC client (stdin/stdout JSONL)
- `transport/types.go` — AgentTransport interface + event types
- Unit tests with a mock pi process

**Phase 2: Configuration**
- `config/agent.go` — AgentConfig struct + builders
- `config/rules.go` — AGENTS.md generation from Go
- `config/skill.go` — Skill definition + SKILL.md writer

**Phase 3: Credentials**
- `credentials/creds.go` — CredentialStore with env/auth.json/runtime layers
- `credentials/provider.go` — Provider-specific auth shapes

**Phase 4: Sandbox**
- `sandbox/docker.go` — Docker-based sandbox
- `sandbox/local.go` — Local process sandbox

**Phase 5: Orchestration**
- `orchestrator/factory.go` — AgentFactory: spawn from config
- `orchestrator/router.go` — Model router: Flash vs Pro

**Phase 6: SDLC Pipeline**
- `sdlc/pipeline.go` — Full SDLC conveyor belt
- `sdlc/planner.go` through `sdlc/verifier.go` — Stage-specific agents

## Key Design Decisions

1. **pi RPC as primary transport** — pi is the most extensible agent (TypeScript extensions, skills, prompt templates), has the cleanest RPC protocol, and DeepSeek officially documents it. But the `AgentTransport` interface abstracts this, so swapping to Claude Code or Codex is a config change.

2. **Configuration as Go structs, rendered to files** — Don't try to reimplement pi internals in Go. Generate the config files pi expects (models.json, settings.json, AGENTS.md, skills/), write them into the sandbox, then spawn pi in RPC mode. Go's job is orchestration, pi's job is agent execution.

3. **Sandbox per agent** — Each agent gets its own sandbox (Docker container or E2B). The factory provisions the sandbox, writes config, installs pi, and spawns the RPC process. When the agent finishes, the sandbox is destroyed (or recycled for the next agent in the same stage).

4. **File leases for parallel safety** — When multiple implementers run in parallel, each holds exclusive leases on the files it's editing. The planner assigns non-overlapping file sets. Leases are released on agent completion.

5. **Pro for planning, Flash for execution** — ~85% of token volume goes through Flash (implementers, reviewers, verifiers). Pro handles planning, complex refactors, and factual QA. The model router enforces this.

6. **SDK as the contract language** — The Helios SDK (core libraries, principles, conventions) IS the interface between stages. The planner doesn't output "make a user service" — it outputs typed Go interfaces against the SDK. The implementer codes to that contract.

## Sources

- [pi SDK Documentation](https://pi.dev/docs/latest/sdk)
- [pi RPC Mode Documentation](https://pi.dev/docs/latest/rpc) (via pi package docs)
- [pi Skills Documentation](https://pi.dev/docs/latest/skills) (via pi package docs)
- [pi Extensions Documentation](https://pi.dev/docs/latest/extensions) (via pi package docs)
- [Sandbox Agent SDK](https://sandboxagent.dev/) / [GitHub](https://github.com/rivet-dev/sandbox-agent)
- [Codex Go SDK Ecosystem](https://codex.danielvaughan.com/2026/04/25/codex-go-sdk-ecosystem-embedding-agents-in-go-applications/)
- [ASDLC Framework](https://asdlc.io/concepts/agentic-sdlc/)
- [DeepSeek-TUI Subagents & RLM](https://deepwiki.com/Hmbown/DeepSeek-TUI/5.4-sub-agents-and-rlm-(recursive-language-model))
- [DeepSeek API Docs — Pi Integration](https://api-docs.deepseek.com/quick_start/agent_integrations/pi_mono)
