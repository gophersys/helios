package configuration

import (
	"errors"
	"strconv"
	"testing"
)

func env(m map[string]string) Source {
	return func(key string) (string, bool) {
		v, ok := m[key]
		return v, ok
	}
}

func TestDefaults(t *testing.T) {
	cfg, err := Load(env(nil))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080", cfg.Port)
	}
	if cfg.Name != "helios" {
		t.Errorf("Name = %q, want helios", cfg.Name)
	}
	if cfg.Debug {
		t.Errorf("Debug = true, want false")
	}
}

func TestCustomValues(t *testing.T) {
	cfg, err := Load(env(map[string]string{
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
	if !cfg.Debug {
		t.Errorf("Debug = false, want true")
	}
}

func TestBadPort(t *testing.T) {
	_, err := Load(env(map[string]string{
		"HELIOS_PORT": "notanumber",
	}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	_, ok := errors.AsType[*strconv.NumError](err)
	if !ok {
		t.Errorf("error does not wrap *strconv.NumError: %v", err)
	}
}

func TestPortOutOfRange(t *testing.T) {
	_, err := Load(env(map[string]string{
		"HELIOS_PORT": "0",
	}))
	if err == nil {
		t.Fatal("expected error for port 0")
	}

	_, err = Load(env(map[string]string{
		"HELIOS_PORT": "65536",
	}))
	if err == nil {
		t.Fatal("expected error for port 65536")
	}

	cfg, err := Load(env(map[string]string{
		"HELIOS_PORT": "1",
	}))
	if err != nil {
		t.Fatalf("unexpected error for port 1: %v", err)
	}
	if cfg.Port != 1 {
		t.Errorf("Port = %d, want 1", cfg.Port)
	}

	cfg, err = Load(env(map[string]string{
		"HELIOS_PORT": "65535",
	}))
	if err != nil {
		t.Fatalf("unexpected error for port 65535: %v", err)
	}
	if cfg.Port != 65535 {
		t.Errorf("Port = %d, want 65535", cfg.Port)
	}
}

func TestEmptyName(t *testing.T) {
	_, err := Load(env(map[string]string{
		"HELIOS_NAME": "",
	}))
	if err == nil {
		t.Fatal("expected error for empty name, got nil")
	}
}

func TestBadDebug(t *testing.T) {
	_, err := Load(env(map[string]string{
		"HELIOS_DEBUG": "yep",
	}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	_, ok := errors.AsType[*strconv.NumError](err)
	if !ok {
		t.Errorf("error does not wrap *strconv.NumError: %v", err)
	}
}

func TestDebugParseBoolVariants(t *testing.T) {
	tests := []struct {
		value string
		want  bool
	}{
		{"1", true},
		{"t", true},
		{"T", true},
		{"TRUE", true},
		{"true", true},
		{"True", true},
		{"0", false},
		{"f", false},
		{"F", false},
		{"FALSE", false},
		{"false", false},
		{"False", false},
	}
	for _, tc := range tests {
		cfg, err := Load(env(map[string]string{
			"HELIOS_DEBUG": tc.value,
		}))
		if err != nil {
			t.Errorf("HELIOS_DEBUG=%q: unexpected error: %v", tc.value, err)
			continue
		}
		if cfg.Debug != tc.want {
			t.Errorf("HELIOS_DEBUG=%q: Debug = %t, want %t", tc.value, cfg.Debug, tc.want)
		}
	}
}

func TestMissingKeysUseDefaults(t *testing.T) {
	cfg, err := Load(env(map[string]string{
		"HELIOS_NAME": "onlyname",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080", cfg.Port)
	}
	if cfg.Name != "onlyname" {
		t.Errorf("Name = %q, want onlyname", cfg.Name)
	}
	if cfg.Debug {
		t.Errorf("Debug = true, want false")
	}
}
