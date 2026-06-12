package configuration

import (
	"errors"
	"strconv"
	"testing"
)

func mapSource(m map[string]string) Source {
	return func(key string) (string, bool) {
		v, ok := m[key]
		return v, ok
	}
}

func TestDefaults(t *testing.T) {
	cfg, err := Load(mapSource(nil))
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

func TestDefaultsEmptyMap(t *testing.T) {
	cfg, err := Load(mapSource(map[string]string{}))
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

func TestCustomPort(t *testing.T) {
	cfg, err := Load(mapSource(map[string]string{
		"HELIOS_PORT": "9090",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 9090 {
		t.Errorf("Port = %d, want 9090", cfg.Port)
	}
	if cfg.Name != "helios" {
		t.Errorf("Name = %q, want helios", cfg.Name)
	}
}

func TestCustomName(t *testing.T) {
	cfg, err := Load(mapSource(map[string]string{
		"HELIOS_NAME": "myapp",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Name != "myapp" {
		t.Errorf("Name = %q, want myapp", cfg.Name)
	}
}

func TestCustomDebugTrue(t *testing.T) {
	cfg, err := Load(mapSource(map[string]string{
		"HELIOS_DEBUG": "true",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !cfg.Debug {
		t.Errorf("Debug = false, want true")
	}
}

func TestCustomDebugOne(t *testing.T) {
	cfg, err := Load(mapSource(map[string]string{
		"HELIOS_DEBUG": "1",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !cfg.Debug {
		t.Errorf("Debug = false, want true")
	}
}

func TestAllCustom(t *testing.T) {
	cfg, err := Load(mapSource(map[string]string{
		"HELIOS_PORT":  "443",
		"HELIOS_NAME":  "production",
		"HELIOS_DEBUG": "false",
	}))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 443 {
		t.Errorf("Port = %d, want 443", cfg.Port)
	}
	if cfg.Name != "production" {
		t.Errorf("Name = %q, want production", cfg.Name)
	}
	if cfg.Debug {
		t.Errorf("Debug = true, want false")
	}
}

func TestPortParseError(t *testing.T) {
	_, err := Load(mapSource(map[string]string{
		"HELIOS_PORT": "notanumber",
	}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	_, ok := errors.AsType[*strconv.NumError](err)
	if !ok {
		t.Errorf("error type = %T, want *strconv.NumError", err)
	}
}

func TestPortOutOfRangeLow(t *testing.T) {
	_, err := Load(mapSource(map[string]string{
		"HELIOS_PORT": "0",
	}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	_, ok := errors.AsType[*strconv.NumError](err)
	if !ok {
		t.Errorf("error type = %T, want *strconv.NumError", err)
	}
}

func TestPortOutOfRangeHigh(t *testing.T) {
	_, err := Load(mapSource(map[string]string{
		"HELIOS_PORT": "65536",
	}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	_, ok := errors.AsType[*strconv.NumError](err)
	if !ok {
		t.Errorf("error type = %T, want *strconv.NumError", err)
	}
}

func TestEmptyName(t *testing.T) {
	_, err := Load(mapSource(map[string]string{
		"HELIOS_NAME": "",
	}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}

func TestBadDebug(t *testing.T) {
	_, err := Load(mapSource(map[string]string{
		"HELIOS_DEBUG": "maybe",
	}))
	if err == nil {
		t.Fatal("expected error, got nil")
	}
}
