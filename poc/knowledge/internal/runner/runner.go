// Package runner executes the experiment matrix: arm × task × seed, each in
// an isolated workspace, through the omp harness in non-interactive mode.
//
// Replicability levers, all recorded in run.json:
//   - pinned model + thinking level
//   - --no-extensions --no-skills --no-rules --no-lsp --no-title (no ambient
//     contamination from the host omp config)
//   - per-run --session-dir capturing the full transcript with token usage
//   - sha256 of the exact prompt and appended system prompt
//   - hard wall-clock budget per run; token budget flagged post-hoc
//   - idempotent: a run directory with run.json is never re-run
package runner

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/helios/poc/knowledge/internal/render"
	"github.com/helios/poc/knowledge/internal/task"
)

// Arm is one knowledge-delivery mechanism.
type Arm struct {
	Name string
	// SystemPromptFile (optional) is appended to the system prompt.
	SystemPromptFile string
	// Checker adds check.sh to the workspace and the iterate-until-green instruction.
	Checker bool
}

// Arms returns the four POC arms. armsDir holds rendered artifacts.
func Arms(armsDir string) []Arm {
	return []Arm{
		{Name: "baseline"},
		{Name: "monolithic", SystemPromptFile: filepath.Join(armsDir, "monolithic", "GUIDE.md")},
		{Name: "checker", Checker: true},
		{Name: "hybrid", SystemPromptFile: filepath.Join(armsDir, "hybrid", "CORE.md"), Checker: true},
	}
}

const basePrompt = "Implement the specification in spec.md in the current working directory. " +
	"Work autonomously: write the implementation and your own tests, then run `go build ./...`, `go vet ./...` and `go test ./...`, fixing failures until everything passes. " +
	"Keep the exported API exactly as the contract in spec.md specifies. " +
	"Do not add third-party dependencies. " +
	"When everything passes, stop."

const checkerPrompt = " Additionally, run `bash ./check.sh` and fix every finding it reports until it exits 0; its findings are mandatory."

const phase2BasePrompt = "Read spec2.md: it extends the module in the current working directory, which was previously implemented per spec.md. " +
	"Implement the extension. Keep every existing exported API and behavior intact. " +
	"Run `go build ./...`, `go vet ./...` and `go test ./...`, fixing failures until everything passes. " +
	"Do not add third-party dependencies. When everything passes, stop."

// Config parameterizes a matrix execution.
type Config struct {
	RootDir         string // poc/knowledge
	ResultsDir      string
	Model           string
	Thinking        string
	Seeds           int
	Parallel        int
	TimeoutSeconds  int
	TokenBudget     int // post-hoc flag threshold (output+input tokens)
	RulecheckBinary string
	// Phase 2 = second-task velocity: extend each phase-1 workspace with the
	// task's _phase2 spec. Default (0 or 1) = phase 1.
	Phase int
}

func (c Config) phase() int {
	if c.Phase == 2 {
		return 2
	}
	return 1
}

// runsSegment separates phase-1 and phase-2 artifacts.
func runsSegment(phase int) string {
	if phase == 2 {
		return "runs2"
	}
	return "runs"
}

// TokenUsage is summed over assistant messages in the session transcript.
type TokenUsage struct {
	Input     int     `json:"input"`
	Output    int     `json:"output"`
	CacheRead int     `json:"cache_read"`
	Total     int     `json:"total"`
	CostUSD   float64 `json:"cost_usd"`
}

// RunRecord is the per-run evidence envelope.
type RunRecord struct {
	Arm                string     `json:"arm"`
	Task               string     `json:"task"`
	Seed               int        `json:"seed"`
	Phase              int        `json:"phase"`
	Model              string     `json:"model"`
	Thinking           string     `json:"thinking"`
	OmpVersion         string     `json:"omp_version"`
	GoVersion          string     `json:"go_version"`
	PromptSHA256       string     `json:"prompt_sha256"`
	SystemPromptSHA256 string     `json:"system_prompt_sha256,omitempty"`
	StartedAt          string     `json:"started_at"`
	DurationSeconds    float64    `json:"duration_seconds"`
	TimedOut           bool       `json:"timed_out"`
	OverTokenBudget    bool       `json:"over_token_budget"`
	ExitCode           int        `json:"exit_code"`
	AssistantTurns     int        `json:"assistant_turns"`
	Tokens             TokenUsage `json:"tokens"`
}

// RunMatrix executes every (arm, task, seed) cell with bounded parallelism.
func RunMatrix(cfg Config, arms []Arm, tasks []task.Task) error {
	type cell struct {
		arm  Arm
		task task.Task
		seed int
	}
	var cells []cell
	for _, a := range arms {
		for _, t := range tasks {
			if cfg.phase() == 2 && !t.HasPhase2() {
				continue
			}
			for s := 1; s <= cfg.Seeds; s++ {
				cells = append(cells, cell{a, t, s})
			}
		}
	}

	parallel := cfg.Parallel
	if parallel < 1 {
		parallel = 1
	}
	semaphore := make(chan struct{}, parallel)
	var wg sync.WaitGroup
	var mu sync.Mutex
	var firstErr error
	for _, c := range cells {
		wg.Go(func() {
			semaphore <- struct{}{}
			defer func() { <-semaphore }()
			if err := RunOne(cfg, c.arm, c.task, c.seed); err != nil {
				mu.Lock()
				if firstErr == nil {
					firstErr = fmt.Errorf("%s/%s/seed%d: %w", c.arm.Name, c.task.ID, c.seed, err)
				}
				fmt.Fprintf(os.Stderr, "ERROR %s/%s/seed%d: %v\n", c.arm.Name, c.task.ID, c.seed, err)
				mu.Unlock()
			}
		})
	}
	wg.Wait()
	return firstErr
}

// RunOne executes a single cell. Idempotent: skips if run.json exists.
func RunOne(cfg Config, arm Arm, t task.Task, seed int) error {
	phase := cfg.phase()
	runDir := filepath.Join(cfg.ResultsDir, runsSegment(phase), arm.Name, t.ID, fmt.Sprintf("seed%d", seed))
	recordPath := filepath.Join(runDir, "run.json")
	if _, err := os.Stat(recordPath); err == nil {
		fmt.Printf("SKIP  %s/%s/seed%d (run.json exists)\n", arm.Name, t.ID, seed)
		return nil
	}
	workspace := filepath.Join(runDir, "workspace")
	sessionDir := filepath.Join(runDir, "session")
	if err := os.RemoveAll(workspace); err != nil {
		return err
	}
	for _, d := range []string{workspace, sessionDir} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			return err
		}
	}
	sourceWorkspace := t.WorkspaceDir()
	if phase == 2 {
		// Phase 2 extends the workspace the SAME arm produced in phase 1.
		phase1Dir := filepath.Join(cfg.ResultsDir, "runs", arm.Name, t.ID, fmt.Sprintf("seed%d", seed))
		if _, err := os.Stat(filepath.Join(phase1Dir, "run.json")); err != nil {
			return fmt.Errorf("phase 2 requires a completed phase-1 run at %s", phase1Dir)
		}
		sourceWorkspace = filepath.Join(phase1Dir, "workspace")
	}
	if err := copyTree(sourceWorkspace, workspace); err != nil {
		return fmt.Errorf("copy workspace: %w", err)
	}
	prompt := basePrompt
	if phase == 2 {
		specData, err := os.ReadFile(filepath.Join(t.Phase2Dir(), "spec2.md"))
		if err != nil {
			return fmt.Errorf("read spec2: %w", err)
		}
		if err := os.WriteFile(filepath.Join(workspace, "spec2.md"), specData, 0o644); err != nil {
			return err
		}
		// A fresh agent extends the codebase: remove phase-1 conversational
		// residue is unnecessary (sessions are isolated), but the scratch
		// clean-room droppings must not leak in.
		_ = os.RemoveAll(filepath.Join(workspace, "scoredir"))
		prompt = phase2BasePrompt
	}
	if arm.Checker {
		script := render.CheckScript(cfg.RulecheckBinary, filepath.Join(cfg.RootDir, "rules"))
		if err := os.WriteFile(filepath.Join(workspace, "check.sh"), []byte(script), 0o755); err != nil {
			return err
		}
		prompt += checkerPrompt
	}

	args := []string{
		"-p", "--mode", "text",
		"--model", cfg.Model,
		"--thinking", cfg.Thinking,
		"--no-extensions", "--no-skills", "--no-rules", "--no-lsp", "--no-title",
		"--auto-approve",
		"--session-dir", sessionDir,
	}
	var systemPromptSHA string
	if arm.SystemPromptFile != "" {
		content, err := os.ReadFile(arm.SystemPromptFile)
		if err != nil {
			return fmt.Errorf("read system prompt artifact: %w", err)
		}
		args = append(args, "--append-system-prompt", string(content))
		systemPromptSHA = sha256Hex(content)
	}
	specReference := "@spec.md"
	if phase == 2 {
		specReference = "@spec2.md"
	}
	args = append(args, specReference, prompt)

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(cfg.TimeoutSeconds)*time.Second)
	defer cancel()
	command := exec.CommandContext(ctx, "omp", args...)
	command.Dir = workspace
	command.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	command.Cancel = func() error {
		// Kill the whole process group so spawned tools die with the harness.
		return syscall.Kill(-command.Process.Pid, syscall.SIGKILL)
	}
	stdout, err := os.Create(filepath.Join(runDir, "omp-stdout.log"))
	if err != nil {
		return err
	}
	defer stdout.Close()
	stderr, err := os.Create(filepath.Join(runDir, "omp-stderr.log"))
	if err != nil {
		return err
	}
	defer stderr.Close()
	command.Stdout = stdout
	command.Stderr = stderr

	fmt.Printf("RUN   %s/%s/seed%d\n", arm.Name, t.ID, seed)
	started := time.Now()
	runErr := command.Run()
	duration := time.Since(started)

	exitCode := 0
	if exitErr, ok := runErr.(*exec.ExitError); ok {
		exitCode = exitErr.ExitCode()
	} else if runErr != nil {
		exitCode = -1
	}

	usage, turns, usageErr := parseSessionUsage(sessionDir)
	if usageErr != nil {
		fmt.Fprintf(os.Stderr, "WARN  %s/%s/seed%d: usage parse: %v\n", arm.Name, t.ID, seed, usageErr)
	}

	record := RunRecord{
		Arm:                arm.Name,
		Task:               t.ID,
		Seed:               seed,
		Phase:              phase,
		Model:              cfg.Model,
		Thinking:           cfg.Thinking,
		OmpVersion:         ompVersion(),
		GoVersion:          runtime.Version(),
		PromptSHA256:       sha256Hex([]byte(prompt)),
		SystemPromptSHA256: systemPromptSHA,
		StartedAt:          started.UTC().Format(time.RFC3339),
		DurationSeconds:    duration.Seconds(),
		TimedOut:           ctx.Err() == context.DeadlineExceeded,
		OverTokenBudget:    cfg.TokenBudget > 0 && usage.Input+usage.Output > cfg.TokenBudget,
		ExitCode:           exitCode,
		AssistantTurns:     turns,
		Tokens:             usage,
	}
	data, err := json.MarshalIndent(record, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(recordPath, append(data, '\n'), 0o644); err != nil {
		return err
	}
	fmt.Printf("DONE  %s/%s/seed%d (%.0fs, %d turns, %d out-tokens)\n",
		arm.Name, t.ID, seed, duration.Seconds(), turns, usage.Output)
	return nil
}

// parseSessionUsage sums assistant-message usage in the session transcript.
func parseSessionUsage(sessionDir string) (TokenUsage, int, error) {
	matches, err := filepath.Glob(filepath.Join(sessionDir, "*.jsonl"))
	if err != nil || len(matches) == 0 {
		return TokenUsage{}, 0, fmt.Errorf("no session transcript in %s", sessionDir)
	}
	sort.Strings(matches)
	var usage TokenUsage
	turns := 0
	for _, path := range matches {
		file, err := os.Open(path)
		if err != nil {
			return usage, turns, err
		}
		decoder := json.NewDecoder(file)
		for {
			var entry struct {
				Type    string `json:"type"`
				Message struct {
					Role  string `json:"role"`
					Usage struct {
						Input     int `json:"input"`
						Output    int `json:"output"`
						CacheRead int `json:"cacheRead"`
						Cost      struct {
							Total float64 `json:"total"`
						} `json:"cost"`
					} `json:"usage"`
				} `json:"message"`
			}
			if err := decoder.Decode(&entry); err == io.EOF {
				break
			} else if err != nil {
				file.Close()
				return usage, turns, err
			}
			if entry.Type == "message" && entry.Message.Role == "assistant" {
				turns++
				usage.Input += entry.Message.Usage.Input
				usage.Output += entry.Message.Usage.Output
				usage.CacheRead += entry.Message.Usage.CacheRead
				usage.CostUSD += entry.Message.Usage.Cost.Total
			}
		}
		file.Close()
	}
	usage.Total = usage.Input + usage.Output + usage.CacheRead
	return usage, turns, nil
}

var ompVersionOnce = sync.OnceValue(func() string {
	out, err := exec.Command("omp", "--version").Output()
	if err != nil {
		return "unknown"
	}
	return strings.TrimSpace(string(out))
})

func ompVersion() string { return ompVersionOnce() }

func sha256Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

// copyTree copies a directory tree (regular files only).
func copyTree(source, destination string) error {
	return filepath.Walk(source, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		relative, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		target := filepath.Join(destination, relative)
		if info.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		return os.WriteFile(target, data, info.Mode())
	})
}

// CopyTree is exported for the scorer.
func CopyTree(source, destination string) error { return copyTree(source, destination) }
