package gateway

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/orchestrator"
)

// maxBodyBytes bounds a request body read so a malicious client cannot exhaust memory.
const maxBodyBytes = 1 << 20 // 1 MiB

// handleCreateSession spawns a session: it records the DESIRED intent through the
// orchestrator.Manager (admission, limits, tenancy — the record plane) AND opens a LIVE
// agentsession.Session through the injected Factory, folding the gateway's configured,
// opaque setup-token reference into the Spec so the credential is resolved SERVER-SIDE at
// Open and never touches the response (REQ-0021). The live session is registered under the
// AgentID so the SSE/control/transcript routes reach it. A supplied prompt is sent as the
// first turn (the fake harness — and a real one — streams the body only after a Prompt).
func (g *Gateway) handleCreateSession(w http.ResponseWriter, r *http.Request) {
	var request createSessionRequest
	if err := decodeJSON(r, &request); err != nil {
		g.writeError(w, err)
		return
	}
	if request.OrganizationID == "" || request.ProjectID == "" {
		g.writeError(w, errors.Wrap(errors.KindInvalid, "gateway: create session",
			RequestError{Reason: "organizationId and projectId are required"}))
		return
	}
	if request.TemplateName == "" || request.TemplateVersion == "" {
		g.writeError(w, errors.Wrap(errors.KindInvalid, "gateway: create session",
			RequestError{Reason: "templateName and templateVersion are required"}))
		return
	}

	ctx := r.Context()

	// The LIVE session OUTLIVES this request: it is registered and tailed by later SSE/control
	// requests, and reaped by Stop/shutdown — NOT by this POST returning. So Open + the opening
	// Control run under a context DETACHED from the request (context.WithoutCancel): otherwise,
	// when this handler returns (right after writing the 201), r.Context() cancels and tears down
	// the just-spawned harness mid-turn — the failure a real (async) claude harness hits that the
	// synchronous fake harness hid (it emits its whole turn before the handler returns). The
	// session's lifecycle context is the registry's; admission/record reads still use the request
	// ctx so a client disconnect aborts the cheap record work.
	sessionCtx := context.WithoutCancel(ctx)

	// Record the desired intent (admission + limits + tenancy). The Manager's already
	// wrapped, typed error (LimitError/TemplateNotFoundError/InvalidRequestError) flows to
	// the client classified by Kind — never a credential (the ref is opaque).
	agent, err := g.dependencies.Manager.Spawn(ctx, g.spawnRequest(&request))
	if err != nil {
		g.writeError(w, err)
		return
	}

	// Open the LIVE session the gateway tails and controls. The credential rides the Spec
	// as an opaque reference; agentsession.Open resolves it server-side. On a failure the
	// recorded intent is rolled back via Stop so no orphan record lingers.
	session, err := g.dependencies.Sessions.Open(sessionCtx, g.openSpec(agent.ID))
	if err != nil {
		_ = g.dependencies.Manager.Stop(context.WithoutCancel(ctx), agent.ID, request.By) //nolint:errcheck // best-effort rollback; the Open error is the actionable outcome surfaced below.
		g.writeError(w, err)
		return
	}
	// Discover the canonical agentsession SessionID from the durable transcript prefix (the
	// Ready event, Seq 1, is appended synchronously during Open's handshake). This is the
	// key the post-mortem transcript route reads by, so the persisted Run is queryable even
	// after the live session is reaped (REQ-0020).
	sessionID := peekSessionID(sessionCtx, session)
	if displaced := g.registry.register(agent.ID, sessionID, session); displaced != nil {
		_ = displaced.Close(context.WithoutCancel(ctx)) //nolint:errcheck // reap a prior handle for the same id (re-create); best-effort.
	}

	// Send the opening prompt so the harness starts its first turn (the events then stream
	// to every SSE subscriber). It runs under the DETACHED sessionCtx — the turn outlives this
	// request, so the real async harness keeps streaming after the 201 is written. A control
	// fault here is non-fatal to creation — the session is live and the client may prompt via
	// the control channel. When the wizard supplied a ProductConfig, its synthesized preamble is
	// prepended so the build agent opens with the full product spec in view (a session IS a product).
	openingPrompt := g.openingPrompt(&request)
	if openingPrompt != "" {
		if _, perr := session.Control(sessionCtx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: openingPrompt}); perr != nil {
			g.logError("gateway: opening prompt failed", "agent", string(agent.ID), "kind", errors.KindOf(perr).String())
		}
	}

	g.logInfo("gateway: session created", "agent", string(agent.ID), "status", agent.Status.String())
	g.writeJSON(w, http.StatusCreated, createResponse{ID: string(agent.ID), Status: agent.Status.String()})
}

// handleListSessions returns the project-scoped, paginated session list (REQ-0022). The
// query narrows by org/project (the authorization scope is applied upstream) and statuses;
// the page size is bounded by Config.MaxPageSize.
func (g *Gateway) handleListSessions(w http.ResponseWriter, r *http.Request) {
	filter := g.listFilter(r)
	page, err := g.dependencies.Manager.List(r.Context(), filter)
	if err != nil {
		g.writeError(w, err)
		return
	}
	views := make([]agentView, 0, len(page.Agents))
	for i := range page.Agents {
		views = append(views, toAgentView(page.Agents[i]))
	}
	g.writeJSON(w, http.StatusOK, listResponse{Sessions: views, Next: page.Next})
}

// handleGetSession returns one session record (REQ-0020 queryable record), or 404.
func (g *Gateway) handleGetSession(w http.ResponseWriter, r *http.Request) {
	id := orchestrator.AgentID(r.PathValue("id"))
	agent, err := g.dependencies.Manager.Get(r.Context(), id)
	if err != nil {
		g.writeError(w, err)
		return
	}
	g.writeJSON(w, http.StatusOK, toAgentView(agent))
}

// handleStopSession records the terminal intent (REQ-0020 abort/stop) and reaps the live
// session so its harness goroutine does not leak. Idempotent: stopping a terminal session
// is a no-op success. The live stream ends cleanly on the session's terminal event.
func (g *Gateway) handleStopSession(w http.ResponseWriter, r *http.Request) {
	id := orchestrator.AgentID(r.PathValue("id"))
	by := r.URL.Query().Get("by")

	if err := g.dependencies.Manager.Stop(r.Context(), id, by); err != nil {
		g.writeError(w, err)
		return
	}
	// Reap the live handle: Close drains the in-flight turn to its terminal event (which
	// every SSE subscriber sees) and ends the streams cleanly (REQ-0023 stop stops the
	// stream cleanly).
	if session, ok := g.registry.remove(id); ok {
		_ = session.Close(r.Context()) //nolint:errcheck // the terminal event + clean stream end is the observable outcome; a close fault is logged by Serve's reaper, not surfaced to the client.
	}
	g.writeJSON(w, http.StatusOK, map[string]string{"status": "stopping"})
}

// handleResumeSession records the resume intent (REQ-0023 resume from the correct seq).
// The record-plane resumability is validated by the Manager (ConflictError on a
// non-resumable status); the live stream is reconstructed by the client reconnecting to
// the SSE route with its last-seen seq (the same from-seq replay mechanism).
func (g *Gateway) handleResumeSession(w http.ResponseWriter, r *http.Request) {
	id := orchestrator.AgentID(r.PathValue("id"))
	by := r.URL.Query().Get("by")
	if err := g.dependencies.Manager.Resume(r.Context(), id, by); err != nil {
		g.writeError(w, err)
		return
	}
	g.writeJSON(w, http.StatusOK, map[string]string{"status": "resuming"})
}

// openingPrompt builds the first-turn text the gateway prompts the live session with. When the
// wizard supplied a ProductConfig, it normalizes it and PREPENDS a synthesized preamble (the
// product spec the build agent opens with) to the user's prompt; otherwise it is the prompt
// verbatim (the existing path, unchanged). An empty result means no opening turn is sent.
func (g *Gateway) openingPrompt(request *createSessionRequest) string {
	if request.Product == nil {
		return request.Prompt
	}
	preamble := productPreamble(NormalizeProductConfig(*request.Product))
	if request.Prompt != "" {
		preamble += "\n\n" + request.Prompt
	}
	// A build prompt is heavyweight; without guidance a model can reason silently for minutes
	// before emitting anything, which reads as a frozen chat. Ask it to NARRATE: lead with a
	// one-sentence summary and a short plan before deep work, so the chat streams visible progress
	// from the first seconds (the thinking-progress status bar covers the silent-reasoning gaps).
	return preamble + buildNarrationDirective
}

// buildNarrationDirective nudges the build agent to stream visible progress instead of reasoning
// silently — appended to the product opening prompt only.
const buildNarrationDirective = "\n\nBegin your reply with a one-sentence summary of what you will build, then a short numbered plan, before any deep work — so progress is visible as you go."

// productPreamble synthesizes the agent's initial-context line from a normalized ProductConfig:
// "Build <productName> (<kind>): <summary>. Stack <...>. Services <...>. Run phases <...>." It is
// the single point a ProductConfig becomes the build agent's opening context (one concept, one
// home). It carries NO credential (ProductConfig has no secret field).
//
//nolint:gocritic // ProductConfig is the copyable wire DTO; the synthesizer reads it by value.
func productPreamble(configuration ProductConfig) string {
	var builder strings.Builder
	builder.WriteString("Build ")
	builder.WriteString(configuration.ProductName)
	builder.WriteString(" (")
	builder.WriteString(configuration.ProductKind)
	builder.WriteString("): ")
	builder.WriteString(configuration.Summary)

	stack := append(append([]string{}, configuration.Stack.Languages...), configuration.Stack.Frameworks...)
	if len(stack) > 0 {
		builder.WriteString(" Stack ")
		builder.WriteString(strings.Join(stack, ", "))
		builder.WriteString(".")
	}
	if len(configuration.Services) > 0 {
		builder.WriteString(" Services ")
		builder.WriteString(strings.Join(configuration.Services, ", "))
		builder.WriteString(".")
	}
	if len(configuration.SDLCPhases) > 0 {
		builder.WriteString(" Run phases ")
		builder.WriteString(strings.Join(configuration.SDLCPhases, ", "))
		builder.WriteString(".")
	}
	return builder.String()
}

// spawnRequest folds a create request into an orchestrator.SpawnRequest, threading the
// gateway's configured opaque credential reference (resolved server-side at Open, never
// here). OnPermission is nil: the chat path surfaces permission requests as events for an
// out-of-band human Resolve (agentsession Q2).
func (g *Gateway) spawnRequest(request *createSessionRequest) orchestrator.SpawnRequest {
	return orchestrator.SpawnRequest{
		Tenant:     orchestrator.Tenancy{OrganizationID: request.OrganizationID, ProjectID: request.ProjectID},
		Template:   orchestrator.TemplateRef{Name: request.TemplateName, Version: request.TemplateVersion},
		Credential: g.configuration.Credential,
		By:         request.By,
		RunID:      request.RunID,
		Labels:     request.Labels,
	}
}

// openSpec builds the agentsession.Spec the gateway opens a live session with. The opaque
// credential reference rides here and is resolved SERVER-SIDE inside Open; the gateway
// never holds the value. The AgentID is carried so the registry key matches the record.
func (g *Gateway) openSpec(_ orchestrator.AgentID) agentsession.Spec {
	return agentsession.Spec{
		Workspace:    g.configuration.Workspace,
		Routing:      g.configuration.Routing,
		Grants:       g.configuration.Grants,
		Credential:   g.configuration.Credential,
		OnPermission: g.configuration.OnPermission,
	}
}

// peekSessionID reads one event from the session's replay tail to learn the canonical
// agentsession SessionID the pump stamps on every event (Event.SessionID). The Ready event
// (Seq 1) is durably appended during Open's handshake, so this peek is non-blocking against
// a fresh session. It uses a fresh sub-stream that is dropped immediately (closing its ctx
// drops only this peek subscriber — never the agent or other viewers). Returns "" if no
// event is available (the caller registers with an empty id and the SSE route still works).
func peekSessionID(ctx context.Context, session agentsession.Session) string {
	peekCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	stream := session.Events(peekCtx, agentsession.FromSeq(0))
	event, ok := stream.Next(peekCtx)
	if !ok {
		return ""
	}
	return event.SessionID
}

// listFilter builds an orchestrator.Filter from the request query (the project-scoped,
// paginated session-list query — REQ-0022).
func (g *Gateway) listFilter(r *http.Request) orchestrator.Filter {
	query := r.URL.Query()
	filter := orchestrator.Filter{
		Tenant: orchestrator.Tenancy{
			OrganizationID: query.Get("organizationId"),
			ProjectID:      query.Get("projectId"),
		},
		Cursor: query.Get("cursor"),
		Limit:  g.configuration.MaxPageSize,
	}
	if query.Get("active") == "true" {
		filter.OnlyActive = true
	}
	return filter
}

// decodeJSON reads and decodes a bounded JSON request body, rejecting unknown fields and a
// body that is not a single JSON value. A decode fault is a typed RequestError (KindInvalid
// → 400). An empty body decodes to the zero request (the caller validates required fields).
func decodeJSON(r *http.Request, into any) error {
	reader := io.LimitReader(r.Body, maxBodyBytes)
	decoder := json.NewDecoder(reader)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(into); err != nil {
		if errors.Is(err, io.EOF) {
			return nil // empty body == zero request; required-field validation follows
		}
		return errors.Wrap(errors.KindInvalid, "gateway: decode request body",
			RequestError{Reason: "malformed JSON body"})
	}
	return nil
}
