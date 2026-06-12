package configuration

import (
	"errors"
	"strconv"
	"strings"
	"testing"
)

func strSource(m map[string]string) Source {
	return func(key string) (string, bool) {
		v, ok := m[key]
		return v, ok
	}
}

func TestLoadDefaults(t *testing.T) {
	cfg, err := Load(strSource(nil))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080", cfg.Port)
	}
	if cfg.Name != "helios" {
		t.Errorf("Name = %q, want helios", cfg.Name)
	}
	if cfg.Debug != false {
		t.Errorf("Debug = %t, want false", cfg.Debug)
	}
}

func TestLoadAllExplicit(t *testing.T) {
	cfg, err := Load(strSource(map[string]string{
		"HELIOS_PORT":  "9090",
		"HELIOS_NAME":  "myapp",
		"HELIOS_DEBUG": "true",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 9090 {
		t.Errorf("Port = %d, want 9090", cfg.Port)
	}
	if cfg.Name != "myapp" {
		t.Errorf("Name = %q, want myapp", cfg.Name)
	}
	if cfg.Debug != true {
		t.Errorf("Debug = %t, want true", cfg.Debug)
	}
}

func TestLoadBadPort(t *testing.T) {
	_, err := Load(strSource(map[string]string{"HELIOS_PORT": "notanumber"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !errors.Is(err, strconv.ErrSyntax) {
		t.Errorf("expected ErrSyntax in error chain, got %v", err)
	}
}

func TestLoadPortOutOfRange(t *testing.T) {
	_, err := Load(strSource(map[string]string{"HELIOS_PORT": "0"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	_, err = Load(strSource(map[string]string{"HELIOS_PORT": "65536"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestLoadEmptyName(t *testing.T) {
	_, err := Load(strSource(map[string]string{"HELIOS_NAME": ""}))
	if err == nil {
		t.Fatal("expected error for empty name, got nil")
	}
}

func TestLoadBadDebug(t *testing.T) {
	_, err := Load(strSource(map[string]string{"HELIOS_DEBUG": "maybe"}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !errors.Is(err, strconv.ErrSyntax) {
		t.Errorf("expected ErrSyntax in error chain, got %v", err)
	}
}

func TestLoadMultipleErrors(t *testing.T) {
	_, err := Load(strSource(map[string]string{
		"HELIOS_PORT":  "xyz",
		"HELIOS_NAME":  "",
		"HELIOS_DEBUG": "bad",
	}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	msg := err.Error()
	for _, want := range []string{"HELIOS_PORT", "HELIOS_NAME", "HELIOS_DEBUG"} {
		if !strings.Contains(msg, want) {
			t.Errorf("error message missing %q: %s", want, msg)
		}
	}
}

func TestLoadPartialOverride(t *testing.T) {
	cfg, err := Load(strSource(map[string]string{
		"HELIOS_NAME": "partial",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080 (default)", cfg.Port)
	}
	if cfg.Name != "partial" {
		t.Errorf("Name = %q, want partial", cfg.Name)
	}
	if cfg.Debug != false {
		t.Errorf("Debug = %t, want false (default)", cfg.Debug)
	}
}