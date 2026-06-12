package configuration

import (
	"errors"
	"strconv"
	"testing"
)

func lookup(m map[string]string) Source {
	return func(key string) (string, bool) {
		v, ok := m[key]
		return v, ok
	}
}

func TestDefaults(t *testing.T) {
	cfg, err := Load(lookup(nil))
	if err != nil {
		t.Fatalf("Load with empty source: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080", cfg.Port)
	}
	if cfg.Name != "helios" {
		t.Errorf("Name = %q, want helios", cfg.Name)
	}
	if cfg.Debug {
		t.Errorf("Debug = %t, want false", cfg.Debug)
	}
}

func TestCustomValues(t *testing.T) {
	cfg, err := Load(lookup(map[string]string{
		"HELIOS_PORT":  "9090",
		"HELIOS_NAME":  "myapp",
		"HELIOS_DEBUG": "true",
	}))
	if err != nil {
		t.Fatalf("Load with custom values: %v", err)
	}
	if cfg.Port != 9090 {
		t.Errorf("Port = %d, want 9090", cfg.Port)
	}
	if cfg.Name != "myapp" {
		t.Errorf("Name = %q, want myapp", cfg.Name)
	}
	if !cfg.Debug {
		t.Errorf("Debug = %t, want true", cfg.Debug)
	}
}

func TestPortInvalidString(t *testing.T) {
	_, err := Load(lookup(map[string]string{
		"HELIOS_PORT": "not-a-number",
	}))
	if err == nil {
		t.Fatal("expected error for invalid port string")
	}
	_, ok := errors.AsType[*strconv.NumError](err)
	if !ok {
		t.Errorf("expected *strconv.NumError in error chain, got %T", err)
	}
}

func TestPortOutOfRange(t *testing.T) {
	tests := []struct {
		val  string
		desc string
	}{
		{"0", "zero"},
		{"-1", "negative"},
		{"65536", "too large"},
		{"100000", "way too large"},
	}
	for _, tt := range tests {
		_, err := Load(lookup(map[string]string{"HELIOS_PORT": tt.val}))
		if err == nil {
			t.Errorf("expected error for port %s (%s)", tt.val, tt.desc)
		}
	}
}

func TestNameEmpty(t *testing.T) {
	tests := []struct {
		val  string
		desc string
	}{
		{"", "explicit empty"},
	}
	for _, tt := range tests {
		_, err := Load(lookup(map[string]string{"HELIOS_NAME": tt.val}))
		if err == nil {
			t.Errorf("expected error for HELIOS_NAME %q (%s)", tt.val, tt.desc)
		}
	}
}

func TestDebugInvalid(t *testing.T) {
	_, err := Load(lookup(map[string]string{
		"HELIOS_DEBUG": "not-a-bool",
	}))
	if err == nil {
		t.Fatal("expected error for invalid debug string")
	}
}

func TestDebugFalseVariants(t *testing.T) {
	for _, val := range []string{"false", "0", "FALSE", "f", "F"} {
		cfg, err := Load(lookup(map[string]string{"HELIOS_DEBUG": val}))
		if err != nil {
			t.Fatalf("Load with HELIOS_DEBUG=%q: %v", val, err)
		}
		if cfg.Debug {
			t.Errorf("Debug = true for HELIOS_DEBUG=%q", val)
		}
	}
}

func TestNameCustom(t *testing.T) {
	cfg, err := Load(lookup(map[string]string{
		"HELIOS_NAME": "production",
	}))
	if err != nil {
		t.Fatalf("Load with HELIOS_NAME=production: %v", err)
	}
	if cfg.Name != "production" {
		t.Errorf("Name = %q, want production", cfg.Name)
	}
}

func TestSourceNotFound(t *testing.T) {
	// Source returns found=false for everything.
	source := func(key string) (string, bool) {
		return "", false
	}
	cfg, err := Load(source)
	if err != nil {
		t.Fatalf("Load with all-not-found source: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080", cfg.Port)
	}
	if cfg.Name != "helios" {
		t.Errorf("Name = %q, want helios", cfg.Name)
	}
	if cfg.Debug {
		t.Errorf("Debug = %t, want false", cfg.Debug)
	}
}

func TestEmptyPortExplicit(t *testing.T) {
	// An empty string is not valid for Atoi.
	_, err := Load(lookup(map[string]string{
		"HELIOS_PORT": "",
	}))
	if err == nil {
		t.Fatal("expected error for empty HELIOS_PORT")
	}
}