package configuration

import (
	"errors"
	"strconv"
	"testing"
)

func staticSource(m map[string]string) Source {
	return func(key string) (string, bool) {
		v, ok := m[key]
		return v, ok
	}
}

func TestLoadDefaults(t *testing.T) {
	cfg, err := Load(staticSource(nil))
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

func TestLoadPort(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  int
	}{
		{"valid min", "1", 1},
		{"valid max", "65535", 65535},
		{"valid typical", "3000", 3000},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg, err := Load(staticSource(map[string]string{"HELIOS_PORT": tt.input}))
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if cfg.Port != tt.want {
				t.Errorf("Port = %d, want %d", cfg.Port, tt.want)
			}
		})
	}
}

func TestLoadPortError(t *testing.T) {
	tests := []struct {
		name  string
		input string
	}{
		{"not a number", "abc"},
		{"zero", "0"},
		{"negative", "-1"},
		{"overflow", "65536"},
		{"overflow huge", "99999"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := Load(staticSource(map[string]string{"HELIOS_PORT": tt.input}))
			if err == nil {
				t.Fatal("expected error, got nil")
			}
		})
	}
}

func TestLoadPortPreservesParseError(t *testing.T) {
	_, err := Load(staticSource(map[string]string{"HELIOS_PORT": "abc"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	var numErr *strconv.NumError
	if !errors.As(err, &numErr) {
		t.Errorf("error does not wrap *strconv.NumError: %v", err)
	}
}

func TestLoadName(t *testing.T) {
	cfg, err := Load(staticSource(map[string]string{"HELIOS_NAME": "my-server"}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Name != "my-server" {
		t.Errorf("Name = %q, want \"my-server\"", cfg.Name)
	}
}

func TestLoadNameEmpty(t *testing.T) {
	_, err := Load(staticSource(map[string]string{"HELIOS_NAME": ""}))
	if err == nil {
		t.Fatal("expected error for empty name, got nil")
	}
}

func TestLoadDebug(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  bool
	}{
		{"true", "true", true},
		{"false", "false", false},
		{"1", "1", true},
		{"0", "0", false},
		{"T", "T", true},
		{"F", "F", false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg, err := Load(staticSource(map[string]string{"HELIOS_DEBUG": tt.input}))
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if cfg.Debug != tt.want {
				t.Errorf("Debug = %t, want %t", cfg.Debug, tt.want)
			}
		})
	}
}

func TestLoadDebugError(t *testing.T) {
	_, err := Load(staticSource(map[string]string{"HELIOS_DEBUG": "notabool"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestLoadDebugPreservesParseError(t *testing.T) {
	_, err := Load(staticSource(map[string]string{"HELIOS_DEBUG": "bogus"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	var numErr *strconv.NumError
	if !errors.As(err, &numErr) {
		t.Errorf("error does not wrap *strconv.NumError: %v", err)
	}
}

func TestLoadPartialConfig(t *testing.T) {
	cfg, err := Load(staticSource(map[string]string{"HELIOS_PORT": "9090"}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 9090 {
		t.Errorf("Port = %d, want 9090", cfg.Port)
	}
	if cfg.Name != "helios" {
		t.Errorf("Name = %q, want \"helios\"", cfg.Name)
	}
	if cfg.Debug {
		t.Errorf("Debug = true, want false")
	}
}