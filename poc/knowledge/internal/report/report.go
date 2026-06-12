// Package report aggregates run + score records into aggregate.json and a
// deterministic markdown report. All ordering is lexicographic; no
// timestamps enter the aggregate, so re-running report on the same results is
// byte-identical.
package report

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/helios/poc/knowledge/internal/rule"
	"github.com/helios/poc/knowledge/internal/runner"
	"github.com/helios/poc/knowledge/internal/score"
)

type runCell struct {
	run   runner.RunRecord
	score score.Record
}

// ArmSummary aggregates one arm.
type ArmSummary struct {
	Arm                string  `json:"arm"`
	Runs               int     `json:"runs"`
	FunctionalPassRate float64 `json:"functional_pass_rate"`
	MeanOutputTokens   float64 `json:"mean_output_tokens"`
	StdOutputTokens    float64 `json:"std_output_tokens"`
	MeanDurationSec    float64 `json:"mean_duration_seconds"`
	MeanTurns          float64 `json:"mean_turns"`
	TotalCostUSD       float64 `json:"total_cost_usd"`
	TimedOut           int     `json:"timed_out"`
	// MeanTemptedViolations is the average count of violated tempted rules per run.
	MeanTemptedViolations float64 `json:"mean_tempted_violations"`
}

// RuleArmCell is the violation rate of one rule under one arm.
type RuleArmCell struct {
	Applicable int     `json:"applicable"`
	Violated   int     `json:"violated"`
	Rate       float64 `json:"rate"`
}

// Phase2Summary aggregates second-task velocity per arm.
type Phase2Summary struct {
	Arm                string  `json:"arm"`
	Runs               int     `json:"runs"`
	Phase2PassRate     float64 `json:"phase2_pass_rate"`
	RegressionPassRate float64 `json:"phase1_regression_pass_rate"`
	MeanOutputTokens   float64 `json:"mean_output_tokens"`
	MeanTurns          float64 `json:"mean_turns"`
	MeanDurationSec    float64 `json:"mean_duration_seconds"`
}

// Aggregate is the whole experiment, summarized.
type Aggregate struct {
	Arms []ArmSummary `json:"arms"`
	// RuleByArm[ruleID][arm]
	RuleByArm map[string]map[string]RuleArmCell `json:"rule_by_arm"`
	// Hypotheses: per rule, the pre-registered prediction vs the measured baseline rate.
	Hypotheses []HypothesisVerdict `json:"hypotheses"`
	// Phase2: second-task velocity (present only when runs2 exists).
	Phase2 []Phase2Summary `json:"phase2,omitempty"`
}

// HypothesisVerdict checks a pre-registered baseline-violation prediction.
type HypothesisVerdict struct {
	Rule       string  `json:"rule"`
	Category   string  `json:"category"`
	Predicted  string  `json:"predicted"` // low | medium | high
	Measured   float64 `json:"measured_baseline_rate"`
	Applicable int     `json:"applicable_baseline_runs"`
	Verdict    string  `json:"verdict"` // CONFIRMED | REFUTED | INSUFFICIENT-DATA
}

// band converts a measured rate into the prediction vocabulary.
// low: <= 1/3, medium: (1/3, 2/3], high: > 2/3.
func band(rate float64) string {
	switch {
	case rate <= 1.0/3.0:
		return "low"
	case rate <= 2.0/3.0:
		return "medium"
	default:
		return "high"
	}
}

// Build reads every run under resultsDir and produces the aggregate.
func Build(resultsDir string, rules []rule.Rule) (*Aggregate, error) {
	cells, err := loadCells(resultsDir)
	if err != nil {
		return nil, err
	}
	if len(cells) == 0 {
		return nil, fmt.Errorf("no completed runs under %s", resultsDir)
	}

	byArm := map[string][]runCell{}
	for _, c := range cells {
		byArm[c.run.Arm] = append(byArm[c.run.Arm], c)
	}
	armNames := make([]string, 0, len(byArm))
	for name := range byArm {
		armNames = append(armNames, name)
	}
	sort.Strings(armNames)

	aggregate := &Aggregate{RuleByArm: map[string]map[string]RuleArmCell{}}

	for _, name := range armNames {
		group := byArm[name]
		summary := ArmSummary{Arm: name, Runs: len(group)}
		var outputs []float64
		for _, c := range group {
			if c.score.FunctionalPass {
				summary.FunctionalPassRate++
			}
			if c.run.TimedOut {
				summary.TimedOut++
			}
			summary.MeanDurationSec += c.run.DurationSeconds
			summary.MeanTurns += float64(c.run.AssistantTurns)
			summary.TotalCostUSD += c.run.Tokens.CostUSD
			outputs = append(outputs, float64(c.run.Tokens.Output))
			for _, violated := range c.score.ApplicableViolated {
				if violated {
					summary.MeanTemptedViolations++
				}
			}
		}
		n := float64(len(group))
		summary.FunctionalPassRate /= n
		summary.MeanDurationSec /= n
		summary.MeanTurns /= n
		summary.MeanTemptedViolations /= n
		summary.MeanOutputTokens = mean(outputs)
		summary.StdOutputTokens = standardDeviation(outputs)
		aggregate.Arms = append(aggregate.Arms, summary)
	}

	// rule × arm violation rates over applicable, analyzable runs
	for _, c := range cells {
		if !c.score.AnalysisOK {
			continue
		}
		for ruleID, violated := range c.score.ApplicableViolated {
			if aggregate.RuleByArm[ruleID] == nil {
				aggregate.RuleByArm[ruleID] = map[string]RuleArmCell{}
			}
			cell := aggregate.RuleByArm[ruleID][c.run.Arm]
			cell.Applicable++
			if violated {
				cell.Violated++
			}
			aggregate.RuleByArm[ruleID][c.run.Arm] = cell
		}
	}
	for ruleID, arms := range aggregate.RuleByArm {
		for armName, cell := range arms {
			if cell.Applicable > 0 {
				cell.Rate = float64(cell.Violated) / float64(cell.Applicable)
			}
			aggregate.RuleByArm[ruleID][armName] = cell
		}
	}

	// hypothesis verdicts against the baseline arm
	for _, r := range rules {
		cell := aggregate.RuleByArm[r.ID]["baseline"]
		verdict := HypothesisVerdict{
			Rule:       r.ID,
			Category:   string(r.Category),
			Predicted:  r.HypothesisBaselineViolation,
			Measured:   cell.Rate,
			Applicable: cell.Applicable,
		}
		switch {
		case cell.Applicable < 3:
			verdict.Verdict = "INSUFFICIENT-DATA"
		case band(cell.Rate) == r.HypothesisBaselineViolation:
			verdict.Verdict = "CONFIRMED"
		default:
			verdict.Verdict = "REFUTED"
		}
		aggregate.Hypotheses = append(aggregate.Hypotheses, verdict)
	}
	sort.Slice(aggregate.Hypotheses, func(i, j int) bool {
		return aggregate.Hypotheses[i].Rule < aggregate.Hypotheses[j].Rule
	})

	// phase 2 (second-task velocity), if present
	phase2Cells, err := loadCellsFrom(resultsDir, "runs2")
	if err == nil && len(phase2Cells) > 0 {
		byArm2 := map[string][]runCell{}
		for _, c := range phase2Cells {
			byArm2[c.run.Arm] = append(byArm2[c.run.Arm], c)
		}
		names := make([]string, 0, len(byArm2))
		for n := range byArm2 {
			names = append(names, n)
		}
		sort.Strings(names)
		for _, name := range names {
			group := byArm2[name]
			s := Phase2Summary{Arm: name, Runs: len(group)}
			var outputs []float64
			for _, c := range group {
				if c.score.Phase2Pass {
					s.Phase2PassRate++
				}
				if c.score.Phase1RegressionPass {
					s.RegressionPassRate++
				}
				s.MeanTurns += float64(c.run.AssistantTurns)
				s.MeanDurationSec += c.run.DurationSeconds
				outputs = append(outputs, float64(c.run.Tokens.Output))
			}
			n := float64(len(group))
			s.Phase2PassRate /= n
			s.RegressionPassRate /= n
			s.MeanTurns /= n
			s.MeanDurationSec /= n
			s.MeanOutputTokens = mean(outputs)
			aggregate.Phase2 = append(aggregate.Phase2, s)
		}
	}
	return aggregate, nil
}

// WriteMarkdown renders the aggregate to report.md and aggregate.json.
func WriteMarkdown(resultsDir string, aggregate *Aggregate, model string) error {
	data, err := json.MarshalIndent(aggregate, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(resultsDir, "aggregate.json"), append(data, '\n'), 0o644); err != nil {
		return err
	}

	var b strings.Builder
	fmt.Fprintf(&b, "# Knowledge-library POC — experiment report\n\n")
	fmt.Fprintf(&b, "Model: `%s` · Harness: omp non-interactive · Scoring: clean-room held-out tests + deterministic rule oracles\n\n", model)

	b.WriteString("## Arms\n\n")
	b.WriteString("| arm | runs | functional pass | tempted-rule violations/run | mean out-tokens | ±sd | mean turns | mean s/run | total cost $ | timeouts |\n")
	b.WriteString("|---|---|---|---|---|---|---|---|---|---|\n")
	for _, a := range aggregate.Arms {
		fmt.Fprintf(&b, "| %s | %d | %.0f%% | %.2f | %.0f | %.0f | %.1f | %.0f | %.4f | %d |\n",
			a.Arm, a.Runs, a.FunctionalPassRate*100, a.MeanTemptedViolations,
			a.MeanOutputTokens, a.StdOutputTokens, a.MeanTurns, a.MeanDurationSec, a.TotalCostUSD, a.TimedOut)
	}

	b.WriteString("\n## Rule × arm violation rates (over applicable runs)\n\n")
	ruleIDs := make([]string, 0, len(aggregate.RuleByArm))
	for id := range aggregate.RuleByArm {
		ruleIDs = append(ruleIDs, id)
	}
	sort.Strings(ruleIDs)
	armNames := make([]string, 0, len(aggregate.Arms))
	for _, a := range aggregate.Arms {
		armNames = append(armNames, a.Arm)
	}
	fmt.Fprintf(&b, "| rule | %s |\n|---|%s\n", strings.Join(armNames, " | "), strings.Repeat("---|", len(armNames)))
	for _, id := range ruleIDs {
		fmt.Fprintf(&b, "| %s |", id)
		for _, armName := range armNames {
			cell := aggregate.RuleByArm[id][armName]
			if cell.Applicable == 0 {
				b.WriteString(" – |")
			} else {
				fmt.Fprintf(&b, " %d/%d (%.0f%%) |", cell.Violated, cell.Applicable, cell.Rate*100)
			}
		}
		b.WriteString("\n")
	}

	b.WriteString("\n## Pre-registered hypotheses (baseline violation rates)\n\n")
	b.WriteString("Bands: low ≤ 33% < medium ≤ 67% < high.\n\n")
	b.WriteString("| rule | category | predicted | measured | n | verdict |\n|---|---|---|---|---|---|\n")
	for _, h := range aggregate.Hypotheses {
		fmt.Fprintf(&b, "| %s | %s | %s | %.0f%% | %d | %s |\n",
			h.Rule, h.Category, h.Predicted, h.Measured*100, h.Applicable, h.Verdict)
	}

	if len(aggregate.Phase2) > 0 {
		b.WriteString("\n## Second-task velocity (phase 2: a fresh agent extends each arm's phase-1 code)\n\n")
		b.WriteString("| arm | runs | phase-2 pass | phase-1 regression pass | mean out-tokens | mean turns | mean s/run |\n|---|---|---|---|---|---|---|\n")
		for _, s := range aggregate.Phase2 {
			fmt.Fprintf(&b, "| %s | %d | %.0f%% | %.0f%% | %.0f | %.1f | %.0f |\n",
				s.Arm, s.Runs, s.Phase2PassRate*100, s.RegressionPassRate*100,
				s.MeanOutputTokens, s.MeanTurns, s.MeanDurationSec)
		}
	}

	return os.WriteFile(filepath.Join(resultsDir, "report.md"), []byte(b.String()), 0o644)
}

func loadCells(resultsDir string) ([]runCell, error) {
	return loadCellsFrom(resultsDir, "runs")
}

func loadCellsFrom(resultsDir, segment string) ([]runCell, error) {
	var cells []runCell
	pattern := filepath.Join(resultsDir, segment, "*", "*", "seed*")
	dirs, err := filepath.Glob(pattern)
	if err != nil {
		return nil, err
	}
	sort.Strings(dirs)
	for _, dir := range dirs {
		var c runCell
		if !readJSON(filepath.Join(dir, "run.json"), &c.run) {
			continue
		}
		if !readJSON(filepath.Join(dir, "score.json"), &c.score) {
			continue
		}
		cells = append(cells, c)
	}
	return cells, nil
}

func readJSON(path string, target any) bool {
	data, err := os.ReadFile(path)
	if err != nil {
		return false
	}
	return json.Unmarshal(data, target) == nil
}

func mean(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	sum := 0.0
	for _, v := range values {
		sum += v
	}
	return sum / float64(len(values))
}

func standardDeviation(values []float64) float64 {
	if len(values) < 2 {
		return 0
	}
	m := mean(values)
	sum := 0.0
	for _, v := range values {
		sum += (v - m) * (v - m)
	}
	return math.Sqrt(sum / float64(len(values)-1))
}
