package configuration

import (
	"errors"
	"fmt"
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
		val     string
		want    int
		wantErr bool
	}{
		{"80", 80, false},
		{"1", 1, false},
		{"65535", 65535, false},
		{"0", 0, true},
		{"65536", 0, true},
		{"-1", 0, true},
		{"abc", 0, true},
		{"", 0, true},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("HELIOS_PORT=%q", tt.val), func(t *testing.T) {
			cfg, err := Load(staticSource(map[string]string{"HELIOS_PORT": tt.val}))
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if cfg.Port != tt.want {
				t.Errorf("Port = %d, want %d", cfg.Port, tt.want)
			}
		})
	}
}

func TestLoadPortPreservesNumError(t *testing.T) {
	_, err := Load(staticSource(map[string]string{"HELIOS_PORT": "abc"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if numErr, ok := errors.AsType[*strconv.NumError](err); !ok {
		t.Fatalf("expected *strconv.NumError in error chain, got %T", err)
	} else if numErr.Func != "Atoi" || numErr.Num != "abc" {
		t.Errorf("unexpected NumError fields: %+v", numErr)
	}
}

func TestLoadName(t *testing.T) {
	tests := []struct {
		val     string
		want    string
		wantErr bool
	}{
		{"my-service", "my-service", false},
		{"", "", true},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("HELIOS_NAME=%q", tt.val), func(t *testing.T) {
			cfg, err := Load(staticSource(map[string]string{"HELIOS_NAME": tt.val}))
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if cfg.Name != tt.want {
				t.Errorf("Name = %q, want %q", cfg.Name, tt.want)
			}
		})
	}
}

func TestLoadDebug(t *testing.T) {
	tests := []struct {
		val     string
		want    bool
		wantErr bool
	}{
		{"true", true, false},
		{"1", true, false},
		{"false", false, false},
		{"0", false, false},
		{"TRUE", true, false},
		{"FALSE", false, false},
		{"yes", false, true},
		{"", false, true},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("HELIOS_DEBUG=%q", tt.val), func(t *testing.T) {
			cfg, err := Load(staticSource(map[string]string{"HELIOS_DEBUG": tt.val}))
			if tt.wantErr {
				if err == nil {
					t.Fatal("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if cfg.Debug != tt.want {
				t.Errorf("Debug = %t, want %t", cfg.Debug, tt.want)
			}
		})
	}
}

func TestLoadDebugPreservesParseError(t *testing.T) {
	_, err := Load(staticSource(map[string]string{"HELIOS_DEBUG": "yes"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if _, ok := errors.AsType[*strconv.NumError](err); !ok {
		t.Fatalf("expected *strconv.NumError in error chain, got %T", err)
	}
}

func TestLoadMultipleKeys(t *testing.T) {
	cfg, err := Load(staticSource(map[string]string{
		"HELIOS_PORT":   "9090",
		"HELIOS_NAME":   "production",
		"HELIOS_DEBUG":  "true",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 9090 {
		t.Errorf("Port = %d, want 9090", cfg.Port)
	}
	if cfg.Name != "production" {
		t.Errorf("Name = %q, want %q", cfg.Name, "production")
	}
	if !cfg.Debug {
		t.Errorf("Debug = false, want true")
	}
}