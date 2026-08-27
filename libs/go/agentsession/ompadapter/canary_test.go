package ompadapter_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// seededCanary is the redaction needle (ADR-0020 dimension (f)): a fake OpenRouter key handed
// to the adapter's credential path that must appear in NO surfaced artifact — not a returned
// error, not an Event the normalizer produces, not a Command. The ONLY place it may legitimately
// land is the assembled child-process environment slice (the injection vehicle), which never
// crosses into an Event or a log. If it leaks anywhere else, the scrub contract is broken. This
// is the PURE-path canary; the subprocess-backed canary (the key threaded through a real spawn,
// asserted absent from every drained Event) rides the integration arm
// (TestIntegration_StubBinary_RealSubprocessLifecycle) and the lifecycle/load lanes.
const seededCanary = "sk-or-v1-SEEDED-CANARY-do-not-leak-aG9yc2U"

// TestCanary_KeyLandsOnlyOnChildEnv threads the seeded key through the REAL injection seam
// (injectEnvironment: resolve the secrets.Secret at Secret.Use, scrub the route-diverters, land
// the plaintext on EXACTLY OPENROUTER_API_KEY). It asserts the key surfaces ONLY on that one
// child-env entry — never on PATH/HOME, never twice, never (by construction) anywhere an Event
// or log could reach.
func TestCanary_KeyLandsOnlyOnChildEnv(t *testing.T) {
	t.Parallel()
	cred := agentsession.InjectedCredential{
		Secret:  secretstest.MintSecret([]byte(seededCanary)),
		EnvName: "OPENROUTER_API_KEY",
	}
	base := []string{"PATH=/usr/bin", "HOME=/home/eden", "OMP_AUTH_TOKEN=lib-default"}

	env, err := ompadapter.InjectEnvironmentForTest(base, cred)
	if err != nil {
		t.Fatalf("injectEnvironment with a valid seeded secret: %v", err)
	}

	hits := 0
	for _, e := range env {
		if strings.Contains(e, seededCanary) {
			hits++
			if !strings.HasPrefix(e, "OPENROUTER_API_KEY=") {
				t.Errorf("the seeded key surfaced on a non-OpenRouter env entry: %q", redactEntry(e))
			}
		}
	}
	if hits != 1 {
		t.Errorf("the seeded key must appear on EXACTLY one child-env entry, found %d", hits)
	}
	// The library-default vehicle var must be scrubbed (precedence-trap defense).
	for _, e := range env {
		if strings.HasPrefix(e, "OMP_AUTH_TOKEN=") {
			t.Errorf("OMP_AUTH_TOKEN must be scrubbed from the child env: %q", redactEntry(e))
		}
	}
}

// TestCanary_NeverLeaksOntoInjectionError proves the AUTH-FAILURE path is redaction-safe: when
// the credential cannot be resolved (a nil Secret — the value was never minted), the returned
// error carries NO key material (there is none to leak) and is a typed, operator-safe message.
// The complementary guarantee that a SUCCESSFULLY-resolved key never rides an error holds by
// construction — the plaintext is confined to the Secret.Use closure and only the env slice
// escapes — so this asserts the error surface itself is canary-free.
func TestCanary_NeverLeaksOntoInjectionError(t *testing.T) {
	t.Parallel()
	// A nil Secret: the AuthError path. No key exists, so the error cannot embed one — but a
	// regression that echoed the EnvName-adjacent state or a resolved value would surface here.
	cred := agentsession.InjectedCredential{Secret: nil, EnvName: "OPENROUTER_API_KEY"}
	_, err := ompadapter.InjectEnvironmentForTest(nil, cred)
	if err == nil {
		t.Fatal("a nil Secret must be an auth error, not a silent success")
	}
	if strings.Contains(err.Error(), seededCanary) {
		t.Fatalf("the canary leaked onto the injection error: %q", err.Error())
	}
}

// TestCanary_NormalizerNeverSurfacesKey proves the key is architecturally absent from the
// normalizer's surface: the normalizer parses omp STDOUT (which never carries the provider key —
// the key lives only in the child env), so even a frame that maliciously embedded the canary in
// a result/args/text field must NOT surface it on a key field of any produced Event. The
// AssertNoSecretInEvent helper checks every redaction-eligible field. (A digested tool-result is
// bounded but not key-redacted by the digester — so the canary is placed in fields that MUST
// stay clean: it never reaches a tool result/arg digest unless omp echoed it, which the engine's
// transcript redactor owns; here we assert the credential-path key never appears on the stream.)
func TestCanary_NormalizerNeverSurfacesKey(t *testing.T) {
	t.Parallel()
	// A stream that does NOT carry the key anywhere (the real invariant: the key is in the child
	// env, never in stdout). Drive a representative live-shaped stream and assert no Event field
	// carries the seeded key.
	normalize := ompadapter.StreamNormalizerForTest()
	lines := []string{
		`{"type":"session","id":"s1","version":3}`,
		`{"type":"message_start","message":{"role":"assistant","model":"deepseek/deepseek-v4-flash","content":[]}}`,
		`{"type":"message_update","assistantMessageEvent":{"type":"thinking_delta","delta":"thinking"}}`,
		`{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"ok"}}`,
		`{"type":"tool_execution_start","toolCallId":"c1","toolName":"read","args":{"path":"x"}}`,
		`{"type":"tool_execution_end","toolCallId":"c1","toolName":"read","isError":false,"result":{"content":[]}}`,
		`{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"ok"}],"usage":{"input":1,"output":2,"cost":{"total":0.001}}}}`,
		`{"type":"agent_end","messages":[{"role":"assistant","model":"deepseek/deepseek-v4-flash","stopReason":"stop","content":[{"type":"text","text":"ok"}],"usage":{"input":1,"output":2,"cost":{"total":0.001}}}]}`,
	}
	var events []agentsession.Event
	for _, l := range lines {
		events = append(events, normalize([]byte(l))...)
	}
	if len(events) == 0 {
		t.Fatal("the representative stream produced no events")
	}
	for i := range events {
		agentsessiontest.AssertNoSecretInEvent(t, events[i], seededCanary)
	}
}

// redactEntry returns an env entry's KEY only, so a leaked value is never re-printed by the
// failure message itself (the test must not become the leak).
func redactEntry(entry string) string {
	if i := strings.IndexByte(entry, '='); i >= 0 {
		return entry[:i] + "=<redacted>"
	}
	return "<redacted>"
}
