package configuration

import (
	"errors"
	"strconv"
	"testing"
)

func TestLoadDefaults(t *testing.T) {
	source := func(key string) (string, bool) { return "", false }
	cfg, err := Load(source)
	if err != nil {
		t.Fatalf("Load with empty source: %v", err)
	}
	if cfg.Port != 8080 {
		t.Errorf("default Port = %d, want 8080", cfg.Port)
	}
	if cfg.Name != "helios" {
		t.Errorf("default Name = %q, want helios", cfg.Name)
	}
	if cfg.Debug {
		t.Errorf("default Debug = true, want false")
	}
}

func TestLoadPort(t *testing.T) {
	source := func(key string) (string, bool) {
		switch key {
		case "HELIOS_PORT":
			return "3000", true
		default:
			return "", false
		}
	}
	cfg, err := Load(source)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	if cfg.Port != 3000 {
		t.Errorf("Port = %d, want 3000", cfg.Port)
	}
}

func TestLoadName(t *testing.T) {
	source := func(key string) (string, bool) {
		switch key {
		case "HELIOS_NAME":
			return "my-app", true
		default:
			return "", false
		}
	}
	cfg, err := Load(source)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	if cfg.Name != "my-app" {
		t.Errorf("Name = %q, want my-app", cfg.Name)
	}
}

func TestLoadDebug(t *testing.T) {
	source := func(key string) (string, bool) {
		switch key {
		case "HELIOS_DEBUG":
			return "true", true
		default:
			return "", false
		}
	}
	cfg, err := Load(source)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	if !cfg.Debug {
		t.Errorf("Debug = false, want true")
	}
}

func TestLoadAll(t *testing.T) {
	source := func(key string) (string, bool) {
		switch key {
		case "HELIOS_PORT":
			return "443", true
		case "HELIOS_NAME":
			return "production", true
		case "HELIOS_DEBUG":
			return "1", true
		default:
			return "", false
		}
	}
	cfg, err := Load(source)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	if cfg.Port != 443 {
		t.Errorf("Port = %d, want 443", cfg.Port)
	}
	if cfg.Name != "production" {
		t.Errorf("Name = %q, want production", cfg.Name)
	}
	if !cfg.Debug {
		t.Errorf("Debug = false, want true")
	}
}

func TestLoadPortOutOfRangeLow(t *testing.T) {
	source := func(key string) (string, bool) {
		if key == "HELIOS_PORT" {
			return "0", true
		}
		return "", false
	}
	_, err := Load(source)
	if err == nil {
		t.Fatal("expected error for port 0")
	}
}

func TestLoadPortOutOfRangeHigh(t *testing.T) {
	source := func(key string) (string, bool) {
		if key == "HELIOS_PORT" {
			return "70000", true
		}
		return "", false
	}
	_, err := Load(source)
	if err == nil {
		t.Fatal("expected error for port 70000")
	}
}

func TestLoadPortNotAnInt(t *testing.T) {
	source := func(key string) (string, bool) {
		if key == "HELIOS_PORT" {
			return "not-a-number", true
		}
		return "", false
	}
	_, err := Load(source)
	if err == nil {
		t.Fatal("expected error for non-integer port")
	}
	_, ok := errors.AsType[*strconv.NumError](err)
	if !ok {
		t.Fatalf("expected *strconv.NumError in error chain, got %T (%v)", err, err)
	}
}

func TestLoadEmptyName(t *testing.T) {
	source := func(key string) (string, bool) {
		if key == "HELIOS_NAME" {
			return "", true
		}
		return "", false
	}
	_, err := Load(source)
	if err == nil {
		t.Fatal("expected error for empty name")
	}
}

func TestLoadDebugParseError(t *testing.T) {
	source := func(key string) (string, bool) {
		if key == "HELIOS_DEBUG" {
			return "notabool", true
		}
		return "", false
	}
	_, err := Load(source)
	if err == nil {
		t.Fatal("expected error for bad debug value")
	}
	_, ok := errors.AsType[*strconv.NumError](err)
	if ok {
		// Acceptable — strconv.ParseBool produces *strconv.NumError
	}
}

func TestLoadPortPreservesNumError(t *testing.T) {
	source := func(key string) (string, bool) {
		if key == "HELIOS_PORT" {
			return "xyz", true
		}
		return "", false
	}
	_, err := Load(source)
	if err == nil {
		t.Fatal("expected error")
	}
	// Verify the underlying *strconv.NumError is reachable.
	numErr, ok := errors.AsType[*strconv.NumError](err)
	if !ok {
		t.Fatalf("expected *strconv.NumError in error chain, got %T (%v)", err, err)
	}
	if numErr.Func != "Atoi" {
		t.Errorf("NumError.Func = %q, want Atoi", numErr.Func)
	}
}
