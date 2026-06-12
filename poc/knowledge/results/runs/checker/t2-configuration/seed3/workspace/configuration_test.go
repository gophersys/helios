package configuration

import (
	"errors"
	"strconv"
	"testing"
)

func env(src map[string]string) Source {
	return func(key string) (string, bool) {
		v, ok := src[key]
		return v, ok
	}
}

func TestDefaults(t *testing.T) {
	cfg, err := Load(env(nil))
	if err != nil {
		t.Fatal("unexpected error:", err)
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
		"HELIOS_PORT":   "9090",
		"HELIOS_NAME":   "myservice",
		"HELIOS_DEBUG":  "true",
	}))
	if err != nil {
		t.Fatal("unexpected error:", err)
	}
	if cfg.Port != 9090 {
		t.Errorf("Port = %d, want 9090", cfg.Port)
	}
	if cfg.Name != "myservice" {
		t.Errorf("Name = %q, want myservice", cfg.Name)
	}
	if !cfg.Debug {
		t.Errorf("Debug = false, want true")
	}
}

func TestDebugFalseVariants(t *testing.T) {
	for _, v := range []string{"false", "0", "FALSE", "f"} {
		cfg, err := Load(env(map[string]string{"HELIOS_DEBUG": v}))
		if err != nil {
			t.Fatalf("debug=%q: unexpected error: %v", v, err)
		}
		if cfg.Debug {
			t.Errorf("debug=%q: Debug = true, want false", v)
		}
	}
}

func TestPortOutOfRange(t *testing.T) {
	for _, v := range []string{"0", "-1", "65536", "99999"} {
		_, err := Load(env(map[string]string{"HELIOS_PORT": v}))
		if err == nil {
			t.Errorf("port=%q: expected error, got nil", v)
		}
	}
}

func TestPortBadSyntax(t *testing.T) {
	_, err := Load(env(map[string]string{"HELIOS_PORT": "not-a-number"}))
	if err == nil {
		t.Fatal("expected error")
	}
	_, ok := errors.AsType[*strconv.NumError](err)
	if !ok {
		t.Errorf("error type %T, want *strconv.NumError", err)
	}
}

func TestNameEmpty(t *testing.T) {
	_, err := Load(env(map[string]string{"HELIOS_NAME": ""}))
	if err == nil {
		t.Fatal("expected error for empty name")
	}
}

func TestDebugBadSyntax(t *testing.T) {
	_, err := Load(env(map[string]string{"HELIOS_DEBUG": "nope"}))
	if err == nil {
		t.Fatal("expected error")
	}
}

func TestAllMissing(t *testing.T) {
	cfg, err := Load(env(nil))
	if err != nil {
		t.Fatal("unexpected error:", err)
	}
	if cfg != (Config{Port: 8080, Name: "helios", Debug: false}) {
		t.Errorf("got %+v, want defaults", cfg)
	}
}

func TestPartialOverride(t *testing.T) {
	cfg, err := Load(env(map[string]string{"HELIOS_NAME": "partial"}))
	if err != nil {
		t.Fatal("unexpected error:", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("Port = %d, want 8080 (default)", cfg.Port)
	}
	if cfg.Name != "partial" {
		t.Errorf("Name = %q, want partial", cfg.Name)
	}
	if cfg.Debug {
		t.Errorf("Debug = true, want false (default)")
	}
}