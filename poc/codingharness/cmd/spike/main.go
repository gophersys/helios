// Command spike drives ONE headless Claude Code session end-to-end and captures
// the full transcript plus a token ledger. It is the WS2 codingharness spike
// (09 §7 item 4): the narrowest thing that de-risks the kernel's F4 adapter
// (ADR-0008) before libs/go/codingharness gets a contract.
//
// Usage:
//
//	spike [-output DIR] [-task TASK] [-keep]
//
// With no flags it runs the canonical trivial task in a fresh temp workspace,
// writes transcript.jsonl + ledger.json into the output dir, prints the ledger
// as one JSON line, and exits non-zero if the session failed.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"time"

	"github.com/gophersys/eden/poc/codingharness/internal/session"
)

// defaultTask is the trivial smoke task: write a file, then run go vet. It
// exercises the two tool classes the kernel cares about (file edit + command)
// without doing anything risky.
const defaultTask = "Create hello.go containing a main package that prints 'eden kernel spike'; then run: go vet ."

// sessionTimeout bounds the wall clock for a single headless run.
const sessionTimeout = 5 * time.Minute

func main() {
	outputDirectory := flag.String("output", "", "directory for transcript + ledger (default: a fresh temp dir)")
	task := flag.String("task", defaultTask, "the task prompt handed to claude -p")
	keepWorkspace := flag.Bool("keep", false, "keep the temp workspace after the run instead of deleting it")
	flag.Parse()

	if err := run(*outputDirectory, *task, *keepWorkspace); err != nil {
		fmt.Fprintf(os.Stderr, "spike: %v\n", err)
		os.Exit(1)
	}
}

func run(outputDirectory, task string, keepWorkspace bool) error {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	ctx, cancel := context.WithTimeout(ctx, sessionTimeout)
	defer cancel()

	workspace, err := os.MkdirTemp("", "codingharness-spike-")
	if err != nil {
		return fmt.Errorf("create workspace: %w", err)
	}
	if keepWorkspace {
		fmt.Fprintf(os.Stderr, "spike: workspace kept at %s\n", workspace)
	} else {
		defer os.RemoveAll(workspace)
	}

	// A standalone Go file needs a module for `go vet` to be meaningful; seed one
	// so the task's verification step has something to chew on.
	if err := seedModule(workspace); err != nil {
		return fmt.Errorf("seed workspace module: %w", err)
	}

	if outputDirectory == "" {
		outputDirectory, err = os.MkdirTemp("", "codingharness-out-")
		if err != nil {
			return fmt.Errorf("create output dir: %w", err)
		}
	}
	if err := os.MkdirAll(outputDirectory, 0o755); err != nil {
		return fmt.Errorf("prepare output dir: %w", err)
	}

	invocation := session.Invocation{
		Task:      task,
		Workspace: workspace,
		// Minimum allowlist for "write a file then go vet": Write to create the
		// file, Read so the agent can re-read it, and Bash scoped to go only.
		AllowedTools:   []string{"Write", "Read", "Bash(go *)"},
		PermissionMode: "acceptEdits",
		TranscriptPath: filepath.Join(outputDirectory, "transcript.jsonl"),
	}

	outcome, err := session.Run(ctx, invocation)
	if err != nil {
		return fmt.Errorf("run session: %w", err)
	}

	ledgerPath := filepath.Join(outputDirectory, "ledger.json")
	if err := writeLedger(ledgerPath, outcome.Ledger); err != nil {
		return fmt.Errorf("write ledger: %w", err)
	}

	// The one-line JSON ledger summary is the spike's headline artifact.
	line, err := json.Marshal(outcome.Ledger)
	if err != nil {
		return fmt.Errorf("marshal ledger line: %w", err)
	}
	fmt.Println(string(line))

	fmt.Fprintf(os.Stderr,
		"spike: workspace=%s output=%s exit=%d decode_fails=%d\n",
		workspace, outputDirectory, outcome.ExitCode, outcome.DecodeFails)

	// Fail loudly if the session did not succeed or the CLI itself exited
	// non-zero. This is what a parent orchestrator branches on.
	if !outcome.Ledger.Succeeded || outcome.ExitCode != 0 {
		os.Exit(2)
	}
	return nil
}

// seedModule writes a minimal go.mod so `go vet .` in the workspace has a module
// context. The temp workspace is outside any existing module tree.
func seedModule(workspace string) error {
	contents := "module codingharness-spike-workspace\n\ngo 1.26\n"
	return os.WriteFile(filepath.Join(workspace, "go.mod"), []byte(contents), 0o644)
}

// writeLedger persists the ledger as pretty JSON alongside the transcript.
func writeLedger(path string, value any) error {
	bytes, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(bytes, '\n'), 0o644)
}
