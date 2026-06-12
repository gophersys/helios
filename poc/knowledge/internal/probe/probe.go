// Package probe measures model CAPABILITY independently of APPLICATION: a
// tool-less, single-turn question per rule. A baseline coding violation can
// mean "never knew" or "knew but ignored"; the probe disambiguates:
//
//	knowledge_rate ≈ 0 and violation high  → never knew (knowledge-base value is real)
//	knowledge_rate high and violation high → knew but ignored (delivery problem, not knowledge problem)
package probe

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/helios/poc/knowledge/internal/rule"
)

// Sample is one probe answer.
type Sample struct {
	Answer  string `json:"answer"`
	Matched bool   `json:"matched"`
}

// Result is the per-rule probe outcome.
type Result struct {
	Rule          string   `json:"rule"`
	Question      string   `json:"question"`
	ExpectMarkers []string `json:"expect_markers"`
	Samples       []Sample `json:"samples"`
	KnowledgeRate float64  `json:"knowledge_rate"`
}

// Run executes n samples per probed rule, sequentially (probes are cheap;
// sequential keeps them off the experiment's rate budget).
func Run(rules []rule.Rule, model string, samples int, resultsDir string) ([]Result, error) {
	var results []Result
	for _, r := range rules {
		if r.Probe == nil {
			continue
		}
		result := Result{Rule: r.ID, Question: r.Probe.Question, ExpectMarkers: r.Probe.ExpectMarkers}
		for i := 0; i < samples; i++ {
			answer, err := ask(model, r.Probe.Question)
			if err != nil {
				return nil, fmt.Errorf("probe %s sample %d: %w", r.ID, i+1, err)
			}
			sample := Sample{Answer: answer}
			for _, marker := range r.Probe.ExpectMarkers {
				if strings.Contains(answer, marker) {
					sample.Matched = true
					break
				}
			}
			result.Samples = append(result.Samples, sample)
			if sample.Matched {
				result.KnowledgeRate++
			}
		}
		result.KnowledgeRate /= float64(samples)
		fmt.Printf("PROBE %-25s knowledge_rate=%.0f%%\n", result.Rule, result.KnowledgeRate*100)
		results = append(results, result)
	}
	data, err := json.MarshalIndent(struct {
		Model   string   `json:"model"`
		Results []Result `json:"results"`
	}{Model: model, Results: results}, "", "  ")
	if err != nil {
		return nil, err
	}
	if err := os.WriteFile(filepath.Join(resultsDir, "probes.json"), append(data, '\n'), 0o644); err != nil {
		return nil, err
	}
	return results, nil
}

func ask(model, question string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	command := exec.CommandContext(ctx, "omp",
		"-p", "--mode", "text",
		"--model", model,
		"--thinking", "low",
		"--no-tools", "--no-extensions", "--no-skills", "--no-rules", "--no-lsp", "--no-title",
		"--no-session",
		question,
	)
	output, err := command.Output()
	if err != nil {
		return "", err
	}
	return string(output), nil
}
