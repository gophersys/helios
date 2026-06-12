package agent

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// ConfigManager handles loading, merging, and validating agent configuration.
type ConfigManager struct {
	config AgentConfig
	path   string
}

// LoadConfig loads agent configuration from a JSON or YAML file.
func LoadConfig(path string) (*ConfigManager, error) {
	cm := &ConfigManager{
		config: DefaultConfig(),
		path:   path,
	}

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return cm, nil // Use defaults
		}
		return nil, fmt.Errorf("read config: %w", err)
	}

	if err := json.Unmarshal(data, &cm.config); err != nil {
		return nil, fmt.Errorf("parse config: %w", err)
	}

	if err := cm.Validate(); err != nil {
		return nil, fmt.Errorf("validate config: %w", err)
	}

	return cm, nil
}

// NewConfigManager creates a config manager from a struct.
func NewConfigManager(config AgentConfig) *ConfigManager {
	return &ConfigManager{config: config}
}

// Config returns the effective configuration.
func (cm *ConfigManager) Config() AgentConfig {
	return cm.config
}

// Validate checks configuration for obvious errors.
func (cm *ConfigManager) Validate() error {
	if cm.config.OMPPath == "" {
		cm.config.OMPPath = "omp"
	}
	if cm.config.Model == "" {
		cm.config.Model = "openrouter/deepseek/deepseek-v4-flash"
	}
	if cm.config.ThinkingLevel == "" {
		cm.config.ThinkingLevel = "medium"
	}
	if cm.config.MaxRunTime <= 0 {
		cm.config.MaxRunTime = 15 * time.Minute
	}
	return nil
}

// Save persists configuration to the configured path.
func (cm *ConfigManager) Save() error {
	if cm.path == "" {
		return fmt.Errorf("no config path set")
	}
	dir := filepath.Dir(cm.path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("mkdir config dir: %w", err)
	}
	data, err := json.MarshalIndent(cm.config, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal config: %w", err)
	}
	return os.WriteFile(cm.path, data, 0644)
}

// WithOMP sets the OMP binary path.
func (cm *ConfigManager) WithOMP(path string) *ConfigManager {
	cm.config.OMPPath = path
	return cm
}

// WithModel sets the model identifier.
func (cm *ConfigManager) WithModel(model string) *ConfigManager {
	cm.config.Model = model
	return cm
}

// WithThinkingLevel sets the thinking level.
func (cm *ConfigManager) WithThinkingLevel(level string) *ConfigManager {
	cm.config.ThinkingLevel = level
	return cm
}

// WithInMemory enables in-memory sessions.
func (cm *ConfigManager) WithInMemory() *ConfigManager {
	cm.config.InMemory = true
	return cm
}

// WithLabel adds a label.
func (cm *ConfigManager) WithLabel(key, value string) *ConfigManager {
	if cm.config.Labels == nil {
		cm.config.Labels = make(map[string]string)
	}
	cm.config.Labels[key] = value
	return cm
}

// WithMaxRunTime sets the maximum run duration.
func (cm *ConfigManager) WithMaxRunTime(d time.Duration) *ConfigManager {
	cm.config.MaxRunTime = d
	return cm
}

// GenerateConfigTemplate writes a default config template as JSON string.
func GenerateConfigTemplate() string {
	return `{
  "omp_path": "omp",
  "model": "openrouter/deepseek/deepseek-v4-flash",
  "thinking_level": "high",
  "in_memory": false,
  "max_run_time": "15m",
  "auto_compaction": true,
  "auto_retry": true,
  "steering_mode": "one-at-a-time",
  "labels": {
    "environment": "development",
    "team": "helios"
  }
}`
}