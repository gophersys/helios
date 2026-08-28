package ompadapter

import (
	"context"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
)

// maxLineBytes bounds one omp json line the scanner accepts. A tool result can carry a whole
// file, so the buffer is generous (4 MiB); beyond it the line is treated as an Extension
// rather than a fatal scan error.
const maxLineBytes = 4 << 20

// reapGrace bounds the wait for omp to drain and exit after Close hands it the stdin EOF. omp
// answers EOF by rejecting its pending requests, disposing the session and exiting 0; a child
// that has not done so within this window is killed, so Close never hangs on a wedged harness.
const reapGrace = 10 * time.Second

// ompCodingAgentVersion matches the coding agent's `--version` line: the coding agent prints
// `omp/<semver>` (q1-install-verify.txt:15, `omp/17.3.7`), while oh-my-posh — whose CLI is ALSO
// named `omp` and to which a bare LookPath("omp") resolves on this host — prints a BARE semver
// ("15.10.0"). The `omp/` prefix is the discriminator.
var ompCodingAgentVersion = regexp.MustCompile(`(?m)(^|\s)omp/\d+\.\d+\.\d+`)

// Spawn launches ONE long-lived `omp --mode rpc` process for spec.Workspace with the resolved
// Route and the OpenRouter key injected onto the CHILD env ONLY. The key crosses the boundary
// EXACTLY at Secret.Use(fn) here — it never enters the Spec, an Event, a log, or a retained
// string outside the assembled child-env slice (the legitimate vehicle). Higher-precedence /
// route-diverting credential keys are scrubbed first, and the session store is rooted inside
// the workspace so the child never writes into the operator's own.
//
// The returned conn speaks omp's rpc transport: NDJSON commands on the child's stdin, NDJSON
// frames on its stdout. It is ready when omp says so — the `ready` frame is the harness's only
// readiness signal (rpc-mode.ts:690), so nothing is synthesized here.
//
//nolint:gocritic,ireturn // contract §2: Spec is the frozen copyable input and Spawn returns the HarnessConn port — the frozen lower seam.
func (a *Adapter) Spawn(ctx context.Context, spec agentsession.Spec, route agentsession.Route, cred agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	if err := errors.FromContext(ctx); err != nil {
		return nil, err
	}
	// Reject the WRONG `omp` BEFORE launching the long-lived session: `omp` is also oh-my-posh's
	// binary name, and driving a prompt theme engine as the coding agent hangs on a handshake that
	// never comes. The check is one short `--version` child, reaped before the session starts.
	if err := verifyBinary(ctx, a.binary); err != nil {
		return nil, err
	}
	env, err := sessionEnvironment(os.Environ(), spec.Workspace, cred)
	if err != nil {
		return nil, err
	}
	command := exec.CommandContext(ctx, a.binary, buildArguments(spec, route)...) // #nosec G204 -- binary is Eden-configured; args are Eden-resolved (mode/model/tools/route), never a shell.
	command.Dir = spec.Workspace
	command.Env = env
	command.Stderr = nil // stderr is diagnostic; the frame stream rides stdout only

	stdin, err := command.StdinPipe()
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "ompadapter: stdin pipe",
			agentsession.SpawnError{Harness: harnessName})
	}
	stdout, err := command.StdoutPipe()
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "ompadapter: stdout pipe",
			agentsession.SpawnError{Harness: harnessName})
	}
	if err := command.Start(); err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "ompadapter: start process",
			agentsession.SpawnError{Harness: harnessName})
	}
	conn := newRPCConn(spec, stdout, stdin)
	conn.attach(command)
	return conn, nil
}

// verifyBinary runs the candidate binary's `--version` and confirms it is the omp CODING AGENT,
// not oh-my-posh. A binary that cannot be probed, or one whose version is not the coding agent's,
// is a SpawnError — the session is never started against the wrong process.
func verifyBinary(ctx context.Context, binary string) error {
	out, err := exec.CommandContext(ctx, binary, "--version").Output() // #nosec G204 -- binary is Eden-configured; `--version` is a fixed literal, never user input.
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "ompadapter: probe omp --version",
			agentsession.SpawnError{Harness: harnessName})
	}
	return verifyOmpBinary(string(out))
}

// verifyOmpBinary is the pure binary-identity classifier: it accepts ONLY the omp coding agent's
// `omp/<semver>` version line and rejects a bare semver (oh-my-posh), a named oh-my-posh line, or
// empty output. It is pure so it is unit-tested directly without a process.
func verifyOmpBinary(versionOutput string) error {
	if ompCodingAgentVersion.MatchString(versionOutput) {
		return nil
	}
	return errors.Wrap(errors.KindUnavailable, "ompadapter: binary is not the omp coding agent (want omp/<semver>)",
		agentsession.SpawnError{Harness: harnessName})
}

// sessionEnvironment assembles the child environment for one rpc session: the scrubbed base
// with the injected OpenRouter key, plus EXACTLY ONE session-store root under the provisioned
// workspace. A duplicate entry is not harmless bookkeeping — execve passes the environ array
// verbatim, so a stale first entry stays visible to anything in the child that reads the array
// instead of the resolved value.
func sessionEnvironment(base []string, workspace string, cred agentsession.InjectedCredential) ([]string, error) {
	env, err := injectEnvironment(base, cred)
	if err != nil {
		return nil, err
	}
	return withSessionStore(env, workspace), nil
}

// withSessionStore strips every inherited session-store entry and appends the one rooted in the
// workspace. With no provisioned workspace there is no root to name, so the inherited value is
// still dropped (the child never writes into the operator's store) and omp falls back to its
// own default.
func withSessionStore(env []string, workspace string) []string {
	out := make([]string, 0, len(env)+1)
	for _, entry := range env {
		if key, _, _ := strings.Cut(entry, "="); key == sessionStoreEnvName {
			continue
		}
		out = append(out, entry)
	}
	if workspace == "" {
		return out
	}
	return append(out, sessionStoreEnvName+"="+strings.TrimRight(workspace, "/")+"/"+sessionStoreDir)
}

// injectEnvironment resolves the OpenRouter key from the protected Secret at the injection
// site (Secret.Use) and returns the scrubbed child environment with exactly the injected var
// set. The plaintext is confined to the Use closure; only the assembled []string escapes,
// and the only entry carrying the key is the one env var omp reads. A nil Secret is an
// AuthError (the value was never resolved).
func injectEnvironment(base []string, cred agentsession.InjectedCredential) ([]string, error) {
	envName := cred.EnvName
	// The adapter OWNS final env placement: it ignores the library default (OMP_AUTH_TOKEN)
	// and lands the key on OPENROUTER_API_KEY, which is where omp's OpenRouter route reads it.
	if envName == "" || envName == "OMP_AUTH_TOKEN" {
		envName = openRouterEnvName
	}
	if cred.Secret == nil {
		return nil, errors.Wrap(errors.KindUnauthenticated, "ompadapter: inject credential",
			agentsession.AuthError{})
	}
	var env []string
	useErr := cred.Secret.Use(func(plaintext []byte) error {
		// childEnvironment copies the key bytes into exactly one env entry; the plaintext slice
		// is not retained past this closure.
		env = childEnvironment(base, envName, string(plaintext))
		return nil
	})
	if useErr != nil {
		return nil, errors.Wrap(errors.KindUnauthenticated, "ompadapter: read credential", useErr)
	}
	return env, nil
}

// attach hands the conn the child process it must reap at Close. The in-memory transport seam
// attaches none, so a conn built over pipes has nothing to wait for.
func (c *rpcConn) attach(command *exec.Cmd) {
	c.mu.Lock()
	c.command = command
	c.mu.Unlock()
}

// reap completes the Close ladder on the child: the stdin EOF has already been handed over, so
// wait for the frame pump to drain omp's stdout to its end, then Wait() the process. Waiting
// for the drain FIRST is required — StdoutPipe's reader is closed by Wait, so reaping while the
// pump still reads would truncate the tail of the session.
//
// A child that has not drained within the grace (or a Close whose ctx is already done) is
// killed, which ends the pump by closing its stdout, and then reaped: an unwaited child stays a
// zombie owned by this process, which the lifecycle lane counts as an orphan.
func (c *rpcConn) reap(ctx context.Context) {
	c.mu.Lock()
	command := c.command
	c.mu.Unlock()
	if command == nil {
		return
	}
	c.reapOnce.Do(func() {
		select {
		case <-c.drained:
		case <-ctx.Done():
			c.kill(command)
			<-c.drained
		case <-time.After(reapGrace):
			c.kill(command)
			<-c.drained
		}
		_ = command.Wait() //nolint:errcheck // the process exit status is not the contract; the terminal Event (or its absence) is.
	})
}

// kill ends a child that did not answer the stdin EOF. Best-effort: a process that has already
// exited is the desired state.
func (c *rpcConn) kill(command *exec.Cmd) {
	if command.Process != nil {
		_ = command.Process.Kill() //nolint:errcheck // best-effort reap of a child that ignored its EOF; an already-exited process is the desired state.
	}
}
