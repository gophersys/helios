package gateway

import (
	"context"
	"net/http"
	"strings"

	"github.com/gophersys/libs/go/errors"
)

// This file is the PRODUCT-CONFIG surface: the wire contract for the create-flow wizard. A
// "session" IS a PRODUCT Eden builds via its 10-phase SDLC. The wizard takes the user's initial
// prompt, AI-PROPOSES a ProductConfig (POST /product/propose), the user edits it, and the edited
// spec rides POST /sessions as the optional "product" field — folded into the agent's initial
// context preamble (sessions_handler.go).
//
// The proposal itself is a CONSUMER-DEFINED port (Proposer): the live composition root binds it to
// ONE real claude/omp turn instructed to return ONLY ProductConfig JSON (liveserve); the dev
// composition root binds it to a deterministic, prompt-derived fake (devserve), so the Playwright
// E2E is stable and needs no model call. The gateway owns the wire shape, validation, and the
// sane-default fallback — never the harness.

// ProductConfig is the product specification the create-flow wizard edits: what Eden will build,
// with which stack/services/capabilities, and which SDLC phases to run. It is a redaction-safe
// value record — no field is or carries a credential (the setup-token rides the gateway's opaque
// secrets.Reference, never this DTO). Its JSON is the exact shape the SvelteKit wizard exchanges.
type ProductConfig struct {
	// ProductName is the short product name, proposed from the prompt (e.g. "invoice-service").
	ProductName string `json:"productName"`
	// ProductKind classifies the artifact: one of the ProductKind* tokens.
	ProductKind string `json:"productKind"`
	// Summary is the one-line statement of what we will build.
	Summary string `json:"summary"`
	// Stack is the language/framework selection (Eden defaults: Go 1.26 backend, Svelte 5 UI).
	Stack ProductStack `json:"stack"`
	// Services are the supporting services the product needs (e.g. "nats", "postgres", "vault").
	Services []string `json:"services"`
	// Capabilities is the agent's harness/model/tool-grant/skill/rule binding for the build.
	Capabilities ProductCapabilities `json:"capabilities"`
	// SDLCPhases is the subset of the 10-phase pipeline to run (e.g. architecture..qa).
	SDLCPhases []string `json:"sdlcPhases"`
	// Sandbox is the egress posture the build agent runs under.
	Sandbox ProductSandbox `json:"sandbox"`
}

// ProductStack is the language/framework selection of a ProductConfig.
type ProductStack struct {
	Languages  []string `json:"languages"`
	Frameworks []string `json:"frameworks"`
}

// ProductCapabilities is the agent capability binding of a ProductConfig: the harness+model the
// build runs on, the standing tool grants, and the skills/rules injected. No field is a secret.
type ProductCapabilities struct {
	Harness    string   `json:"harness"`
	Model      string   `json:"model"`
	ToolGrants []string `json:"toolGrants"`
	Skills     []string `json:"skills"`
	Rules      []string `json:"rules"`
}

// ProductSandbox is the egress posture of a ProductConfig build agent.
type ProductSandbox struct {
	Posture     string   `json:"posture"`
	EgressAllow []string `json:"egressAllow"`
}

// The ProductKind* tokens are the closed set of ProductConfig.ProductKind values. An unrecognized
// kind from a proposal falls back to ProductKindService (the Eden default build target).
const (
	ProductKindService     = "service"
	ProductKindLibrary     = "library"
	ProductKindApplication = "application"
	ProductKindCLI         = "cli"
	ProductKindUI          = "ui"
	ProductKindOther       = "other"
)

// The Harness* tokens are the closed set of ProductCapabilities.Harness values (the agentsession
// adapter keys). An unrecognized harness from a proposal falls back to HarnessClaude.
const (
	HarnessClaude = "claude"
	HarnessOMP    = "omp"
	HarnessCodex  = "codex"
)

// The Posture* tokens are the closed set of ProductSandbox.Posture values. An unrecognized posture
// from a proposal falls back to PostureStrict (default-deny — the safe default for an unattended
// build agent, 07 §3).
const (
	PostureStrict  = "strict"
	PostureRelaxed = "relaxed"
)

// Proposer is the consumer-defined port the propose route calls: it turns the user's initial
// prompt into a ProductConfig. It is the shape of the need — the gateway does not know whether the
// implementation runs a real harness turn (liveserve) or derives a deterministic fake (devserve).
// The implementation returns a best-effort ProductConfig; the gateway normalizes it to sane
// defaults so the wizard always receives a complete, valid spec (NormalizeProductConfig).
type Proposer interface {
	// Propose returns a ProductConfig derived from prompt. It returns a wrapped, classified error
	// only on an infrastructure fault (e.g. the harness is unreachable); a parse/shape failure is
	// the implementation's concern and is resolved by returning its best-effort partial config (the
	// gateway fills the gaps), not by erroring.
	Propose(ctx context.Context, prompt string) (ProductConfig, error)
}

// proposeRequest is the body of POST /product/propose: the user's initial free-text prompt.
type proposeRequest struct {
	Prompt string `json:"prompt"`
}

// handleProductPropose is the create-flow wizard's first step: from the initial prompt it
// AI-PROPOSES a ProductConfig the user then edits. It decodes {prompt}, calls the injected
// Proposer (one real claude/omp turn in liveserve; a deterministic fake in devserve), normalizes
// the result to a complete, valid spec, and returns the {data, errors, kind} envelope. When no
// Proposer is wired (a composition that does not offer the wizard), it is a 503.
func (g *Gateway) handleProductPropose(w http.ResponseWriter, r *http.Request) {
	if g.dependencies.Proposer == nil {
		g.writeEnvelopeError(w, errors.New(errors.KindUnavailable, "gateway: product propose is not configured"))
		return
	}

	var request proposeRequest
	if err := decodeJSON(r, &request); err != nil {
		g.writeEnvelopeError(w, err)
		return
	}
	if strings.TrimSpace(request.Prompt) == "" {
		g.writeEnvelopeError(w, errors.Wrap(errors.KindInvalid, "gateway: product propose",
			RequestError{Reason: "prompt is required"}))
		return
	}

	// The proposal may run a real harness turn (liveserve) — admit it under a context DERIVED from
	// the request so a client disconnect aborts it, but bound by the gateway's write timeout so a
	// hung harness cannot pin the request forever. A parse failure is NOT an error here: the
	// Proposer returns its best-effort partial config and NormalizeProductConfig fills the gaps.
	ctx, cancel := context.WithTimeout(r.Context(), g.configuration.WriteTimeout)
	defer cancel()

	proposed, err := g.dependencies.Proposer.Propose(ctx, request.Prompt)
	if err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	configuration := NormalizeProductConfig(proposed)
	g.logInfo("gateway: product proposed", "productName", configuration.ProductName, "kind", configuration.ProductKind, "harness", configuration.Capabilities.Harness)
	g.writeData(w, http.StatusOK, configuration)
}

// NormalizeProductConfig folds a best-effort (possibly partial or parse-failed) ProductConfig into
// a COMPLETE, VALID spec by applying Eden's sane defaults to every empty/invalid field. It is the
// single point a proposal becomes wizard-ready, so both the live (real-harness, parse-failure-
// prone) and dev (deterministic) Proposers — and the wizard's own edits on POST /sessions — pass
// through ONE definition of "valid" (one concept, one home). It is exported so a composition root
// or a test can assert/seed a complete config.
//
//nolint:gocritic // ProductConfig is the copyable wire DTO; Normalize takes it by value and returns the completed copy.
func NormalizeProductConfig(configuration ProductConfig) ProductConfig {
	configuration.ProductName = defaultString(slugify(configuration.ProductName), "eden-product")
	configuration.ProductKind = normalizeProductKind(configuration.ProductKind)
	configuration.Summary = defaultString(strings.TrimSpace(configuration.Summary), "An Eden-built "+configuration.ProductKind+".")

	if len(configuration.Stack.Languages) == 0 {
		configuration.Stack.Languages = defaultLanguages(configuration.ProductKind)
	}
	if configuration.Stack.Frameworks == nil {
		configuration.Stack.Frameworks = defaultFrameworks(configuration.ProductKind)
	}
	if configuration.Services == nil {
		configuration.Services = []string{}
	}

	configuration.Capabilities.Harness = normalizeHarness(configuration.Capabilities.Harness)
	configuration.Capabilities.Model = defaultString(strings.TrimSpace(configuration.Capabilities.Model), defaultModel(configuration.Capabilities.Harness))
	if len(configuration.Capabilities.ToolGrants) == 0 {
		configuration.Capabilities.ToolGrants = defaultToolGrants()
	}
	if configuration.Capabilities.Skills == nil {
		configuration.Capabilities.Skills = []string{}
	}
	if configuration.Capabilities.Rules == nil {
		configuration.Capabilities.Rules = []string{}
	}

	if len(configuration.SDLCPhases) == 0 {
		configuration.SDLCPhases = DefaultSDLCPhases()
	}

	configuration.Sandbox.Posture = normalizePosture(configuration.Sandbox.Posture)
	if configuration.Sandbox.EgressAllow == nil {
		configuration.Sandbox.EgressAllow = []string{}
	}
	return configuration
}

// DefaultSDLCPhases is Eden's default phase subset for a build (the four-phase library SDLC, the
// canonical core of the 10-phase pipeline — ADR-0020). The wizard surfaces the full set; this is
// the proposed default.
func DefaultSDLCPhases() []string {
	return []string{"architecture", "implementation", "testing", "qa"}
}

// normalizeProductKind maps an arbitrary kind onto the closed ProductKind set, defaulting an
// unrecognized value to the Eden default build target (a service).
func normalizeProductKind(kind string) string {
	switch strings.ToLower(strings.TrimSpace(kind)) {
	case ProductKindService:
		return ProductKindService
	case ProductKindLibrary:
		return ProductKindLibrary
	case ProductKindApplication:
		return ProductKindApplication
	case ProductKindCLI:
		return ProductKindCLI
	case ProductKindUI:
		return ProductKindUI
	case ProductKindOther:
		return ProductKindOther
	default:
		return ProductKindService
	}
}

// normalizeHarness maps an arbitrary harness onto the closed Harness set, defaulting an
// unrecognized value to claude (the verified live default).
func normalizeHarness(harness string) string {
	switch strings.ToLower(strings.TrimSpace(harness)) {
	case HarnessClaude, "claude-code":
		return HarnessClaude
	case HarnessOMP:
		return HarnessOMP
	case HarnessCodex:
		return HarnessCodex
	default:
		return HarnessClaude
	}
}

// normalizePosture maps an arbitrary posture onto the closed Posture set, defaulting an
// unrecognized value to strict (default-deny — the safe posture for an unattended agent).
func normalizePosture(posture string) string {
	if strings.ToLower(strings.TrimSpace(posture)) == PostureRelaxed {
		return PostureRelaxed
	}
	return PostureStrict
}

// defaultLanguages is the Eden default language set for a kind (Go 1.26 backend; Svelte/TypeScript
// for a UI).
func defaultLanguages(kind string) []string {
	if kind == ProductKindUI {
		return []string{"typescript"}
	}
	return []string{"go"}
}

// defaultFrameworks is the Eden default framework set for a kind (Svelte 5 for a UI; none for a
// backend by default).
func defaultFrameworks(kind string) []string {
	if kind == ProductKindUI {
		return []string{"svelte"}
	}
	return []string{}
}

// defaultModel is the default model id for a harness (surfaced in the wizard; the live route's
// account default still wins at run time when empty upstream).
func defaultModel(harness string) string {
	switch harness {
	case HarnessOMP:
		return "deepseek-v4-flash"
	case HarnessCodex:
		return "gpt-5-codex"
	default:
		return "claude-fable-5"
	}
}

// defaultToolGrants is the Eden default standing tool allowlist proposed for a build agent.
func defaultToolGrants() []string {
	return []string{"filesystem", "shell", "git"}
}

// defaultString returns value when non-empty, else fallback.
func defaultString(value, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}

// slugify renders a free-text name into the HNS-1 slug grammar (lowercase, hyphen-separated,
// [a-z0-9]+ words) so a proposed productName is a valid Eden identifier. An empty result yields ""
// (the caller applies the fallback).
func slugify(name string) string {
	var builder strings.Builder
	prevHyphen := true // leading-hyphen suppression
	for _, r := range strings.ToLower(strings.TrimSpace(name)) {
		switch {
		case (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9'):
			builder.WriteRune(r)
			prevHyphen = false
		case !prevHyphen:
			builder.WriteByte('-')
			prevHyphen = true
		}
	}
	return strings.Trim(builder.String(), "-")
}
