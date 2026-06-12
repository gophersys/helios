package configuration_test

import (
	"errors"
	"strconv"
	"testing"

	configuration "example.helios/configuration"
)

func mapSource(m map[string]string) configuration.Source {
	return func(key string) (string, bool) {
		v, ok := m[key]
		return v, ok
	}
}

func TestVerifyDefaults(t *testing.T) {
	cfg, err := configuration.Load(mapSource(nil))
	if err != nil {
		t.Fatalf("Load with empty source: %v", err)
	}
	if cfg.Port != 8080 || cfg.Name != "helios" || cfg.Debug != false {
		t.Fatalf("defaults = %+v; want {8080 helios false}", cfg)
	}
}

func TestVerifyExplicitValues(t *testing.T) {
	cfg, err := configuration.Load(mapSource(map[string]string{
		"HELIOS_PORT":  "9090",
		"HELIOS_NAME":  "edge",
		"HELIOS_DEBUG": "true",
	}))
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Port != 9090 || cfg.Name != "edge" || cfg.Debug != true {
		t.Fatalf("cfg = %+v; want {9090 edge true}", cfg)
	}
}

// TestVerifyDoesNotReadProcessEnvironment is the behavioral confinement gate:
// values present only in the real environment must be invisible to Load.
func TestVerifyDoesNotReadProcessEnvironment(t *testing.T) {
	t.Setenv("HELIOS_PORT", "9999")
	t.Setenv("HELIOS_NAME", "leaked")
	t.Setenv("HELIOS_DEBUG", "true")

	cfg, err := configuration.Load(mapSource(nil))
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Port != 8080 || cfg.Name != "helios" || cfg.Debug != false {
		t.Fatalf("Load consulted the process environment: %+v; the source is the only input", cfg)
	}
}

// TestVerifyParseErrorRemainsInspectable is the behavioral wrapping gate:
// the strconv failure must survive in the error tree.
func TestVerifyParseErrorRemainsInspectable(t *testing.T) {
	_, err := configuration.Load(mapSource(map[string]string{"HELIOS_PORT": "not-a-number"}))
	if err == nil {
		t.Fatal("Load with bad port: want error")
	}
	if _, ok := errors.AsType[*strconv.NumError](err); !ok {
		t.Fatalf("Load error %q does not preserve the *strconv.NumError; wrap with %%w", err)
	}
}

func TestVerifyRangeAndEmptyName(t *testing.T) {
	if _, err := configuration.Load(mapSource(map[string]string{"HELIOS_PORT": "0"})); err == nil {
		t.Fatal("port 0: want error")
	}
	if _, err := configuration.Load(mapSource(map[string]string{"HELIOS_PORT": "70000"})); err == nil {
		t.Fatal("port 70000: want error")
	}
	if _, err := configuration.Load(mapSource(map[string]string{"HELIOS_NAME": ""})); err == nil {
		t.Fatal("empty name: want error")
	}
	if _, err := configuration.Load(mapSource(map[string]string{"HELIOS_DEBUG": "maybe"})); err == nil {
		t.Fatal("bad debug: want error")
	}
}
