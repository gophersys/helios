// Package session drives one headless Claude Code session end-to-end: it spawns
// the CLI, streams stdout line-by-line writing every event verbatim to a
// transcript, folds those events into a ledger, and reports the outcome.
//
// This is the F4-adapter spike (ADR-0008): the narrowest thing that proves the
// kernel can capture a transcript and a token ledger from a real agent loop.
package session

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/gophersys/eden/poc/codingharness/internal/ledger"
)

// Invocation is the immutable input for one session. It is fully resolved by the
// caller before the session runs; the session itself performs no env reads or
// flag parsing, keeping the spawn deterministic.
type Invocation struct {
	// Task is the prompt handed to `claude -p`.
	Task string
	// Workspace is the directory the session runs in; the agent's file writes
	// land here. The caller owns its lifecycle.
	Workspace string
	// AllowedTools is the minimum tool allowlist the task needs, passed through
	// to --allowedTools (for example: "Write", "Read", "Bash(go *)").
	AllowedTools []string
	// PermissionMode is passed to --permission-mode. "acceptEdits" lets file
	// writes proceed without a prompt while still denying anything outside the
	// allowlist — narrower than bypassPermissions.
	PermissionMode string
	// MaxBudgetUSD, when positive, caps spend via --max-budget-usd.
	MaxBudgetUSD float64
	// TranscriptPath is where every streamed event line is written verbatim.
	TranscriptPath string
}

// Outcome is what one session produced.
type Outcome struct {
	Ledger      ledger.Ledger
	ExitCode    int
	DecodeFails int
}

// claudeBinary is the CLI name; resolved from PATH by exec.Command.
const claudeBinary = "claude"

// Run spawns the session, streams the transcript, and returns the folded
// outcome. The caller's context bounds the wall clock; cancelling it kills the
// child process. Run does not call os.Exit — the caller maps Outcome to a code.
func Run(ctx context.Context, invocation Invocation) (Outcome, error) {
	arguments := buildArguments(invocation)

	command := exec.CommandContext(ctx, claudeBinary, arguments...)
	command.Dir = invocation.Workspace
	// Inherit the environment so the CLI finds its existing auth; the spike does
	// not inject credentials. stderr is surfaced for diagnostics only.
	command.Env = os.Environ()
	command.Stderr = os.Stderr

	stdout, err := command.StdoutPipe()
	if err != nil {
		return Outcome{}, fmt.Errorf("session: open stdout pipe: %w", err)
	}

	if err := os.MkdirAll(filepath.Dir(invocation.TranscriptPath), 0o755); err != nil {
		return Outcome{}, fmt.Errorf("session: prepare transcript dir: %w", err)
	}
	transcript, err := os.Create(invocation.TranscriptPath)
	if err != nil {
		return Outcome{}, fmt.Errorf("session: create transcript: %w", err)
	}
	defer transcript.Close()

	started := time.Now()
	if err := command.Start(); err != nil {
		return Outcome{}, fmt.Errorf("session: start claude: %w", err)
	}

	folder := ledger.NewFolder()
	decodeFails := stream(stdout, transcript, folder)

	waitErr := command.Wait()
	wallMillis := time.Since(started).Milliseconds()

	outcome := Outcome{
		Ledger:      folder.Finish(wallMillis),
		DecodeFails: decodeFails,
		ExitCode:    exitCode(waitErr),
	}
	return outcome, nil
}

// stream reads stdout line by line, writing each line verbatim to the transcript
// and folding the decoded event. A line that fails to decode is still written
// (nothing is lost) and counted, never fatal. Returns the decode-failure count.
func stream(stdout io.Reader, transcript io.Writer, folder *ledger.Folder) int {
	decodeFails := 0
	scanner := bufio.NewScanner(stdout)
	// Stream-json lines can be large (a tool result can carry a whole file), so
	// raise the line cap well above the default 64 KiB.
	scanner.Buffer(make([]byte, 0, 1024*1024), 16*1024*1024)
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		// Verbatim capture first — the transcript is the source of truth even if
		// our decoder is wrong about the shape.
		fmt.Fprintf(transcript, "%s\n", line)

		event, err := ledger.Decode(line)
		if err != nil {
			decodeFails++
			continue
		}
		folder.Add(event)
	}
	return decodeFails
}

// buildArguments assembles the headless flag set. The choices and their
// rationale are documented in the README; the short version: -p for headless,
// stream-json + --verbose for the event stream, a minimal --allowedTools, and
// --permission-mode acceptEdits instead of --dangerously-skip-permissions.
func buildArguments(invocation Invocation) []string {
	arguments := []string{
		"-p", invocation.Task,
		"--output-format", "stream-json",
		"--verbose",
	}
	if len(invocation.AllowedTools) > 0 {
		arguments = append(arguments, "--allowedTools")
		arguments = append(arguments, invocation.AllowedTools...)
	}
	if invocation.PermissionMode != "" {
		arguments = append(arguments, "--permission-mode", invocation.PermissionMode)
	}
	if invocation.MaxBudgetUSD > 0 {
		arguments = append(arguments, "--max-budget-usd", fmt.Sprintf("%g", invocation.MaxBudgetUSD))
	}
	return arguments
}

// exitCode extracts a process exit code from a Wait error. A nil error is 0; a
// non-ExitError (for example, the process was killed by context cancellation) is
// reported as a generic failure. Inspection is via errors.AsType per the Eden
// error-handling discipline.
func exitCode(waitErr error) int {
	if waitErr == nil {
		return 0
	}
	if exitErr, ok := errors.AsType[*exec.ExitError](waitErr); ok {
		return exitErr.ExitCode()
	}
	return 1
}
