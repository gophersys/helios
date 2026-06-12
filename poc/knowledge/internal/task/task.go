// Package task loads the temptation-task suite.
package task

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"gopkg.in/yaml.v3"
)

// Task is one temptation task.
type Task struct {
	ID      string   `yaml:"id"`
	Package string   `yaml:"package"`
	Tempts  []string `yaml:"tempts"` // rule IDs this task tempts (the applicability set)

	Dir string `yaml:"-"` // tasks/<id>
}

// WorkspaceDir is the agent-facing scaffold.
func (t *Task) WorkspaceDir() string { return filepath.Join(t.Dir, "workspace") }

// VerifyDir holds the held-out clean-room tests. The underscore prefix keeps
// the go tool from treating these files as part of the harness module.
func (t *Task) VerifyDir() string { return filepath.Join(t.Dir, "_verify") }

// ReferenceDir holds the gold implementation (never shown to the agent).
func (t *Task) ReferenceDir() string { return filepath.Join(t.Dir, "_reference") }

// Phase2Dir holds the second-task-velocity extension: spec2.md, the held-out
// zz_phase2_test.go suite, and reference/ with the gold extension.
func (t *Task) Phase2Dir() string { return filepath.Join(t.Dir, "_phase2") }

// HasPhase2 reports whether this task has a velocity extension.
func (t *Task) HasPhase2() bool {
	_, err := os.Stat(filepath.Join(t.Phase2Dir(), "spec2.md"))
	return err == nil
}

// LoadDir loads every task under dir, sorted by ID.
func LoadDir(dir string) ([]Task, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var tasks []Task
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		path := filepath.Join(dir, e.Name(), "task.yaml")
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("read %s: %w", path, err)
		}
		var t Task
		if err := yaml.Unmarshal(data, &t); err != nil {
			return nil, fmt.Errorf("parse %s: %w", path, err)
		}
		if t.ID == "" || t.Package == "" || len(t.Tempts) == 0 {
			return nil, fmt.Errorf("%s: id, package and tempts are required", path)
		}
		t.Dir = filepath.Join(dir, e.Name())
		tasks = append(tasks, t)
	}
	sort.Slice(tasks, func(i, j int) bool { return tasks[i].ID < tasks[j].ID })
	if len(tasks) == 0 {
		return nil, fmt.Errorf("no tasks found in %s", dir)
	}
	return tasks, nil
}
