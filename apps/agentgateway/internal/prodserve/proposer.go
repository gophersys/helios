package prodserve

import (
	"context"
	"encoding/json"
	"strings"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// harnessProposer is the PRODUCTION gateway.Proposer: the create-flow wizard's first step runs as
// ONE real harness turn (claude-code | omp) instructed to return ONLY a ProductConfig JSON object.
// It is the production counterpart of liveserve.harnessProposer (the same one-turn seam, wired here
// so the production binary imports NO test-fake-laden liveserve). It opens a SHORT-LIVED
// agentsession.Session on the shared Pool under the Vault-resolved credential, sends the instruction
// prompt, drains the normalized Event stream to terminal, and parses the result into a ProductConfig
// (the gateway NORMALIZES gaps, so a parse failure is best-effort, NOT an error). Only an
// infrastructure fault (the harness is unreachable) is surfaced as a wrapped, classified error.
type harnessProposer struct {
	// sessions is the live Factory the proposer opens its one-shot session on (the same real Pool).
	sessions agentsession.Factory
	// spec is the immutable session input: the workspace, routing, grants, and the opaque Vault
	// credential reference (resolved server-side at Open). It carries NO secret value.
	spec agentsession.Spec
	// logger, when non-nil, records a redaction-safe line on a parse fallback (never a secret).
	logger Logger
}

// proposeInstruction is the system-style framing prepended to the user's prompt so the harness
// returns ONLY a ProductConfig JSON object and nothing else. It names the exact shape and the closed
// token sets so the output parses without post-processing; the gateway still normalizes.
const proposeInstruction = `You are Eden's product-design assistant. A "session" is a PRODUCT Eden builds via its 10-phase SDLC. ` +
	`From the user's request below, propose a product configuration. ` +
	`Respond with ONLY a single JSON object (no prose, no markdown fences) matching exactly this shape:` + "\n" +
	`{"productName":string,"productKind":"service"|"library"|"application"|"cli"|"ui"|"other",` +
	`"summary":string,"stack":{"languages":[string],"frameworks":[string]},"services":[string],` +
	`"capabilities":{"harness":"claude"|"omp"|"codex","model":string,"toolGrants":[string],"skills":[string],"rules":[string]},` +
	`"sdlcPhases":[string],"sandbox":{"posture":"strict"|"relaxed","egressAllow":[string]}}` + "\n" +
	`Eden defaults: Go 1.26 backend, Svelte 5 UI, harness "claude", strict sandbox. ` +
	`Keep productName a short lowercase hyphenated slug. User request:` + "\n"

// Propose runs ONE real harness turn to derive a ProductConfig from prompt. It opens a short-lived
// session, prompts it with the JSON instruction, drains to terminal, and parses the result. A parse
// failure returns a best-effort partial config (NOT an error — the gateway normalizes the gaps);
// only an Open/stream infrastructure fault is returned as a wrapped, classified error.
//
//nolint:ireturn // satisfies the gateway.Proposer port; the gateway holds the abstraction.
func (p *harnessProposer) Propose(ctx context.Context, prompt string) (gateway.ProductConfig, error) {
	session, err := p.sessions.Open(ctx, p.spec)
	if err != nil {
		return gateway.ProductConfig{}, errors.Wrap(errors.KindUnavailable, "prodserve: open propose session", err)
	}
	defer func() {
		_ = session.Close(context.WithoutCancel(ctx)) //nolint:errcheck // the parsed result is the actionable outcome; a reap fault is logged by the pool, not surfaced to the wizard.
	}()

	stream := session.Events(ctx, agentsession.FromSeq(0))
	if _, err = session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: proposeInstruction + prompt}); err != nil {
		return gateway.ProductConfig{}, errors.Wrap(errors.KindUnavailable, "prodserve: prompt propose session", err)
	}

	resultText, err := drainResultText(ctx, stream)
	if err != nil {
		return gateway.ProductConfig{}, errors.Wrap(errors.KindUnavailable, "prodserve: drain propose turn", err)
	}

	configuration, ok := parseProductConfig(resultText)
	if !ok && p.logger != nil {
		p.logger.Info("prodserve: propose result not valid ProductConfig JSON, using sane defaults")
	}
	return configuration, nil
}

// drainResultText reads the session's normalized event stream to terminal and returns the final
// assistant text. A stream fault (Err non-nil at an early end) is the only infrastructure error
// returned — a terminal Failed is NOT a fault (an empty/unparseable result is a parse fallback).
func drainResultText(ctx context.Context, stream agentsession.Stream) (string, error) {
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			if err := stream.Err(); err != nil {
				return "", errors.Wrap(errors.KindUnavailable, "prodserve: propose stream ended early", err)
			}
			return "", nil
		}
		if event.IsTerminal() {
			if event.Terminal != nil {
				return event.Terminal.ResultText, nil
			}
			return "", nil
		}
	}
}

// parseProductConfig extracts a gateway.ProductConfig from the harness's result text (a bare JSON
// object, possibly wrapped in prose/a fence). It returns ok=false when no JSON object parses — the
// gateway then applies every sane default. Best-effort: a partial object parses to a partial config.
func parseProductConfig(resultText string) (gateway.ProductConfig, bool) {
	candidate := isolateJSONObject(resultText)
	if candidate == "" {
		return gateway.ProductConfig{}, false
	}
	var configuration gateway.ProductConfig
	if err := json.Unmarshal([]byte(candidate), &configuration); err != nil {
		return gateway.ProductConfig{}, false
	}
	return configuration, true
}

// isolateJSONObject returns the substring from the first '{' to the last '}' (inclusive), or "" when
// no such span exists — stripping a leading label / a ```json fence / trailing prose so the common
// wrapping cases parse. A malformed span still fails json.Unmarshal (and falls back to defaults).
func isolateJSONObject(text string) string {
	start := strings.IndexByte(text, '{')
	end := strings.LastIndexByte(text, '}')
	if start < 0 || end < start {
		return ""
	}
	return text[start : end+1]
}

// compile-time assertion: *harnessProposer satisfies the gateway.Proposer port.
var _ gateway.Proposer = (*harnessProposer)(nil)
