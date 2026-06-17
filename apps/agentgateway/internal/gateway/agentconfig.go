package gateway

import (
	"context"
	"strings"
	"time"
)

// This file is the per-agent-type CONFIGURATION contract: the AgentConfig value, the
// AgentConfigStore port (the consumer-defined persistence seam), and the wire DTOs the Settings →
// Agents tab exchanges. An AgentConfig is the USER's editable default for one agent type
// (implementer/architect/…): the model it starts from, its standing tool grants, and its sandbox
// posture. It is the user-PREFERENCE layer — distinct from, and folded under, the git-backed
// AgentTemplate ceiling (ADR-0020 / the planned agent-configs repo): a saved value overrides the
// inherited default; an empty value inherits. Per-dimension honoring at spawn is incremental (the
// same stance the ProductConfig takes — the spec is carried + visible, applied progressively). No
// field is a credential.

// AgentConfig is the user's saved default for one agent type. The empty string on Model/
// SandboxPosture means "inherit from the AgentTemplate" (no override).
type AgentConfig struct {
	AgentType      string    `json:"agentType"`
	Model          string    `json:"model"`
	ToolGrants     []string  `json:"toolGrants"`
	SandboxPosture string    `json:"sandboxPosture"`
	UpdatedAt      time.Time `json:"updatedAt"`
}

// AgentConfigStore is the per-agent-type configuration port: the consumer-defined seam the Settings
// surface reads and writes user defaults through. A real Postgres adapter backs it in liveserve; an
// in-memory fake backs it in devserve — the real-vs-fake mirror the Proposer/ProjectStore use. It is
// OPTIONAL on Deps: when nil the /agent-configs routes are a 503.
//
// List returns every saved configuration; Get returns one (a wrapped KindNotFound when absent); Put upserts
// one (keyed by AgentType) and returns the stored copy.
type AgentConfigStore interface {
	List(ctx context.Context) ([]AgentConfig, error)
	Get(ctx context.Context, agentType string) (AgentConfig, error)
	Put(ctx context.Context, configuration AgentConfig) (AgentConfig, error)
}

// NormalizeAgentConfig folds a request into a complete, valid AgentConfig: trimmed fields, a non-nil
// grant slice, and a sandbox posture constrained to the closed set (an unrecognized posture clears
// to "inherit" rather than erroring — the same forgiving stance the product normalizer takes).
//
//nolint:gocritic // AgentConfig is the copyable wire DTO; Normalize takes it by value and returns the completed copy.
func NormalizeAgentConfig(configuration AgentConfig) AgentConfig {
	configuration.AgentType = strings.TrimSpace(configuration.AgentType)
	configuration.Model = strings.TrimSpace(configuration.Model)
	if configuration.ToolGrants == nil {
		configuration.ToolGrants = []string{}
	}
	configuration.SandboxPosture = normalizeAgentPosture(configuration.SandboxPosture)
	return configuration
}

// normalizeAgentPosture constrains the posture to the closed set; the empty string ("inherit") and
// any unrecognized value both resolve to "" (inherit), so the field never carries a junk value.
func normalizeAgentPosture(posture string) string {
	switch strings.ToLower(strings.TrimSpace(posture)) {
	case PostureStrict:
		return PostureStrict
	case PostureRelaxed:
		return PostureRelaxed
	default:
		return ""
	}
}

// ── wire DTOs ──────────────────────────────────────────────────────────────────.

// putAgentConfigRequest is the body of PUT /agent-configs/{agentType}: the editable fields. The
// agentType is the PATH wildcard, not a body field.
type putAgentConfigRequest struct {
	Model          string   `json:"model"`
	ToolGrants     []string `json:"toolGrants"`
	SandboxPosture string   `json:"sandboxPosture"`
}

// agentConfigView is the JSON projection of an AgentConfig for the Settings tab.
type agentConfigView struct {
	AgentType      string    `json:"agentType"`
	Model          string    `json:"model"`
	ToolGrants     []string  `json:"toolGrants"`
	SandboxPosture string    `json:"sandboxPosture"`
	UpdatedAt      time.Time `json:"updatedAt"`
}

// listAgentConfigsResponse is the body of GET /agent-configs (wrapped in the data envelope): every
// saved per-agent-type configuration.
type listAgentConfigsResponse struct {
	Configs []agentConfigView `json:"configs"`
}

// toAgentConfigView projects an AgentConfig onto its wire DTO (a non-nil grant slice so the JSON is
// always an array, never null).
//
//nolint:gocritic // AgentConfig is the copyable persisted record; the projector reads it by value.
func toAgentConfigView(configuration AgentConfig) agentConfigView {
	grants := configuration.ToolGrants
	if grants == nil {
		grants = []string{}
	}
	return agentConfigView{
		AgentType:      configuration.AgentType,
		Model:          configuration.Model,
		ToolGrants:     grants,
		SandboxPosture: configuration.SandboxPosture,
		UpdatedAt:      configuration.UpdatedAt,
	}
}
