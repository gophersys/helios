package configuration

import (
	"errors"
	"strconv"
	"testing"
)

// static returns a source that serves key->value from a fixed map.
func static(m map[string]string) Source {
	return func(key string) (string, bool) {
		v, ok := m[key]
		return v, ok
	}
}

func TestLoadDefaults(t *testing.T) {
	cfg, err := Load(func(_ string) (string, bool) {
		return "", false
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080", cfg.Port)
	}
	if cfg.Name != "helios" {
		t.Errorf("Name = %q, want \"helios\"", cfg.Name)
	}
	if cfg.Debug {
		t.Errorf("Debug = true, want false")
	}
}

func TestLoadAllExplicit(t *testing.T) {
	cfg, err := Load(static(map[string]string{
		"HELIOS_PORT":   "9090",
		"HELIOS_NAME":   "myapp",
		"HELIOS_DEBUG":  "true",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 9090 {
		t.Errorf("Port = %d, want 9090", cfg.Port)
	}
	if cfg.Name != "myapp" {
		t.Errorf("Name = %q, want \"myapp\"", cfg.Name)
	}
	if !cfg.Debug {
		t.Errorf("Debug = false, want true")
	}
}

func TestLoadPartialOverride(t *testing.T) {
	cfg, err := Load(static(map[string]string{
		"HELIOS_NAME": "partial",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080 (default)", cfg.Port)
	}
	if cfg.Name != "partial" {
		t.Errorf("Name = %q, want \"partial\"", cfg.Name)
	}
	if cfg.Debug {
		t.Errorf("Debug = true, want false (default)")
	}
}

func TestLoadPortMinMax(t *testing.T) {
	tests := []struct {
		val  string
		want int
	}{
		{"1", 1},
		{"65535", 65535},
	}
	for _, tt := range tests {
		cfg, err := Load(static(map[string]string{"HELIOS_PORT": tt.val}))
		if err != nil {
			t.Errorf("HELIOS_PORT=%q: unexpected error: %v", tt.val, err)
			continue
		}
		if cfg.Port != tt.want {
			t.Errorf("HELIOS_PORT=%q: got %d, want %d", tt.val, cfg.Port, tt.want)
		}
	}
}

func TestLoadPortParseError(t *testing.T) {
	_, err := Load(static(map[string]string{"HELIOS_PORT": "not-a-number"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if ne, ok := errors.AsType[*strconv.NumError](err); ok {
		if ne.Func != "Atoi" {
			t.Errorf("NumError.Func = %q, want \"Atoi\"", ne.Func)
		}
	} else {
		t.Errorf("expected *strconv.NumError, got %T", errors.Unwrap(err))
	}
}

func TestLoadPortOutOfRange(t *testing.T) {
	tests := []string{"0", "65536", "-1", "100000"}
	for _, val := range tests {
		_, err := Load(static(map[string]string{"HELIOS_PORT": val}))
		if err == nil {
			t.Errorf("HELIOS_PORT=%q: expected error, got nil", val)
		}
	}
}

func TestLoadNameEmpty(t *testing.T) {
	_, err := Load(static(map[string]string{"HELIOS_NAME": ""}))
	if err == nil {
		t.Fatal("expected error for empty name, got nil")
	}
}

func TestLoadDebugParseError(t *testing.T) {
	_, err := Load(static(map[string]string{"HELIOS_DEBUG": "not-a-bool"}))
	if err == nil {
		t.Fatal("expected error for bad debug, got nil")
	}
}

func TestLoadDebugParseBoolVariants(t *testing.T) {
	tests := []struct {
		val  string
		want bool
	}{
		{"true", true},
		{"TRUE", true},
		{"1", true},
		{"t", true},
		{"false", false},
		{"FALSE", false},
		{"0", false},
		{"f", false},
	}
	for _, tt := range tests {
		cfg, err := Load(static(map[string]string{"HELIOS_DEBUG": tt.val}))
		if err != nil {
			t.Errorf("HELIOS_DEBUG=%q: unexpected error: %v", tt.val, err)
			continue
		}
		if cfg.Debug != tt.want {
			t.Errorf("HELIOS_DEBUG=%q: got %t, want %t", tt.val, cfg.Debug, tt.want)
		}
	}
}