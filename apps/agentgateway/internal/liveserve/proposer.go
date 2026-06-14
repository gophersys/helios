package liveserve

import (
	"context"
	"encoding/json"
	"strings"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// harnessProposer is the LIVE gateway.Proposer: the create-flow wizard's first step runs as ONE
// real harness turn (claude-code | omp) instructed to return ONLY a ProductConfig JSON object. It
// is the real counterpart of devserve.fakeProposer (the deterministic, no-model dev path).
//
// It opens a SHORT-LIVED agentsession.Session through the SAME real Factory the live plane streams
// the chat off (the harness CLI under the Vault-resolved credential), sends the instruction prompt,
// drains the normalized Event stream to its terminal event, and parses the result text into a
// ProductConfig. The gateway then NORMALIZES whatever this returns (gateway.NormalizeProductConfig),
// so a parse failure is NOT an error: the proposer returns its best-effort partial config (possibly
// the zero value) and the gateway fills every gap with Eden's sane defaults. Only an INFRASTRUCTURE
// fault (the harness is unreachable / the session cannot open) is surfaced as a wrapped, classified
// error — exactly the Proposer port's contract.
//
// Model-call economics: a session is opened ONLY when the wizard is used (POST /product/propose),
// and EXACTLY ONE turn is run per request. The session is closed as soon as the terminal event is
// drained, so no harness process lingers.
type harnessProposer struct {
	// sessions is the live Factory the proposer opens its one-shot session on (the same real Pool
	// the gateway tails the chat off — the harness CLI under the Vault-resolved credential).
	sessions agentsession.Factory
	// spec is the immutable, fully-resolved session input the proposer opens with: the live
	// workspace, routing, and the opaque Vault credential reference (resolved server-side at Open).
	// It carries NO secret value — only the loggable reference (the same seam the chat path uses).
	spec agentsession.Spec
	// logger, when non-nil, records a redaction-safe line on a parse fallback (never a secret).
	logger Logger
}

// proposeInstruction is the system-style framing prepended to the user's prompt so the harness
// returns ONLY a ProductConfig JSON object and nothing else. It names the exact shape and the
// closed token sets so the model's output parses without post-processing; the gateway still
// normalizes (so an out-of-set token or a missing field is recovered, not fatal).
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
// session, prompts it with the JSON instruction, drains to the terminal event, and parses the
// result text. A parse failure returns a best-effort partial config (NOT an error — the gateway
// normalizes the gaps); only an Open/stream INFRASTRUCTURE fault is returned as a wrapped error.
//
//nolint:ireturn // satisfies the gateway.Proposer port; the gateway holds the abstraction.
func (p *harnessProposer) Propose(ctx context.Context, prompt string) (gateway.ProductConfig, error) {
	session, err := p.sessions.Open(ctx, p.spec)
	if err != nil {
		return gateway.ProductConfig{}, errors.Wrap(errors.KindUnavailable, "liveserve: open propose session", err)
	}
	// The one-shot session is reaped as soon as the turn is drained, regardless of outcome, so no
	// harness process lingers past the request. Close drains the terminal event and reaps the child.
	defer func() {
		_ = session.Close(context.WithoutCancel(ctx)) //nolint:errcheck // the parsed result is the actionable outcome; a reap fault is logged by the pool, not surfaced to the wizard.
	}()

	stream := session.Events(ctx, agentsession.FromSeq(0))
	if _, err = session.Control(ctx, agentsession.Command{Kind: agentsession.CommandPrompt, Text: proposeInstruction + prompt}); err != nil {
		return gateway.ProductConfig{}, errors.Wrap(errors.KindUnavailable, "liveserve: prompt propose session", err)
	}

	resultText, err := drainResultText(ctx, stream)
	if err != nil {
		return gateway.ProductConfig{}, errors.Wrap(errors.KindUnavailable, "liveserve: drain propose turn", err)
	}

	configuration, ok := parseProductConfig(resultText)
	if !ok && p.logger != nil {
		// The model did not return parseable JSON — the gateway will fill EVERY field with a sane
		// default. Record it (the prompt and result text are NOT logged: they may echo user input,
		// and the line stays redaction-safe by construction).
		p.logger.Info("liveserve: propose result not valid ProductConfig JSON, using sane defaults")
	}
	return configuration, nil
}

// drainResultText reads the session's normalized event stream to its terminal event and returns the
// final assistant text. A clean terminal Result carries the model's reply in Terminal.ResultText;
// any terminal kind (Result/Failed/Aborted) ends the drain. A stream fault (Err non-nil at an early
// end) is the only infrastructure error returned — a terminal Failed is NOT a fault here (the
// caller treats an empty/unparseable result as a parse fallback, not an error).
func drainResultText(ctx context.Context, stream agentsession.Stream) (string, error) {
	for {
		event, ok := stream.Next(ctx)
		if !ok {
			if err := stream.Err(); err != nil {
				return "", errors.Wrap(errors.KindUnavailable, "liveserve: propose stream ended early", err)
			}
			return "", nil // clean end with no terminal Result text (the gateway uses sane defaults)
		}
		if event.IsTerminal() {
			if event.Terminal != nil {
				return event.Terminal.ResultText, nil
			}
			return "", nil
		}
	}
}

// parseProductConfig extracts a gateway.ProductConfig from the harness's result text. The text is
// instructed to be a bare JSON object, but a real model may wrap it in prose or a markdown fence;
// this isolates the outermost JSON object and unmarshals it. It returns ok=false (and the zero
// config) when no JSON object parses — the gateway then applies every sane default. It is
// best-effort by design: a partial object (some fields present) parses to a partial config the
// gateway completes.
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

// isolateJSONObject returns the substring from the first '{' to the last '}' in text (inclusive),
// or "" when no such span exists. This strips a leading "Here is the config:" / a ```json fence /
// trailing prose the model may add around the object, so the common wrapping cases parse. A
// malformed span still fails json.Unmarshal (and falls back to defaults), so this never widens what
// is accepted — it only trims the obvious envelope.
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
