package gateway

import (
	"net/http"
	"strings"

	"github.com/gophersys/libs/go/errors"
)

// agent_configs_handler holds the Settings → Agents surface: list every saved per-agent-type configuration,
// and upsert one. Both routes are enveloped (the edenhttp {data, errors, kind} shape) and 503 when no
// AgentConfigStore is wired (the AgentConfigs dep is OPTIONAL). No field is a credential.

// handleListAgentConfigs returns every saved per-agent-type configuration (the Settings tab loads
// these to seed its editor; an agent type with no saved configuration simply does not appear, and the UI
// shows the inherited default).
func (g *Gateway) handleListAgentConfigs(w http.ResponseWriter, r *http.Request) {
	if g.dependencies.AgentConfigs == nil {
		g.writeEnvelopeError(w, errors.New(errors.KindUnavailable, "gateway: agent-configuration persistence is not configured"))
		return
	}

	configs, err := g.dependencies.AgentConfigs.List(r.Context())
	if err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	views := make([]agentConfigView, 0, len(configs))
	for i := range configs {
		views = append(views, toAgentConfigView(configs[i]))
	}
	g.writeData(w, http.StatusOK, listAgentConfigsResponse{Configs: views})
}

// handlePutAgentConfig upserts the configuration for one agent type (the PATH wildcard). It
// normalizes the editable fields, stamps the update time, and returns the stored view.
func (g *Gateway) handlePutAgentConfig(w http.ResponseWriter, r *http.Request) {
	if g.dependencies.AgentConfigs == nil {
		g.writeEnvelopeError(w, errors.New(errors.KindUnavailable, "gateway: agent-configuration persistence is not configured"))
		return
	}

	agentType := strings.TrimSpace(r.PathValue("agentType"))
	if agentType == "" {
		g.writeEnvelopeError(w, errors.Wrap(errors.KindInvalid, "gateway: put agent configuration",
			RequestError{Reason: "agentType is required"}))
		return
	}

	var request putAgentConfigRequest
	if err := decodeJSON(r, &request); err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	configuration := NormalizeAgentConfig(AgentConfig{
		AgentType:      agentType,
		Model:          request.Model,
		ToolGrants:     request.ToolGrants,
		SandboxPosture: request.SandboxPosture,
		UpdatedAt:      g.dependencies.Clock.Now(),
	})

	stored, err := g.dependencies.AgentConfigs.Put(r.Context(), configuration)
	if err != nil {
		g.writeEnvelopeError(w, err)
		return
	}

	g.logInfo("gateway: agent configuration saved", "agentType", stored.AgentType, "model", stored.Model)
	g.writeData(w, http.StatusOK, toAgentConfigView(stored))
}
