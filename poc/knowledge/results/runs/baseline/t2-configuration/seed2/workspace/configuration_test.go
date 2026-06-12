package configuration

import (
	"errors"
	"strconv"
	"testing"
)

func src(m map[string]string) Source {
	return func(key string) (string, bool) {
		v, ok := m[key]
		return v, ok
	}
}

func TestDefaults(t *testing.T) {
	cfg, err := Load(src(nil))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080", cfg.Port)
	}
	if cfg.Name != "helios" {
		t.Errorf("Name = %q, want %q", cfg.Name, "helios")
	}
	if cfg.Debug != false {
		t.Errorf("Debug = %v, want false", cfg.Debug)
	}
}

func TestEmptySourceReturnsDefaults(t *testing.T) {
	cfg, err := Load(src(map[string]string{}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 8080 || cfg.Name != "helios" || cfg.Debug != false {
		t.Error("expected defaults with empty source")
	}
}

func TestPortParsing(t *testing.T) {
	tests := []struct {
		val     string
		want    int
		wantErr bool
	}{
		{"1", 1, false},
		{"8080", 8080, false},
		{"65535", 65535, false},
		{"0", 0, true},
		{"65536", 0, true},
		{"-1", 0, true},
		{"abc", 0, true},
		{"", 0, true},
	}
	for _, tt := range tests {
		cfg, err := Load(src(map[string]string{"HELIOS_PORT": tt.val}))
		if tt.wantErr {
			if err == nil {
				t.Errorf("HELIOS_PORT=%q: expected error, got %+v", tt.val, cfg)
			}
			continue
		}
		if err != nil {
			t.Errorf("HELIOS_PORT=%q: unexpected error: %v", tt.val, err)
		} else if cfg.Port != tt.want {
			t.Errorf("HELIOS_PORT=%q: Port=%d, want %d", tt.val, cfg.Port, tt.want)
		}
	}
}

func TestPortParseErrorIsPreserved(t *testing.T) {
	_, err := Load(src(map[string]string{"HELIOS_PORT": "not-a-number"}))
	if err == nil {
		t.Fatal("expected error")
	}
	var numErr *strconv.NumError
	if !errors.As(err, &numErr) {
		t.Errorf("expected *strconv.NumError to be reachable via errors.As, got %T", err)
	}
}

func TestNameValidation(t *testing.T) {
	cfg, err := Load(src(map[string]string{"HELIOS_NAME": "my-service"}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Name != "my-service" {
		t.Errorf("Name = %q, want %q", cfg.Name, "my-service")
	}
}

func TestNameEmptyIsError(t *testing.T) {
	_, err := Load(src(map[string]string{"HELIOS_NAME": ""}))
	if err == nil {
		t.Fatal("expected error for empty HELIOS_NAME")
	}
}

func TestDebugParsing(t *testing.T) {
	tests := []struct {
		val     string
		want    bool
		wantErr bool
	}{
		{"true", true, false},
		{"1", true, false},
		{"false", false, false},
		{"0", false, false},
		{"t", true, false},
		{"f", false, false},
		{"TRUE", true, false},
		{"FALSE", false, false},
		{"", false, true},
		{"bad", false, true},
	}
	for _, tt := range tests {
		cfg, err := Load(src(map[string]string{"HELIOS_DEBUG": tt.val}))
		if tt.wantErr {
			if err == nil {
				t.Errorf("HELIOS_DEBUG=%q: expected error", tt.val)
			}
			continue
		}
		if err != nil {
			t.Errorf("HELIOS_DEBUG=%q: unexpected error: %v", tt.val, err)
		} else if cfg.Debug != tt.want {
			t.Errorf("HELIOS_DEBUG=%q: Debug=%v, want %v", tt.val, cfg.Debug, tt.want)
		}
	}
}

func TestAllFieldsSet(t *testing.T) {
	cfg, err := Load(src(map[string]string{
		"HELIOS_PORT":  "9090",
		"HELIOS_NAME":  "production",
		"HELIOS_DEBUG": "true",
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
	if cfg.Debug != true {
		t.Errorf("Debug = %v, want true", cfg.Debug)
	}
}

func TestSourceReturnsNotFoundFallsBackToDefaults(t *testing.T) {
	cfg, err := Load(func(key string) (string, bool) {
		return "", false
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 8080 || cfg.Name != "helios" || cfg.Debug != false {
		t.Error("expected defaults when source returns not-found")
	}
}