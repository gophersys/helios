package configuration

import (
	"errors"
	"fmt"
	"strconv"
	"testing"
)

func TestLoadDefaults(t *testing.T) {
	source := func(key string) (string, bool) {
		return "", false
	}
	cfg, err := Load(source)
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
	source := func(key string) (string, bool) {
		switch key {
		case "HELIOS_PORT":
			return "3000", true
		case "HELIOS_NAME":
			return "myservice", true
		case "HELIOS_DEBUG":
			return "true", true
		}
		return "", false
	}
	cfg, err := Load(source)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Port != 3000 {
		t.Errorf("Port = %d, want 3000", cfg.Port)
	}
	if cfg.Name != "myservice" {
		t.Errorf("Name = %q, want \"myservice\"", cfg.Name)
	}
	if !cfg.Debug {
		t.Errorf("Debug = false, want true")
	}
}

func TestLoadPortRange(t *testing.T) {
	tests := []struct {
		name  string
		value string
	}{
		{"below minimum", "0"},
		{"above maximum", "65536"},
		{"negative", "-1"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			source := func(key string) (string, bool) {
				if key == "HELIOS_PORT" {
					return tt.value, true
				}
				return "", false
			}
			_, err := Load(source)
			if err == nil {
				t.Fatal("expected error, got nil")
			}
		})
	}
}

func TestLoadPortParseError(t *testing.T) {
	source := func(key string) (string, bool) {
		if key == "HELIOS_PORT" {
			return "not-a-number", true
		}
		return "", false
	}
	_, err := Load(source)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	var numErr *strconv.NumError
	if !errors.As(err, &numErr) {
		t.Errorf("error does not wrap *strconv.NumError: %v", err)
	}
}

func TestLoadPortValidEdgeCases(t *testing.T) {
	edges := []struct {
		value string
		want  int
	}{
		{"1", 1},
		{"65535", 65535},
	}
	for _, e := range edges {
		t.Run(e.value, func(t *testing.T) {
			source := func(key string) (string, bool) {
				if key == "HELIOS_PORT" {
					return e.value, true
				}
				return "", false
			}
			cfg, err := Load(source)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if cfg.Port != e.want {
				t.Errorf("Port = %d, want %d", cfg.Port, e.want)
			}
		})
	}
}

func TestLoadNameEmpty(t *testing.T) {
	source := func(key string) (string, bool) {
		if key == "HELIOS_NAME" {
			return "", true
		}
		return "", false
	}
	_, err := Load(source)
	if err == nil {
		t.Fatal("expected error for empty name, got nil")
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
		t.Fatal("expected error, got nil")
	}
}

func TestLoadDebugFalseVariants(t *testing.T) {
	variants := []string{"false", "0", "f", "F", "False", "FALSE"}
	for _, v := range variants {
		t.Run(v, func(t *testing.T) {
			source := func(key string) (string, bool) {
				if key == "HELIOS_DEBUG" {
					return v, true
				}
				return "", false
			}
			cfg, err := Load(source)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if cfg.Debug {
				t.Errorf("Debug = true, want false (value %q)", v)
			}
		})
	}
}

func TestLoadDebugTrueVariants(t *testing.T) {
	variants := []string{"true", "1", "t", "T", "True", "TRUE"}
	for _, v := range variants {
		t.Run(v, func(t *testing.T) {
			source := func(key string) (string, bool) {
				if key == "HELIOS_DEBUG" {
					return v, true
				}
				return "", false
			}
			cfg, err := Load(source)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !cfg.Debug {
				t.Errorf("Debug = false, want true (value %q)", v)
			}
		})
	}
}

// ExampleLoad shows a typical usage with os.LookupEnv.
func ExampleLoad() {
	source := func(key string) (string, bool) {
		m := map[string]string{
			"HELIOS_PORT":  "9090",
			"HELIOS_NAME":  "example",
			"HELIOS_DEBUG": "true",
		}
		v, ok := m[key]
		return v, ok
	}
	cfg, err := Load(source)
	if err != nil {
		fmt.Println("error:", err)
		return
	}
	fmt.Printf("port=%d name=%s debug=%t\n", cfg.Port, cfg.Name, cfg.Debug)
	// Output: port=9090 name=example debug=true
}