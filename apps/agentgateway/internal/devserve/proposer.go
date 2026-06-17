package devserve

import (
	"context"
	"strings"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// fakeProposer is the DEV-ONLY, DETERMINISTIC gateway.Proposer: it derives a ProductConfig from the
// prompt by simple keyword inspection — NO model call, NO real harness, NO network. This is what
// makes the create-flow wizard's Playwright E2E stable: the same prompt always yields the same
// proposal. The real claude/omp one-shot lives in liveserve; this fake is the dev counterpart, the
// same way the scripted harness is the dev counterpart of the real harness on the chat path.
//
// The gateway NORMALIZES whatever this returns (gateway.NormalizeProductConfig), so this fake only
// needs to fill the prompt-derived fields (name, kind, summary, a couple of stack/service hints);
// the Eden defaults fill the rest. The output is wizard-ready and editable.
type fakeProposer struct{}

// Propose derives a deterministic ProductConfig from prompt. It never errors (it makes no I/O): a
// proposal is always produced, exactly as the live proposer's sane-default fallback guarantees.
//
//nolint:ireturn // satisfies the gateway.Proposer port; the gateway holds the abstraction.
func (fakeProposer) Propose(_ context.Context, prompt string) (gateway.ProductConfig, error) {
	lowered := strings.ToLower(prompt)
	kind := deriveKind(lowered)
	return gateway.ProductConfig{
		ProductName: deriveName(prompt, kind),
		ProductKind: kind,
		Summary:     deriveSummary(prompt),
		Services:    deriveServices(lowered),
		Capabilities: gateway.ProductCapabilities{
			Harness: deriveHarness(lowered),
		},
		Sandbox: gateway.ProductSandbox{Posture: gateway.PostureStrict},
	}, nil
}

// deriveHarness picks the build harness from the prompt by keyword (deterministic), so the create
// flow can scope an omp or codex product, not only claude — the dev counterpart of the live
// proposer choosing a harness. The model is filled by NormalizeProductConfig's per-harness default.
// It uses DISTINCTIVE tokens (never the bare "omp", a substring of "compose"/"complete") and defaults
// to claude (the Eden default build target) when none match.
func deriveHarness(lowered string) string {
	switch {
	case containsAny(lowered, "oh my pi", "oh-my-pi", "deepseek", "openrouter"):
		return gateway.HarnessOMP
	case containsAny(lowered, "codex"):
		return gateway.HarnessCodex
	default:
		return gateway.HarnessClaude
	}
}

// deriveKind classifies the prompt into a ProductKind by keyword (deterministic). It defaults to a
// service (the Eden default build target) when no keyword matches.
func deriveKind(lowered string) string {
	switch {
	case containsAny(lowered, "library", "package", "sdk"):
		return gateway.ProductKindLibrary
	case containsAny(lowered, "cli", "command-line", "command line", "terminal tool"):
		return gateway.ProductKindCLI
	case containsAny(lowered, "ui", "frontend", "dashboard", "web app", "website", "svelte"):
		return gateway.ProductKindUI
	case containsAny(lowered, "application", "desktop app", "platform"):
		return gateway.ProductKindApplication
	case containsAny(lowered, "service", "api", "server", "backend", "microservice"):
		return gateway.ProductKindService
	default:
		return gateway.ProductKindService
	}
}

// deriveName extracts a short product name from the prompt: the first few significant words,
// hyphen-joined (the gateway slugifies + validates it). A prompt with no usable words yields a
// kind-derived default so the field is always populated.
func deriveName(prompt, kind string) string {
	fields := strings.Fields(strings.ToLower(prompt))
	words := make([]string, 0, 3)
	for _, field := range fields {
		word := strings.Trim(field, ".,!?;:\"'()")
		if isStopWord(word) || word == "" {
			continue
		}
		words = append(words, word)
		if len(words) == 3 {
			break
		}
	}
	if len(words) == 0 {
		return "eden-" + kind
	}
	return strings.Join(words, "-")
}

// deriveSummary produces the one-line summary: a trimmed, single-line echo of the prompt (bounded),
// so the wizard shows the user what was understood. The gateway fills a default when this is empty.
func deriveSummary(prompt string) string {
	summary := strings.Join(strings.Fields(prompt), " ") // collapse whitespace/newlines to one line
	const maxSummary = 200
	if len(summary) > maxSummary {
		summary = summary[:maxSummary]
	}
	return summary
}

// deriveServices proposes supporting services by keyword (deterministic). Empty when no keyword
// matches (the wizard lets the user add services).
func deriveServices(lowered string) []string {
	services := make([]string, 0, 3)
	if containsAny(lowered, "postgres", "database", "sql", "persist") {
		services = append(services, "postgres")
	}
	if containsAny(lowered, "nats", "event", "queue", "stream", "pub/sub", "pubsub") {
		services = append(services, "nats")
	}
	if containsAny(lowered, "secret", "vault", "credential") {
		services = append(services, "vault")
	}
	return services
}

// containsAny reports whether haystack contains any of the needles.
func containsAny(haystack string, needles ...string) bool {
	for _, needle := range needles {
		if strings.Contains(haystack, needle) {
			return true
		}
	}
	return false
}

// isStopWord reports whether a word is a low-signal filler skipped by deriveName.
func isStopWord(word string) bool {
	switch word {
	case "a", "an", "the", "build", "create", "make", "me", "please", "that", "to", "for", "with", "and", "of", "i", "want", "need":
		return true
	default:
		return false
	}
}
