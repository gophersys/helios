// Package score grades completed runs in a clean room:
//
//  1. copy the agent workspace to an isolated score directory,
//  2. inject the held-out verify tests (which the agent never saw),
//  3. run `go build` + `go test -run ^TestVerify` hermetically (GOPROXY=off),
//  4. run every rule oracle over the agent's code (verify files excluded by
//     the zz_ prefix convention),
//  5. emit score.json with per-applicable-rule verdicts.
//
// The verifier never sees what arm produced the code — the information
// barrier from the helios evidence model.
package score

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/helios/poc/knowledge/internal/check"
	"github.com/helios/poc/knowledge/internal/runner"
	"github.com/helios/poc/knowledge/internal/task"
)

// Record is the per-run verdict envelope.
type Record struct {
	Arm            string `json:"arm"`
	Task           string `json:"task"`
	Seed           int    `json:"seed"`
	Phase          int    `json:"phase"`
	BuildOK        bool   `json:"build_ok"`
	FunctionalPass bool   `json:"functional_pass"`
	AnalysisOK     bool   `json:"analysis_ok"` // oracles could run (code compiles)
	// Phase-2 only: did the extension pass, and did phase-1 behavior survive?
	Phase2Pass           bool `json:"phase2_pass,omitempty"`
	Phase1RegressionPass bool `json:"phase1_regression_pass,omitempty"`
	// ApplicableViolated maps each rule the task tempts to whether it was violated.
	ApplicableViolated map[string]bool   `json:"applicable_violated"`
	AllViolations      []check.Violation `json:"all_violations"`
	TestOutputTail     string            `json:"test_output_tail"`
}

// ScoreOne grades one run directory.
func ScoreOne(resultsDir string, t task.Task, arm string, seed int, phase int) (*Record, error) {
	segment := "runs"
	if phase == 2 {
		segment = "runs2"
	}
	runDir := filepath.Join(resultsDir, segment, arm, t.ID, fmt.Sprintf("seed%d", seed))
	workspace := filepath.Join(runDir, "workspace")
	if _, err := os.Stat(workspace); err != nil {
		return nil, fmt.Errorf("missing workspace: %w", err)
	}
	scoreDir := filepath.Join(runDir, "scoredir")
	if err := os.RemoveAll(scoreDir); err != nil {
		return nil, err
	}
	if err := runner.CopyTree(workspace, scoreDir); err != nil {
		return nil, err
	}
	// The clean room must not contain harness droppings.
	_ = os.Remove(filepath.Join(scoreDir, "check.sh"))

	record := &Record{
		Arm:                arm,
		Task:               t.ID,
		Seed:               seed,
		Phase:              max(phase, 1),
		ApplicableViolated: map[string]bool{},
	}

	// 1. Oracles on the agent's code, before verify injection.
	violations, err := check.Run(scoreDir, check.All())
	if err == nil {
		record.AnalysisOK = true
		record.AllViolations = violations
	}
	violated := map[string]bool{}
	for _, v := range record.AllViolations {
		violated[v.Rule] = true
	}
	for _, ruleID := range t.Tempts {
		record.ApplicableViolated[ruleID] = violated[ruleID]
	}

	// 2. Hermetic build.
	record.BuildOK = hermeticGo(scoreDir, "build", "./...") == nil

	// 3. Inject held-out tests, run the clean-room suite.
	verifySource := filepath.Join(t.VerifyDir(), "zz_verify_test.go")
	verifyData, err := os.ReadFile(verifySource)
	if err != nil {
		return nil, fmt.Errorf("read verify suite: %w", err)
	}
	if err := os.WriteFile(filepath.Join(scoreDir, "zz_verify_test.go"), verifyData, 0o644); err != nil {
		return nil, err
	}
	if record.Phase == 2 {
		phase2Data, err := os.ReadFile(filepath.Join(t.Phase2Dir(), "zz_phase2_test.go"))
		if err != nil {
			return nil, fmt.Errorf("read phase2 suite: %w", err)
		}
		if err := os.WriteFile(filepath.Join(scoreDir, "zz_phase2_test.go"), phase2Data, 0o644); err != nil {
			return nil, err
		}
	}
	testErr := hermeticGoCapture(scoreDir, &record.TestOutputTail, "test", "-count=1", "-run", "^TestVerify", "./...")
	record.FunctionalPass = record.BuildOK && testErr == nil
	if record.Phase == 2 {
		var scratch string
		phase2Err := hermeticGoCapture(scoreDir, &scratch, "test", "-count=1", "-run", "^TestVerifyP2", "./...")
		record.Phase2Pass = record.BuildOK && phase2Err == nil
		regressionErr := hermeticGoCapture(scoreDir, &scratch, "test", "-count=1", "-run", "^TestVerify", "-skip", "^TestVerifyP2", "./...")
		record.Phase1RegressionPass = record.BuildOK && regressionErr == nil
	}

	data, err := json.MarshalIndent(record, "", "  ")
	if err != nil {
		return nil, err
	}
	if err := os.WriteFile(filepath.Join(runDir, "score.json"), append(data, '\n'), 0o644); err != nil {
		return nil, err
	}
	return record, nil
}

// ScoreAll grades every run found under resultsDir (both phases) for the
// given tasks.
func ScoreAll(resultsDir string, tasks []task.Task) error {
	if err := scorePhase(resultsDir, tasks, 1); err != nil {
		return err
	}
	if _, err := os.Stat(filepath.Join(resultsDir, "runs2")); err == nil {
		return scorePhase(resultsDir, tasks, 2)
	}
	return nil
}

func scorePhase(resultsDir string, tasks []task.Task, phase int) error {
	taskByID := map[string]task.Task{}
	for _, t := range tasks {
		taskByID[t.ID] = t
	}
	segment := "runs"
	if phase == 2 {
		segment = "runs2"
	}
	runsDir := filepath.Join(resultsDir, segment)
	arms, err := os.ReadDir(runsDir)
	if err != nil {
		return err
	}
	for _, armEntry := range arms {
		if !armEntry.IsDir() {
			continue
		}
		taskEntries, err := os.ReadDir(filepath.Join(runsDir, armEntry.Name()))
		if err != nil {
			return err
		}
		for _, taskEntry := range taskEntries {
			t, ok := taskByID[taskEntry.Name()]
			if !ok {
				continue
			}
			seedEntries, err := os.ReadDir(filepath.Join(runsDir, armEntry.Name(), taskEntry.Name()))
			if err != nil {
				return err
			}
			names := []string{}
			for _, s := range seedEntries {
				names = append(names, s.Name())
			}
			sort.Strings(names)
			for _, name := range names {
				if !strings.HasPrefix(name, "seed") {
					continue
				}
				var seed int
				if _, err := fmt.Sscanf(name, "seed%d", &seed); err != nil {
					continue
				}
				record, err := ScoreOne(resultsDir, t, armEntry.Name(), seed, phase)
				if err != nil {
					fmt.Fprintf(os.Stderr, "SCORE ERROR %s/%s/%s: %v\n", armEntry.Name(), t.ID, name, err)
					continue
				}
				fmt.Printf("SCORE p%d %s/%s/%s functional=%v analysis=%v violations=%d\n",
					phase, armEntry.Name(), t.ID, name, record.FunctionalPass, record.AnalysisOK, len(record.AllViolations))
			}
		}
	}
	return nil
}

func hermeticEnv() []string {
	env := os.Environ()
	env = append(env, "GOPROXY=off", "GOFLAGS=-mod=mod")
	return env
}

func hermeticGo(dir string, args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	command := exec.CommandContext(ctx, "go", args...)
	command.Dir = dir
	command.Env = hermeticEnv()
	return command.Run()
}

func hermeticGoCapture(dir string, tail *string, args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	command := exec.CommandContext(ctx, "go", args...)
	command.Dir = dir
	command.Env = hermeticEnv()
	output, err := command.CombinedOutput()
	text := string(output)
	const tailLimit = 4000
	if len(text) > tailLimit {
		text = text[len(text)-tailLimit:]
	}
	*tail = text
	return err
}
