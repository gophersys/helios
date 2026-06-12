// harness drives the knowledge-library experiment end to end.
//
//	harness render                  # rules DB → arm artifacts (pure function)
//	harness selftest                # verify suites must pass on references; references must be rule-clean
//	harness run    [flags]          # execute the arm × task × seed matrix via omp
//	harness score                   # clean-room grading of every completed run
//	harness report                  # aggregate.json + report.md
//
// Every step is idempotent and deterministic given the same inputs; `run` is
// the only step that talks to a model.
package main

import (
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/helios/poc/knowledge/internal/check"
	"github.com/helios/poc/knowledge/internal/probe"
	"github.com/helios/poc/knowledge/internal/render"
	"github.com/helios/poc/knowledge/internal/report"
	"github.com/helios/poc/knowledge/internal/rule"
	"github.com/helios/poc/knowledge/internal/runner"
	"github.com/helios/poc/knowledge/internal/score"
	"github.com/helios/poc/knowledge/internal/task"
)

// resultsDir separates result sets per label (e.g. per model) so the same
// matrix can be re-run against another model and diffed.
func resultsDir(root, label string) string {
	if label == "" {
		return filepath.Join(root, "results")
	}
	return filepath.Join(root, "results-"+label)
}

func main() {
	if len(os.Args) < 2 {
		fatal("usage: harness <render|selftest|run|score|report> [flags]")
	}
	root, err := moduleRoot()
	if err != nil {
		fatal("locate module root: %v", err)
	}

	rules, err := rule.LoadDir(filepath.Join(root, "rules"))
	if err != nil {
		fatal("load rules: %v", err)
	}
	tasks, err := task.LoadDir(filepath.Join(root, "tasks"))
	if err != nil {
		fatal("load tasks: %v", err)
	}

	switch os.Args[1] {
	case "render":
		if err := render.WriteArtifacts(filepath.Join(root, "arms"), rules); err != nil {
			fatal("render: %v", err)
		}
		fmt.Println("rendered arms/monolithic/GUIDE.md and arms/hybrid/CORE.md")

	case "selftest":
		if err := selftest(root, tasks); err != nil {
			fatal("selftest: %v", err)
		}
		fmt.Println("selftest: all verify suites pass on references; all references rule-clean")

	case "run":
		flags := flag.NewFlagSet("run", flag.ExitOnError)
		model := flags.String("model", "openrouter/deepseek/deepseek-v4-flash", "model id")
		thinking := flags.String("thinking", "low", "thinking level")
		seeds := flags.Int("seeds", 3, "seeds per cell")
		parallel := flags.Int("parallel", 4, "concurrent omp processes")
		timeout := flags.Int("timeout", 600, "per-run wall-clock budget (seconds)")
		tokenBudget := flags.Int("token-budget", 400000, "per-run input+output token budget (post-hoc flag)")
		armsFilter := flags.String("arms", "", "comma-separated arm filter (default: all)")
		tasksFilter := flags.String("tasks", "", "comma-separated task filter (default: all)")
		phase := flags.Int("phase", 1, "1 = main matrix; 2 = second-task velocity (extends phase-1 workspaces)")
		label := flags.String("label", "", "results label, e.g. a model slug — runs land in results-<label>/")
		flags.Parse(os.Args[2:])

		rulecheckBinary := filepath.Join(root, "bin", "rulecheck")
		if _, err := os.Stat(rulecheckBinary); err != nil {
			fatal("bin/rulecheck missing — run: go build -o bin/rulecheck ./cmd/rulecheck")
		}
		if err := render.WriteArtifacts(filepath.Join(root, "arms"), rules); err != nil {
			fatal("render: %v", err)
		}
		arms := filterArms(runner.Arms(filepath.Join(root, "arms")), *armsFilter)
		selectedTasks := filterTasks(tasks, *tasksFilter)
		cfg := runner.Config{
			RootDir:         root,
			ResultsDir:      resultsDir(root, *label),
			Model:           *model,
			Thinking:        *thinking,
			Seeds:           *seeds,
			Parallel:        *parallel,
			TimeoutSeconds:  *timeout,
			TokenBudget:     *tokenBudget,
			RulecheckBinary: rulecheckBinary,
			Phase:           *phase,
		}
		if err := runner.RunMatrix(cfg, arms, selectedTasks); err != nil {
			fatal("run: %v", err)
		}

	case "score":
		flags := flag.NewFlagSet("score", flag.ExitOnError)
		label := flags.String("label", "", "results label")
		flags.Parse(os.Args[2:])
		if err := score.ScoreAll(resultsDir(root, *label), tasks); err != nil {
			fatal("score: %v", err)
		}

	case "report":
		flags := flag.NewFlagSet("report", flag.ExitOnError)
		model := flags.String("model", "openrouter/deepseek/deepseek-v4-flash", "model id (for the header)")
		label := flags.String("label", "", "results label")
		flags.Parse(os.Args[2:])
		aggregate, err := report.Build(resultsDir(root, *label), rules)
		if err != nil {
			fatal("report: %v", err)
		}
		if err := report.WriteMarkdown(resultsDir(root, *label), aggregate, *model); err != nil {
			fatal("report: %v", err)
		}
		fmt.Println("wrote aggregate.json and report.md under " + resultsDir(root, *label))

	case "probe":
		flags := flag.NewFlagSet("probe", flag.ExitOnError)
		model := flags.String("model", "openrouter/deepseek/deepseek-v4-flash", "model id")
		samples := flags.Int("samples", 5, "samples per probed rule")
		label := flags.String("label", "", "results label")
		flags.Parse(os.Args[2:])
		if _, err := probe.Run(rules, *model, *samples, resultsDir(root, *label)); err != nil {
			fatal("probe: %v", err)
		}
		fmt.Println("wrote probes.json under " + resultsDir(root, *label))

	default:
		fatal("unknown subcommand %q", os.Args[1])
	}
}

// selftest assembles workspace+reference+verify per task in a temp dir, runs
// the held-out suite, and runs every oracle — the references must be both
// functionally correct and rule-clean, proving rules and contracts are
// jointly satisfiable.
func selftest(root string, tasks []task.Task) error {
	for _, t := range tasks {
		dir, err := os.MkdirTemp("", "selftest-"+t.ID+"-")
		if err != nil {
			return err
		}
		defer os.RemoveAll(dir)
		for _, source := range []string{t.WorkspaceDir(), t.ReferenceDir()} {
			if err := runner.CopyTree(source, dir); err != nil {
				return fmt.Errorf("%s: copy %s: %w", t.ID, source, err)
			}
		}
		verifyData, err := os.ReadFile(filepath.Join(t.VerifyDir(), "zz_verify_test.go"))
		if err != nil {
			return fmt.Errorf("%s: %w", t.ID, err)
		}
		if err := os.WriteFile(filepath.Join(dir, "zz_verify_test.go"), verifyData, 0o644); err != nil {
			return err
		}
		if t.HasPhase2() {
			// the phase-2 reference extension + its held-out suite must also hold
			if err := runner.CopyTree(filepath.Join(t.Phase2Dir(), "reference"), dir); err != nil {
				return fmt.Errorf("%s: copy phase2 reference: %w", t.ID, err)
			}
			phase2Data, err := os.ReadFile(filepath.Join(t.Phase2Dir(), "zz_phase2_test.go"))
			if err != nil {
				return fmt.Errorf("%s: %w", t.ID, err)
			}
			if err := os.WriteFile(filepath.Join(dir, "zz_phase2_test.go"), phase2Data, 0o644); err != nil {
				return err
			}
		}
		command := exec.Command("go", "test", "-count=1", "-run", "^TestVerify", "./...")
		command.Dir = dir
		command.Env = append(os.Environ(), "GOPROXY=off")
		if output, err := command.CombinedOutput(); err != nil {
			return fmt.Errorf("%s: verify suite failed on reference:\n%s", t.ID, output)
		}
		violations, err := check.Run(dir, check.All())
		if err != nil {
			return fmt.Errorf("%s: oracle run: %w", t.ID, err)
		}
		if len(violations) > 0 {
			return fmt.Errorf("%s: reference violates rules: %+v", t.ID, violations)
		}
		fmt.Printf("selftest %s: ok\n", t.ID)
	}
	return nil
}

func filterArms(arms []runner.Arm, filter string) []runner.Arm {
	if filter == "" {
		return arms
	}
	wanted := map[string]bool{}
	for _, name := range strings.Split(filter, ",") {
		wanted[strings.TrimSpace(name)] = true
	}
	var out []runner.Arm
	for _, a := range arms {
		if wanted[a.Name] {
			out = append(out, a)
		}
	}
	return out
}

func filterTasks(tasks []task.Task, filter string) []task.Task {
	if filter == "" {
		return tasks
	}
	wanted := map[string]bool{}
	for _, name := range strings.Split(filter, ",") {
		wanted[strings.TrimSpace(name)] = true
	}
	var out []task.Task
	for _, t := range tasks {
		if wanted[t.ID] {
			out = append(out, t)
		}
	}
	return out
}

// moduleRoot walks up from the executable's working directory to the dir
// containing go.mod with our module path.
func moduleRoot() (string, error) {
	dir, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for {
		data, err := os.ReadFile(filepath.Join(dir, "go.mod"))
		if err == nil && strings.Contains(string(data), "module github.com/helios/poc/knowledge") {
			return dir, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return "", fmt.Errorf("go.mod for poc/knowledge not found above %s", dir)
		}
		dir = parent
	}
}

func fatal(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(1)
}
